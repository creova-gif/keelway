"""
Keelway Multi-Tenant Organization & RBAC Subsystem.
Provides enterprise-grade access control, team isolation, and audit logging.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import hashlib


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    ENGINEER = "engineer"
    AUDITOR = "auditor"  # Read-only for compliance/security review
    PHONE = "phone"  # Paired phone: sees agent runs and approves or denies their steps, nothing else
    GATE = "gate"  # Claude Code hook: submits commands for approval and redeems tickets, nothing else


class Permission(str, Enum):
    EXECUTE_AGENT = "execute_agent"
    APPROVE_TIER3 = "approve_tier3"
    MANAGE_MEMORIES = "manage_memories"
    EXPORT_DATASETS = "export_datasets"
    MANAGE_KEYS = "manage_keys"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    APPROVE_AGENT_STEPS = "approve_agent_steps"
    GATE_SUBMIT = "gate_submit"


ROLE_PERMISSIONS: Dict[Role, List[Permission]] = {
    Role.OWNER: list(Permission),
    Role.ADMIN: [
        Permission.EXECUTE_AGENT,
        Permission.APPROVE_TIER3,
        Permission.MANAGE_MEMORIES,
        Permission.EXPORT_DATASETS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.APPROVE_AGENT_STEPS,
    ],
    Role.ENGINEER: [
        Permission.EXECUTE_AGENT,
        Permission.MANAGE_MEMORIES,
        Permission.VIEW_AUDIT_LOGS,
    ],
    Role.AUDITOR: [
        Permission.VIEW_AUDIT_LOGS,
    ],
    Role.PHONE: [
        Permission.APPROVE_AGENT_STEPS,
    ],
    Role.GATE: [
        Permission.GATE_SUBMIT,
    ],
}


class AccessControlManager:
    """Evaluates whether an actor has sufficient role privileges to perform an action."""

    @staticmethod
    def can_perform(role: Role, permission: Permission) -> bool:
        allowed = ROLE_PERMISSIONS.get(role, [])
        return permission in allowed

    @staticmethod
    def audit_event(
        actor_id: str,
        role: Role,
        action: str,
        resource: str,
        allowed: bool,
    ) -> Dict[str, Any]:
        """Creates an immutable audit log entry for security and compliance."""
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = f"{actor_id}:{role.value}:{action}:{resource}:{allowed}:{timestamp}"
        entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return {
            "entry_hash": entry_hash,
            "actor_id": actor_id,
            "role": role.value,
            "action": action,
            "resource": resource,
            "allowed": allowed,
            "timestamp": timestamp,
        }
