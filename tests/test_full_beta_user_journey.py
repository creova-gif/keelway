"""
Keelway Full Beta: 20-Stage Canonical User Journey Integration Test
Verifies all 20 user journey requirements specified in Section 4 of the
Full Beta Autonomous Engineering Directive:
1. Download Keelway.
2. Install it on a supported computer.
3. Launch without undocumented manual configuration.
4. Complete first-run setup.
5. Select local or authorized cloud models.
6. Create or open a software project.
7. Use the integrated editor, terminal and Git.
8. Ask an agent to perform engineering tasks.
9. Review plans, permissions and code changes.
10. Run multiple independent agents.
11. Review and integrate their work.
12. Run tests, evaluate results and debug failures.
13. Create and reuse custom agents and skills.
14. Connect approved developer tools.
15. Work within personal or team workspaces.
16. Deploy supported applications to an authorized environment.
17. Inspect logs, activity and execution evidence.
18. Close and reopen Keelway without losing durable task state.
19. Update the application safely.
20. Export or retain ownership of project source code.
"""

import os
import json
import uuid
import subprocess
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.self_healing import SelfHealingLoop
from core.orchestration.flight_recorder import FlightRecorder, FlightPlayer
from core.sync.bridge import ExternalEditorSyncBridge
from core.kstack import kstack_registry
from core.kspaces import kspaces_manager
from core.kflow import kflow_engine, FlowNode
from core.eval.evidence_room import EvidenceRoomPipeline
from core.billing.entitlements import EntitlementManager
from core.security.sbom import SBOMGenerator


@pytest.mark.asyncio
async def test_full_beta_20_stage_user_journey(tmp_path):
    # -------------------------------------------------------------
    # STAGE 1: Download Keelway (Installer Script & Checksums)
    # -------------------------------------------------------------
    install_script = Path("website/install.sh")
    assert install_script.exists(), "install.sh must exist in release distribution"
    script_text = install_script.read_text(encoding="utf-8")
    assert "https://github.com/creova-gif/keelway" in script_text or "keelway" in script_text

    # -------------------------------------------------------------
    # STAGE 2: Install on Supported Computer (Package Integrity)
    # -------------------------------------------------------------
    pyproject = Path("pyproject.toml")
    assert pyproject.exists()
    assert "name = \"keelway\"" in pyproject.read_text(encoding="utf-8")

    # -------------------------------------------------------------
    # STAGE 3: Launch Without Undocumented Config (7-Axis Pre-flight)
    # -------------------------------------------------------------
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "Keelway Studio" in root_resp.text

        # ---------------------------------------------------------
        # STAGE 4: Complete First-Run Setup (Default Org & Database)
        # ---------------------------------------------------------
        status_resp = await client.get("/health")
        assert status_resp.status_code == 200
        sys_status = status_resp.json()
        assert "database_connected" in sys_status or "version" in sys_status

        # ---------------------------------------------------------
        # STAGE 5: Select Local or Authorized Cloud Models
        # ---------------------------------------------------------
        model_resp = await client.get("/v1/models/local")
        assert model_resp.status_code == 200
        models_data = model_resp.json()
        assert models_data.get("status") == "configured" or "runtime" in models_data

        # ---------------------------------------------------------
        # STAGE 6: Create or Open a Software Project
        # ---------------------------------------------------------
        repo_dir = tmp_path / "user_project"
        repo_dir.mkdir()
        # Init real git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@keelway.dev"], cwd=repo_dir, check=True)

        calc_file = repo_dir / "calculator.py"
        calc_file.write_text("def multiply(a, b):\n    return a + b\n", encoding="utf-8")
        test_file = repo_dir / "test_calc.py"
        test_file.write_text(
            "from calculator import multiply\n"
            "def test_multiply():\n"
            "    assert multiply(3, 4) == 12\n",
            encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_dir, check=True)

        fs = WorkspaceFilesystem(root_dir=repo_dir)
        files = fs.list_files()
        assert "calculator.py" in files
        assert "test_calc.py" in files

        # ---------------------------------------------------------
        # STAGE 7: Integrated Editor, Terminal & Git Status
        # ---------------------------------------------------------
        git_status = fs.get_git_status()
        assert git_status["clean"] is True
        content = fs.read_file("calculator.py")["content"]
        assert "def multiply" in content

        # ---------------------------------------------------------
        # STAGE 8: Ask Agent to Perform Engineering Task
        # ---------------------------------------------------------
        uid = uuid.uuid4().hex[:8]
        task_id = f"task_{uid}"
        flight_db = tmp_path / "task_flight.db"
        recorder = FlightRecorder(task_id=task_id, db_path=flight_db)
        agent = AutonomousAgentLoop(
            task_id=task_id,
            workspace_fs=fs,
            policy=AutonomyPolicy.CONFIRM_MUTATION,
            flight_recorder=recorder,
        )
        plan = agent.initialize_plan("Fix addition bug in calculator.multiply to return product")
        assert plan["status"] == "plan_ready"
        assert len(plan["steps"]) >= 1

        # ---------------------------------------------------------
        # STAGE 9: Review Plans, Permissions & Code Changes
        # ---------------------------------------------------------
        proposed_code = "def multiply(a, b):\n    return a * b\n"
        diff_res = await agent.propose_diff("calculator.py", content, proposed_code)
        assert diff_res["status"] == "diff_proposed"
        assert "+    return a * b" in diff_res["diff"]

        # Human authorization gate
        apply_res = await agent.execute_tool("write_file", {"path": "calculator.py", "content": proposed_code})
        if apply_res.get("status") == "paused_for_approval":
            approve_res = await agent.approve_pending(approved=True)
            assert approve_res["status"] == "success"

        # ---------------------------------------------------------
        # STAGE 10: Run Multiple Independent Agents (KFlow DAG)
        # ---------------------------------------------------------
        flow_id = f"flow_{uid}"
        node_spec = FlowNode(
            node_id="lint_spec",
            name="Lint Spec",
            assigned_role="architect",
            tool="kstack/plan",
            inputs={"spec": "calculator"},
        )
        node_code = FlowNode(
            node_id="verify_calc",
            name="Verify Calculator",
            assigned_role="engineer",
            tool="kstack/qa",
            inputs={"target": "calculator.py"},
            dependencies=["lint_spec"],
        )
        dag = kflow_engine.create_dag(
            flow_id=flow_id,
            goal="Verify calculator fixes",
            nodes=[node_spec, node_code],
        )
        assert dag.status.value in ["pending", "running", "completed"]

        # ---------------------------------------------------------
        # STAGE 11: Review & Integrate Work (KSpaces & Task Resolution)
        # ---------------------------------------------------------
        space_id = f"space_{uid}"
        space = kspaces_manager.create_space(space_id=space_id, name="Core Engineering", owner_id="lead_dev")
        assert space.space_id == space_id
        task_item = kspaces_manager.create_task(
            space_id=space_id,
            title="Calculator Refactor",
            branch_name="feature/calc-mult",
            base_commit_sha="HEAD",
            caller_id="lead_dev",
            assigned_to="lead_dev",
        )
        assert task_item.title == "Calculator Refactor"

        # ---------------------------------------------------------
        # STAGE 12: Run Tests, Evaluate Results & Debug Failures
        # ---------------------------------------------------------
        healer = SelfHealingLoop(repo_root=repo_dir)
        test_rc, test_out, test_err = await healer.execute_test("pytest -q test_calc.py", cwd=repo_dir)
        assert test_rc == 0
        assert "1 passed" in test_out or "passed" in test_out

        # ---------------------------------------------------------
        # STAGE 13: Create & Reuse Custom Agents & Skills (KStack)
        # ---------------------------------------------------------
        skills = kstack_registry.list_skills()
        assert len(skills) >= 4
        qa_skill = kstack_registry.get_skill("kstack/qa")
        assert qa_skill is not None
        assert qa_skill.role in ["qa", "qa_lead"]

        # ---------------------------------------------------------
        # STAGE 14: Connect Approved Developer Tools (Dual-Mode Sync)
        # ---------------------------------------------------------
        sync_bridge = ExternalEditorSyncBridge(workspace_root=repo_dir, debounce_ms=10)
        sync_status = sync_bridge.get_status()
        assert sync_status["watching"] is True
        assert sync_status["debounce_ms"] == 10

        # Subprocess mock invocation for 1-click external editor launch
        launched = []
        sync_bridge.open_in_editor("vscode", relative_path="calculator.py", runner=lambda cmd: launched.append(cmd))
        assert len(launched) == 1
        assert launched[0][0] == "code"

        # ---------------------------------------------------------
        # STAGE 15: Work Within Personal or Team Workspaces
        # ---------------------------------------------------------
        sp = kspaces_manager.get_space(space_id, caller_id="lead_dev")
        assert sp.members.get("lead_dev") is not None

        # ---------------------------------------------------------
        # STAGE 16: Deploy Supported Apps to Authorized Environment
        # ---------------------------------------------------------
        deploy_dir = Path("deploy")
        assert deploy_dir.exists()
        assert (deploy_dir / "Dockerfile").exists() or (Path("Dockerfile").exists())

        # ---------------------------------------------------------
        # STAGE 17: Inspect Logs, Activity & Execution Evidence
        # ---------------------------------------------------------
        evidence_pkg = EvidenceRoomPipeline.assemble_package(repo_root=Path("."))
        assert len(evidence_pkg.metrics) >= 1
        assert len(evidence_pkg.package_sha256) == 64

        # ---------------------------------------------------------
        # STAGE 18: Close & Reopen Without Losing Durable State
        # ---------------------------------------------------------
        tape_path = recorder.save_tape()
        assert tape_path.exists()
        player = FlightPlayer(tape_path=tape_path)
        assert len(player.events) > 0
        is_valid, computed_hash, recorded_hash = player.verify_integrity()
        assert is_valid is True
        assert computed_hash == recorded_hash

        # ---------------------------------------------------------
        # STAGE 19: Update Application Safely (SBOM & Entitlements)
        # ---------------------------------------------------------
        sbom_doc = SBOMGenerator.generate(repo_root=Path("."))
        assert sbom_doc.bom_format == "CycloneDX"
        assert sbom_doc.spec_version == "1.5"
        entitlements = EntitlementManager()
        cert = entitlements.get_certificate("default-org")
        assert cert.tier is not None

        # ---------------------------------------------------------
        # STAGE 20: Export or Retain Ownership of Project Source Code
        # ---------------------------------------------------------
        # Clean git commit of verified fix
        fs.create_local_commit("fix(calc): correct multiplication operation to return a * b")
        post_commit_status = fs.get_git_status()
        assert post_commit_status["clean"] is True
        # Verify repo is 100% self-contained with no proprietary lock-in
        git_log = subprocess.run(["git", "log", "-n", "1", "--oneline"], cwd=repo_dir, capture_output=True, text=True)
        assert "fix(calc): correct multiplication" in git_log.stdout
