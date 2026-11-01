"""
Unit tests for the Keelway Task State Machine.
"""

import pytest
from core.orchestration.state import (
    TaskState,
    InvalidStateTransitionError,
    can_transition,
    validate_transition,
)


def test_valid_transitions_happy_path():
    """Verify happy path from creation to completion."""
    assert can_transition(TaskState.CREATED, TaskState.PLANNED)
    assert can_transition(TaskState.PLANNED, TaskState.AWAITING_APPROVAL)
    assert can_transition(TaskState.AWAITING_APPROVAL, TaskState.RUNNING)
    assert can_transition(TaskState.RUNNING, TaskState.VERIFYING)
    assert can_transition(TaskState.VERIFYING, TaskState.COMPLETED)


def test_retry_loop_transition():
    """Verify failed tasks can loop back to planned for controlled retry."""
    assert can_transition(TaskState.RUNNING, TaskState.FAILED)
    assert can_transition(TaskState.FAILED, TaskState.PLANNED)


def test_cancellation_from_active_states():
    """Verify tasks can be cancelled from created, planned, approval, or running states."""
    assert can_transition(TaskState.CREATED, TaskState.CANCELLED)
    assert can_transition(TaskState.PLANNED, TaskState.CANCELLED)
    assert can_transition(TaskState.AWAITING_APPROVAL, TaskState.CANCELLED)
    assert can_transition(TaskState.RUNNING, TaskState.CANCELLED)


def test_illegal_transitions_raise_error():
    """Verify invalid transitions raise InvalidStateTransitionError."""
    # Cannot jump directly from created to completed
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        validate_transition(TaskState.CREATED, TaskState.COMPLETED)
    assert exc_info.value.current_state == TaskState.CREATED
    assert exc_info.value.target_state == TaskState.COMPLETED

    # Cannot transition out of terminal completed state
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TaskState.COMPLETED, TaskState.RUNNING)

    # Cannot transition out of terminal cancelled state
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TaskState.CANCELLED, TaskState.PLANNED)
