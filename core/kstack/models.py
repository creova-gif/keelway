"""
KStack Role Skills Data Models.
Defines typed schemas for SKILL.md workflows, permission tiers, and execution provenance.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillContract:
    inputs: Dict[str, str] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)


@dataclass
class SkillDefinition:
    name: str
    version: str
    role: str
    description: str
    permissions: List[str]
    contract: SkillContract
    instructions: str
    source_uri: str
    digest_sha256: str = ""
    pinned: bool = True
    revoked: bool = False
    revocation_reason: Optional[str] = None
    created_at_utc: float = field(default_factory=time.time)

    def calculate_digest(self) -> str:
        payload = {
            "name": self.name,
            "version": self.version,
            "role": self.role,
            "permissions": sorted(self.permissions),
            "instructions": self.instructions.strip(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not self.digest_sha256:
            data["digest_sha256"] = self.calculate_digest()
        return data


@dataclass
class SkillExecutionProof:
    execution_id: str
    skill_name: str
    skill_digest_sha256: str
    actor: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    permissions_used: List[str]
    success: bool
    duration_ms: float
    timestamp_utc: float = field(default_factory=time.time)
    signature_sha256: str = ""

    def seal(self) -> str:
        payload = {
            "execution_id": self.execution_id,
            "skill_name": self.skill_name,
            "skill_digest_sha256": self.skill_digest_sha256,
            "actor": self.actor,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "success": self.success,
            "timestamp_utc": self.timestamp_utc,
        }
        self.signature_sha256 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return self.signature_sha256

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
