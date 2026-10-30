"""
Kora AI Sovereign Workspace Filesystem & Live Git Engine.
Provides safe, sandboxed file operations, directory tree indexing, and git diff inspection.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional


DEFAULT_IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".DS_Store",
    ".kora/recordings",
}


class WorkspaceSecurityError(PermissionError):
    """Raised when an operation attempts directory traversal outside the workspace root."""
    pass


class WorkspaceFilesystem:
    """Safe, scoped filesystem operations for the local developer workspace."""

    def __init__(self, root_dir: Optional[str] = None):
        if root_dir:
            self.root = Path(root_dir).resolve()
        else:
            self.root = Path.cwd().resolve()

    def resolve_safe_path(self, relative_path: str) -> Path:
        """
        Resolves path and guarantees it resides within self.root.
        Prevents directory traversal attacks (e.g., ../../etc/passwd).
        """
        if not relative_path or relative_path == ".":
            return self.root

        # Normalize away redundant slashes
        clean_rel = relative_path.lstrip("/\\")
        candidate = (self.root / clean_rel).resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise WorkspaceSecurityError(
                f"Path traversal detected: '{relative_path}' resolves outside workspace root."
            )
        return candidate

    def get_file_tree(self, subpath: str = ".", max_depth: int = 4, max_files: int = 500) -> Dict[str, Any]:
        """
        Recursively scans workspace directory, respecting ignore lists.
        Returns a hierarchical JSON-ready tree structure.
        """
        target_dir = self.resolve_safe_path(subpath)
        if not target_dir.is_dir():
            raise ValueError(f"Target '{subpath}' is not a directory.")

        file_count = 0

        def _scan(current_path: Path, depth: int) -> Dict[str, Any]:
            nonlocal file_count
            rel_path = current_path.relative_to(self.root).as_posix()
            node: Dict[str, Any] = {
                "name": current_path.name if current_path != self.root else self.root.name,
                "path": rel_path if rel_path != "." else "",
                "type": "directory" if current_path.is_dir() else "file",
            }

            if current_path.is_file():
                try:
                    stat = current_path.stat()
                    node["size"] = stat.st_size
                    node["modified"] = int(stat.st_mtime)
                except OSError:
                    node["size"] = 0
                return node

            if depth > max_depth or file_count >= max_files:
                node["children"] = []
                return node

            children = []
            try:
                entries = sorted(list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
                for entry in entries:
                    if entry.name in DEFAULT_IGNORED_DIRS:
                        continue
                    if entry.name.startswith(".") and entry.name not in (".env.example", ".gitignore"):
                        continue
                    
                    file_count += 1
                    children.append(_scan(entry, depth + 1))
            except PermissionError:
                pass

            node["children"] = children
            return node

        return {
            "root": str(self.root),
            "name": self.root.name,
            "tree": _scan(target_dir, 0),
        }

    def read_file(self, relative_path: str, max_bytes: int = 5_000_000) -> Dict[str, Any]:
        """Reads file content safely with UTF-8 decoding."""
        target = self.resolve_safe_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if target.is_dir():
            raise IsADirectoryError(f"Target is a directory, not a file: {relative_path}")

        stat = target.stat()
        if stat.st_size > max_bytes:
            raise ValueError(f"File exceeds maximum allowed size ({max_bytes} bytes).")

        raw_bytes = target.read_bytes()
        try:
            content = raw_bytes.decode("utf-8")
            is_binary = False
        except UnicodeDecodeError:
            content = f"[Binary file, {stat.st_size} bytes]"
            is_binary = True

        return {
            "path": relative_path,
            "absolute_path": str(target),
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "is_binary": is_binary,
            "content": content,
        }

    def write_file(self, relative_path: str, content: str) -> Dict[str, Any]:
        """
        Safely writes file content using atomic rename to prevent corruption.
        Ensures parent directories exist.
        """
        target = self.resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp_target = target.with_suffix(f"{target.suffix}.kora_tmp_{os.getpid()}")
        try:
            tmp_target.write_text(content, encoding="utf-8")
            # Atomic replace
            os.replace(tmp_target, target)
        finally:
            if tmp_target.exists():
                try:
                    tmp_target.unlink()
                except OSError:
                    pass

        stat = target.stat()
        return {
            "status": "saved",
            "path": relative_path,
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
        }

    def get_git_status(self) -> Dict[str, Any]:
        """Inspects working directory Git status."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return {"is_git": False, "branch": "", "clean": True, "files": []}

            lines = res.stdout.strip().split("\n")
            branch_line = lines[0] if lines else "## unknown"
            branch = branch_line.replace("## ", "").split("...")[0].strip()

            files = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                status_code = line[:2].strip()
                file_path = line[3:].strip()
                files.append({"status": status_code, "path": file_path})

            return {
                "is_git": True,
                "branch": branch,
                "clean": len(files) == 0,
                "files": files,
            }
        except Exception:
            return {"is_git": False, "branch": "", "clean": True, "files": []}

    def get_git_diff(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves unified git diff for workspace or specific file."""
        cmd = ["git", "diff", "HEAD"]
        if path:
            safe_target = self.resolve_safe_path(path)
            cmd.append(str(safe_target.relative_to(self.root)))

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=8,
            )
            return {
                "path": path or "workspace",
                "diff": res.stdout if res.returncode == 0 else "",
            }
        except Exception as e:
            return {"path": path or "workspace", "diff": "", "error": str(e)}
