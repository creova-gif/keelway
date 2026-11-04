"""
KBrain Scope-Aware Knowledge & Fact Memory Models.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class KnowledgeScope(str, Enum):
    LOCAL_SESSION = "local_session"
    PROJECT = "project"
    TEAM = "team"
    ORG = "org"


class FactStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    CONFLICT = "conflict"
    CORRECTED = "corrected"
    WITHDRAWN = "withdrawn"


@dataclass
class FactRecord:
    id: str
    scope: KnowledgeScope
    key: str
    statement: str
    provenance_uri: str
    provenance_reason: str
    status: FactStatus = FactStatus.PROPOSED
    revision: int = 1
    created_by: str = "system"
    approved_by: Optional[str] = None
    created_at_utc: float = field(default_factory=time.time)
    updated_at_utc: float = field(default_factory=time.time)
    superseded_by: Optional[str] = None
    sha256: str = ""

    def calculate_sha256(self) -> str:
        payload = {
            "id": self.id,
            "scope": self.scope.value if isinstance(self.scope, KnowledgeScope) else str(self.scope),
            "key": self.key,
            "statement": self.statement,
            "provenance_uri": self.provenance_uri,
            "revision": self.revision,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["scope"] = self.scope.value if isinstance(self.scope, KnowledgeScope) else str(self.scope)
        data["status"] = self.status.value if isinstance(self.status, FactStatus) else str(self.status)
        if not self.sha256:
            data["sha256"] = self.calculate_sha256()
        return data
