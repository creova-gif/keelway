"""
Keelway AgentSpec v1.
Declarative specification for AI agents conforming to Section 12 of the Keelway Master Directive.
Defines inputs/outputs, model policy, tool allowlist, permissions, state contract,
evaluation criteria, cost/latency limits, and deployment targets.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from core.agents import manifest as am


SPEC_SCHEMA_ID = "keelway.spec/v1"


class AgentParam(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    type: Literal["string", "number", "boolean", "list", "dict"] = "string"
    description: str = Field(default="", max_length=200)
    required: bool = True
    default: Optional[Any] = None


class StateContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_state: str = "CREATED"
    terminal_states: List[str] = Field(default_factory=lambda: ["COMPLETED", "FAILED", "CANCELLED"])
    allowed_states: List[str] = Field(
        default_factory=lambda: [
            "CREATED",
            "CONTEXT_LOADING",
            "PLANNING",
            "PLAN_READY",
            "AWAITING_APPROVAL",
            "EXECUTING",
            "VERIFYING",
            "COMPLETED",
            "PAUSED",
            "BLOCKED",
            "FAILED",
            "CANCELLED",
        ]
    )


class EvaluationCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_command: str = Field(default="pytest -q", min_length=1)
    max_latency_ms: int = Field(default=30000, ge=100)
    max_usd_budget: float = Field(default=1.0, gt=0, le=1000)
    pass_condition: str = Field(default="exit_code == 0", max_length=100)


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_id: Literal["keelway.spec/v1"] = Field(default=SPEC_SCHEMA_ID, alias="schema")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,62}$")
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    author: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    instructions: str = Field(min_length=1, max_length=20000)
    inputs: List[AgentParam] = Field(default_factory=list)
    outputs: List[AgentParam] = Field(default_factory=list)
    model: am.ModelPolicy = Field(default_factory=am.ModelPolicy)
    tools: List[str] = Field(default_factory=lambda: ["read_file", "edit_file", "run_command", "list_dir"])
    permissions: am.Permissions = Field(default_factory=am.Permissions)
    budget: am.Budget = Field(default_factory=lambda: am.Budget(max_usd_per_run=1.0, max_steps=50))
    state_contract: StateContract = Field(default_factory=StateContract)
    evaluation: EvaluationCriteria = Field(default_factory=EvaluationCriteria)
    deployment_target: Literal["local", "worktree", "container"] = "worktree"

    def to_manifest_dict(self) -> Dict[str, Any]:
        """Compile AgentSpec into a valid Keelway AgentManifest v1 dictionary."""
        return {
            "schema": am.SCHEMA_ID,
            "name": self.name,
            "version": self.version,
            "owner": self.author,
            "description": self.description,
            "instructions": self.instructions,
            "model": self.model.model_dump(exclude_none=True),
            "tools": self.tools,
            "permissions": self.permissions.model_dump(exclude_none=True),
            "budget": self.budget.model_dump(),
            "sandbox": "worktree" if self.deployment_target in ("worktree", "local") else "container",
        }

    def validate_manifest(self) -> am.ValidationReport:
        """Validate the compiled manifest against Keelway AgentManifest v1 schema."""
        return am.validate(self.to_manifest_dict())

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(by_alias=True), indent=indent)

    @classmethod
    def from_json(cls, raw: str | Dict[str, Any]) -> "AgentSpec":
        data = json.loads(raw) if isinstance(raw, str) else raw
        return cls(**data)
