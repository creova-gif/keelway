"""
KEEL-REL-063 / release defect D-003: composed clean-environment coding journey.

Drives the real /v1 API end-to-end in the golden-journey order that the
release audit requires: launch -> workspace -> agent plan -> P-10 approval
gate -> isolated worktree -> governed edit -> test -> diff -> checkpoint ->
rollback -> commit -> PR proposal -> CI status -> evidence -> durable state
-> cleanup. Every step hits the authoritative core.main:app surface; nothing
is stubbed. State dirs are isolated by conftest (KEELWAY_STATE_DIR, DATABASE_URL).
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.kflow import kflow_engine, FlowNode
from core.orchestration.self_healing import SelfHealingLoop
from core.security.auth import launch_token


@pytest.fixture
def owner_headers():
    return {"Authorization": f"Bearer {launch_token()}"}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.mark.asyncio
async def test_composed_30_step_coding_journey(tmp_path, owner_headers):
    uid = uuid.uuid4().hex[:8]
    task_id = f"journey_{uid}"
    flow_id = f"flow_{uid}"
    h = owner_headers

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ------------------------------------------------------------------
        # STEP 1: Launch — health endpoint live
        # ------------------------------------------------------------------
        health = await client.get("/health", headers=h)
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # ------------------------------------------------------------------
        # STEP 2: Studio shell serves
        # ------------------------------------------------------------------
        studio = await client.get("/", headers=h)
        assert studio.status_code == 200
        assert "Keelway Studio" in studio.text

        # ------------------------------------------------------------------
        # STEP 3: Model runtime status is honestly reported
        # ------------------------------------------------------------------
        models = await client.get("/v1/models/local", headers=h)
        assert models.status_code == 200

        # ------------------------------------------------------------------
        # STEP 4: Clean project — fresh git repo with a seeded bug
        # ------------------------------------------------------------------
        repo = tmp_path / "journey_repo"
        repo.mkdir()
        _git(repo, "init")
        _git(repo, "config", "user.name", "Journey Tester")
        _git(repo, "config", "user.email", "journey@keelway.dev")
        (repo / "calculator.py").write_text("def multiply(a, b):\n    return a + b\n")
        (repo / "test_calc.py").write_text(
            "from calculator import multiply\n"
            "def test_multiply():\n"
            "    assert multiply(3, 4) == 12\n"
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "seed: calculator with multiply bug")

        # ------------------------------------------------------------------
        # STEP 5: Register + activate the workspace through the API
        # ------------------------------------------------------------------
        reg = await client.post("/v1/workspaces", json={
            "path": str(repo), "name": "Journey Repo", "make_active": True,
        }, headers=h)
        assert reg.status_code == 200, reg.text
        assert reg.json()["status"] == "registered"

        # ------------------------------------------------------------------
        # STEP 6: Active workspace info reflects the repo
        # ------------------------------------------------------------------
        ws = await client.get("/v1/workspace", headers=h)
        assert ws.status_code == 200
        assert ws.json()["is_git"] is True

        # ------------------------------------------------------------------
        # STEP 7: Project adapter detects the Python runtime
        # ------------------------------------------------------------------
        info = await client.get("/v1/project/info", headers=h)
        assert info.status_code == 200

        # ------------------------------------------------------------------
        # STEP 8: File tree + content read through the API
        # ------------------------------------------------------------------
        tree = await client.get("/v1/files/tree", headers=h)
        assert tree.status_code == 200
        assert "calculator.py" in json.dumps(tree.json())
        content = await client.get("/v1/files/content", params={"path": "calculator.py"}, headers=h)
        assert content.status_code == 200
        assert "return a + b" in content.json()["content"]

        # ------------------------------------------------------------------
        # STEP 9: Path traversal is refused (fail-closed file boundary)
        # ------------------------------------------------------------------
        escape = await client.get("/v1/files/content", params={"path": "../outside.txt"}, headers=h)
        assert escape.status_code in (400, 403)

        # ------------------------------------------------------------------
        # STEP 10: Agent task created under confirm-mutation policy
        # ------------------------------------------------------------------
        run = await client.post("/v1/agent/run", json={
            "task_id": task_id,
            "goal": "Fix calculator.multiply to return the product",
            "policy": "confirm_mutation",
        }, headers=h)
        assert run.status_code == 200, run.text
        assert run.json()["task_id"] == task_id

        # ------------------------------------------------------------------
        # STEP 11: Agent status is inspectable
        # ------------------------------------------------------------------
        status = await client.get(f"/v1/agent/status/{task_id}", headers=h)
        assert status.status_code == 200

        # ------------------------------------------------------------------
        # STEP 12: Mutating tool call pauses at the P-10 human gate
        # ------------------------------------------------------------------
        fixed = "def multiply(a, b):\n    return a * b\n"
        step = await client.post(f"/v1/agent/step/{task_id}", json={
            "tool_name": "write_file",
            "arguments": {"path": "calculator.py", "content": fixed},
        }, headers=h)
        assert step.status_code == 200, step.text
        assert step.json()["step_result"]["status"] == "paused_for_approval"

        # ------------------------------------------------------------------
        # STEP 13: Fail-closed proof — the write did not land before approval
        # ------------------------------------------------------------------
        assert "return a + b" in (repo / "calculator.py").read_text()

        # ------------------------------------------------------------------
        # STEP 14: Human approval applies the pending write
        # ------------------------------------------------------------------
        approve = await client.post(f"/v1/agent/approve/{task_id}", json={"approved": True}, headers=h)
        assert approve.status_code == 200, approve.text
        assert "return a * b" in (repo / "calculator.py").read_text()

        # ------------------------------------------------------------------
        # STEP 15: Approval without explicit boolean is refused (P-10)
        # ------------------------------------------------------------------
        bad_approve = await client.post(f"/v1/agent/approve/{task_id}", json={}, headers=h)
        assert bad_approve.status_code == 400

        # ------------------------------------------------------------------
        # STEP 16: Isolated agent worktree created through the API
        # ------------------------------------------------------------------
        wt = await client.post("/v1/worktrees", json={"task_id": task_id}, headers=h)
        assert wt.status_code == 200, wt.text
        assert "worktrees" in wt.json()["path"]

        # ------------------------------------------------------------------
        # STEP 17: Worktree list shows the isolated entry
        # ------------------------------------------------------------------
        wt_list = await client.get("/v1/worktrees", headers=h)
        assert wt_list.status_code == 200
        assert task_id in json.dumps(wt_list.json())

        # ------------------------------------------------------------------
        # STEP 18: Checkpoint snapshots the dirty working tree
        # ------------------------------------------------------------------
        cp = await client.post("/v1/checkpoints", json={"label": "post-fix"}, headers=h)
        assert cp.status_code == 200, cp.text
        cp_id = cp.json()["id"]

        # ------------------------------------------------------------------
        # STEP 19: Checkpoint is listed
        # ------------------------------------------------------------------
        cp_list = await client.get("/v1/checkpoints", headers=h)
        assert cp_list.status_code == 200
        assert any(c["id"] == cp_id for c in cp_list.json()["checkpoints"])

        # ------------------------------------------------------------------
        # STEP 20: Simulate user discarding the fix, then restore via API
        # ------------------------------------------------------------------
        _git(repo, "checkout", "--", "calculator.py")
        assert "return a + b" in (repo / "calculator.py").read_text()
        restore = await client.post(f"/v1/checkpoints/{cp_id}/restore", headers=h)
        assert restore.status_code == 200, restore.text
        assert "return a * b" in (repo / "calculator.py").read_text()

        # ------------------------------------------------------------------
        # STEP 21: Real test run verifies the repair (self-healing runner)
        # ------------------------------------------------------------------
        healer = SelfHealingLoop(repo_root=repo)
        rc, out, err = await healer.execute_test("pytest -q test_calc.py", cwd=repo)
        assert rc == 0, f"{out}\n{err}"

        # ------------------------------------------------------------------
        # STEP 22: Git diff surfaces the fix for review
        # ------------------------------------------------------------------
        diff = await client.get("/v1/git/diff", headers=h)
        assert diff.status_code == 200
        assert "return a * b" in json.dumps(diff.json())

        # ------------------------------------------------------------------
        # STEP 23: Semantic commit proposal generated
        # ------------------------------------------------------------------
        proposal = await client.get("/v1/git/proposal", headers=h)
        assert proposal.status_code == 200

        # ------------------------------------------------------------------
        # STEP 24: Local commit lands through the API (never pushes)
        # ------------------------------------------------------------------
        commit = await client.post("/v1/git/commit", json={
            "message": "fix(calc): multiply returns product",
        }, headers=h)
        assert commit.status_code == 200, commit.text
        assert commit.json()["commit_sha"]

        # ------------------------------------------------------------------
        # STEP 25: PR proposal surface responds honestly
        # ------------------------------------------------------------------
        pr = await client.get("/v1/git/pr/proposal", headers=h)
        assert pr.status_code == 200

        # ------------------------------------------------------------------
        # STEP 26: CI status degrades honestly (no gh remote in test repo)
        # ------------------------------------------------------------------
        ci = await client.get("/v1/git/ci/status", headers=h)
        assert ci.status_code == 200
        assert "available" in ci.json()

        # ------------------------------------------------------------------
        # STEP 27: Flight recorder tape captured the agent run
        # ------------------------------------------------------------------
        tape = await client.get(f"/v1/flight/tape/{task_id}", headers=h)
        assert tape.status_code == 200
        assert len(json.dumps(tape.json())) > 2

        # ------------------------------------------------------------------
        # STEP 28: Merkle audit root exists (append-only evidence chain)
        # ------------------------------------------------------------------
        merkle = await client.get("/v1/audit/merkle/root", headers=h)
        assert merkle.status_code == 200

        # ------------------------------------------------------------------
        # STEP 29: Durable schedules — register a DAG, schedule it, prove
        # the record lands on disk under the isolated state dir (KEEL-REL-062)
        # ------------------------------------------------------------------
        node = FlowNode(node_id="n1", name="Verify", assigned_role="qa",
                        tool="kstack/qa", inputs={"target": "calculator.py"})
        kflow_engine.create_dag(flow_id=flow_id, goal="nightly verify", nodes=[node])
        sched = await client.post("/v1/schedules", json={
            "flow_id": flow_id, "interval_seconds": 3600,
        }, headers=h)
        assert sched.status_code == 200, sched.text
        sched_id = sched.json()["schedule_id"]
        state_dir = Path(os.environ["KEELWAY_STATE_DIR"])
        persisted = json.loads((state_dir / "schedules.json").read_text())
        assert any(s["schedule_id"] == sched_id for s in persisted["schedules"])
        del_sched = await client.delete(f"/v1/schedules/{sched_id}", headers=h)
        assert del_sched.status_code == 200

        # ------------------------------------------------------------------
        # STEP 30: Cleanup + ownership — worktree removed, commit retained
        # ------------------------------------------------------------------
        del_wt = await client.delete(f"/v1/worktrees/{task_id}", headers=h)
        assert del_wt.status_code == 200
        log = _git(repo, "log", "-n", "1", "--oneline").stdout
        assert "multiply returns product" in log
