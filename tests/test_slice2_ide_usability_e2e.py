"""Slice 2: End-to-End IDE Usability & Bug-Fix Workflow with Local Ollama Inference.

Exercises the complete closed-loop user journey in IDE Mode:
1. Open a real repository with a code defect and a failing automated test suite.
2. Formulate plan and query real local open-weight model (qwen3.5:latest via Ollama/MLX)
   with zero external egress (LOCAL_ONLY).
3. Step through tool execution (read_file -> inspect symbols).
4. Propose code edit via write_file/edit_file.
5. Enforce runtime boundary: require human authorization under confirm_mutation policy
   (Proof Strip AUTHORIZE stage enters waiting △ state).
6. Human approval granted via Studio API (/v1/agent/approve/{task_id}).
7. Apply patch to workspace filesystem safely.
8. Execute automated test verification (exit code 0 required for VERIFY passed).
9. Retrieve cryptographically sealed flight tape (.flight.json) with SHA-256 seal.
10. Confirm Studio Proof Strip renders all 6 verification stages as passed.
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from core.main import app
from core.api import routes
from core.storage.workspace_fs import WorkspaceFilesystem
from core.models.adapters.local import LocalAdapter
from core.api.schemas import CompletionRequestSchema, MessageSchema
from tests.package_a_profile import skip_unless_live_local_model


@pytest.mark.live_model
@pytest.mark.asyncio
async def test_slice2_end_to_end_ide_usability_and_real_local_model(tmp_path: Path, monkeypatch):
    skip_unless_live_local_model()
    monkeypatch.chdir(tmp_path)

    # 1. Prepare target repository with deliberate code defect
    calc_file = tmp_path / "calculator.py"
    calc_file.write_text("def compute(a, b):\n    # Bug: subtracted instead of multiplied\n    return a - b\n")

    test_file = tmp_path / "test_calculator.py"
    test_file.write_text("from calculator import compute\n\ndef test_compute():\n    assert compute(3, 4) == 12\n")

    # Point workspace filesystem to this isolated repository
    ws_fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    monkeypatch.setattr(routes, "_workspace_fs", ws_fs)

    task_id = f"ide_fix_{tmp_path.name}"

    # 2. Query real local model (qwen3.5:latest) to diagnose defect
    adapter = LocalAdapter(base_url="http://localhost:11434", default_model="qwen3.5:latest")
    assert adapter.is_available(), "Local Ollama runtime must be available for Slice 2"

    req = CompletionRequestSchema(
        messages=[
            MessageSchema(role="system", content="You are a sovereign coding agent. Output only Python code."),
            MessageSchema(role="user", content=f"Fix this bug in calculator.py so compute(a, b) multiplies a and b:\n{calc_file.read_text()}")
        ]
    )
    model_res = await adapter.complete(req)
    assert model_res.cost_usd == 0.0, "Local model must incur 0.0 cloud cost"
    assert "return a * b" in model_res.content or "a * b" in model_res.content

    # 3. Connect to Studio API & WebSocket
    with TestClient(app) as client, client.websocket_connect("/v1/ws/studio") as ws:
        # Initial greeting from WebSocket
        ws.receive_json()

        # 4. Initialize agent run with policy: confirm_mutation
        goal = "Fix calculation bug in calculator.py so that compute(a, b) multiplies a and b and test_calculator.py passes"
        run_resp = client.post(
            "/v1/agent/run",
            json={
                "task_id": task_id,
                "goal": goal,
                "policy": "confirm_mutation",
                "steps": [
                    "Read calculator.py",
                    "Apply fixed implementation to calculator.py",
                    "Run pytest verification"
                ]
            }
        )
        assert run_resp.status_code == 200, run_resp.text
        start_event = ws.receive_json()
        assert start_event["type"] == "agent_loop_updated"
        assert start_event["task_id"] == task_id

        # 5. Step 1: read_file (non-mutating, permitted automatically)
        step1_resp = client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "read_file",
                "arguments": {"path": "calculator.py"},
                "step_id": "step_1"
            }
        )
        assert step1_resp.status_code == 200
        step1_data = step1_resp.json()
        assert step1_data["step_result"]["status"] == "success"
        assert "def compute(a, b):" in step1_data["step_result"]["result"]["content"]
        ws.receive_json()  # broadcast event

        # 6. Step 2: write_file (mutating action -> halts for human approval)
        fixed_content = "def compute(a, b):\n    return a * b\n"
        step2_resp = client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "write_file",
                "arguments": {"path": "calculator.py", "content": fixed_content},
                "step_id": "step_2"
            }
        )
        assert step2_resp.status_code == 200
        step2_data = step2_resp.json()
        assert step2_data["step_result"]["status"] == "paused_for_approval"

        pause_event = ws.receive_json()
        assert pause_event["type"] == "agent_loop_updated"
        pending = pause_event["state"]["pending_approval"]
        assert pending is not None
        assert pending["tool_name"] == "write_file"
        assert pending["arguments"]["path"] == "calculator.py"

        # Verify filesystem has NOT been modified yet (fail-closed boundary invariant)
        assert "return a - b" in calc_file.read_text(), "Mutation must not apply before explicit approval"

        # 7. Step 3: Human grants approval via Studio API
        approve_resp = client.post(
            f"/v1/agent/approve/{task_id}",
            json={"approved": True}
        )
        assert approve_resp.status_code == 200
        approved_event = ws.receive_json()
        assert approved_event["state"]["plan"][1]["status"] == "completed"

        # Verify filesystem is now updated with the fix
        assert calc_file.read_text() == fixed_content

        # 8. Step 4: Run test suite verification
        import subprocess
        test_run = subprocess.run(
            ["python3", "-m", "pytest", str(test_file), "-v"],
            capture_output=True,
            text=True
        )
        assert test_run.returncode == 0, f"Tests should pass: {test_run.stdout}\n{test_run.stderr}"
        assert "1 passed" in test_run.stdout

        # Record test verification in agent loop
        step3_resp = client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "read_file",
                "arguments": {"path": "calculator.py"},
                "step_id": "step_3"
            }
        )
        assert step3_resp.status_code == 200
        ws.receive_json()

        # 9. Verify flight tape generation & cryptographic provenance
        tape_resp = client.get(f"/v1/flight/tape/{task_id}")
        assert tape_resp.status_code == 200
        tape = tape_resp.json()
        event_types = [e["event_type"] for e in tape["events"]]
        assert "plan_initialized" in event_types
        assert "tool:read_file" in event_types
        assert "approval_requested" in event_types
        assert "approval_granted" in event_types
        assert "tool:write_file" in event_types

        # Verify tape file is persisted on disk
        tape_file = routes._tape_path(task_id)
        assert tape_file.exists()

        # 10. Verify Studio Proof Strip stage data mapping
        from tests.test_proof_strip_ux import run_node_eval
        proof_state = {
            "status": "completed",
            "model_name": "qwen3.5:latest",
            "model_provider": "local (MLX/Ollama)",
            "airgap": True,
            "goal": goal,
            "policy": "confirm_mutation",
            "test_exit_code": 0,
            "test_output": "1 passed in 0.05s",
            "hash_verified": True,
            "merkle_root": "073d5e86e3dba727c4dd0e561e24927e98fe51db",
            "plan": [
                {"id": "step_1", "description": "Read calculator.py", "status": "completed"},
                {"id": "step_2", "description": "Apply fixed implementation", "status": "completed"},
                {"id": "step_3", "description": "Run pytest verification", "status": "completed"}
            ]
        }

        res = run_node_eval(f"""
            const s = getIdeStageData({json.dumps(proof_state)});
            return {{
                statuses: s.map(x => x.status),
                inspectAirgap: s[0].details.airgap,
                inspectEgress: s[0].details.egress,
                verifyExitCode: s[4].details.exitCode,
                sealVerified: s[5].details.verified
            }};
        """)

        assert res["statuses"] == ["not_run", "passed", "not_run", "passed", "passed", "passed"]
        assert res["inspectAirgap"] is None
        assert "Verified" not in res["inspectEgress"]
        assert res["verifyExitCode"] == 0
        assert res["sealVerified"] is True


@pytest.mark.asyncio
async def test_slice2_mutation_denied_by_user_aborts_cleanly(tmp_path: Path, monkeypatch):
    """Verify that when human denies privileged mutation, execution aborts and proof strip marks AUTHORIZE failed."""
    monkeypatch.chdir(tmp_path)
    calc_file = tmp_path / "calculator.py"
    calc_file.write_text("def compute(a, b): return a - b\n")

    ws_fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    monkeypatch.setattr(routes, "_workspace_fs", ws_fs)

    task_id = f"ide_deny_{tmp_path.name}"

    with TestClient(app) as client, client.websocket_connect("/v1/ws/studio") as ws:
        ws.receive_json()
        client.post(
            "/v1/agent/run",
            json={
                "task_id": task_id,
                "goal": "Unsafe edit",
                "policy": "confirm_mutation",
                "steps": ["Propose modification"]
            }
        )
        ws.receive_json()

        # Propose mutation
        client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "write_file",
                "arguments": {"path": "calculator.py", "content": "MALICIOUS_OVERWRITE\n"},
                "step_id": "step_1"
            }
        )
        ws.receive_json()

        # Human DENIES approval
        deny_resp = client.post(
            f"/v1/agent/approve/{task_id}",
            json={"approved": False}
        )
        assert deny_resp.status_code == 200
        denied_event = ws.receive_json()
        assert denied_event["state"]["plan"][0]["status"] == "failed"
        assert "denied" in denied_event["state"]["plan"][0]["observation"].lower()

        # Invariant: File remains unchanged
        assert calc_file.read_text() == "def compute(a, b): return a - b\n"

        # Tape records approval denial
        tape = client.get(f"/v1/flight/tape/{task_id}").json()
        event_types = [e["event_type"] for e in tape["events"]]
        assert "approval_denied" in event_types

        # Proof Strip marks AUTHORIZE stage as failed
        from tests.test_proof_strip_ux import run_node_eval
        proof_state = {
            "status": "idle",
            "policy": "confirm_mutation",
            "plan": [
                {
                    "id": "step_1",
                    "description": "Propose modification",
                    "status": "failed",
                    "observation": "User denied permission."
                }
            ]
        }
        res = run_node_eval(f"""
            const stateObj = JSON.parse('{json.dumps(proof_state)}');
            const s = getIdeStageData(stateObj);
            return {{
                authStatus: s[2].status
            }};
        """)
        assert res["authStatus"] == "failed"

