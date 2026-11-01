"""
Keelway Autonomous ReAct Agent Loop.
Implements the multi-step Observe -> Plan -> Tool Call -> Observation -> Verify loop
with native workspace tools, deterministic flight recording, and human-in-the-loop safety controls.
"""

import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable

from core.storage.workspace_fs import WorkspaceFilesystem, WorkspaceSecurityError
from core.storage.ast_index import CodebaseSemanticIndex
from core.orchestration.flight_recorder import FlightRecorder, FlightEvent


class AgentLoopStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING_TOOL = "executing_tool"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


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
    ):
        self.task_id = task_id
        self.fs = workspace_fs or WorkspaceFilesystem()
        self.policy = policy
        self.goal = ""
        self.status = AgentLoopStatus.IDLE
        self.plan: List[PlanStep] = []
        self.events: List[Dict[str, Any]] = []
        self.pending_approval: Optional[Dict[str, Any]] = None
        self.semantic_index = CodebaseSemanticIndex(self.fs)

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
            cmd = args.get("command", "")
            timeout = min(int(args.get("timeout", 30)), 120)
            
            # Security filter against dangerous commands
            danger_patterns = [r"\brm\s+-rf\s+/", r">\s*/dev/sd[a-z]", r":\(\)\{ :\|:& \};:"]
            for pat in danger_patterns:
                if re.search(pat, cmd):
                    raise PermissionError(f"Command rejected by safety gate: '{cmd}'")

            start_t = time.perf_counter()
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.fs.root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            dur_ms = (time.perf_counter() - start_t) * 1000.0

            return {
                "command": cmd,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[-10000:],  # Tail last 10KB
                "stderr": proc.stderr[-10000:],
                "duration_ms": round(dur_ms, 2),
            }

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

    def initialize_plan(self, goal: str, steps: List[str]) -> None:
        """Initializes a structured multi-step execution plan."""
        self.goal = goal
        self.plan = [
            PlanStep(id=f"step_{idx+1}", description=desc, status="pending")
            for idx, desc in enumerate(steps)
        ]
        self.status = AgentLoopStatus.PLANNING
        self._record_event("plan_initialized", {"goal": goal, "step_count": len(steps)})

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], step_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a tool with policy gating and flight recording.
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")

        tool = self.tools[tool_name]

        # Permission check
        needs_approval = (
            self.policy == AutonomyPolicy.CONFIRM_ALL
            or (self.policy == AutonomyPolicy.CONFIRM_MUTATION and tool.is_mutation)
        )

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
        }
