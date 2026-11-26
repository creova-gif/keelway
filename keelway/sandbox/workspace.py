"""Keelway Sandboxed Workspace and Worktree Manager.
Implements FR-01 (immutable base SHA checkout) and FR-03 (isolated sandboxed execution).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple


class WorkspaceError(Exception):
    pass


class WorkspaceManager:
    """Manages isolated local worktrees and safe sandboxed execution."""

    def __init__(self, repo_path: str, base_commit_sha: Optional[str] = None):
        self.repo_path = os.path.abspath(repo_path)
        if not os.path.isdir(self.repo_path):
            raise WorkspaceError(f"Repository directory does not exist: {self.repo_path}")

        self.git_root = self._get_git_root()
        self.base_commit_sha = base_commit_sha or self._get_head_commit_sha()
        self.worktree_path: Optional[str] = None
        self._is_worktree_created = False

    def _get_git_root(self) -> str:
        """Finds the enclosing git repository root for self.repo_path."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except subprocess.SubprocessError:
            return self.repo_path

    def _get_head_commit_sha(self) -> str:
        """Resolves current HEAD commit SHA."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except subprocess.SubprocessError as e:
            raise WorkspaceError(f"Failed to resolve HEAD commit: {e}") from e

    def create_worktree(self, run_id: str) -> str:
        """Creates an isolated git workspace attached to the immutable base commit.
        
        Uses git clone --shared to guarantee parent repository isolation and avoid
        modifying the host's .git metadata.
        """
        temp_dir = tempfile.mkdtemp(prefix=f"keelway_run_{run_id[:8]}_")

        try:
            # 1. First attempt: lightweight shared clone (completely isolated .git)
            res = subprocess.run(
                ["git", "clone", "--shared", "--no-checkout", self.git_root, temp_dir],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                # Checkout exact immutable base commit SHA
                subprocess.run(
                    ["git", "checkout", "--detach", self.base_commit_sha],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.worktree_path = temp_dir
                self._is_worktree_created = True
                return self.worktree_path

            # 2. Fallback: standard git worktree add
            subprocess.run(
                ["git", "worktree", "add", "--detach", temp_dir, self.base_commit_sha],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self.worktree_path = temp_dir
            self._is_worktree_created = True
            return self.worktree_path

        except subprocess.SubprocessError as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise WorkspaceError(f"Failed to create isolated workspace at {self.base_commit_sha}: {e}") from e

    def write_file(self, relative_path: str, content: str) -> None:
        """Writes a file within the isolated worktree directory."""
        if not self.worktree_path:
            raise WorkspaceError("Worktree has not been initialized.")

        # Prevent directory traversal attacks
        target_path = os.path.abspath(os.path.join(self.worktree_path, relative_path))
        if not target_path.startswith(self.worktree_path):
            raise WorkspaceError(f"Path traversal detected: {relative_path}")

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

    def get_diff(self) -> str:
        """Gets unified git diff of all modifications relative to base commit."""
        if not self.worktree_path:
            raise WorkspaceError("Worktree has not been initialized.")

        try:
            # Add untracked files into staging intent to include them in diff
            subprocess.run(
                ["git", "add", "-N", "."],
                cwd=self.worktree_path,
                capture_output=True,
                check=False,
            )
            res = subprocess.run(
                ["git", "diff", self.base_commit_sha],
                cwd=self.worktree_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout
        except subprocess.SubprocessError as e:
            raise WorkspaceError(f"Failed to generate git diff: {e}") from e

    def get_patch_hash(self) -> str:
        """Computes SHA-256 hash of the unified git diff."""
        diff_text = self.get_diff()
        return hashlib.sha256(diff_text.encode("utf-8")).hexdigest()

    def run_command(
        self,
        command: List[str],
        timeout_seconds: int = 60,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """Executes a bounded command inside the worktree sandbox."""
        if not self.worktree_path:
            raise WorkspaceError("Worktree has not been initialized.")

        # Clean environment to prevent secret leakage from host
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.worktree_path,
            "TMPDIR": "/tmp",
            "PYTHONPATH": self.worktree_path,
        }
        if env_vars:
            safe_env.update(env_vars)

        try:
            proc = subprocess.run(
                command,
                cwd=self.worktree_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=safe_env,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout_seconds}s"
        except Exception as e:
            return 1, "", str(e)

    def cleanup(self) -> None:
        """Removes the worktree and cleans up git worktree metadata."""
        if self._is_worktree_created and self.worktree_path:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", self.worktree_path],
                    cwd=self.repo_path,
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass
            if os.path.exists(self.worktree_path):
                shutil.rmtree(self.worktree_path, ignore_errors=True)
            self._is_worktree_created = False
            self.worktree_path = None
