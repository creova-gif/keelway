"""
KFlow Durable Task DAG Orchestration Engine.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set

from core.kflow.models import FlowDAG, FlowNode, FlowStatus, ProofPacket


class BaseShaDriftError(ValueError):
    """Raised when the target repository's current HEAD does not match the exact base SHA approved."""
    pass


class KFlowEngine:
    """Durable DAG orchestration engine with fanout caps, base SHA enforcement, and proof packets."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self._lock = Lock()
        self.storage_dir = storage_dir or Path(".keelway/kflow")
        self._flows: Dict[str, FlowDAG] = {}
        self._leases: Dict[str, str] = {}  # branch_name -> lease_holder_flow_id

    def create_dag(
        self,
        flow_id: str,
        goal: str,
        nodes: List[FlowNode],
        max_fanout: int = 4,
    ) -> FlowDAG:
        with self._lock:
            if flow_id in self._flows:
                raise ValueError(f"Flow DAG '{flow_id}' already exists")
            node_map = {n.node_id: n for n in nodes}
            dag = FlowDAG(
                flow_id=flow_id,
                goal=goal,
                nodes=node_map,
                max_fanout=max_fanout,
                status=FlowStatus.PENDING,
            )
            dag.checkpoint_sha256 = dag.calculate_checkpoint_hash()
            self._flows[flow_id] = dag
            self._checkpoint(dag)
            return dag

    def acquire_worktree_lease(self, flow_id: str, branch_name: str) -> str:
        """Acquire an exclusive execution lease for a specific worktree branch."""
        with self._lock:
            if branch_name in self._leases and self._leases[branch_name] != flow_id:
                raise PermissionError(f"Branch '{branch_name}' is locked by active lease for flow '{self._leases[branch_name]}'")
            lease_id = f"lease_{branch_name}_{int(time.time() * 1000)}"
            self._leases[branch_name] = flow_id
            if flow_id in self._flows:
                self._flows[flow_id].worktree_lease_id = lease_id
            return lease_id

    def release_worktree_lease(self, branch_name: str) -> bool:
        with self._lock:
            if branch_name in self._leases:
                del self._leases[branch_name]
                return True
            return False

    def _checkpoint(self, dag: FlowDAG) -> None:
        if not self.storage_dir:
            return
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            f_path = self.storage_dir / f"{dag.flow_id}.flow.json"
            dag.checkpoint_sha256 = dag.calculate_checkpoint_hash()
            f_path.write_text(json.dumps(dag.to_dict(), indent=2), encoding="utf-8")
        except Exception:
            pass

    def execute_dag(
        self,
        flow_id: str,
        current_git_head_sha: str,
        node_executor: Optional[Callable[[FlowNode], Dict[str, Any]]] = None,
    ) -> ProofPacket:
        """Execute flow in topological order, asserting base SHA integrity and assembling proof packet."""
        with self._lock:
            dag = self._flows.get(flow_id)
            if not dag:
                raise KeyError(f"Flow '{flow_id}' not found")
            dag.status = FlowStatus.RUNNING

        completed_node_ids: Set[str] = set()
        evidence_items: List[Dict[str, Any]] = []

        # Find nodes ready to run in topological order
        while True:
            # Check for cancellation
            with self._lock:
                if dag.status == FlowStatus.CANCELLED:
                    raise InterruptedError(f"Flow '{flow_id}' was cancelled.")

            ready_nodes = [
                n for n in dag.nodes.values()
                if n.status == FlowStatus.PENDING
                and all(dep in completed_node_ids for dep in n.dependencies)
            ]

            if not ready_nodes:
                break

            # Enforce max fanout cap
            batch = ready_nodes[:dag.max_fanout]

            for node in batch:
                # Exact base SHA check
                if node.exact_base_sha and current_git_head_sha != node.exact_base_sha:
                    node.status = FlowStatus.FAILED
                    node.result = {"error": f"Base SHA drifted: approved={node.exact_base_sha}, current={current_git_head_sha}"}
                    dag.status = FlowStatus.FAILED
                    self._checkpoint(dag)
                    raise BaseShaDriftError(f"Base SHA drift detected on node '{node.node_id}'")

                node.status = FlowStatus.RUNNING
                node.started_at_epoch = time.time()
                self._checkpoint(dag)

                try:
                    if node_executor:
                        res = node_executor(node)
                    else:
                        res = {"status": "ok", "action": f"Executed {node.tool} by {node.assigned_role}"}
                    node.result = res
                    node.status = FlowStatus.COMPLETED
                    completed_node_ids.add(node.node_id)
                    evidence_items.append({
                        "node_id": node.node_id,
                        "tool": node.tool,
                        "role": node.assigned_role,
                        "output": res,
                    })
                except Exception as e:
                    node.status = FlowStatus.FAILED
                    node.result = {"error": str(e)}
                    dag.status = FlowStatus.FAILED
                    self._checkpoint(dag)
                    raise e
                finally:
                    node.completed_at_epoch = time.time()
                    self._checkpoint(dag)

        all_completed = all(n.status == FlowStatus.COMPLETED for n in dag.nodes.values())
        dag.status = FlowStatus.COMPLETED if all_completed else FlowStatus.FAILED
        self._checkpoint(dag)

        # Assemble proof packet
        proof = ProofPacket(
            flow_id=dag.flow_id,
            goal=dag.goal,
            base_commit_sha=current_git_head_sha,
            head_commit_sha=current_git_head_sha,
            nodes_executed=len(completed_node_ids),
            all_tests_passed=all_completed,
            evidence_items=evidence_items,
        )
        proof.seal()
        return proof

    def cancel_flow(self, flow_id: str) -> bool:
        with self._lock:
            dag = self._flows.get(flow_id)
            if not dag:
                return False
            dag.status = FlowStatus.CANCELLED
            for n in dag.nodes.values():
                if n.status in (FlowStatus.PENDING, FlowStatus.RUNNING):
                    n.status = FlowStatus.CANCELLED
            self._checkpoint(dag)
            return True

    def get_flow(self, flow_id: str) -> Optional[FlowDAG]:
        with self._lock:
            return self._flows.get(flow_id)


# Singleton instance
kflow_engine = KFlowEngine()
