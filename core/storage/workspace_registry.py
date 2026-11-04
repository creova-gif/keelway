"""
Keelway Multi-Workspace Manager and Enterprise Workspace Registry.
Enables developers and AI agent swarms to register, inspect, and switch between
multiple sovereign repositories, monorepo packages, or microservices with strict
path containment and security verification.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.storage.workspace_fs import WorkspaceFilesystem, WorkspaceSecurityError
from core.orchestration.project_adapter import ProjectAdapter


FORBIDDEN_WORKSPACE_EXACT = {
    "/",
    "/etc",
    "/private/etc",
    "/var",
    "/private/var",
    "/usr",
    "/bin",
    "/sbin",
    "/root",
    "/System",
    "/Library",
    "/Applications",
}

FORBIDDEN_PREFIXES = {
    "/etc/",
    "/private/etc/",
    "/root/",
    "/System/",
    str(Path("~/.ssh").expanduser().resolve()),
    str(Path("~/.aws").expanduser().resolve()),
    str(Path("~/.gnupg").expanduser().resolve()),
}


@dataclass
class WorkspaceEntry:
    """Represents a registered enterprise repository or local development workspace."""
    id: str
    name: str
    path: str
    registered_at: str
    last_accessed_at: str
    git_branch: Optional[str] = None
    detected_framework: str = "unknown"
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "registered_at": self.registered_at,
            "last_accessed_at": self.last_accessed_at,
            "git_branch": self.git_branch,
            "detected_framework": self.detected_framework,
            "is_active": self.is_active,
        }


class WorkspaceRegistry:
    """Enterprise registry of developer workspaces and repositories."""

    def __init__(self, registry_file: Optional[Path] = None, auto_register_cwd: bool = True):
        self.registry_file = registry_file or (Path.home() / ".keelway" / "workspaces.json")
        self.workspaces: Dict[str, WorkspaceEntry] = {}
        self.active_workspace_id: Optional[str] = None
        self._load()

        if auto_register_cwd and not self.workspaces:
            try:
                self.register(str(Path.cwd()), name=Path.cwd().name, make_active=True)
            except Exception:
                pass

    def _load(self) -> None:
        if not self.registry_file.is_file():
            return
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            for item in data.get("workspaces", []):
                entry = WorkspaceEntry(
                    id=item["id"],
                    name=item["name"],
                    path=item["path"],
                    registered_at=item["registered_at"],
                    last_accessed_at=item.get("last_accessed_at", item["registered_at"]),
                    git_branch=item.get("git_branch"),
                    detected_framework=item.get("detected_framework", "unknown"),
                    is_active=item.get("is_active", False),
                )
                self.workspaces[entry.id] = entry
                if entry.is_active:
                    self.active_workspace_id = entry.id
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": "1.0",
                "active_workspace_id": self.active_workspace_id,
                "workspaces": [w.to_dict() for w in self.workspaces.values()],
            }
            self.registry_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _validate_path(self, raw_path: str) -> Path:
        raw_p = Path(raw_path).expanduser()
        resolved = raw_p.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Workspace path '{resolved}' does not exist.")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Workspace path '{resolved}' is not a directory.")

        resolved_str = str(resolved)
        raw_str = str(raw_p.absolute())

        if resolved_str in FORBIDDEN_WORKSPACE_EXACT or raw_str in FORBIDDEN_WORKSPACE_EXACT:
            raise WorkspaceSecurityError(f"Registering system-critical directory '{resolved}' as workspace is prohibited.")

        for prefix in FORBIDDEN_PREFIXES:
            if (
                resolved_str == prefix
                or resolved_str.startswith(prefix if prefix.endswith("/") else prefix + "/")
                or raw_str == prefix
                or raw_str.startswith(prefix if prefix.endswith("/") else prefix + "/")
            ):
                raise WorkspaceSecurityError(f"Registering system-critical directory '{resolved}' as workspace is prohibited.")

        return resolved

    def _detect_git_branch(self, path: Path) -> Optional[str]:
        git_head = path / ".git" / "HEAD"
        if git_head.is_file():
            try:
                line = git_head.read_text(encoding="utf-8").strip()
                if line.startswith("ref: refs/heads/"):
                    return line.replace("ref: refs/heads/", "")
                return line[:8]
            except Exception:
                pass
        return None

    def _detect_framework(self, path: Path) -> str:
        try:
            meta = ProjectAdapter.inspect(path)
            return meta.project_type
        except Exception:
            return "generic"

    def register(
        self,
        raw_path: str,
        name: Optional[str] = None,
        make_active: bool = False,
    ) -> WorkspaceEntry:
        """Registers a directory as a recognized enterprise workspace."""
        path = self._validate_path(raw_path)
        path_str = str(path)

        # Check if already registered
        for existing in self.workspaces.values():
            if existing.path == path_str:
                if make_active:
                    self.activate(existing.id)
                return existing

        ws_id = f"ws_{uuid.uuid4().hex[:8]}"
        ws_name = name or path.name or "workspace"
        now = datetime.now(timezone.utc).isoformat()
        branch = self._detect_git_branch(path)
        framework = self._detect_framework(path)

        entry = WorkspaceEntry(
            id=ws_id,
            name=ws_name,
            path=path_str,
            registered_at=now,
            last_accessed_at=now,
            git_branch=branch,
            detected_framework=framework,
            is_active=make_active or not self.workspaces,
        )

        if entry.is_active:
            for w in self.workspaces.values():
                w.is_active = False
            self.active_workspace_id = ws_id

        self.workspaces[ws_id] = entry
        self._save()
        return entry

    def activate(self, workspace_id_or_path: str) -> WorkspaceEntry:
        """Activates a workspace by id or path and updates last accessed timestamp."""
        target: Optional[WorkspaceEntry] = None
        if workspace_id_or_path in self.workspaces:
            target = self.workspaces[workspace_id_or_path]
        else:
            resolved_str = str(Path(workspace_id_or_path).expanduser().resolve())
            for w in self.workspaces.values():
                if w.path == resolved_str:
                    target = w
                    break

        if not target:
            raise KeyError(f"Workspace '{workspace_id_or_path}' is not registered.")

        for w in self.workspaces.values():
            w.is_active = (w.id == target.id)

        target.is_active = True
        target.last_accessed_at = datetime.now(timezone.utc).isoformat()
        # Refresh branch & framework
        p = Path(target.path)
        if p.exists():
            target.git_branch = self._detect_git_branch(p)
            target.detected_framework = self._detect_framework(p)

        self.active_workspace_id = target.id
        self._save()
        return target

    def get_active(self) -> Optional[WorkspaceEntry]:
        """Returns the currently active workspace entry."""
        if self.active_workspace_id and self.active_workspace_id in self.workspaces:
            return self.workspaces[self.active_workspace_id]
        active = [w for w in self.workspaces.values() if w.is_active]
        return active[0] if active else None

    def unregister(self, workspace_id: str) -> bool:
        """Removes a workspace registration."""
        if workspace_id not in self.workspaces:
            return False

        was_active = self.workspaces[workspace_id].is_active
        del self.workspaces[workspace_id]

        if was_active:
            if self.workspaces:
                new_active = next(iter(self.workspaces.values()))
                new_active.is_active = True
                self.active_workspace_id = new_active.id
            else:
                self.active_workspace_id = None

        self._save()
        return True

    def list_all(self) -> List[WorkspaceEntry]:
        """Returns all registered workspaces sorted by last accessed descending."""
        entries = list(self.workspaces.values())
        entries.sort(key=lambda w: w.last_accessed_at, reverse=True)
        return entries


# Singleton instance for process-wide workspace resolution
_SHARED_REGISTRY = WorkspaceRegistry()


def get_shared_workspace_registry() -> WorkspaceRegistry:
    """Returns the process-wide WorkspaceRegistry."""
    return _SHARED_REGISTRY
