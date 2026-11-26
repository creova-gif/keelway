"""Agent Manifest v1: a declarative, versioned, signable description of one agent.

A manifest says what an agent may do (tools, paths, commands, network), how much it may spend, which models it
may use and how isolated it runs. It is data only: nothing here runs an agent. The schema is deliberately
strict (unknown fields are rejected) and safe by default.

Signing here is HMAC-SHA256 with a local workspace key. That proves "this manifest is unchanged since someone
holding this key signed it", which suits a team that shares a key. It is NOT public-key signing: a third party
cannot verify it without the key. Ed25519 signatures (so a registry can verify without a secret) are the planned
follow-up and need the `cryptography` package, which is not a dependency yet.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_ID = "keelway.agent/v1"
KNOWN_TOOLS = ("read_file", "write_file", "edit_file", "run_command", "list_dir", "search_codebase")
MUTATING_TOOLS = {"write_file", "edit_file"}
# Keelway's own state (including the signing key) and git internals are never readable or writable by an agent.
PROTECTED_PREFIXES = (".keelway", ".kora", ".git")
SHELL_META = re.compile(r"[;&|`$<>\n\\]")
HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
KEY_FILE = "agent_signing.key"


def _check_path(raw: str, *, allow_catch_all: bool) -> str:
    text = str(raw).strip()
    if not text or "\\" in text:
        raise ValueError("paths must be non-empty and use '/'")
    p = PurePosixPath(text)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"'{raw}' must be relative to the workspace and stay inside it")
    norm = str(p)
    if norm == ".":
        raise ValueError("'.' is not a valid path pattern; name a folder or a file")
    first = p.parts[0]
    if any(first == prefix for prefix in PROTECTED_PREFIXES):
        raise ValueError(f"'{raw}' is protected: Keelway and git internals are off limits")
    if not allow_catch_all and not norm.strip("*?[]/."):
        raise ValueError(f"'{raw}' matches every file; scope it to a file or folder")
    return norm


class ModelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    routing: Literal["local_first", "local_only", "cloud_only"] = "local_first"
    preferred_provider: Optional[Literal["anthropic", "openai", "google", "local"]] = None

    @model_validator(mode="after")
    def _consistent(self) -> "ModelPolicy":
        if self.routing == "local_only" and self.preferred_provider not in (None, "local"):
            raise ValueError("routing 'local_only' cannot prefer a cloud provider")
        if self.routing == "cloud_only" and self.preferred_provider == "local":
            raise ValueError("routing 'cloud_only' cannot prefer the local provider")
        return self


class Permissions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    autonomy: Literal["confirm_all", "confirm_mutation", "autonomous"] = "confirm_mutation"
    read_paths: List[str] = Field(default_factory=list)
    write_paths: List[str] = Field(default_factory=list)
    commands: List[str] = Field(default_factory=list, description="Exact commands only; no shell operators.")
    network: Literal["none", "allowlist"] = "none"
    network_allow: List[str] = Field(default_factory=list)

    @field_validator("read_paths")
    @classmethod
    def _read(cls, value: List[str]) -> List[str]:
        return [_check_path(v, allow_catch_all=True) for v in value]

    @field_validator("write_paths")
    @classmethod
    def _write(cls, value: List[str]) -> List[str]:
        return [_check_path(v, allow_catch_all=False) for v in value]

    @field_validator("commands")
    @classmethod
    def _commands(cls, value: List[str]) -> List[str]:
        out = []
        for cmd in value:
            cmd = cmd.strip()
            if not cmd:
                raise ValueError("commands must not be blank")
            if SHELL_META.search(cmd):
                raise ValueError(f"'{cmd}': shell operators are not allowed; list each command on its own")
            out.append(cmd)
        return out

    @field_validator("network_allow")
    @classmethod
    def _hosts(cls, value: List[str]) -> List[str]:
        for host in value:
            if not HOST_RE.match(host):
                raise ValueError(f"'{host}' is not a plain hostname (no wildcards, ports or schemes)")
        return value

    @model_validator(mode="after")
    def _network(self) -> "Permissions":
        if self.network == "none" and self.network_allow:
            raise ValueError("network_allow is set but network is 'none'")
        if self.network == "allowlist" and not self.network_allow:
            raise ValueError("network 'allowlist' needs at least one host in network_allow")
        return self


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_usd_per_run: float = Field(gt=0, le=1000)
    max_steps: int = Field(ge=1, le=500)


class Signature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alg: Literal["hmac-sha256"]
    key_id: str
    digest: str
    value: str
    signed_by: str
    signed_at: str


class AgentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_id: Literal["keelway.agent/v1"] = Field(alias="schema")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,62}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    owner: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    instructions: str = Field(min_length=1, max_length=20000)
    model: ModelPolicy = Field(default_factory=ModelPolicy)
    tools: List[str] = Field(min_length=1)
    mcp_servers: List[str] = Field(default_factory=list, description="Names of host-configured MCP servers.")
    permissions: Permissions = Field(default_factory=Permissions)
    budget: Budget
    sandbox: Literal["workspace", "worktree", "container"] = "worktree"
    signature: Optional[Signature] = None

    @field_validator("tools")
    @classmethod
    def _tools(cls, value: List[str]) -> List[str]:
        unknown = [t for t in value if t not in KNOWN_TOOLS]
        if unknown:
            raise ValueError(f"unknown tool(s): {', '.join(unknown)}; known: {', '.join(KNOWN_TOOLS)}")
        if len(set(value)) != len(value):
            raise ValueError("tools must not repeat")
        return value

    @field_validator("mcp_servers")
    @classmethod
    def _mcp(cls, value: List[str]) -> List[str]:
        for name in value:
            if not re.match(r"^[a-z][a-z0-9_-]{0,62}$", name):
                raise ValueError(f"'{name}' is not a valid MCP server name")
        if len(set(value)) != len(value):
            raise ValueError("mcp_servers must not repeat")
        return value

    @model_validator(mode="after")
    def _cross_rules(self) -> "AgentManifest":
        perms, tools = self.permissions, set(self.tools)
        if tools & MUTATING_TOOLS and not perms.write_paths:
            raise ValueError("write_file/edit_file need at least one entry in permissions.write_paths")
        if not tools & MUTATING_TOOLS and perms.write_paths:
            raise ValueError("permissions.write_paths is set but no write_file/edit_file tool is enabled")
        if "run_command" in tools and not perms.commands:
            raise ValueError("run_command needs at least one exact command in permissions.commands")
        if "run_command" not in tools and perms.commands:
            raise ValueError("permissions.commands is set but run_command is not enabled")
        if perms.autonomy == "autonomous" and "run_command" in tools and self.sandbox == "workspace":
            raise ValueError("autonomous agents that run commands must use sandbox 'worktree' or 'container'")
        return self


@dataclass
class Report:
    manifest: Optional[AgentManifest] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.manifest is not None and not self.errors


def validate(data: Any) -> Report:
    """Validate a parsed manifest. Never raises on bad input; returns every problem found."""
    if not isinstance(data, dict):
        return Report(errors=["a manifest must be a JSON object"])
    try:
        manifest = AgentManifest.model_validate(data)
    except ValidationError as exc:
        messages = []
        for err in exc.errors():
            where = ".".join(str(p) for p in err["loc"]) or "manifest"
            messages.append(f"{where}: {err['msg'].removeprefix('Value error, ')}")
        return Report(errors=messages)
    report = Report(manifest=manifest)
    perms = manifest.permissions
    if perms.autonomy == "autonomous":
        report.warnings.append("autonomy 'autonomous' skips approvals; running it needs the approve_tier3 permission")
    if not perms.read_paths and "read_file" in manifest.tools:
        report.warnings.append("read_file is enabled with no read_paths: the whole workspace (minus protected paths) is readable")
    if manifest.sandbox == "workspace" and "run_command" in manifest.tools:
        report.warnings.append("run_command in sandbox 'workspace' runs against your real files; prefer 'worktree'")
    if manifest.model.routing != "local_only" and perms.network == "none":
        report.warnings.append("cloud model use sends prompts off the machine even though permissions.network is 'none' (that field limits tools)")
    return report


def load_file(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc


def canonical_bytes(manifest: AgentManifest) -> bytes:
    body = manifest.model_dump(mode="json", by_alias=True, exclude={"signature"}, exclude_none=True)
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(manifest: AgentManifest) -> str:
    """Deterministic content hash of everything except the signature."""
    return "sha256:" + hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def key_id(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:12]


def load_or_create_key(workspace_root: Path) -> bytes:
    """Read the workspace signing key, creating it (owner-only permissions) on first use."""
    directory = Path(workspace_root) / ".keelway"
    path = directory / KEY_FILE
    if path.exists():
        return bytes.fromhex(path.read_text().strip())
    directory.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(key.hex() + "\n")
    return key


def sign(manifest: AgentManifest, key: bytes, signed_by: str) -> AgentManifest:
    dig = digest(manifest)
    mac = hmac.new(key, dig.encode("utf-8"), hashlib.sha256).hexdigest()
    sig = Signature(
        alg="hmac-sha256", key_id=key_id(key), digest=dig, value=mac, signed_by=signed_by,
        signed_at=datetime.now(timezone.utc).isoformat(),
    )
    return manifest.model_copy(update={"signature": sig})


def verify(manifest: AgentManifest, key: bytes) -> Tuple[bool, str]:
    sig = manifest.signature
    if sig is None:
        return False, "not_signed"
    if sig.key_id != key_id(key):
        return False, "wrong_key"
    if sig.digest != digest(manifest):
        return False, "content_changed_since_signing"
    expected = hmac.new(key, sig.digest.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig.value):
        return False, "bad_signature"
    return True, "ok"


def to_json(manifest: AgentManifest) -> str:
    body = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
    return json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
