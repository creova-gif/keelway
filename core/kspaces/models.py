"""
KSpaces Collaborative Team Workspace & Agent Service Identity Models.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SpaceRole(str, Enum):
    OWNER = "owner"
    AGENT_MANAGER = "agent_manager"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class AgentIdentityStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    MERGED = "merged"
    CLOSED = "closed"


@dataclass
class AgentServiceIdentity:
    agent_id: str
    name: str
    owner_user_id: str
    role_description: str
    allowed_tools: List[str]
    expires_at_epoch: float
    created_at_epoch: float = field(default_factory=time.time)
    status: AgentIdentityStatus = AgentIdentityStatus.ACTIVE

    def is_valid(self) -> bool:
        if self.status != AgentIdentityStatus.ACTIVE:
            return False
        return time.time() < self.expires_at_epoch

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, AgentIdentityStatus) else str(self.status)
        data["is_valid"] = self.is_valid()
        return data


@dataclass
class ReviewComment:
    comment_id: str
    task_id: str
    author_id: str
    file_path: str
    line_number: int
    body: str
    is_resolved: bool = False
    created_at_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpaceTask:
    task_id: str
    title: str
    branch_name: str
    base_commit_sha: str
    status: TaskStatus = TaskStatus.OPEN
    assigned_to: Optional[str] = None
    created_by: str = ""
    approved_for_merge_by: Optional[str] = None
    comments: List[ReviewComment] = field(default_factory=list)
    created_at_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, TaskStatus) else str(self.status)
        data["comments"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.comments]
        return data


@dataclass
class KSpace:
    space_id: str
    name: str
    owner_id: str
    members: Dict[str, SpaceRole] = field(default_factory=dict)
    agents: Dict[str, AgentServiceIdentity] = field(default_factory=dict)
    tasks: Dict[str, SpaceTask] = field(default_factory=dict)
    created_at_epoch: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "space_id": self.space_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "members": {uid: r.value if isinstance(r, SpaceRole) else str(r) for uid, r in self.members.items()},
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "created_at_epoch": self.created_at_epoch,
        }
