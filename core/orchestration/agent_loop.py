"""
Keelway Autonomous ReAct Agent Loop.
Implements the multi-step Observe -> Plan -> Tool Call -> Observation -> Verify loop
with native workspace tools, deterministic flight recording, and human-in-the-loop safety controls.
"""

import difflib
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable

from core.agents.sandbox import CommandExecutionUnavailable
from core.storage.workspace_fs import WorkspaceFilesystem
from core.storage.ast_index import CodebaseSemanticIndex
from core.orchestration.flight_recorder import FlightRecorder
from keelway.core.models import DecisionEnum, ToolAuthorizationRequest


class AgentLoopStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING_TOOL = "executing_tool"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutonomyPolicy(str, Enum):
    AUTONOMOUS = "autonomous"            # Execute all tools automatically
    CONFIRM_MUTATION = "confirm_mutation"# Require approval for write/edit/command
    CONFIRM_ALL = "confirm_all"          # Require approval for every tool invocation


@dataclass
class PlanStep:
    id: str
    description: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    tool_call: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "tool_call": self.tool_call,
            "observation": self.observation,
        }


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    is_mutation: bool
    handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class AutonomousAgentLoop:
    """Multi-step ReAct agent runtime for deterministic local software engineering."""

    def __init__(
        self,
        task_id: str,
        workspace_fs: Optional[WorkspaceFilesystem] = None,
        policy: AutonomyPolicy = AutonomyPolicy.CONFIRM_MUTATION,
        record_flight: bool = True,
        approval_rules: Optional[Any] = None,
        policy_engine: Optional[Any] = None,
        quorum_service: Optional[Any] = None,
        environment: str = "internal",
        actor_id: str = "local_engineer",
        flight_recorder: Optional[FlightRecorder] = None,
        model_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ):
        self.task_id = task_id
        self.fs = workspace_fs or WorkspaceFilesystem()
        self.policy = policy
        self.policy_engine = policy_engine
        self.quorum_service = quorum_service
        self.environment = environment
        self.actor_id = actor_id
        self.active_quorum_id: Optional[str] = None
        self.goal = ""
        self.status = AgentLoopStatus.IDLE
        self.plan: List[PlanStep] = []
        self.events: List[Dict[str, Any]] = []
        self.pending_approval: Optional[Dict[str, Any]] = None
        self.approval_rules = approval_rules
        self.model_id = model_id
        self.prompt_version = prompt_version
        self.command_runner: Optional[Any] = None  # (command, timeout) -> tool result; set when commands must run confined
        self.guard: Optional[Any] = None  # a core.agents.guard.ManifestGuard when running under an Agent Manifest
        self.active_proc: Optional[subprocess.Popen] = None
        self.semantic_index = CodebaseSemanticIndex(self.fs)

        if flight_recorder is not None:
            self.flight_recorder = flight_recorder
        else:
            self.flight_recorder = FlightRecorder(task_id=task_id) if record_flight else None
        self.tools: Dict[str, AgentTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Registers the 6 foundational developer tools."""
        
        # 1. read_file
        async def _h_read(args: Dict[str, Any]) -> Dict[str, Any]:
            path = args.get("path", "")
            start = args.get("start_line")
            end = args.get("end_line")
            res = self.fs.read_file(path)
            content = res.get("content", "")
            
            if start is not None or end is not None:
                lines = content.splitlines()
                s_idx = max(0, (start - 1)) if start else 0
                e_idx = min(len(lines), end) if end else len(lines)
                sliced = "\n".join(lines[s_idx:e_idx])
                res["content"] = sliced
                res["line_range"] = [s_idx + 1, e_idx]
            return res

        self.tools["read_file"] = AgentTool(
            name="read_file",
            description="Read text content of a file, optionally within start_line and end_line range.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
            is_mutation=False,
            handler=_h_read,
        )

        # 2. write_file
        async def _h_write(args: Dict[str, Any]) -> Dict[str, Any]:
            path = args.get("path", "")
            content = args.get("content", "")
            return self.fs.write_file(path, content)

        self.tools["write_file"] = AgentTool(
            name="write_file",
            description="Create or overwrite a file with given content atomically.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            is_mutation=True,
            handler=_h_write,
        )

        # 3. edit_file
        async def _h_edit(args: Dict[str, Any]) -> Dict[str, Any]:
            path = args.get("path", "")
            target = args.get("target", "")
            replacement = args.get("replacement", "")

            file_data = self.fs.read_file(path)
            content = file_data.get("content", "")

            if target not in content:
                raise ValueError(f"Target string not found in '{path}'.")

            occurrences = content.count(target)
            new_content = content.replace(target, replacement)
            save_res = self.fs.write_file(path, new_content)
            save_res["replacements_count"] = occurrences
            return save_res

        self.tools["edit_file"] = AgentTool(
            name="edit_file",
            description="Replace exact target substring with replacement in a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "target": {"type": "string"},
                    "replacement": {"type": "string"},
                },
                "required": ["path", "target", "replacement"],
            },
            is_mutation=True,
            handler=_h_edit,
        )

        # 4. run_command
        async def _h_run(args: Dict[str, Any]) -> Dict[str, Any]:
            # No verified runner means the command is unavailable. There is no host shell fallback.
            if self.command_runner is None:
                raise CommandExecutionUnavailable(
                    "command execution is unavailable: no verified isolation boundary is configured"
                )
            if not isinstance(args, dict):
                raise CommandExecutionUnavailable(
                    "command execution is unavailable: malformed tool arguments"
                )
            cmd = args.get("command", "")
            timeout = min(int(args.get("timeout", 30)), 120)

            danger_patterns = [r"\brm\s+-rf\s+/", r">\s*/dev/sd[a-z]", r":\(\)\{ :\|:& \};:"]
            for pat in danger_patterns:
                if re.search(pat, cmd):
                    raise PermissionError(f"Command rejected by safety gate: '{cmd}'")

            return self.command_runner(cmd, timeout)

        self.tools["run_command"] = AgentTool(
            name="run_command",
            description="Execute a bash/zsh shell command inside workspace root.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
            is_mutation=True,
            handler=_h_run,
        )

        # 5. list_dir
        async def _h_list(args: Dict[str, Any]) -> Dict[str, Any]:
            path = args.get("path", ".")
            tree = self.fs.get_file_tree(subpath=path, max_depth=1)
            return tree

        self.tools["list_dir"] = AgentTool(
            name="list_dir",
            description="List directory files and folders.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                },
            },
            is_mutation=False,
            handler=_h_list,
        )

        # 6. search_codebase
        async def _h_search(args: Dict[str, Any]) -> Dict[str, Any]:
            query = args.get("query", "")
            if not query:
                return {"symbols": [], "matches": []}
            
            # 1. AST Symbol & Semantic Search
            if not self.semantic_index.symbols:
                self.semantic_index.index_workspace(max_files=100)
            symbol_hits = self.semantic_index.search_symbols(query, top_k=8)

            # 2. Fast ripgrep or git grep for literal matches
            matches = []
            try:
                res = subprocess.run(
                    ["git", "grep", "-n", "-I", "--max-count=30", query],
                    cwd=str(self.fs.root),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                raw = res.stdout if res.returncode == 0 else ""
                for line in raw.splitlines()[:30]:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        matches.append({"path": parts[0], "line": parts[1], "snippet": parts[2].strip()})
            except Exception:
                pass

            return {
                "query": query,
                "symbols": symbol_hits,
                "total_symbols": len(symbol_hits),
                "text_matches": matches,
                "total_text_matches": len(matches),
            }

        self.tools["search_codebase"] = AgentTool(
            name="search_codebase",
            description="Search workspace files for text matches using fast grep.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            is_mutation=False,
            handler=_h_search,
        )

    def initialize_plan(
        self,
        goal: Optional[str] = None,
        steps: Optional[List[str]] = None,
        *,
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initializes a structured multi-step execution plan."""
        effective_goal = goal or intent or ""
        if steps is None:
            steps = AutonomousAgentLoop.formulate_plan(effective_goal)
        self.goal = effective_goal
        self.plan = [
            PlanStep(id=f"step_{idx+1}", description=desc, status="pending")
            for idx, desc in enumerate(steps)
        ]
        self.status = AgentLoopStatus.PLANNING
        self._record_event("plan_initialized", {"goal": effective_goal, "step_count": len(steps)})
        return {
            "status": "plan_ready",
            "goal": effective_goal,
            "steps": [s.to_dict() for s in self.plan],
        }

    async def propose_diff(self, file_path: str, old_content: Any, new_content: str) -> Dict[str, Any]:
        """Generates a unified diff for human inspection and records diff_proposed event."""
        if isinstance(old_content, dict):
            old_content = old_content.get("content", "")
        if isinstance(new_content, dict):
            new_content = new_content.get("content", "")

        old_lines = str(old_content).splitlines(keepends=True)
        new_lines = str(new_content).splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))
        diff_text = "".join(diff_lines)
        lines_added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

        self._record_event("diff_proposed", {
            "file_path": file_path,
            "diff": diff_text,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
        })

        return {
            "status": "diff_proposed",
            "file_path": file_path,
            "diff": diff_text,
        }

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], step_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a tool with policy gating and flight recording.
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")

        tool = self.tools[tool_name]

        # An Agent Manifest can only narrow what is allowed: it denies before approvals are even considered.
        if self.guard is not None:
            decision = self.guard.check(tool_name, arguments)
            if not decision.allowed:
                self._record_event("policy_denied", {
                    "task_id": self.task_id, "tool_name": tool_name, "arguments": arguments, "step_id": step_id,
                    "code": decision.code, "reason": decision.reason, "manifest_digest": self.guard.manifest_digest,
                })
                if step_id:
                    self._update_step_status(step_id, "failed", f"Blocked by agent manifest: {decision.reason}")
                return {"status": "denied_by_manifest", "code": decision.code, "reason": decision.reason}

        # Policy Engine Evaluation (FR-02)
        if self.policy_engine is not None:
            tool_policy_map = {
                "read_file": "git.read",
                "write_file": "git.write_patch",
                "edit_file": "git.write_patch",
                "exec_command": "sandbox.exec_test",
                "list_dir": "git.read",
                "eval_benchmark": "eval.run",
            }
            active_rule = self.policy_engine.rules.get(getattr(self.policy_engine, "policy_id", "default_governed_v1"))
            policy_tool = tool_name
            if active_rule and tool_name not in active_rule.allowed_tools and tool_name in tool_policy_map:
                policy_tool = tool_policy_map[tool_name]

            action_bytes = json.dumps({"tool": policy_tool, "args": arguments}, sort_keys=True).encode("utf-8")
            action_digest = hashlib.sha256(action_bytes).hexdigest()
            auth_req = ToolAuthorizationRequest(
                run_id=self.task_id,
                tool=policy_tool,
                action_digest=f"sha256:{action_digest}",
                scope={"path": arguments.get("path", ""), "repo": arguments.get("repo", "."), "network_egress": arguments.get("network_egress", False)},
                actor_id=self.actor_id,
                policy_version=getattr(self.policy_engine, "policy_id", "default_governed_v1"),
            )
            policy_decision = self.policy_engine.evaluate(auth_req)
            if policy_decision.decision == DecisionEnum.DENY:
                self._record_event("policy_denied", {
                    "task_id": self.task_id, "tool_name": tool_name, "policy_tool": policy_tool,
                    "arguments": arguments, "step_id": step_id,
                    "reason_code": policy_decision.reason_code, "decision_id": policy_decision.decision_id,
                })
                if step_id:
                    self._update_step_status(step_id, "failed", f"Denied by policy engine: {policy_decision.reason_code}")
                return {
                    "status": "denied_by_policy",
                    "reason_code": policy_decision.reason_code,
                    "decision_id": policy_decision.decision_id,
                    "signature": policy_decision.signature,
                }
            elif policy_decision.decision == DecisionEnum.REQUIRE_APPROVAL:
                # Production Quorum Gate (ADR-045 / ADR-046)
                if self.environment == "production" and self.quorum_service is not None:
                    q_req = self.quorum_service.create_quorum_request(
                        run_id=self.task_id,
                        patch_hash=f"sha256:{action_digest}",
                        environment=self.environment,
                    )
                    self.active_quorum_id = q_req.id
                    self.status = AgentLoopStatus.AWAITING_APPROVAL
                    self.pending_approval = {
                        "task_id": self.task_id,
                        "tool_name": tool_name,
                        "policy_tool": policy_tool,
                        "arguments": arguments,
                        "is_mutation": tool.is_mutation,
                        "step_id": step_id,
                        "requires_quorum": True,
                        "quorum_id": q_req.id,
                        "required_roles": list(q_req.required_roles),
                        "decision_id": policy_decision.decision_id,
                    }
                    self._record_event("quorum_approval_requested", self.pending_approval)
                    return {"status": "paused_for_quorum", "pending": self.pending_approval}
                else:
                    needs_approval = True

        # Permission check
        needs_approval = (
            self.policy == AutonomyPolicy.CONFIRM_ALL
            or (self.policy == AutonomyPolicy.CONFIRM_MUTATION and tool.is_mutation)
        )

        if needs_approval and self.policy == AutonomyPolicy.CONFIRM_MUTATION and self.approval_rules is not None:
            rule = self.approval_rules.match(
                tool_name, arguments,
                model_id=self.model_id, prompt_version=self.prompt_version,
            )
            if rule:
                self._record_event("approval_auto_granted", {
                    "task_id": self.task_id, "tool_name": tool_name, "arguments": arguments,
                    "step_id": step_id, "rule_id": rule.id, "scope": rule.scope,
                })
                result = await self._run_approved_tool(tool, arguments, step_id)
                result["approved_by_rule"] = rule.to_dict()
                return result

        if needs_approval:
            self.status = AgentLoopStatus.AWAITING_APPROVAL
            self.pending_approval = {
                "task_id": self.task_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "is_mutation": tool.is_mutation,
                "step_id": step_id,
            }
            self._record_event("approval_requested", self.pending_approval)
            return {"status": "paused_for_approval", "pending": self.pending_approval}

        return await self._run_approved_tool(tool, arguments, step_id)

    def submit_quorum_approval(self, principal_id: str, role: str) -> Dict[str, Any]:
        """Submits an independent human signature toward achieving two-human quorum (ADR-045)."""
        if not self.quorum_service or not self.active_quorum_id:
            return {"status": "no_active_quorum"}

        q_req = self.quorum_service.get_request(self.active_quorum_id)
        if not q_req:
            return {"status": "quorum_request_not_found"}

        try:
            ok, msg = self.quorum_service.submit_role_approval(
                request_id=self.active_quorum_id,
                principal_id=principal_id,
                role=role,
                current_patch_hash=q_req.patch_hash,
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}

        if not ok:
            return {"status": "error", "message": msg}

        if q_req.is_fully_approved:
            self._record_event("quorum_fully_approved", {
                "quorum_id": q_req.id,
                "signatures": {k: sig.model_dump() for k, sig in q_req.signatures.items()},
            })
            return {"status": "fully_approved", "quorum_id": q_req.id, "message": msg}

        return {
            "status": "pending_remaining_approvers",
            "quorum_id": q_req.id,
            "message": msg,
            "signatures_collected": list(q_req.signatures.keys()),
            "signatures_remaining": list(q_req.required_roles - set(q_req.signatures.keys())),
        }

    async def approve_pending(self, approved: bool) -> Dict[str, Any]:
        """User grants or denies permission for pending tool execution."""
        if not self.pending_approval:
            return {"status": "no_pending_approval"}

        pending = self.pending_approval
        self.pending_approval = None

        if not approved:
            self.status = AgentLoopStatus.IDLE
            self._record_event("approval_denied", pending)
            if pending.get("step_id"):
                self._update_step_status(pending["step_id"], "failed", "User denied permission.")
            return {"status": "denied", "tool_name": pending["tool_name"]}

        # If pending item requires two-human quorum, verify that quorum is fully satisfied
        if pending.get("requires_quorum"):
            if not self.quorum_service:
                return {"status": "error", "message": "Quorum service unavailable"}
            q_req = self.quorum_service.get_request(pending["quorum_id"])
            if not q_req or not q_req.is_fully_approved:
                # Restore pending approval and reject execution until quorum is achieved
                self.pending_approval = pending
                self.status = AgentLoopStatus.AWAITING_APPROVAL
                pending_roles = list(q_req.required_roles - set(q_req.signatures.keys())) if q_req else []
                return {
                    "status": "quorum_not_satisfied",
                    "quorum_id": pending["quorum_id"],
                    "pending_roles": pending_roles,
                }

        self._record_event("approval_granted", pending)
        tool = self.tools[pending["tool_name"]]
        return await self._run_approved_tool(tool, pending["arguments"], pending.get("step_id"))

    async def _run_approved_tool(self, tool: AgentTool, arguments: Dict[str, Any], step_id: Optional[str]) -> Dict[str, Any]:
        """Internal execution of an approved tool."""
        self.status = AgentLoopStatus.EXECUTING_TOOL
        if step_id:
            self._update_step_status(step_id, "running")

        self._record_event("tool_call", {"tool": tool.name, "arguments": arguments, "step_id": step_id})

        start_time = time.perf_counter()
        try:
            result = await tool.handler(arguments)
            if self.guard is not None:
                result = self.guard.filter_result(tool.name, result)
            dur_ms = (time.perf_counter() - start_time) * 1000.0

            if self.flight_recorder:
                self.flight_recorder.record_event(
                    event_type=f"tool:{tool.name}",
                    payload={
                        "arguments": arguments,
                        "result": result,
                        "duration_ms": dur_ms,
                        "step_id": step_id,
                    },
                )

            if step_id:
                self._update_step_status(step_id, "completed", observation=str(result)[:500])

            self.status = AgentLoopStatus.IDLE
            self._record_event("tool_success", {"tool": tool.name, "result": result, "duration_ms": round(dur_ms, 2)})
            return {"status": "success", "tool": tool.name, "result": result}

        except Exception as e:
            dur_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = str(e)
            if step_id:
                self._update_step_status(step_id, "failed", observation=err_msg)

            self.status = AgentLoopStatus.FAILED
            self._record_event("tool_error", {"tool": tool.name, "error": err_msg, "duration_ms": round(dur_ms, 2)})
            return {"status": "error", "tool": tool.name, "error": err_msg}

    def cancel(self) -> Dict[str, Any]:
        """Cancels running tool execution, terminates active subprocess, and transitions to CANCELLED."""
        if self.active_proc and self.active_proc.poll() is None:
            try:
                self.active_proc.terminate()
                self.active_proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.active_proc.kill()
                except Exception:
                    pass
        self.active_proc = None
        pending_step_id = (self.pending_approval or {}).get("step_id")
        self.pending_approval = None
        self.status = AgentLoopStatus.CANCELLED
        for s in self.plan:
            if s.status == "running" or (s.status == "pending" and s.id == pending_step_id):
                s.status = "failed"
                s.observation = "Task execution cancelled by user."
        self._record_event("task_cancelled", {"task_id": self.task_id})
        return {"status": "cancelled", "task_id": self.task_id}

    @staticmethod
    def formulate_plan(goal: str) -> List[str]:
        """Generates dynamic structured execution steps for a goal based on intent recognition."""
        lower = goal.lower()
        if "test" in lower or "fix" in lower or "bug" in lower or "discount" in lower:
            return [
                "Inspect source files and locate target symbols",
                "Formulate and apply code changes",
                "Run automated tests to verify repair",
            ]
        elif "refactor" in lower or "clean" in lower:
            return [
                "Analyze codebase architecture and dependencies",
                "Apply structured code refactoring",
                "Verify zero-regression with test suite",
            ]
        elif "feature" in lower or "add" in lower or "implement" in lower:
            return [
                "Examine project context and existing interfaces",
                "Implement new feature module and endpoints",
                "Add test coverage and run verification",
            ]
        return [
            "Inspect workspace files and dependencies",
            "Search codebase for target symbols",
            "Formulate and verify solution patch",
            "Run automated checks",
        ]

    def _update_step_status(self, step_id: str, status: str, observation: Optional[str] = None) -> None:
        for s in self.plan:
            if s.id == step_id:
                s.status = status
                if observation:
                    s.observation = observation
                break

    def _record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self.events.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data,
        })
        # Tool calls/results are already taped as "tool:<name>"; tape the decisions around them too.
        if self.flight_recorder and event_type not in ("tool_call", "tool_success"):
            self.flight_recorder.record_event(event_type=event_type, payload=data)

    def get_state(self) -> Dict[str, Any]:
        """Returns JSON state for the Dev Studio frontend."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status.value,
            "policy": self.policy.value,
            "plan": [
                {
                    "id": s.id,
                    "description": s.description,
                    "status": s.status,
                    "observation": s.observation,
                }
                for s in self.plan
            ],
            "pending_approval": self.pending_approval,
            "events_count": len(self.events),
            "recent_events": self.events[-10:],
            "manifest": self.guard.summary() if self.guard is not None else None,
        }
