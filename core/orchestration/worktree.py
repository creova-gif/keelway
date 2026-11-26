"""
Keelway Ephemeral Git Worktree Manager.
Enables concurrent, non-colliding execution of parallel AI coding agents
by attaching isolated disposable worktrees to the local repository.
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple


class WorktreeSession:
    """Represents an active isolated Git worktree for an agent task."""

    def __init__(self, task_id: str, repo_root: Path, worktree_dir: Path, branch_name: str):
        self.task_id = task_id
        self.repo_root = repo_root
        self.worktree_dir = worktree_dir
        self.branch_name = branch_name
        self.is_active = True

    async def run_command(self, cmd: str) -> Tuple[int, str, str]:
        """Runs a shell command isolated inside the agent's dedicated worktree directory."""
        import sys
        if cmd.startswith("python3 ") or cmd.startswith("python "):
            parts = cmd.split(" ", 1)
            cmd = f"{sys.executable} {parts[1]}"

        sub_env = dict(os.environ)
        sub_env["PYTHONPATH"] = f"{self.worktree_dir}:{sub_env.get('PYTHONPATH', '')}"

        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(self.worktree_dir),
            env=sub_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )


class EphemeralWorktreeManager:
    """Provisions and cleans up Git worktrees for safe, parallel agent task execution."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()
        self.worktrees_root = self.repo_root / ".keelway" / "worktrees"

    async def create_worktree(self, task_id: str) -> WorktreeSession:
        """Creates an ephemeral worktree directory and dedicated git branch."""
        self.worktrees_root.mkdir(parents=True, exist_ok=True)
        worktree_path = self.worktrees_root / f"agent_{task_id}"
        branch_name = f"keelway/agent/{task_id}"

        # Clean existing directory if leftover
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)

        # Run git worktree add
        cmd = f"git worktree add -b {branch_name} {worktree_path} HEAD"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            # Fallback for mock/test environments without active git branches
            worktree_path.mkdir(parents=True, exist_ok=True)
            for item in self.repo_root.iterdir():
                if item.name == ".keelway":
                    continue
                dst = worktree_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                elif item.is_file():
                    shutil.copy2(item, dst)

        return WorktreeSession(
            task_id=task_id,
            repo_root=self.repo_root,
            worktree_dir=worktree_path,
            branch_name=branch_name,
        )

    async def cleanup_worktree(self, session: WorktreeSession, delete_branch: bool = True) -> bool:
        """Alias for remove_worktree."""
        return await self.remove_worktree(session, delete_branch=delete_branch)

    async def remove_worktree(self, session: WorktreeSession, delete_branch: bool = True) -> bool:
        """Safely detaches and prunes the worktree directory and branch."""
        if not session.is_active:
            return True

        # Remove git worktree
        cmd = f"git worktree remove --force {session.worktree_dir}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if session.worktree_dir.exists():
            shutil.rmtree(session.worktree_dir, ignore_errors=True)

        if delete_branch:
            branch_cmd = f"git branch -D {session.branch_name}"
            del_proc = await asyncio.create_subprocess_shell(
                branch_cmd,
                cwd=str(self.repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await del_proc.communicate()

        session.is_active = False
        return True
