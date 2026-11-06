"""
Automated Integration Test for Keelway Milestone M1 — Complete Vertical Slice (PRD-001).
Tests all 10 stages end-to-end on a real local repository:
1. Launch Keelway.
2. Open an existing local source repository.
3. See real files in the project explorer.
4. Ask AI agent to implement a small feature.
5. See agent's plan and files intended to change.
6. Review actual code diff.
7. Approve proposed edits and required commands.
8. Apply authorized changes.
9. Run project's test command.
10. View actual results, changed files, logs, and task history.
"""

import pytest
from pathlib import Path
from starlette.testclient import TestClient

from core.main import app
from core.m1_slice import MilestoneM1Runner, init_sample_repo, BUGGY_LINE, FIXED_LINE
from core.api.routes import set_workspace_fs
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.mark.asyncio
async def test_m1_vertical_slice_all_10_stages_runner(tmp_path: Path):
    """Executes the complete Milestone M1 vertical slice runner on an isolated real Git repo."""
    repo_dir = init_sample_repo(tmp_path / "acme_checkout_repo")
    runner = MilestoneM1Runner(workspace_path=repo_dir, verbose=False)
    results = await runner.execute_m1()

    # Stage 1 assertions
    assert results["stage_1_launch"]["status"] == "ok"

    # Stage 2 assertions
    assert results["stage_2_repo"]["is_git"] is True
    assert Path(results["stage_2_repo"]["root"]) == repo_dir

    # Stage 3 assertions
    assert "pricing.py" in results["stage_3_explorer"]["files"]
    assert "test_pricing.py" in results["stage_3_explorer"]["files"]

    # Stage 4 & 5 assertions
    assert results["stage_4_task"]["task_id"].startswith("m1_task_")
    assert len(results["stage_5_plan"]["steps"]) == 3
    assert results["stage_5_plan"]["step_1_result"] == "success"

    # Stage 6 & 7 assertions
    assert results["stage_6_diff_review"]["pending_tool"] == "edit_file"
    assert results["stage_7_approval"]["approved"] is True

    # Stage 8 assertions
    assert FIXED_LINE in (repo_dir / "pricing.py").read_text(encoding="utf-8")
    assert "pricing.py" in results["stage_8_applied"]["git_diff"]

    # Stage 9 assertions: the test command is refused until isolation is verified.
    assert results["stage_9_test"]["status"] == "unavailable"

    # Stage 10 assertions
    assert results["stage_10_results"]["all_steps_completed"] is False
    assert len(results["stage_10_results"]["tape_sha256"]) == 64
    assert "pricing.py" in results["stage_10_results"]["modified_files"]


def test_m1_vertical_slice_via_fastapi_rest_endpoints(tmp_path: Path):
    """Executes the 10 stages using the real FastAPI REST endpoints."""
    repo_dir = init_sample_repo(tmp_path / "api_acme_checkout")
    fs = WorkspaceFilesystem(str(repo_dir))
    set_workspace_fs(fs)

    with TestClient(app) as client:
        # 1. Launch / Health check
        res_health = client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] in ("ok", "degraded")

        # 2. Open workspace
        res_ws = client.post("/v1/workspace/open", json={"path": str(repo_dir)})
        assert res_ws.status_code == 200
        assert res_ws.json()["status"] == "opened"
        assert res_ws.json()["is_git"] is True

        # 3. Explore files
        res_tree = client.get("/v1/files/tree")
        assert res_tree.status_code == 200
        paths = [c["path"] for c in res_tree.json()["tree"]["children"]]
        assert "pricing.py" in paths

        res_content = client.get("/v1/files/content?path=pricing.py")
        assert res_content.status_code == 200
        assert BUGGY_LINE in res_content.json()["content"]

        # 4. Submit agent task
        import time
        task_id = f"test_api_m1_task_{time.time_ns()}"
        res_run = client.post(
            "/v1/agent/run",
            json={
                "task_id": task_id,
                "goal": "Fix discount calculation bug in pricing.py",
                "steps": [
                    "Inspect pricing.py file content",
                    "Apply correct discount calculation formula",
                    "Run unit tests to verify",
                ],
                "policy": "confirm_mutation",
            },
        )
        assert res_run.status_code == 200
        run_data = res_run.json()
        assert run_data["task_id"] == task_id

        # 5. See plan and execute step 1 (read_file)
        res_step1 = client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "read_file",
                "arguments": {"path": "pricing.py"},
                "step_id": "step_1",
            },
        )
        assert res_step1.status_code == 200
        assert res_step1.json()["step_result"]["status"] == "success"

        # 6. Propose edit (edit_file) -> pauses for approval
        res_step2 = client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "edit_file",
                "arguments": {
                    "path": "pricing.py",
                    "target": BUGGY_LINE,
                    "replacement": FIXED_LINE,
                },
                "step_id": "step_2",
            },
        )
        assert res_step2.status_code == 200
        assert res_step2.json()["step_result"]["status"] == "paused_for_approval"

        # 7. Approve the edit
        res_appr1 = client.post(
            f"/v1/agent/approve/{task_id}",
            json={"approved": True},
        )
        assert res_appr1.status_code == 200
        assert res_appr1.json()["approval_result"]["status"] == "success"

        # 8. Check that change was applied to disk and git diff reflects it
        assert FIXED_LINE in (repo_dir / "pricing.py").read_text(encoding="utf-8")
        res_diff = client.get("/v1/git/diff")
        assert res_diff.status_code == 200
        assert "pricing.py" in res_diff.json()["diff"]

        # 9. Step 3: Run project's test command
        res_step3 = client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "run_command",
                "arguments": {"command": "python3 -m unittest -q test_pricing.py"},
                "step_id": "step_3",
            },
        )
        assert res_step3.status_code == 200
        assert res_step3.json()["step_result"]["status"] == "paused_for_approval"

        # Approve command execution
        res_appr2 = client.post(
            f"/v1/agent/approve/{task_id}",
            json={"approved": True},
        )
        assert res_appr2.status_code == 200
        test_res = res_appr2.json()["approval_result"]
        assert test_res["status"] == "error"
        assert "unavailable" in test_res["error"].lower()

        # 10. View final task status, git status, and flight tape
        res_status = client.get(f"/v1/agent/status/{task_id}")
        assert res_status.status_code == 200
        plan = {step["id"]: step["status"] for step in res_status.json()["plan"]}
        assert plan["step_1"] == "completed"
        assert plan["step_2"] == "completed"
        assert plan["step_3"] == "failed"

        res_git = client.get("/v1/git/status")
        assert res_git.status_code == 200
        git_paths = [f["path"] for f in res_git.json().get("files", [])]
        assert "pricing.py" in git_paths

        res_tape = client.get(f"/v1/flight/tape/{task_id}")
        assert res_tape.status_code == 200
        tape = res_tape.json()
        assert len(tape["events"]) >= 5
        assert len(tape["tape_sha256"]) == 64
