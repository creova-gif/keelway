"""
Keelway Task State Machine

Explicit states, deterministic transitions, and recovery rules.
Aligned with KEELWAY.md: 'Prefer explicit state over opaque agent loops'.
"""

from enum import Enum
from typing import Dict, Set


class TaskState(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    def __init__(self, current_state: TaskState, target_state: TaskState):
        super().__init__(
            f"Invalid task state transition from '{current_state.value}' to '{target_state.value}'."
        )
        self.current_state = current_state
        self.target_state = target_state


# Explicit deterministic transition graph
VALID_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.CREATED: {TaskState.PLANNED, TaskState.CANCELLED},
    TaskState.PLANNED: {TaskState.AWAITING_APPROVAL, TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.AWAITING_APPROVAL: {TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.VERIFYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.PLANNED},
    TaskState.FAILED: {TaskState.PLANNED, TaskState.CANCELLED},  # Retry loops back to planned
    TaskState.COMPLETED: set(),  # Terminal state
    TaskState.CANCELLED: set(),  # Terminal state
}


def can_transition(current: TaskState, target: TaskState) -> bool:
    """Check whether a transition between two states is valid."""
    return target in VALID_TRANSITIONS.get(current, set())


def validate_transition(current: TaskState, target: TaskState) -> None:
    """Validate transition, raising InvalidStateTransitionError if illegal."""
    if not can_transition(current, target):
        raise InvalidStateTransitionError(current_state=current, target_state=target)
