"""Workspace-local Agent Manifest registry.

Registry entries are immutable by ``name@version``. Disabling an entry is a
kill switch for new runs and for later steps in runs started from that entry.
The registry is stored in Keelway's protected workspace state and replaced
atomically so a partial write cannot corrupt the previous copy.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.agents.manifest import AgentManifest, digest, validate

REGISTRY_FILE = "agent_registry.json"


class RegistryError(ValueError):
    pass


class ManifestNotFound(RegistryError):
    pass


class ManifestDisabled(RegistryError):
    pass


class ManifestVersionConflict(RegistryError):
    pass


@dataclass(frozen=True)
class RegistryEntry:
    manifest: AgentManifest
    enabled: bool
    created_at: str
    created_by: str

    def summary(self) -> Dict[str, Any]:
        manifest = self.manifest
        return {
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "owner": manifest.owner,
            "enabled": self.enabled,
            "digest": digest(manifest),
            "signed": manifest.signature is not None,
            "autonomy": manifest.permissions.autonomy,
            "tools": manifest.tools,
            "sandbox": manifest.sandbox,
            "max_steps": manifest.budget.max_steps,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


class ManifestRegistry:
    _lock = threading.RLock()

    def __init__(self, workspace_root: Path):
        self.path = Path(workspace_root) / ".keelway" / REGISTRY_FILE

    @staticmethod
    def _key(name: str, version: str) -> str:
        return f"{name}@{version}"

    def _read(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            body = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RegistryError(f"Manifest registry is unreadable: {exc}") from exc
        entries = body.get("entries") if isinstance(body, dict) else None
        if not isinstance(entries, dict):
            raise RegistryError("Manifest registry has an invalid format.")
        return entries

    def _write(self, entries: Dict[str, Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        payload = {"schema": "keelway.agent-registry/v1", "entries": entries}
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    @staticmethod
    def _entry(raw: Dict[str, Any]) -> RegistryEntry:
        report = validate(raw.get("manifest"))
        if not report.ok:
            raise RegistryError(f"Stored manifest is invalid: {report.errors[0]}")
        return RegistryEntry(
            manifest=report.manifest,
            enabled=raw.get("enabled") is True,
            created_at=str(raw.get("created_at", "")),
            created_by=str(raw.get("created_by", "")),
        )

    def register(self, manifest: AgentManifest, created_by: str, *, enabled: bool = True) -> RegistryEntry:
        key = self._key(manifest.name, manifest.version)
        with self._lock:
            entries = self._read()
            if key in entries:
                existing = self._entry(entries[key])
                if digest(existing.manifest) != digest(manifest):
                    raise ManifestVersionConflict(
                        f"{key} already exists with different content; publish a new version instead."
                    )
                return existing
            raw = {
                "manifest": manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
                "enabled": bool(enabled),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": created_by,
            }
            entries[key] = raw
            self._write(entries)
            return self._entry(raw)

    def list(self) -> List[RegistryEntry]:
        with self._lock:
            entries = [self._entry(raw) for raw in self._read().values()]
        return sorted(entries, key=lambda item: (item.manifest.name, item.manifest.version))

    def get(self, name: str, version: str) -> RegistryEntry:
        with self._lock:
            raw = self._read().get(self._key(name, version))
        if raw is None:
            raise ManifestNotFound(f"Registered manifest {name}@{version} was not found.")
        return self._entry(raw)

    def resolve(self, name: str, version: str) -> RegistryEntry:
        entry = self.get(name, version)
        if not entry.enabled:
            raise ManifestDisabled(f"Registered manifest {name}@{version} is disabled by its kill switch.")
        return entry

    def set_enabled(self, name: str, version: str, enabled: bool) -> RegistryEntry:
        key = self._key(name, version)
        with self._lock:
            entries = self._read()
            if key not in entries:
                raise ManifestNotFound(f"Registered manifest {name}@{version} was not found.")
            entries[key]["enabled"] = bool(enabled)
            self._write(entries)
            return self._entry(entries[key])
