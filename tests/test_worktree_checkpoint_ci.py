import json, os, subprocess
import pytest
from pathlib import Path
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "init"],
                   cwd=tmp_path, check=True, capture_output=True)
    return WorkspaceFilesystem(root_dir=str(tmp_path))


def test_worktree_lifecycle(repo):
    res = repo.create_worktree("task-1")
    assert res["status"] == "created" and res["branch"] == "keelway/task-task-1"
    assert "worktrees/task-1" in res["path"]
    listed = repo.list_worktrees()["worktrees"]
    assert any(t["agent_isolated"] for t in listed)
    assert repo.remove_worktree("task-1")["status"] == "removed"
    with pytest.raises(ValueError):
        repo.remove_worktree("task-1")


def test_worktree_rejects_non_repo(tmp_path):
    fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    with pytest.raises(ValueError, match="not a Git repository"):
        fs.create_worktree("t")


def test_worktree_id_sanitized(repo):
    res = repo.create_worktree("task/../escape;rm")
    assert ".." not in res["task_id"] and ";" not in res["task_id"]


def test_checkpoint_untracked_restore(repo, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("one")
    cp = repo.create_checkpoint(label="cp1")
    assert cp["status"] == "created" and cp["untracked_captured"]
    f.unlink()
    res = repo.restore_checkpoint(cp["id"])
    assert res["status"] == "restored" and f.read_text() == "one"


def test_checkpoint_tracked_restore(repo, tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("one")
    subprocess.run(["git", "add", "t.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "add"],
                   cwd=tmp_path, check=True, capture_output=True)
    f.write_text("two")
    cp = repo.create_checkpoint()
    assert cp["stash_oid"]
    f.write_text("three")
    repo.restore_checkpoint(cp["id"])
    assert f.read_text() == "two"


def test_checkpoint_clean_tree(repo):
    cp = repo.create_checkpoint()
    assert cp["stash_oid"] is None
    assert repo.restore_checkpoint(cp["id"])["status"] == "restored"


def test_checkpoint_unknown(repo):
    with pytest.raises(ValueError, match="not found"):
        repo.restore_checkpoint("nope")


def test_ci_status_shape(repo):
    res = repo.get_ci_status()
    assert "available" in res
    if res["available"]:
        assert isinstance(res["runs"], list)
    else:
        assert res["reason"]
