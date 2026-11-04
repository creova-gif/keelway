"""
KHub Universal Skills & Tools Importer Data Models.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillSourceType(str, Enum):
    CLAUDE_SKILL = "claude_skill"
    CURSOR_SKILL = "cursor_skill"
    CURSOR_RULE = "cursor_rule"
    AGENTS_SKILL = "agents_skill"
    CODEX_SKILL = "codex_skill"
    MCP_TOOL_BUNDLE = "mcp_tool_bundle"


@dataclass
class ImportedSkill:
    id: str
    name: str
    source_type: SkillSourceType
    source_path: str
    content: str
    digest_sha256: str
    is_rule_only: bool = False  # True for .cursor/rules, distinct from executable skills
    permissions_required: List[str] = field(default_factory=list)
    version_pinned: bool = True
    upstream_has_drift: bool = False
    approved_by_user: bool = False
    imported_at_utc: float = field(default_factory=time.time)

    def calculate_digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["source_type"] = self.source_type.value if isinstance(self.source_type, SkillSourceType) else str(self.source_type)
        return data
