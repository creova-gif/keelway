"""
Tests for Keelway Terminal Execution, Dynamic Plan Formulation, and Task Cancellation.
"""

import time
import pytest
from starlette.testclient import TestClient

from core.main import app
from core.orchestration.agent_loop import AutonomousAgentLoop, AgentLoopStatus


def test_formulate_plan_intent_detection():
    """Verifies dynamic plan formulation based on developer intent."""
    plan_fix = AutonomousAgentLoop.formulate_plan("Fix the discount calculation bug in checkout")
    assert len(plan_fix) == 3
    assert any("repair" in step.lower() or "tests" in step.lower() for step in plan_fix)

    plan_refactor = AutonomousAgentLoop.formulate_plan("Refactor billing database queries")
    assert len(plan_refactor) == 3
    assert any("refactoring" in step.lower() for step in plan_refactor)

    plan_feature = AutonomousAgentLoop.formulate_plan("Implement user profile avatars endpoint")
    assert len(plan_feature) == 3
    assert any("feature" in step.lower() for step in plan_feature)


def test_terminal_exec_endpoint():
    """Verifies that terminal commands run securely with environment scrubbing."""
    with TestClient(app) as client:
        # 1. Valid command execution
        res = client.post("/v1/terminal/exec", json={"command": "python3 -c 'print(40 + 2)'"})
        assert res.status_code == 200
        data = res.json()
        assert data["exit_code"] == 0
        assert "42" in data["stdout"]
        assert "duration_ms" in data

        # 2. Block dangerous destructive commands
        res_deny = client.post("/v1/terminal/exec", json={"command": "rm -rf /"})
        assert res_deny.status_code == 403
        assert "rejected by security safety gate" in res_deny.json()["detail"]


def test_agent_task_cancellation():
    """Verifies that active agent runs can be cancelled cleanly."""
    task_id = f"test_cancel_task_{time.time_ns()}"
    with TestClient(app) as client:
        # Start a task
        res_run = client.post(
            "/v1/agent/run",
            json={
                "task_id": task_id,
                "goal": "Refactor billing system",
            },
        )
        assert res_run.status_code == 200
        assert res_run.json()["task_id"] == task_id

        # Cancel the task
        res_cancel = client.post(f"/v1/agent/cancel/{task_id}")
        assert res_cancel.status_code == 200
        data = res_cancel.json()
        assert data["result"]["status"] == "cancelled"
        assert data["agent_state"]["status"] == AgentLoopStatus.CANCELLED.value

        # Status check reflects cancelled
        res_status = client.get(f"/v1/agent/status/{task_id}")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == AgentLoopStatus.CANCELLED.value
