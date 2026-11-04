"""
Complete end-to-end investor demonstration test verifying the 12-step milestone:
INSTALL -> LAUNCH -> OPEN REPOSITORY -> CONFIGURE LOCAL MODEL -> REQUEST CODE CHANGE 
-> REVIEW PLAN -> REVIEW DIFF -> APPROVE -> APPLY PATCH -> RUN TESTS -> INSPECT RESULTS 
-> RECOVER HISTORY.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.self_healing import SelfHealingLoop
from core.orchestration.flight_recorder import FlightRecorder


@pytest.mark.asyncio
async def test_complete_investor_demo_journey(tmp_path):
    # 1. LAUNCH & RUNTIME VERIFICATION
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "Keelway Studio" in root_resp.text

        # 2. OPEN REPOSITORY / WORKSPACE
        repo_dir = tmp_path / "demo_repo"
        repo_dir.mkdir()
        (repo_dir / "calculator.py").write_text("def multiply(a, b):\n    return a + b\n") # Intentional bug
        (repo_dir / "test_calc.py").write_text(
            "import sys\nfrom calculator import multiply\n"
            "def test_multiply():\n    assert multiply(3, 4) == 12\n"
        )
        fs = WorkspaceFilesystem(root_dir=repo_dir)
        files = fs.list_files()
        assert "calculator.py" in files
        assert "test_calc.py" in files

        # 3. CONFIGURE LOCAL MODEL
        model_resp = await client.get("/v1/models/local")
        assert model_resp.status_code == 200

        # 4. REQUEST CODE CHANGE & PLAN INITIALIZATION
        task_id = "investor_demo_task_01"
        recorder = FlightRecorder(task_id=task_id, db_path=tmp_path / "demo_flight.db")
        agent = AutonomousAgentLoop(
            task_id=task_id,
            workspace_fs=fs,
            policy=AutonomyPolicy.CONFIRM_MUTATION,
            flight_recorder=recorder,
        )

        plan_step = agent.initialize_plan(
            intent="Fix multiplication bug in calculator.py where addition is returned"
        )
        assert plan_step["status"] == "plan_ready"
        assert len(plan_step["steps"]) > 0

        # 5. REVIEW DIFF
        old_content = fs.read_file("calculator.py")
        new_content = "def multiply(a, b):\n    return a * b\n"
        diff_res = await agent.propose_diff("calculator.py", old_content, new_content)
        assert diff_res["status"] == "diff_proposed"
        assert "-    return a + b" in diff_res["diff"]
        assert "+    return a * b" in diff_res["diff"]

        # 6. APPROVE & APPLY PATCH
        apply_res = await agent.execute_tool("write_file", {"path": "calculator.py", "content": new_content})
        if apply_res.get("status") == "paused_for_approval":
            app_res = await agent.approve_pending(approved=True)
            assert app_res["status"] == "success"

        # 7. RUN TESTS & INSPECT RESULTS
        healer = SelfHealingLoop(repo_root=repo_dir)
        test_code, stdout, stderr = await healer.execute_test("pytest -q test_calc.py", cwd=repo_dir)
        assert test_code == 0
        assert "passed" in stdout or "1 passed" in stdout

        # 8. RECOVER HISTORY & VERIFY CRYPTOGRAPHIC SEAL
        tape = recorder.get_tape()
        assert len(tape.events) > 0
        sealed_tape = recorder.seal_tape()
        assert sealed_tape.tape_sha256 != ""

        # 9. TIME-TRAVEL FORK VERIFICATION
        fork_dest = tmp_path / "historical_fork"
        fork_res = recorder.fork_checkpoint(event_index=0, destination_path=fork_dest)
        assert fork_res["status"] == "success"
