"""
KSpaces Manager: Multi-Tenant Team Workspaces & Agent Governance.
"""

from __future__ import annotations

import time
import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from core.kspaces.models import (
    AgentIdentityStatus,
    AgentServiceIdentity,
    KSpace,
    ReviewComment,
    SpaceRole,
    SpaceTask,
    TaskStatus,
)


class KSpacesManager:
    """Manages team spaces, role-based access control, agent service identities, and merge gates."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self._lock = Lock()
        self._spaces: Dict[str, KSpace] = {}
        self.persistence_path = persistence_path or Path(".keelway/kspaces/spaces.json")
        if self.persistence_path and self.persistence_path.exists():
            self._load()

    def _save(self) -> None:
        if not self.persistence_path:
            return
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_path, "w", encoding="utf-8") as f:
                json.dump({"spaces": {sid: s.to_dict() for sid, s in self._spaces.items()}}, f, indent=2)
        except Exception:
            pass

    def _load(self) -> None:
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for sid, sdata in data.get("spaces", {}).items():
                    members = {uid: SpaceRole(r) for uid, r in sdata.get("members", {}).items()}
                    agents = {}
                    for aid, adata in sdata.get("agents", {}).items():
                        agents[aid] = AgentServiceIdentity(
                            agent_id=adata["agent_id"],
                            name=adata["name"],
                            owner_user_id=adata["owner_user_id"],
                            role_description=adata["role_description"],
                            allowed_tools=adata["allowed_tools"],
                            expires_at_epoch=adata["expires_at_epoch"],
                            created_at_epoch=adata.get("created_at_epoch", time.time()),
                            status=AgentIdentityStatus(adata.get("status", "active")),
                        )
                    tasks = {}
                    for tid, tdata in sdata.get("tasks", {}).items():
                        comments = [ReviewComment(**c) for c in tdata.get("comments", [])]
                        tasks[tid] = SpaceTask(
                            task_id=tdata["task_id"],
                            title=tdata["title"],
                            branch_name=tdata["branch_name"],
                            base_commit_sha=tdata["base_commit_sha"],
                            status=TaskStatus(tdata.get("status", "open")),
                            assigned_to=tdata.get("assigned_to"),
                            created_by=tdata.get("created_by", ""),
                            approved_for_merge_by=tdata.get("approved_for_merge_by"),
                            comments=comments,
                            created_at_epoch=tdata.get("created_at_epoch", time.time()),
                        )
                    self._spaces[sid] = KSpace(
                        space_id=sid,
                        name=sdata["name"],
                        owner_id=sdata["owner_id"],
                        members=members,
                        agents=agents,
                        tasks=tasks,
                        created_at_epoch=sdata.get("created_at_epoch", time.time()),
                    )
        except Exception:
            pass

    def create_space(self, space_id: str, name: str, owner_id: str) -> KSpace:
        with self._lock:
            if space_id in self._spaces:
                raise ValueError(f"Space '{space_id}' already exists")
            space = KSpace(
                space_id=space_id,
                name=name,
                owner_id=owner_id,
                members={owner_id: SpaceRole.OWNER},
            )
            self._spaces[space_id] = space
            self._save()
            return space

    def get_space(self, space_id: str, caller_id: str) -> KSpace:
        with self._lock:
            space = self._spaces.get(space_id)
            if not space:
                raise KeyError(f"Space '{space_id}' not found")
            if caller_id not in space.members:
                raise PermissionError(f"User '{caller_id}' is not a member of space '{space_id}'")
            return space

    def add_member(self, space_id: str, user_id: str, role: SpaceRole, caller_id: str) -> bool:
        with self._lock:
            space = self._spaces.get(space_id)
            if not space:
                raise KeyError(f"Space '{space_id}' not found")
            caller_role = space.members.get(caller_id)
            if caller_role not in (SpaceRole.OWNER, SpaceRole.AGENT_MANAGER):
                raise PermissionError("Only Space Owner or Agent Manager can manage members")
            space.members[user_id] = role
            self._save()
            return True

    def register_agent_identity(
        self,
        space_id: str,
        name: str,
        owner_user_id: str,
        role_description: str,
        allowed_tools: List[str],
        ttl_seconds: float = 86400.0,
    ) -> AgentServiceIdentity:
        """Register a time-bound agent service identity owned by a specific human."""
        with self._lock:
            space = self._spaces.get(space_id)
            if not space:
                raise KeyError(f"Space '{space_id}' not found")
            if owner_user_id not in space.members:
                raise PermissionError(f"Owner '{owner_user_id}' must be a member of space '{space_id}'")

            agent_id = f"sa_{name}_{int(time.time() * 1000)}"
            now = time.time()
            identity = AgentServiceIdentity(
                agent_id=agent_id,
                name=name,
                owner_user_id=owner_user_id,
                role_description=role_description,
                allowed_tools=allowed_tools,
                expires_at_epoch=now + ttl_seconds,
                created_at_epoch=now,
                status=AgentIdentityStatus.ACTIVE,
            )
            space.agents[agent_id] = identity
            self._save()
            return identity

    def create_task(
        self,
        space_id: str,
        title: str,
        branch_name: str,
        base_commit_sha: str,
        caller_id: str,
        assigned_to: Optional[str] = None,
    ) -> SpaceTask:
        with self._lock:
            space = self._spaces.get(space_id)
            if not space:
                raise KeyError(f"Space '{space_id}' not found")
            if caller_id not in space.members:
                raise PermissionError(f"Caller '{caller_id}' is not a member of space '{space_id}'")

            task_id = f"task_{int(time.time() * 1000)}"
            task = SpaceTask(
                task_id=task_id,
                title=title,
                branch_name=branch_name,
                base_commit_sha=base_commit_sha,
                assigned_to=assigned_to,
                created_by=caller_id,
            )
            space.tasks[task_id] = task
            self._save()
            return task

    def add_review_comment(
        self,
        space_id: str,
        task_id: str,
        author_id: str,
        file_path: str,
        line_number: int,
        body: str,
    ) -> ReviewComment:
        with self._lock:
            space = self._spaces.get(space_id)
            if not space:
                raise KeyError(f"Space '{space_id}' not found")
            if author_id not in space.members and author_id not in space.agents:
                raise PermissionError(f"Author '{author_id}' is not authorized in space '{space_id}'")
            task = space.tasks.get(task_id)
            if not task:
                raise KeyError(f"Task '{task_id}' not found")

            comment_id = f"rc_{int(time.time() * 1000)}"
            comment = ReviewComment(
                comment_id=comment_id,
                task_id=task_id,
                author_id=author_id,
                file_path=file_path,
                line_number=line_number,
                body=body,
            )
            task.comments.append(comment)
            self._save()
            return comment

    def approve_merge(self, space_id: str, task_id: str, manager_id: str) -> bool:
        """Approve task for merge. Restricted strictly to OWNER or AGENT_MANAGER roles."""
        with self._lock:
            space = self._spaces.get(space_id)
            if not space:
                raise KeyError(f"Space '{space_id}' not found")
            role = space.members.get(manager_id)
            if role not in (SpaceRole.OWNER, SpaceRole.AGENT_MANAGER):
                raise PermissionError("Only Space Owner or Agent Manager can approve merges.")
            task = space.tasks.get(task_id)
            if not task:
                raise KeyError(f"Task '{task_id}' not found")

            task.status = TaskStatus.MERGED
            task.approved_for_merge_by = manager_id
            self._save()
            return True


# Singleton instance
kspaces_manager = KSpacesManager()
