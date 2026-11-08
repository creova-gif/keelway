"""
Complete end-to-end developer journey test verifying Section 5 of the Master Directive:
"The beta must deliver one high-quality developer workflow:
1. Install and launch Keelway.
2. Open a local project or Git repository.
3. Select a supported local model.
4. Inspect and ask questions about the repository.
5. Create a coding task.
6. Review the proposed plan.
7. Approve permitted actions.
8. Execute the agent in a verified sandbox.
9. Inspect changed files and diffs.
10. Run project tests.
11. Review the final task summary.
12. Accept or reject changes."
"""
import subprocess
import sys
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.self_healing import SelfHealingLoop
from core.orchestration.flight_recorder import FlightRecorder
from core.system.doctor import SystemDoctor
from core.agents.sandbox import verified_command_runner, CommandExecutionUnavailable


@pytest.mark.asyncio
async def test_complete_investor_demo_journey(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent

    # =========================================================================
    # STAGE 1: INSTALL AND LAUNCH KEELWAY
    # =========================================================================
    installer_path = repo_root / "bin" / "install.sh"
    assert installer_path.exists(), "bin/install.sh must exist in release distribution"
    syntax_check = subprocess.run(["sh", "-n", str(installer_path)], capture_output=True, text=True)
    assert syntax_check.returncode == 0, f"Installer syntax error: {syntax_check.stderr}"

    doctor_report = await SystemDoctor.run_diagnostics()
    assert doctor_report.overall_status == "HEALTHY"
    assert len(doctor_report.sections) >= 5

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "Keelway Studio" in root_resp.text

        # =====================================================================
        # STAGE 2: OPEN A LOCAL PROJECT OR GIT REPOSITORY
        # =====================================================================
        repo_dir = tmp_path / "demo_repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Keelway Developer"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "developer@keelway.internal"], cwd=repo_dir, check=True)

        calc_file = repo_dir / "calculator.py"
        calc_file.write_text("def multiply(a, b):\n    return a + b\n")  # Intentional bug: + instead of *
        test_file = repo_dir / "test_calc.py"
        test_file.write_text(
            "import sys\nfrom calculator import multiply\n"
            "def test_multiply():\n    assert multiply(3, 4) == 12\n"
        )

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit with intentional bug", "--quiet"], cwd=repo_dir, check=True)

        fs = WorkspaceFilesystem(root_dir=repo_dir)
        files = fs.list_files()
        assert "calculator.py" in files
        assert "test_calc.py" in files

        git_status = fs.get_git_status()
        assert git_status["is_git"] is True
        assert git_status["clean"] is True

        # =====================================================================
        # STAGE 3: SELECT A SUPPORTED LOCAL MODEL
        # =====================================================================
        model_resp = await client.get("/v1/models/local")
        assert model_resp.status_code == 200
        models_data = model_resp.json()
        assert "runtime" in models_data or "models" in models_data or "status" in models_data

    # =========================================================================
    # STAGE 4: INSPECT AND ASK QUESTIONS ABOUT THE REPOSITORY
    # =========================================================================
    file_info = fs.read_file("calculator.py")
    assert "def multiply(a, b):" in file_info["content"]
    assert file_info["is_binary"] is False

    tree = fs.get_file_tree()
    assert tree["name"] == repo_dir.name
    assert "tree" in tree

    task_id = "investor_demo_task_01"
    flight_db = tmp_path / "demo_flight.db"
    recorder = FlightRecorder(task_id=task_id, db_path=flight_db)
    agent = AutonomousAgentLoop(
        task_id=task_id,
        workspace_fs=fs,
        policy=AutonomyPolicy.CONFIRM_MUTATION,
        flight_recorder=recorder,
    )

    search_res = await agent.execute_tool("search_codebase", {"query": "multiply"})
    assert search_res["status"] == "success"
    symbols = search_res["result"].get("symbols", [])
    text_matches = search_res["result"].get("text_matches", [])
    assert len(symbols) > 0 or len(text_matches) > 0

    # =========================================================================
    # STAGE 5: CREATE A CODING TASK
    # =========================================================================
    plan_res = agent.initialize_plan(
        intent="Fix multiplication bug in calculator.py where addition is returned"
    )
    assert plan_res["status"] == "plan_ready"
    assert agent.goal == "Fix multiplication bug in calculator.py where addition is returned"

    # =========================================================================
    # STAGE 6: REVIEW THE PROPOSED PLAN
    # =========================================================================
    assert len(plan_res["steps"]) >= 3
    step_descriptions = [s["description"] for s in plan_res["steps"]]
    assert any("Inspect" in d or "symbols" in d for d in step_descriptions)
    assert any("changes" in d or "Formulate" in d for d in step_descriptions)
    assert any("tests" in d or "verify" in d.lower() for d in step_descriptions)

    agent_state = agent.get_state()
    assert agent_state["task_id"] == task_id
    assert agent_state["status"] in ("planning", "idle")

    # =========================================================================
    # STAGE 7: APPROVE PERMITTED ACTIONS
    # =========================================================================
    old_content = fs.read_file("calculator.py")["content"]
    new_content = "def multiply(a, b):\n    return a * b\n"
    diff_res = await agent.propose_diff("calculator.py", old_content, new_content)
    assert diff_res["status"] == "diff_proposed"
    assert "-    return a + b" in diff_res["diff"]
    assert "+    return a * b" in diff_res["diff"]

    # Attempt mutation under CONFIRM_MUTATION policy -> requires approval
    apply_res = await agent.execute_tool("write_file", {"path": "calculator.py", "content": new_content})
    assert apply_res.get("status") == "paused_for_approval"
    assert agent.pending_approval is not None
    assert agent.pending_approval["tool_name"] == "write_file"

    # Grant approval
    app_res = await agent.approve_pending(approved=True)
    assert app_res["status"] == "success"
    assert agent.pending_approval is None
    assert fs.read_file("calculator.py")["content"] == new_content

    # =========================================================================
    # STAGE 8: EXECUTE THE AGENT IN A VERIFIED SANDBOX
    # =========================================================================
    # 8a: Verify unverified commands without configured runner are blocked
    assert agent.command_runner is None
    with pytest.raises(CommandExecutionUnavailable):
        await agent.tools["run_command"].handler({"command": "echo unverified"})

    # 8b: Verify sandbox isolation boundary on host
    runner, detail = verified_command_runner(repo_dir)
    assert runner is not None, f"Sandbox verification failed: {detail}"
    assert "all escape attempts blocked" in detail
    agent.command_runner = runner

    # 8c: Verify rejection of dangerous unverified commands by safety gate
    danger_res = await agent.execute_tool("run_command", {"command": "rm -rf /"})
    if danger_res.get("status") == "paused_for_approval":
        danger_res = await agent.approve_pending(approved=True)
    assert danger_res["status"] == "error"
    assert "rejected by safety gate" in danger_res["error"]

    # 8d: Execute verified command inside sandbox
    py_exec = sys.executable
    sbx_exec = await agent.execute_tool("run_command", {"command": f'{py_exec} -c "import os; print(\'sandbox_verified\')"' })
    if sbx_exec.get("status") == "paused_for_approval":
        sbx_exec = await agent.approve_pending(approved=True)
    assert sbx_exec["status"] == "success"
    assert "sandbox_verified" in sbx_exec["result"]["stdout"]
    assert sbx_exec["result"]["exit_code"] == 0
    assert sbx_exec["result"]["sandbox"] in ("seatbelt", "bubblewrap")

    # =========================================================================
    # STAGE 9: INSPECT CHANGED FILES AND DIFFS
    # =========================================================================
    git_status = fs.get_git_status()
    assert git_status["clean"] is False
    assert any(f["path"] == "calculator.py" for f in git_status["files"])

    file_diff = fs.get_git_diff("calculator.py")
    assert "-    return a + b" in file_diff["diff"]
    assert "+    return a * b" in file_diff["diff"]

    proposal = fs.prepare_commit_proposal()
    assert proposal["clean"] is False
    assert proposal["files_count"] == 1
    assert len(proposal["patch_hash"]) == 64

    # =========================================================================
    # STAGE 10: RUN PROJECT TESTS
    # =========================================================================
    healer = SelfHealingLoop(repo_root=repo_dir)
    test_code, stdout, stderr = await healer.execute_test(f"{sys.executable} -m pytest -q test_calc.py", cwd=repo_dir)
    assert test_code == 0
    assert "passed" in stdout or "1 passed" in stdout

    # =========================================================================
    # STAGE 11: REVIEW THE FINAL TASK SUMMARY
    # =========================================================================
    final_state = agent.get_state()
    assert final_state["task_id"] == task_id
    assert final_state["status"] == "idle"
    assert final_state["events_count"] > 0
    assert final_state["pending_approval"] is None

    tape = recorder.get_tape()
    assert len(tape.events) > 0
    sealed_tape = recorder.seal_tape()
    assert sealed_tape.tape_sha256 != ""
    assert len(sealed_tape.tape_sha256) == 64

    tape_path = recorder.save_tape()
    assert tape_path.exists()

    # =========================================================================
    # STAGE 12: ACCEPT OR REJECT CHANGES
    # =========================================================================
    # 12a: Verify rejection of unpermitted mutations
    reject_res = await agent.execute_tool("write_file", {"path": "calculator.py", "content": "broken = True"})
    assert reject_res["status"] == "paused_for_approval"
    denied_res = await agent.approve_pending(approved=False)
    assert denied_res["status"] == "denied"
    assert fs.read_file("calculator.py")["content"] == new_content

    # 12b: Accept and commit verified changes
    commit_res = fs.create_local_commit(
        message="fix(calc): repair multiplication operator to return product",
        author_name="Keelway Developer",
        author_email="dev@keelway.local",
    )
    assert commit_res["status"] == "committed"
    assert commit_res["clean"] is True
    assert len(commit_res["commit_sha"]) == 40

    final_git_status = fs.get_git_status()
    assert final_git_status["clean"] is True

    # 12c: Historical time-travel fork verification (preserves investor demo capability)
    fork_dest = tmp_path / "historical_fork"
    fork_res = recorder.fork_checkpoint(event_index=0, destination_path=fork_dest)
    assert fork_res["status"] == "success"
    assert fork_dest.exists()
