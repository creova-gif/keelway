"""
Keelway Plugin & Extension Manifest Specification.
Defines plugin metadata, declared MCP servers, permission envelopes, and cryptographic digests.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PluginPermissions:
    read_paths: List[str] = field(default_factory=lambda: ["**"])
    write_paths: List[str] = field(default_factory=list)
    network: str = "none"  # "none" | "loopback" | "full"
    commands: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str
    license: str = "Apache-2.0"
    homepage: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    mcp_servers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    permissions: PluginPermissions = field(default_factory=PluginPermissions)
    digest_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.digest_sha256:
            self.digest_sha256 = self.calculate_digest()

    def calculate_digest(self) -> str:
        """Compute deterministic SHA-256 digest of manifest contents."""
        data = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "capabilities": sorted(self.capabilities),
            "mcp_servers": self.mcp_servers,
            "permissions": self.permissions.to_dict(),
        }
        canonical_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if not res.get("digest_sha256"):
            res["digest_sha256"] = self.calculate_digest()
        return res

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PluginManifest:
        perms_raw = data.get("permissions") or {}
        permissions = PluginPermissions(
            read_paths=perms_raw.get("read_paths", ["**"]),
            write_paths=perms_raw.get("write_paths", []),
            network=perms_raw.get("network", "none"),
            commands=perms_raw.get("commands", []),
        )

        manifest = cls(
            name=data["name"],
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            license=data.get("license", "Apache-2.0"),
            homepage=data.get("homepage"),
            capabilities=data.get("capabilities", []),
            mcp_servers=data.get("mcp_servers", {}),
            permissions=permissions,
            digest_sha256=data.get("digest_sha256", ""),
        )
        if not manifest.digest_sha256:
            manifest.digest_sha256 = manifest.calculate_digest()
        return manifest

    @classmethod
    def load_file(cls, path: Path) -> PluginManifest:
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Plugin manifest file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(raw)
