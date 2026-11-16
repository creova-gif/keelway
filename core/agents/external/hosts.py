"""Concrete adapters for hook-capable third-party coding agents.

Currently: Claude Code (`claude`) and Codex CLI (`codex`). Cursor's
`cursor-agent` shares the Claude-style hook payload shape and is registered
behind the same extractor; its hook schema is version-sensitive and remains
`audit_only` until contract-tested against a pinned CLI version.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from core.agents.external.base import (
    AgentDetection,
    AgentHostAdapter,
    LaunchSpec,
    NormalizedToolCall,
)
from core.security.env_scrub import scrub_env

_DETECT_TIMEOUT_S = 5.0


def _detect_binary(agent_id: str, binary: str) -> AgentDetection:
    path = shutil.which(binary)
    if not path:
        return AgentDetection(agent_id=agent_id, installed=False,
                              detail=f"'{binary}' not found on PATH.")
    version: Optional[str] = None
    try:
        proc = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=_DETECT_TIMEOUT_S,
        )
        out = (proc.stdout or proc.stderr or "").strip().splitlines()
        version = out[0].strip()[:200] if out else None
    except (OSError, subprocess.TimeoutExpired):
        version = None
    return AgentDetection(agent_id=agent_id, installed=True, binary_path=path,
                          version=version, detail="detected")


def _scrubbed_env() -> Dict[str, str]:
    clean_env, _ = scrub_env(dict(os.environ))
    return clean_env


def _extract_command(tool_input: Dict[str, Any]) -> str:
    """Best-effort command string from a tool_input object."""
    for key in ("command", "cmd", "file_path", "path", "notebook_path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    try:
        return json.dumps(tool_input, sort_keys=True)[:2000]
    except (TypeError, ValueError):
        return str(tool_input)[:2000]


class ClaudeCodeAdapter(AgentHostAdapter):
    """Claude Code (`claude`) — `.claude/settings.local.json` PreToolUse hooks."""

    agent_id = "claude_code"
    display_name = "Claude Code"
    binary_name = "claude"
    hook_event = "PreToolUse"

    def detect(self) -> AgentDetection:
        return _detect_binary(self.agent_id, self.binary_name)

    def build_launch(self, workspace_root: Optional[str] = None,
                     extra_args: Optional[List[str]] = None) -> LaunchSpec:
        argv = [self.binary_name, *(extra_args or [])]
        return LaunchSpec(agent_id=self.agent_id, argv=argv,
                          env=_scrubbed_env(), cwd=workspace_root)

    def parse_hook_payload(self, payload: Dict[str, Any]) -> NormalizedToolCall:
        tool_input = payload.get("tool_input")
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        tool_name = str(payload.get("tool_name") or "Bash").strip() or "Bash"
        ticket = payload.get("ticket_id") or payload.get("approval_ticket")
        return NormalizedToolCall(
            agent_id=self.agent_id,
            tool_name=tool_name,
            command=_extract_command(tool_input),
            ticket_id=str(ticket).strip() if ticket else None,
            raw=dict(payload),
        )


class CodexCliAdapter(AgentHostAdapter):
    """Codex CLI (`codex`) — `.codex/hooks.toml` PreToolUse hooks."""

    agent_id = "codex_cli"
    display_name = "Codex CLI"
    binary_name = "codex"
    hook_event = "PreToolUse"

    def detect(self) -> AgentDetection:
        return _detect_binary(self.agent_id, self.binary_name)

    def build_launch(self, workspace_root: Optional[str] = None,
                     extra_args: Optional[List[str]] = None) -> LaunchSpec:
        argv = [self.binary_name, *(extra_args or [])]
        return LaunchSpec(agent_id=self.agent_id, argv=argv,
                          env=_scrubbed_env(), cwd=workspace_root)

    def parse_hook_payload(self, payload: Dict[str, Any]) -> NormalizedToolCall:
        # Codex hook payloads may nest under "tool"/"input" or mirror Claude's shape.
        tool_input = payload.get("tool_input") or payload.get("input") or {}
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "Bash").strip() or "Bash"
        ticket = payload.get("ticket_id") or payload.get("approval_ticket")
        return NormalizedToolCall(
            agent_id=self.agent_id,
            tool_name=tool_name,
            command=_extract_command(tool_input),
            ticket_id=str(ticket).strip() if ticket else None,
            raw=dict(payload),
        )


class CursorAgentAdapter(AgentHostAdapter):
    """Cursor agent CLI (`cursor-agent`) — `.cursor/hooks.json` hooks.

    Payload shape assumed Claude-compatible (`tool_name`/`tool_input`);
    unverified against a pinned cursor-agent release — treat as audit_only
    until contract-tested (THIRD_PARTY_AGENT_INTEGRATION.md §6).
    """

    agent_id = "cursor"
    display_name = "Cursor Agent"
    binary_name = "cursor-agent"
    hook_event = "PreToolUse"
    supported_modes = ("audit_only", "enforce")

    def detect(self) -> AgentDetection:
        return _detect_binary(self.agent_id, self.binary_name)

    def build_launch(self, workspace_root: Optional[str] = None,
                     extra_args: Optional[List[str]] = None) -> LaunchSpec:
        argv = [self.binary_name, *(extra_args or [])]
        return LaunchSpec(agent_id=self.agent_id, argv=argv,
                          env=_scrubbed_env(), cwd=workspace_root)

    def parse_hook_payload(self, payload: Dict[str, Any]) -> NormalizedToolCall:
        tool_input = payload.get("tool_input") or payload.get("input") or {}
        tool_input = tool_input if isinstance(tool_input, dict) else {}
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "Bash").strip() or "Bash"
        ticket = payload.get("ticket_id") or payload.get("approval_ticket")
        return NormalizedToolCall(
            agent_id=self.agent_id,
            tool_name=tool_name,
            command=_extract_command(tool_input),
            ticket_id=str(ticket).strip() if ticket else None,
            raw=dict(payload),
        )


EXTERNAL_AGENT_ADAPTERS: Dict[str, AgentHostAdapter] = {
    ClaudeCodeAdapter.agent_id: ClaudeCodeAdapter(),
    CodexCliAdapter.agent_id: CodexCliAdapter(),
    CursorAgentAdapter.agent_id: CursorAgentAdapter(),
}


def get_adapter(agent_id: str) -> AgentHostAdapter:
    """Return the adapter for `agent_id` or raise KeyError."""
    clean = str(agent_id or "").strip()
    if clean not in EXTERNAL_AGENT_ADAPTERS:
        raise KeyError(f"No external agent adapter registered for '{agent_id}'.")
    return EXTERNAL_AGENT_ADAPTERS[clean]


def detect_external_agents() -> List[AgentDetection]:
    """Probe all registered adapters; never raises on missing binaries."""
    results: List[AgentDetection] = []
    for adapter in EXTERNAL_AGENT_ADAPTERS.values():
        try:
            results.append(adapter.detect())
        except Exception as exc:  # detection must never break callers
            results.append(AgentDetection(agent_id=adapter.agent_id, installed=False,
                                          detail=f"detection error: {exc}"))
    return results
