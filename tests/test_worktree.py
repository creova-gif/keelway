"""
Tests for Keelway Ephemeral Git Worktree Manager (core/orchestration/worktree.py).
Ensures safe, isolated execution for parallel AI agent tasks.
"""

import subprocess
import pytest
from core.orchestration.worktree import EphemeralWorktreeManager


@pytest.mark.asyncio
async def test_worktree_creation_and_command_execution(tmp_path):
    # Initialize a mock git repository in tmp_path
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("def hello(): return 'v1'\n")
    (repo_dir / "test_app.py").write_text("from app import hello\ndef test_hello(): assert hello() == 'v1'\n")

    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@keelway.dev"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Keelway Tester"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo_dir), check=True)

    mgr = EphemeralWorktreeManager(repo_root=repo_dir)
    session = await mgr.create_worktree("task_worktree_01")

    assert session.is_active is True
    assert session.worktree_dir.exists()
    assert (session.worktree_dir / "app.py").exists()

    # Modify file inside isolated worktree
    (session.worktree_dir / "app.py").write_text("def hello(): return 'v2_isolated'\n")

    # Verify primary repo file remains unaffected
    assert (repo_dir / "app.py").read_text() == "def hello(): return 'v1'\n"

    # Run command inside worktree session
    code, stdout, stderr = await session.run_command("python3 -c \"import app; print(app.hello())\"")
    assert code == 0
    assert "v2_isolated" in stdout

    # Cleanup worktree session
    cleaned = await mgr.remove_worktree(session, delete_branch=True)
    assert cleaned is True
    assert session.is_active is False
    assert not session.worktree_dir.exists()


@pytest.mark.asyncio
async def test_worktree_fallback_for_non_git_directories(tmp_path):
    plain_dir = tmp_path / "plain_dir"
    plain_dir.mkdir()
    (plain_dir / "script.py").write_text("print('hello fallback')\n")

    mgr = EphemeralWorktreeManager(repo_root=plain_dir)
    session = await mgr.create_worktree("task_fallback_02")

    assert session.is_active is True
    assert session.worktree_dir.exists()
    assert (session.worktree_dir / "script.py").exists()

    # Run command in isolated copy
    code, stdout, _ = await session.run_command("python3 script.py")
    assert code == 0
    assert "hello fallback" in stdout

    # Cleanup
    cleaned = await mgr.cleanup_worktree(session)
    assert cleaned is True
    assert not session.worktree_dir.exists()
