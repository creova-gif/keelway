"""
KSpaces — Collaborative Team Workspaces & Agent Governance for Keelway.
"""

from core.kspaces.models import (
    AgentIdentityStatus,
    AgentServiceIdentity,
    KSpace,
    ReviewComment,
    SpaceRole,
    SpaceTask,
    TaskStatus,
)
from core.kspaces.manager import KSpacesManager, kspaces_manager
from core.kspaces.conflict import ConflictDetector, ConflictHunk, ConflictReport

__all__ = [
    "AgentIdentityStatus",
    "AgentServiceIdentity",
    "KSpace",
    "ReviewComment",
    "SpaceRole",
    "SpaceTask",
    "TaskStatus",
    "KSpacesManager",
    "kspaces_manager",
    "ConflictDetector",
    "ConflictHunk",
    "ConflictReport",
]
