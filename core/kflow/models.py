"""
KFlow Durable Task DAG Orchestration & Proof Packet Models.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FlowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class FlowNode:
    node_id: str
    name: str
    assigned_role: str
    tool: str
    inputs: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    budget_token_cap: int = 50000
    timeout_seconds: float = 300.0
    status: FlowStatus = FlowStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    exact_base_sha: str = ""
    started_at_epoch: Optional[float] = None
    completed_at_epoch: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, FlowStatus) else str(self.status)
        return data


@dataclass
class FlowDAG:
    flow_id: str
    goal: str
    nodes: Dict[str, FlowNode]
    max_fanout: int = 4
    status: FlowStatus = FlowStatus.PENDING
    worktree_lease_id: Optional[str] = None
    created_at_epoch: float = field(default_factory=time.time)
    checkpoint_sha256: str = ""

    def calculate_checkpoint_hash(self) -> str:
        payload = {
            "flow_id": self.flow_id,
            "goal": self.goal,
            "nodes": {nid: n.to_dict() for nid, n in sorted(self.nodes.items())},
            "status": self.status.value if isinstance(self.status, FlowStatus) else str(self.status),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "goal": self.goal,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "max_fanout": self.max_fanout,
            "status": self.status.value if isinstance(self.status, FlowStatus) else str(self.status),
            "worktree_lease_id": self.worktree_lease_id,
            "created_at_epoch": self.created_at_epoch,
            "checkpoint_sha256": self.checkpoint_sha256 or self.calculate_checkpoint_hash(),
        }


@dataclass
class ProofPacket:
    flow_id: str
    goal: str
    base_commit_sha: str
    head_commit_sha: str
    nodes_executed: int
    all_tests_passed: bool
    evidence_items: List[Dict[str, Any]]
    sealed_at_epoch: float = field(default_factory=time.time)
    proof_sha256: str = ""

    def seal(self) -> str:
        payload = {
            "flow_id": self.flow_id,
            "goal": self.goal,
            "base_commit_sha": self.base_commit_sha,
            "head_commit_sha": self.head_commit_sha,
            "nodes_executed": self.nodes_executed,
            "all_tests_passed": self.all_tests_passed,
            "evidence_items": self.evidence_items,
            "sealed_at_epoch": self.sealed_at_epoch,
        }
        self.proof_sha256 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return self.proof_sha256

    def to_dict(self) -> Dict[str, Any]:
        if not self.proof_sha256:
            self.seal()
        return asdict(self)
