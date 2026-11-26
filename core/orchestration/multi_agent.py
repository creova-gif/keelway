"""
Keelway Multi-Agent Coordination & Execution Engine.

Implements deterministic multi-agent teams with role specialization, DAG-based
task decomposition, context handoffs, security review gates, and unified
flight-tape auditing.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.orchestration.flight_recorder import FlightRecorder
from core.orchestration.project_adapter import ProjectAdapter
from core.security.firewall import SecurityGateway
from core.storage.ast_index import CodebaseSemanticIndex
from core.storage.workspace_fs import WorkspaceFilesystem


class AgentRole(str, Enum):
    ARCHITECT = "lead-architect"
    CODER = "coder-agent"
    REVIEWER = "security-reviewer"
    VERIFIER = "test-verifier"


class NodeState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class TeamTaskNode:
    id: str
    title: str
    role: AgentRole
    description: str
    depends_on: List[str] = field(default_factory=list)
    state: NodeState = NodeState.PENDING
    assigned_tools: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TeamTaskNode:
        payload = dict(data)
        if isinstance(payload.get("role"), str):
            payload["role"] = AgentRole(payload["role"])
        if isinstance(payload.get("state"), str):
            payload["state"] = NodeState(payload["state"])
        return cls(**payload)


@dataclass
class TeamExecutionPlan:
    team_id: str
    goal: str
    created_at: str
    nodes: Dict[str, TeamTaskNode] = field(default_factory=dict)
    flight_tape_path: Optional[str] = None
    flight_tape_sha256: Optional[str] = None

    def add_node(self, node: TeamTaskNode) -> None:
        self.nodes[node.id] = node

    def topological_order(self) -> List[str]:
        """Return node IDs in topological order. Raises ValueError if cycle detected."""
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}

        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    raise ValueError(f"Node '{nid}' depends on nonexistent task '{dep}'")
                adj[dep].append(nid)
                in_degree[nid] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: List[str] = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in multi-agent execution DAG")

        return order

    def get_ready_nodes(self) -> List[TeamTaskNode]:
        """Return nodes that are PENDING and whose dependencies have all SUCCEEDED."""
        ready: List[TeamTaskNode] = []
        for node in self.nodes.values():
            if node.state == NodeState.PENDING:
                deps_met = all(
                    self.nodes[dep].state == NodeState.SUCCEEDED
                    for dep in node.depends_on
                    if dep in self.nodes
                )
                if deps_met:
                    ready.append(node)
        return ready

    def is_completed(self) -> bool:
        return all(n.state in (NodeState.SUCCEEDED, NodeState.FAILED, NodeState.SKIPPED) for n in self.nodes.values())

    def has_failed(self) -> bool:
        return any(n.state == NodeState.FAILED for n in self.nodes.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "flight_tape_path": self.flight_tape_path,
            "flight_tape_sha256": self.flight_tape_sha256,
        }


@dataclass
class TeamExecutionResult:
    team_id: str
    goal: str
    status: str  # "succeeded" | "failed" | "blocked"
    duration_ms: float
    nodes_executed: int
    plan: TeamExecutionPlan
    summary: str
    flight_tape_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "goal": self.goal,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "nodes_executed": self.nodes_executed,
            "plan": self.plan.to_dict(),
            "summary": self.summary,
            "flight_tape_sha256": self.flight_tape_sha256,
        }


class MultiAgentCoordinator:
    """Orchestrates deterministic multi-agent teams with explicit DAG execution and handoffs."""

    def __init__(
        self,
        workspace_fs: Optional[WorkspaceFilesystem] = None,
        security_gateway: Optional[SecurityGateway] = None,
    ):
        self.fs = workspace_fs or WorkspaceFilesystem()
        self.security = security_gateway or SecurityGateway(block_on_injection=True, redact_secrets=True)
        self.semantic_index = CodebaseSemanticIndex(self.fs)

    def plan_team_workflow(
        self,
        goal: str,
        custom_subtasks: Optional[List[Dict[str, Any]]] = None,
    ) -> TeamExecutionPlan:
        """Decompose developer goal into a topologically sound multi-agent DAG."""
        team_id = f"team_{int(time.time())}_{os.urandom(3).hex()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        plan = TeamExecutionPlan(team_id=team_id, goal=goal, created_at=now_iso)

        if custom_subtasks:
            for s in custom_subtasks:
                node = TeamTaskNode(
                    id=s["id"],
                    title=s.get("title", s["id"]),
                    role=AgentRole(s.get("role", AgentRole.CODER.value)),
                    description=s.get("description", ""),
                    depends_on=s.get("depends_on", []),
                    assigned_tools=s.get("assigned_tools", []),
                    inputs=s.get("inputs", {}),
                )
                plan.add_node(node)
            # Validate DAG acyclicity
            plan.topological_order()
            return plan

        # Standard 4-Agent Enterprise Crew Topology:
        # 1. Lead Architect: inspects repository context, analyzes symbols & dependencies.
        # 2. Coder Agent: implements changes, prepares atomic edits.
        # 3. Security Reviewer: scans diff for leaks, prompt injection, safety rules.
        # 4. Test Verifier: runs project test runner and confirms zero regressions.

        project_info = ProjectAdapter.inspect(self.fs.root)

        arch_node = TeamTaskNode(
            id="arch-01",
            title="Architecture & Codebase Analysis",
            role=AgentRole.ARCHITECT,
            description=f"Inspect codebase structure and plan implementation strategy for: {goal}",
            depends_on=[],
            assigned_tools=["search_codebase", "read_file", "list_dir"],
            inputs={"goal": goal},
        )
        plan.add_node(arch_node)

        code_node = TeamTaskNode(
            id="code-01",
            title="Implementation & File Editing",
            role=AgentRole.CODER,
            description=f"Implement changes for goal: {goal}",
            depends_on=["arch-01"],
            assigned_tools=["read_file", "edit_file", "write_file"],
            inputs={"goal": goal},
        )
        plan.add_node(code_node)

        sec_node = TeamTaskNode(
            id="review-01",
            title="Security & Policy Review",
            role=AgentRole.REVIEWER,
            description="Audit proposed changes for secrets, injections, and governance conformance",
            depends_on=["code-01"],
            assigned_tools=["read_file"],
            inputs={"strict_mode": True},
        )
        plan.add_node(sec_node)

        verify_node = TeamTaskNode(
            id="verify-01",
            title="Automated Test Verification",
            role=AgentRole.VERIFIER,
            description="Execute project test suite to verify changes pass all test suites",
            depends_on=["code-01", "review-01"],
            assigned_tools=["run_command"],
            inputs={"test_framework": project_info.detected_test_command},
        )
        plan.add_node(verify_node)

        # Confirm DAG acyclicity
        plan.topological_order()
        return plan

    async def execute_team_workflow(
        self,
        plan: TeamExecutionPlan,
        auto_approve: bool = True,
    ) -> TeamExecutionResult:
        """Execute the multi-agent team DAG with deterministic context handoffs and flight recording."""
        start_time = time.perf_counter()
        recorder = FlightRecorder(task_id=plan.team_id)
        recorder.record_event("team_workflow_started", {
            "team_id": plan.team_id,
            "goal": plan.goal,
            "total_nodes": len(plan.nodes),
        })

        executed_count = 0
        overall_status = "succeeded"

        while not plan.is_completed():
            ready_nodes = plan.get_ready_nodes()
            if not ready_nodes:
                # If there are unfinished nodes but none are ready, we are blocked
                unfinished = [n for n in plan.nodes.values() if n.state == NodeState.PENDING]
                if unfinished:
                    for u in unfinished:
                        u.state = NodeState.BLOCKED
                        u.error = "Dependencies failed or blocked"
                    overall_status = "blocked"
                break

            # Execute ready nodes
            for node in ready_nodes:
                node.state = NodeState.RUNNING
                node.started_at = datetime.now(timezone.utc).isoformat()
                recorder.record_event(f"node_started:{node.role.value}", {
                    "node_id": node.id,
                    "title": node.title,
                    "role": node.role.value,
                    "inputs": node.inputs,
                })

                n_start = time.perf_counter()
                try:
                    outputs = await self._dispatch_agent_role(node, plan, recorder)
                    node.outputs = outputs
                    node.state = NodeState.SUCCEEDED
                    node.duration_ms = round((time.perf_counter() - n_start) * 1000.0, 2)
                    node.completed_at = datetime.now(timezone.utc).isoformat()
                    executed_count += 1

                    recorder.record_event(f"node_completed:{node.role.value}", {
                        "node_id": node.id,
                        "outputs": outputs,
                        "duration_ms": node.duration_ms,
                    })

                except Exception as exc:
                    node.state = NodeState.FAILED
                    node.error = str(exc)
                    node.duration_ms = round((time.perf_counter() - n_start) * 1000.0, 2)
                    node.completed_at = datetime.now(timezone.utc).isoformat()
                    executed_count += 1
                    overall_status = "failed"

                    recorder.record_event(f"node_failed:{node.role.value}", {
                        "node_id": node.id,
                        "error": str(exc),
                        "duration_ms": node.duration_ms,
                    })
                    # On node failure, mark dependent nodes as BLOCKED
                    self._cascade_block(plan, node.id)
                    break

        total_dur_ms = (time.perf_counter() - start_time) * 1000.0

        # Seal flight tape
        tape_path = recorder.save_tape()
        plan.flight_tape_path = str(tape_path)
        plan.flight_tape_sha256 = recorder.tape_sha256

        summary = f"Multi-agent team workflow '{plan.goal}' finished with status '{overall_status}' ({executed_count}/{len(plan.nodes)} nodes executed in {total_dur_ms:.1f}ms)."

        return TeamExecutionResult(
            team_id=plan.team_id,
            goal=plan.goal,
            status=overall_status,
            duration_ms=total_dur_ms,
            nodes_executed=executed_count,
            plan=plan,
            summary=summary,
            flight_tape_sha256=recorder.tape_sha256,
        )

    def _cascade_block(self, plan: TeamExecutionPlan, failed_node_id: str) -> None:
        """Mark all transitive downstream dependents of a failed node as BLOCKED."""
        for nid, node in plan.nodes.items():
            if failed_node_id in node.depends_on and node.state == NodeState.PENDING:
                node.state = NodeState.BLOCKED
                node.error = f"Blocked by failed dependency '{failed_node_id}'"
                self._cascade_block(plan, nid)

    async def _dispatch_agent_role(
        self,
        node: TeamTaskNode,
        plan: TeamExecutionPlan,
        recorder: FlightRecorder,
    ) -> Dict[str, Any]:
        """Execute role-specialized logic with context inheritance from upstream nodes."""
        # Inherit outputs from dependencies
        inherited_context: Dict[str, Any] = {}
        for dep in node.depends_on:
            if dep in plan.nodes:
                inherited_context[dep] = plan.nodes[dep].outputs

        if node.role == AgentRole.ARCHITECT:
            # 1. ARCHITECT: inspects codebase symbols and identifies relevant files
            if not self.semantic_index.symbols:
                try:
                    self.semantic_index.index_workspace(max_files=100)
                except Exception:
                    pass
            results = self.semantic_index.search_symbols(node.inputs.get("goal", plan.goal), top_k=5)
            symbols = [
                {"symbol": r.get("name"), "type": r.get("kind"), "file": r.get("file_path"), "score": r.get("score")}
                for r in results
            ]
            project_info = ProjectAdapter.inspect(self.fs.root)
            return {
                "relevant_symbols": symbols,
                "project_framework": project_info.detected_test_command,
                "recommended_files": list({s["file"] for s in symbols}),
                "architect_notes": f"Identified {len(symbols)} relevant symbols across {project_info.project_type} project.",
            }

        elif node.role == AgentRole.CODER:
            # 2. CODER: prepares atomic changes or locates files to modify
            arch_out = inherited_context.get("arch-01", {})
            files_to_touch = node.inputs.get("files") or arch_out.get("recommended_files") or []
            
            modified_files = []
            diff_text = ""
            if node.inputs.get("patch"):
                # Apply explicit patch if supplied in inputs
                target = node.inputs.get("target_file")
                patch_content = node.inputs.get("patch")
                if target and patch_content:
                    self.fs.write_file(target, patch_content)
                    modified_files.append(target)
                    diff_text = f"+++ {target}\n{patch_content}"

            git_diff_res = self.fs.get_git_diff()
            if git_diff_res.get("diff"):
                diff_text = git_diff_res["diff"]

            patch_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
            return {
                "target_files": files_to_touch,
                "modified_files": modified_files,
                "diff_bytes": len(diff_text.encode("utf-8")),
                "diff_snippet": diff_text[:1000] if diff_text else "No uncommitted modifications.",
                "patch_hash": patch_hash,
            }

        elif node.role == AgentRole.REVIEWER:
            # 3. REVIEWER: audits diff for security violations, prompt injections, and secret leakage
            code_out = inherited_context.get("code-01", {})
            diff_text = code_out.get("diff_snippet", "")

            # Security inspection
            sec_res = self.security.inspect_and_sanitize(diff_text)
            if not sec_res.is_safe:
                raise ValueError(f"Security Reviewer Gate Rejected: {sec_res.blocked_reason}")

            return {
                "approved": True,
                "security_scan": "PASS",
                "sanitized_diff_bytes": len(sec_res.sanitized_text.encode("utf-8")),
                "violations_found": 0,
                "governance_verdict": "APPROVED",
            }

        elif node.role == AgentRole.VERIFIER:
            # 4. VERIFIER: executes project test command and confirms zero regressions
            test_cmd = node.inputs.get("test_framework") or ProjectAdapter.inspect(self.fs.root).detected_test_command
            if not test_cmd:
                return {"test_status": "SKIPPED", "reason": "No test framework detected"}

            if test_cmd.startswith("python3 "):
                test_cmd = f"{sys.executable} {test_cmd[8:]}"
            elif test_cmd.startswith("python "):
                test_cmd = f"{sys.executable} {test_cmd[7:]}"
            elif test_cmd == "pytest" or test_cmd.startswith("pytest "):
                test_cmd = f"{sys.executable} -m pytest {test_cmd[6:]}".strip()

            from core.security.env_scrub import scrub_env
            clean_env, _ = scrub_env(dict(os.environ))
            clean_env["PYTHONPATH"] = f".:{clean_env.get('PYTHONPATH', '')}".rstrip(":")

            proc = await asyncio.create_subprocess_shell(
                test_cmd,
                cwd=str(self.fs.root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env,
            )
            stdout_b, stderr_b = await proc.communicate()
            exit_code = proc.returncode or 0
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")

            if exit_code != 0:
                raise RuntimeError(
                    f"Test Verifier Failure (exit code {exit_code}): "
                    f"{stderr.strip() or stdout.strip() or 'Test suite failed'}"
                )

            return {
                "test_status": "PASSED",
                "exit_code": exit_code,
                "stdout_summary": stdout[:500],
            }

        return {"status": "ok"}
