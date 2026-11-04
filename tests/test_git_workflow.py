"""
Tests for Keelway Local Git Governance, Semantic Commit Proposals, and PR Preparation (WP12).
"""
import subprocess
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem
from core.api import routes
from cli import cmd_git


@pytest.fixture
def git_repo_dir(tmp_path):
    repo = tmp_path / "git_test_repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test Repo\n")
    (repo / "app.py").write_text("def hello(): return 'world'\n")

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Tester", "-c", "user.email=test@keelway.local", "add", "-A"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "-c", "user.name=Tester", "-c", "user.email=test@keelway.local", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial commit"],
        cwd=repo,
        check=True,
    )
    return repo


@pytest.fixture
def git_client(git_repo_dir, monkeypatch):
    prev_fs = routes._workspace_fs
    monkeypatch.chdir(git_repo_dir)
    routes.set_workspace_fs(WorkspaceFilesystem(root_dir=str(git_repo_dir)))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        routes.set_workspace_fs(prev_fs)


def test_prepare_commit_proposal_clean_and_modified(git_repo_dir):
    ws = WorkspaceFilesystem(root_dir=str(git_repo_dir))
    
    # 1. Clean repo
    prop = ws.prepare_commit_proposal()
    assert prop["clean"] is True
    assert prop["files_count"] == 0

    # 2. Modify a file
    (git_repo_dir / "app.py").write_text("def hello(): return 'keelway'\n")
    prop_mod = ws.prepare_commit_proposal()
    assert prop_mod["clean"] is False
    assert prop_mod["files_count"] == 1
    assert "app.py" in prop_mod["proposed_message"]
    assert len(prop_mod["patch_hash"]) == 64


def test_create_local_commit_lifecycle(git_repo_dir):
    ws = WorkspaceFilesystem(root_dir=str(git_repo_dir))
    (git_repo_dir / "new_feature.py").write_text("# Feature code\n")
    
    res = ws.create_local_commit(
        message="feat(core): add new feature module",
        author_name="Alice Dev",
        author_email="alice@company.com",
    )
    assert res["status"] == "committed"
    assert len(res["commit_sha"]) == 40
    assert res["clean"] is True

    # Verify commit exists in git log
    log = subprocess.run(["git", "log", "-1", "--oneline"], cwd=git_repo_dir, capture_output=True, text=True, check=True)
    assert "feat(core): add new feature module" in log.stdout


def test_prepare_pr_proposal(git_repo_dir):
    ws = WorkspaceFilesystem(root_dir=str(git_repo_dir))
    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature/auth-v2"], cwd=git_repo_dir, check=True)
    (git_repo_dir / "auth.py").write_text("# Auth v2\n")
    ws.create_local_commit("feat(auth): implement token rotation")

    pr = ws.prepare_pr_proposal(base_branch="main")
    assert pr["head_branch"] == "feature/auth-v2"
    assert pr["base_branch"] == "main"
    assert pr["commits_count"] == 1
    assert "feat(auth): implement token rotation" in pr["title"]
    assert pr["ready_to_push"] is False  # Safeguard active


def test_api_git_proposal_and_commit(git_client, git_repo_dir):
    (git_repo_dir / "app.py").write_text("def hello(): return 'updated'\n")

    # 1. GET /v1/git/proposal
    p_res = git_client.get("/v1/git/proposal")
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["clean"] is False
    assert p_data["files_count"] == 1

    # 2. POST /v1/git/commit
    c_res = git_client.post("/v1/git/commit", json={"message": "fix(app): return updated greeting"})
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["status"] == "committed"
    assert len(c_data["commit_sha"]) == 40
    assert c_data["clean"] is True


def test_cli_git_commands(git_repo_dir, monkeypatch):
    monkeypatch.chdir(git_repo_dir)
    assert cmd_git("status") == 0
    assert cmd_git("diff") == 0
    assert cmd_git("propose") == 0

    (git_repo_dir / "note.txt").write_text("developer note\n")
    assert cmd_git("propose") == 0
    assert cmd_git("commit", msg="docs: add developer note") == 0
    assert cmd_git("pr", base="main") == 0
