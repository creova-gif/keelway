"""
Tests for Keelway 4 Conversation Modes (Ask, Plan, Edit, Agent) and Expanded Enterprise Task State Lifecycle.
Section 6.1 & 7.2 of the Master Architecture Directive.
"""

import pytest
from starlette.testclient import TestClient

from core.main import app
from core.orchestration.chat import ConversationMode, InteractiveChatSession
from core.orchestration.state import TaskState, can_transition, validate_transition, InvalidStateTransitionError


def test_chat_modes_metadata_endpoint():
    """Verifies that GET /v1/chat/modes exposes all 4 modes and their governance constraints."""
    with TestClient(app) as client:
        res = client.get("/v1/chat/modes")
        assert res.status_code == 200
        data = res.json()
        modes = data["modes"]
        mode_ids = [m["id"] for m in modes]
        assert "ask" in mode_ids
        assert "plan" in mode_ids
        assert "edit" in mode_ids
        assert "agent" in mode_ids

        # Governance assertion: Ask mode is read-only and does not mutate files
        ask_mode = next(m for m in modes if m["id"] == "ask")
        assert ask_mode["mutates_files"] is False
        assert ask_mode["requires_approval"] is False

        # Governance assertion: Edit mode requires approval before applying
        edit_mode = next(m for m in modes if m["id"] == "edit")
        assert edit_mode["requires_approval"] is True

        # Governance assertion: Agent mode requires approval for mutating actions
        agent_mode = next(m for m in modes if m["id"] == "agent")
        assert agent_mode["mutates_files"] is True
        assert agent_mode["requires_approval"] is True


def test_chat_message_ask_mode():
    """Verifies Ask Mode returns read-only explanations with citations."""
    with TestClient(app) as client:
        res = client.post(
            "/v1/chat/message",
            json={
                "message": "Explain how discount calculation works in pricing.py",
                "mode": "ask",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "ask"
        assert "content" in data
        assert "model" in data
        assert "latency_ms" in data


def test_chat_message_plan_mode():
    """Verifies Plan Mode generates a structured implementation plan with steps and test strategy."""
    with TestClient(app) as client:
        res = client.post(
            "/v1/chat/message",
            json={
                "message": "Add a bulk checkout feature with tier discounts",
                "mode": "plan",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "plan"
        assert "structured_plan" in data
        plan = data["structured_plan"]
        assert len(plan["steps"]) >= 3
        assert "required_permissions" in plan
        assert "test_strategy" in plan


def test_chat_message_edit_mode():
    """Verifies Edit Mode produces a structured patch proposal with diff preview and requires authorization."""
    with TestClient(app) as client:
        res = client.post(
            "/v1/chat/message",
            json={
                "message": "Fix the discount calculation in pricing.py",
                "mode": "edit",
                "target_file": "pricing.py",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "edit"
        assert "edit_proposal" in data
        proposal = data["edit_proposal"]
        assert proposal["file_path"] == "pricing.py"
        assert proposal["authorized"] is False  # Never applied without separate human authorization


def test_chat_message_agent_mode():
    """Verifies Agent Mode initializes an autonomous multi-step execution loop."""
    with TestClient(app) as client:
        res = client.post(
            "/v1/chat/message",
            json={
                "message": "Verify checkout test suite and fix failures",
                "mode": "agent",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "agent"
        assert "agent_task" in data
        task = data["agent_task"]
        assert task["task_id"].startswith("task_")
        assert len(task["plan"]) >= 3


def test_expanded_enterprise_task_state_machine():
    """Verifies Section 7.2 durable lifecycle transitions and illegal transition rejections."""
    # 1. Forward progression
    assert can_transition(TaskState.CREATED, TaskState.CONTEXT_LOADING)
    assert can_transition(TaskState.CONTEXT_LOADING, TaskState.PLANNING)
    assert can_transition(TaskState.PLANNING, TaskState.PLAN_READY)
    assert can_transition(TaskState.PLAN_READY, TaskState.AWAITING_APPROVAL)
    assert can_transition(TaskState.AWAITING_APPROVAL, TaskState.EXECUTING)
    assert can_transition(TaskState.EXECUTING, TaskState.VERIFYING)
    assert can_transition(TaskState.VERIFYING, TaskState.COMPLETED)

    # 2. Paused and blocked states
    assert can_transition(TaskState.RUNNING, TaskState.PAUSED)
    assert can_transition(TaskState.PAUSED, TaskState.RUNNING)
    assert can_transition(TaskState.AWAITING_APPROVAL, TaskState.BLOCKED)
    assert can_transition(TaskState.BLOCKED, TaskState.AWAITING_APPROVAL)

    # 3. Timeout and retry states
    assert can_transition(TaskState.RUNNING, TaskState.TIMED_OUT)
    assert can_transition(TaskState.TIMED_OUT, TaskState.AWAITING_RETRY)
    assert can_transition(TaskState.AWAITING_RETRY, TaskState.RUNNING)

    # 4. Backward compatibility with existing paths
    assert can_transition(TaskState.CREATED, TaskState.PLANNED)
    assert can_transition(TaskState.PLANNED, TaskState.RUNNING)
    assert can_transition(TaskState.RUNNING, TaskState.FAILED)
    assert can_transition(TaskState.FAILED, TaskState.PLANNED)

    # 5. Illegal transition rejection
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TaskState.CREATED, TaskState.COMPLETED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TaskState.COMPLETED, TaskState.RUNNING)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TaskState.CANCELLED, TaskState.EXECUTING)
