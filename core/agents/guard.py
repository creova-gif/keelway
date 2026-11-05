"""Run-time enforcement of an Agent Manifest.

`ManifestGuard` decides, per tool call, whether the manifest permits it. It only ever NARROWS what the loop would
do: it can deny a call, never grant one. Approval rules and autonomy policy still apply after it.

What is enforced (see ENFORCED) and what is not (see not_enforced()) is stated plainly on purpose: a manifest
that declares a sandbox or a dollar budget must not give the impression of protection that does not exist yet.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from core.agents.manifest import PROTECTED_PREFIXES, AgentManifest, digest

ENFORCED = (
    "tools: only the listed tools are registered and callable",
    "permissions.read_paths / write_paths: checked on the real, symlink-resolved path",
    "permissions.commands: exact string match",
    "budget.max_steps: counted per guard (one per tool call that passes the checks)",
    "budget.max_usd_per_run: actively metered and enforced per model call",
    "permissions.autonomy: becomes the loop's approval policy",
)


class ManifestNotRunnable(ValueError):
    """The manifest is valid but asks for something this runtime cannot safely provide yet."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str = "ok"
    reason: str = ""


def _glob_to_regex(pattern: str) -> "re.Pattern[str]":
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


class ManifestGuard:
    def __init__(self, manifest: AgentManifest, workspace_root: Path):
        self.manifest = manifest
        self.manifest_digest = digest(manifest)
        self.root = Path(workspace_root).resolve()
        perms = manifest.permissions
        self._read = [_glob_to_regex(p) for p in perms.read_paths]
        self._write = [_glob_to_regex(p) for p in perms.write_paths]
        self._commands = {c.strip() for c in perms.commands}
        self._tools = set(manifest.tools)
        self.steps_used = 0
        self.usd_spent = 0.0
        self.signed = False  # set by the caller that verified a signature

    def record_cost(self, amount_usd: float) -> None:
        """Accumulate cost spent during this agent run."""
        self.usd_spent += max(0.0, float(amount_usd))

    # ---- path handling -------------------------------------------------
    def _real_relative(self, raw: Any) -> Tuple[Optional[str], Optional[Decision]]:
        if not isinstance(raw, str) or "\x00" in raw or "\\" in raw:
            return None, Decision(False, "bad_path", "The path is not a plain workspace-relative path.")
        pure = PurePosixPath(raw.strip() or ".")
        if pure.is_absolute() or ".." in pure.parts:
            return None, Decision(False, "path_escape", f"'{raw}' must be relative and stay inside the workspace.")
        lexical = str(pure)
        try:
            rel = (self.root / lexical).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return None, Decision(False, "path_escape", f"'{raw}' resolves outside the workspace.")
        for candidate in (lexical, rel):
            if candidate != "." and PurePosixPath(candidate).parts[0] in PROTECTED_PREFIXES:
                return None, Decision(False, "protected_path", f"'{raw}' is protected (Keelway state or git internals).")
        return rel, None

    @staticmethod
    def _in_scope(rel: str, patterns: List["re.Pattern[str]"], is_dir: bool = False) -> bool:
        return any(p.match(rel) or (is_dir and p.match(rel.rstrip("/") + "/_")) for p in patterns)

    def _check_path(self, raw: Any, patterns: List["re.Pattern[str]"], label: str, *, empty_means_all: bool, is_dir: bool = False) -> Decision:
        rel, denied = self._real_relative(raw)
        if denied:
            return denied
        if not patterns and empty_means_all:
            return Decision(True)
        if rel is not None and self._in_scope(rel, patterns, is_dir):
            return Decision(True)
        return Decision(False, "path_not_in_scope", f"'{raw}' is outside this agent's {label} paths.")

    # ---- decision ------------------------------------------------------
    def check(self, tool_name: str, arguments: Dict[str, Any]) -> Decision:
        if tool_name.startswith("mcp:") or tool_name.startswith("mcp__"):
            sep = ":" if ":" in tool_name else "__"
            parts = tool_name.split(sep)
            server_name = parts[1] if len(parts) > 1 else ""
            if not self.manifest.mcp_servers or server_name not in self.manifest.mcp_servers:
                return Decision(
                    False,
                    "mcp_server_not_declared",
                    f"MCP server '{server_name}' is not in this agent's declared mcp_servers: {self.manifest.mcp_servers}",
                )
            decision = Decision(True)
        elif tool_name not in self._tools:
            return Decision(False, "tool_not_allowed", f"'{tool_name}' is not in this agent's tools.")
        else:
            args = arguments if isinstance(arguments, dict) else {}
            if tool_name == "read_file":
                decision = self._check_path(args.get("path", ""), self._read, "read", empty_means_all=True)
            elif tool_name == "list_dir":
                decision = self._check_path(args.get("path", "."), self._read, "read", empty_means_all=True, is_dir=True)
            elif tool_name in ("write_file", "edit_file"):
                decision = self._check_path(args.get("path", ""), self._write, "write", empty_means_all=False)
            elif tool_name == "run_command":
                command = args.get("command")
                if not isinstance(command, str) or command.strip() not in self._commands:
                    decision = Decision(False, "command_not_allowed", "That exact command is not in this agent's allowed commands.")
                else:
                    decision = Decision(True)
            else:  # search_codebase: allowed here; its results are filtered by filter_result
                decision = Decision(True)
        if not decision.allowed:
            return decision
        if self.usd_spent >= self.manifest.budget.max_usd_per_run:
            return Decision(False, "cost_budget_exhausted", f"This agent's cost budget of ${self.manifest.budget.max_usd_per_run:.2f} is exhausted (spent ${self.usd_spent:.2f}).")
        if self.steps_used >= self.manifest.budget.max_steps:
            return Decision(False, "step_budget_exhausted", f"This agent's budget of {self.manifest.budget.max_steps} steps is used up.")
        self.steps_used += 1
        return decision

    def summary(self) -> Dict[str, Any]:
        m = self.manifest
        return {
            "name": m.name, "version": m.version, "digest": self.manifest_digest, "signed": self.signed,
            "steps_used": self.steps_used, "max_steps": m.budget.max_steps,
            "usd_spent": round(self.usd_spent, 4), "max_usd": m.budget.max_usd_per_run,
            "sandbox": m.sandbox,
        }

    def filter_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Drop search hits from files the agent may not read."""
        if tool_name != "search_codebase" or not self._read or not isinstance(result, dict):
            return result
        out = copy.deepcopy(result)

        def readable(path: Any) -> bool:
            rel, denied = self._real_relative(path)
            return denied is None and rel is not None and self._in_scope(rel, self._read)

        out["symbols"] = [s for s in out.get("symbols", []) if readable(s.get("file_path"))]
        out["text_matches"] = [m for m in out.get("text_matches", []) if readable(m.get("path"))]
        out["total_symbols"], out["total_text_matches"] = len(out["symbols"]), len(out["text_matches"])
        return out


def not_enforced(manifest: AgentManifest) -> List[str]:
    """Things this manifest declares that the runtime does not enforce (or enforces only in some places)."""
    notes = []
    runs_commands = "run_command" in manifest.tools
    if manifest.sandbox == "worktree" and runs_commands:
        notes.append("sandbox 'worktree': enforced with the macOS seatbelt backend after a self-test; on other platforms the run is refused")
    elif manifest.sandbox == "container":
        notes.append("sandbox 'container': not built; a run that uses run_command is refused")
    elif manifest.sandbox == "workspace" and runs_commands:
        notes.append("sandbox 'workspace': commands run unconfined in your shell and inherit your environment")
    if manifest.permissions.network != "none":
        if runs_commands:
            notes.append("permissions.network 'allowlist': per-host filtering does not exist, so a run with run_command is refused")
        else:
            notes.append("permissions.network: no tool of this agent uses the network (model calls follow model.routing)")
    notes.append("budget.max_usd_per_run: token-level metering is active; over-budget calls are halted")
    if manifest.mcp_servers:
        notes.append("mcp_servers: enforced against declared server names (undeclared servers are blocked)")
    return notes


def static_refusal(manifest: Any) -> Optional[str]:
    """Reasons a valid manifest can never run, decided without touching the machine. None means no static objection."""
    if isinstance(manifest, dict):
        from core.agents import manifest as am
        report = am.validate(manifest)
        if not report.ok:
            return f"invalid manifest: {report.errors}"
        manifest = report.manifest

    runs_commands = "run_command" in manifest.tools
    if runs_commands and manifest.sandbox == "container":
        return "sandbox 'container' is not built; use 'worktree' on macOS or drop run_command"
    if runs_commands and manifest.sandbox == "workspace" and manifest.permissions.autonomy == "autonomous":
        return "autonomous agents that run commands must not use sandbox 'workspace' (unconfined shell)"
    if runs_commands and manifest.sandbox == "worktree" and manifest.permissions.network != "none":
        return "per-host network allowlists cannot be enforced; set permissions.network to 'none' or drop run_command"
    return None


def preflight(manifest: AgentManifest, workspace_root: Path) -> Optional[str]:
    """Why this manifest cannot run on THIS machine, or None if it can. May start processes (the sandbox self-test)."""
    refusal = static_refusal(manifest)
    if refusal:
        return refusal
    if "run_command" in manifest.tools and manifest.sandbox == "worktree":
        from core.agents.sandbox import Sandbox

        ok, detail = Sandbox(workspace_root).verify()
        if not ok:
            return f"commands need a verified sandbox and this machine has none: sandbox could not be verified on this machine: {detail}"
    return None


def loop_from_manifest(
    manifest: Any,
    task_id: str,
    workspace_fs: Optional[Any] = None,
    record_flight: bool = True,
    approval_rules: Optional[Any] = None,
):
    """Build an AutonomousAgentLoop that can only do what the manifest allows."""
    from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy

    if isinstance(manifest, dict):
        from core.agents import manifest as am
        report = am.validate(manifest)
        if not report.ok:
            raise ManifestNotRunnable(f"invalid manifest: {report.errors}")
        manifest = report.manifest

    refusal = static_refusal(manifest)
    if refusal:
        raise ManifestNotRunnable(refusal)
    agent = AutonomousAgentLoop(
        task_id=task_id,
        workspace_fs=workspace_fs,
        policy=AutonomyPolicy(manifest.permissions.autonomy),
        record_flight=record_flight,
        approval_rules=approval_rules,
    )
    runner = None
    if "run_command" in manifest.tools and manifest.sandbox == "worktree":
        from core.agents.sandbox import Sandbox, SandboxUnavailable

        sandbox = Sandbox(agent.fs.root)
        try:
            sandbox.require_verified()
        except SandboxUnavailable as exc:
            raise ManifestNotRunnable(f"commands need a verified sandbox and this machine has none: {exc}") from exc
        runner = lambda command, timeout: sandbox.run(command, timeout).to_tool_result(command)  # noqa: E731
    agent.tools = {name: tool for name, tool in agent.tools.items() if name in manifest.tools}
    agent.guard = ManifestGuard(manifest, agent.fs.root)
    agent.command_runner = runner
    agent._record_event("manifest_bound", {"task_id": task_id, "name": manifest.name, "version": manifest.version, "digest": agent.guard.manifest_digest})
    return agent
