"""
Keelway Dual-Mode Sovereign IDE: External Editor Sync Bridge
Enables bidirectional synchronization between Keelway Studio and external IDEs (VS Code, Cursor, VSCodium).
Enforces 150ms debouncing and Pessimistic Pause & Prompt on concurrent agent/human file mutations.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class ConcurrentEditConflict:
    """Represents a collision where an external editor modified a file leased by an autonomous agent."""
    file_path: str
    agent_id: str
    agent_content: str
    external_content: str
    base_content: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: Optional[str] = None


class ExternalEditorSyncBridge:
    """
    Manages synchronization between Keelway Studio workspace and external desktop editors.
    """

    SUPPORTED_EDITORS = {
        "vscode": "code",
        "cursor": "cursor",
        "vscodium": "codium",
        "sublime": "subl",
    }

    IGNORE_PATTERNS = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        ".pytest_cache",
        ".coverage",
        ".gstack",
    }

    def __init__(
        self,
        workspace_root: Path | str,
        debounce_ms: int = 150,
        on_conflict_callback: Optional[Callable[[ConcurrentEditConflict], None]] = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.debounce_ms = debounce_ms
        self.debounce_seconds = debounce_ms / 1000.0
        self.on_conflict_callback = on_conflict_callback

        self._active_leases: Dict[str, dict] = {}  # file_path -> {agent_id, base_content, agent_content}
        self._pending_conflicts: Dict[str, ConcurrentEditConflict] = {}
        self._last_event_times: Dict[str, float] = {}
        self._is_watching = True

    def validate_path_containment(self, relative_path: str = "") -> Path:
        """Strictly validates that the target path does not escape the workspace root boundary."""
        target = (self.workspace_root / relative_path).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError:
            raise ValueError(f"Path traversal detected: '{relative_path}' escapes workspace root.")
        return target

    def detect_available_editors(self) -> List[str]:
        """Returns the list of editor IDs whose CLI binaries are currently installed and in PATH."""
        available = []
        for editor_id, binary_name in self.SUPPORTED_EDITORS.items():
            if shutil.which(binary_name):
                available.append(editor_id)
        return available

    def open_in_editor(
        self,
        editor: str = "vscode",
        relative_path: str = "",
        runner: Optional[Callable[[List[str]], None]] = None,
    ) -> dict:
        """
        Launches the target file or workspace in an external editor.
        Uses `-r` flag to reuse existing windows in VS Code / Cursor / VSCodium.
        """
        editor_key = editor.lower().strip()
        binary_name = self.SUPPORTED_EDITORS.get(editor_key)
        if not binary_name:
            raise ValueError(
                f"Unsupported editor '{editor}'. Supported: {list(self.SUPPORTED_EDITORS.keys())}"
            )

        target_path = self.validate_path_containment(relative_path)

        resolved_binary = shutil.which(binary_name)
        if not resolved_binary and runner is None:
            raise FileNotFoundError(
                f"Executable '{binary_name}' for editor '{editor}' was not found in system PATH. "
                f"Ensure the '{binary_name}' shell command is installed."
            )

        # Build execution arguments
        if editor_key in ("vscode", "cursor", "vscodium"):
            cmd = [binary_name, "-r", str(target_path)]
        else:
            cmd = [binary_name, str(target_path)]

        if runner:
            runner(cmd)
        else:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        return {
            "status": "launched",
            "editor": editor_key,
            "binary": binary_name,
            "target": str(target_path),
        }

    def acquire_file_lease(
        self,
        file_path: str,
        agent_id: str,
        base_content: str = "",
        agent_content: str = "",
    ):
        """Registers that an autonomous agent is actively reading or formulating edits for a file."""
        norm_path = str(Path(file_path)).lstrip("/")
        self._active_leases[norm_path] = {
            "agent_id": agent_id,
            "base_content": base_content,
            "agent_content": agent_content,
            "acquired_at": time.time(),
        }

    def release_file_lease(self, file_path: str, agent_id: str):
        """Releases the agent's file lease once task completes or is cancelled."""
        norm_path = str(Path(file_path)).lstrip("/")
        if norm_path in self._active_leases and self._active_leases[norm_path]["agent_id"] == agent_id:
            del self._active_leases[norm_path]

    def is_debounced(self, file_path: str) -> bool:
        """
        Returns True if this event arrived within the 150ms debounce window of a previous event.
        Coalesces high-frequency autosave bursts into a single notification.
        """
        now = time.time()
        last_time = self._last_event_times.get(file_path, 0.0)
        self._last_event_times[file_path] = now
        return (now - last_time) < self.debounce_seconds

    def notify_external_change(
        self,
        file_path: str,
        external_content: str,
    ) -> Optional[ConcurrentEditConflict]:
        """
        Processes an external file modification event.
        If the file has an active agent lease, detects conflict, pauses agent, and triggers callback.
        """
        norm_path = str(Path(file_path)).lstrip("/")
        
        # Debounce check
        if self.is_debounced(norm_path):
            return None

        # Check for active lease conflict
        lease = self._active_leases.get(norm_path)
        if lease:
            # If external content differs from base content, we have an un-isolated concurrent edit!
            if external_content != lease["base_content"]:
                conflict = ConcurrentEditConflict(
                    file_path=norm_path,
                    agent_id=lease["agent_id"],
                    agent_content=lease.get("agent_content", ""),
                    external_content=external_content,
                    base_content=lease.get("base_content", ""),
                )
                self._pending_conflicts[norm_path] = conflict
                if self.on_conflict_callback:
                    self.on_conflict_callback(conflict)
                return conflict

        return None

    def resolve_conflict(self, file_path: str, resolution: str) -> dict:
        """
        Resolves a pending conflict per human instruction:
        - 'keep_agent': apply the agent's suggested content
        - 'keep_external': keep the externally saved content and discard agent proposal
        """
        norm_path = str(Path(file_path)).lstrip("/")
        conflict = self._pending_conflicts.get(norm_path)
        if not conflict:
            raise KeyError(f"No pending conflict found for '{file_path}'.")

        if resolution not in ("keep_agent", "keep_external"):
            raise ValueError("Resolution must be either 'keep_agent' or 'keep_external'.")

        target_file = self.workspace_root / norm_path
        if resolution == "keep_agent":
            target_file.write_text(conflict.agent_content, encoding="utf-8")
        # If keep_external, file already contains external_content on disk

        conflict.resolved = True
        conflict.resolution = resolution
        del self._pending_conflicts[norm_path]

        return {
            "status": "resolved",
            "file_path": norm_path,
            "resolution": resolution,
        }

    def get_status(self) -> dict:
        """Returns the current bridge status, active leases, detected editors, and pending conflicts."""
        return {
            "watching": self._is_watching,
            "workspace_root": str(self.workspace_root),
            "debounce_ms": self.debounce_ms,
            "active_leases_count": len(self._active_leases),
            "active_leases": list(self._active_leases.keys()),
            "pending_conflicts_count": len(self._pending_conflicts),
            "pending_conflicts": [
                {
                    "file_path": c.file_path,
                    "agent_id": c.agent_id,
                    "timestamp": c.timestamp,
                }
                for c in self._pending_conflicts.values()
            ],
            "detected_editors": self.detect_available_editors(),
        }
