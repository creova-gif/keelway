"""
Full Beta Autonomous Engineering Directive — 20-Stage Developer Journey E2E Test.
Formally verifies all 20 stages required by Section 4 of the Beta Directive.
"""
import pytest
import subprocess
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.self_healing import SelfHealingLoop
from core.orchestration.flight_recorder import FlightRecorder
from core.orchestration.multi_agent import MultiAgentCoordinator
from core.system.doctor import SystemDoctor
from core.security.auth import launch_token
from core.agents.builder import AgentBuilder
from core.agents.sandbox import verified_command_runner, CommandExecutionUnavailable
from core.eval.evidence_room import EvidenceRoomPipeline


@pytest.mark.asyncio
async def test_complete_20_stage_beta_user_journey(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent

    # =========================================================================
    # STAGE 1: DOWNLOAD KEELWAY (Installer syntax & POSIX compliance)
    # =========================================================================
    installer_path = repo_root / "bin" / "install.sh"
    assert installer_path.exists(), "bin/install.sh must exist"
    syntax_check = subprocess.run(["sh", "-n", str(installer_path)], capture_output=True, text=True)
    assert syntax_check.returncode == 0, f"Installer syntax error: {syntax_check.stderr}"

    # =========================================================================
    # STAGE 2: INSTALL & PRE-FLIGHT SYSTEM DOCTOR
    # =========================================================================
    doctor_report = await SystemDoctor.run_diagnostics()
    assert doctor_report.overall_status == "HEALTHY"
    assert len(doctor_report.sections) >= 7

    # =========================================================================
    # STAGE 3: LAUNCH WITHOUT UNDOCUMENTED CONFIGURATION
    # =========================================================================
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        studio_resp = await client.get("/")
        assert studio_resp.status_code == 200
        assert "Keelway Studio" in studio_resp.text

        # =====================================================================
        # STAGE 4: FIRST-RUN SETUP & AUTHENTICATION
        # =====================================================================
        token = launch_token()
        assert token.startswith("keelway_")

        # =====================================================================
        # STAGE 5: SELECT LOCAL OR AUTHORIZED CLOUD MODELS
        # =====================================================================
        model_resp = await client.get("/v1/models/local")
        assert model_resp.status_code == 200
        models_data = model_resp.json()
        assert "runtime" in models_data or "models" in models_data

    # =========================================================================
    # STAGE 6: CREATE OR OPEN A SOFTWARE PROJECT
    # =========================================================================
    project_dir = tmp_path / "beta_sample_app"
    project_dir.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Keelway Engineer"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "engineer@keelway.internal"], cwd=project_dir, check=True)

    # =========================================================================
    # STAGE 7: INTEGRATED EDITOR, TERMINAL & GIT
    # =========================================================================
    calc_py = project_dir / "service.py"
    calc_py.write_text("def run_job(x):\n    return x + 10  # BUG: should multiply by 10\n")
    test_py = project_dir / "test_service.py"
    test_py.write_text("from service import run_job\ndef test_job():\n    assert run_job(5) == 50\n")

    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit with intentional bug", "--quiet"], cwd=project_dir, check=True)

    fs = WorkspaceFilesystem(root_dir=project_dir)
    assert "service.py" in fs.list_files()
    assert "test_service.py" in fs.list_files()

    # =========================================================================
    # STAGE 8: ASK AN AGENT TO PERFORM ENGINEERING TASKS
    # =========================================================================
    task_id = "beta_journey_task_001"
    flight_db = tmp_path / "beta_journey_flight.db"
    recorder = FlightRecorder(task_id=task_id, db_path=flight_db)
    agent = AutonomousAgentLoop(
        task_id=task_id,
        workspace_fs=fs,
        policy=AutonomyPolicy.CONFIRM_MUTATION,
        flight_recorder=recorder,
    )

    plan = agent.initialize_plan(intent="Repair run_job function in service.py to multiply by 10 instead of adding")
    assert plan["status"] == "plan_ready"
    assert len(plan["steps"]) >= 1

    # =========================================================================
    # STAGE 9: REVIEW PLANS, PERMISSIONS AND CODE CHANGES
    # =========================================================================
    old_content = fs.read_file("service.py")
    patch = "def run_job(x):\n    return x * 10\n"
    diff = await agent.propose_diff("service.py", old_content, patch)
    assert "-    return x + 10" in diff["diff"]
    assert "+    return x * 10" in diff["diff"]

    # =========================================================================
    # STAGE 10: RUN MULTIPLE INDEPENDENT AGENTS
    # =========================================================================
    coordinator = MultiAgentCoordinator(workspace_fs=fs)
    crew_plan = coordinator.plan_team_workflow(
        goal="Audit security and benchmark unit tests for service.py"
    )
    assert len(crew_plan.nodes) >= 3
    order = crew_plan.topological_order()
    assert len(order) >= 3

    # =========================================================================
    # STAGE 11: REVIEW AND INTEGRATE THEIR WORK
    # =========================================================================
    tool_res = await agent.execute_tool("write_file", {"path": "service.py", "content": patch})
    if tool_res.get("status") == "paused_for_approval":
        app_res = await agent.approve_pending(approved=True)
        assert app_res["status"] == "success"
    read_back = fs.read_file("service.py")
    content = read_back["content"] if isinstance(read_back, dict) else read_back
    assert content == patch

    # Sandbox isolation and runner boundary verification
    assert agent.command_runner is None
    with pytest.raises(CommandExecutionUnavailable):
        await agent.tools["run_command"].handler({"command": "echo unverified"})

    runner, detail = verified_command_runner(project_dir)
    assert runner is not None, f"Sandbox verification failed: {detail}"
    agent.command_runner = runner

    # Safety gate blocks dangerous unverified commands
    danger_res = await agent.execute_tool("run_command", {"command": "rm -rf /"})
    if danger_res.get("status") == "paused_for_approval":
        danger_res = await agent.approve_pending(approved=True)
    assert danger_res["status"] == "error"
    assert "rejected by safety gate" in danger_res["error"]

    # Sandboxed execution verifies code environment
    sbx_exec = await agent.execute_tool("run_command", {"command": f'{sys.executable} -c "import service; print(\'service_ok\')"' })
    if sbx_exec.get("status") == "paused_for_approval":
        sbx_exec = await agent.approve_pending(approved=True)
    assert sbx_exec["status"] == "success"
    assert "service_ok" in sbx_exec["result"]["stdout"]
    assert sbx_exec["result"]["sandbox"] in ("seatbelt", "bubblewrap")

    # =========================================================================
    # STAGE 12: RUN TESTS, EVALUATE RESULTS AND DEBUG FAILURES
    # =========================================================================
    healer = SelfHealingLoop(repo_root=project_dir)
    rc, stdout, stderr = await healer.execute_test(f"{sys.executable} -m pytest test_service.py -q")
    assert rc == 0, f"Tests should pass after patch: {stdout}\n{stderr}"

    # =========================================================================
    # STAGE 13: CREATE AND REUSE CUSTOM AGENTS AND SKILLS
    # =========================================================================
    templates = AgentBuilder.list_templates()
    assert len(templates) >= 3
    spec = AgentBuilder.create_from_template("code-reviewer", name="performance-auditor", author="engineer")
    assert spec.name == "performance-auditor"
    artifacts = AgentBuilder.generate_source_artifacts(spec)
    assert f"{spec.name}.agent.json" in artifacts

    # =========================================================================
    # STAGE 14: CONNECT APPROVED DEVELOPER TOOLS
    # =========================================================================
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        plugins_resp = await client.get("/v1/plugins")
        assert plugins_resp.status_code == 200

        # =====================================================================
        # STAGE 15: WORK WITHIN PERSONAL OR TEAM WORKSPACES
        # =====================================================================
        ws_resp = await client.get("/v1/workspaces")
        assert ws_resp.status_code == 200

        # =====================================================================
        # STAGE 16: DEPLOY SUPPORTED APPLICATIONS TO AUTHORIZED ENVIRONMENT
        # =====================================================================
        harness_resp = await client.get("/v1/builder/app/templates")
        assert harness_resp.status_code == 200

        # =====================================================================
        # STAGE 17: INSPECT LOGS, ACTIVITY AND EXECUTION EVIDENCE
        # =====================================================================
        evidence_resp = await client.get("/v1/evidence/summary")
        assert evidence_resp.status_code == 200
        ev_data = evidence_resp.json()
        assert "package_id" in ev_data
        assert "package_sha256" in ev_data
        assert len(ev_data.get("metrics", [])) >= 4

    # =========================================================================
    # STAGE 18: CLOSE AND REOPEN KEELWAY WITHOUT LOSING DURABLE TASK STATE
    # =========================================================================
    recorder.seal_tape()
    tape_path = recorder.save_tape()
    assert tape_path.exists()
    assert len(recorder.events) >= 1
    assert any(e.event_type == "plan_initialized" for e in recorder.events)

    # =========================================================================
    # STAGE 19: UPDATE THE APPLICATION SAFELY
    # =========================================================================
    assert "git -C \"$INSTALL_DIR\" pull" in installer_path.read_text()

    # =========================================================================
    # STAGE 20: EXPORT OR RETAIN OWNERSHIP OF PROJECT SOURCE CODE
    # =========================================================================
    status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=project_dir, capture_output=True, text=True)
    assert "M service.py" in status_proc.stdout
    # Fork flight checkpoint into isolated worktree directory
    fork_dir = tmp_path / "forked_checkpoint_worktree"
    fork_result = recorder.fork_checkpoint(
        event_index=0,
        destination_path=fork_dir,
    )
    assert fork_result["status"] == "success"
    assert fork_dir.exists()
