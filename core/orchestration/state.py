"""
Keelway Task State Machine

Explicit states, deterministic transitions, and recovery rules.
Aligned with KEELWAY.md: 'Prefer explicit state over opaque agent loops'.
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class TaskState(str, Enum):
    CREATED = "created"
    CONTEXT_LOADING = "context_loading"
    PLANNING = "planning"
    PLANNED = "planned"
    PLAN_READY = "plan_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    PAUSED = "paused"
    BLOCKED = "blocked"
    AWAITING_RETRY = "awaiting_retry"
    TIMED_OUT = "timed_out"
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


# Explicit deterministic transition graph (PRD-001 & Section 7.2)
VALID_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.CREATED: {TaskState.PLANNED, TaskState.CONTEXT_LOADING, TaskState.PLANNING, TaskState.CANCELLED},
    TaskState.CONTEXT_LOADING: {TaskState.PLANNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PLANNING: {TaskState.PLANNED, TaskState.PLAN_READY, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PLANNED: {TaskState.AWAITING_APPROVAL, TaskState.RUNNING, TaskState.EXECUTING, TaskState.CANCELLED},
    TaskState.PLAN_READY: {TaskState.AWAITING_APPROVAL, TaskState.RUNNING, TaskState.EXECUTING, TaskState.CANCELLED},
    TaskState.AWAITING_APPROVAL: {TaskState.RUNNING, TaskState.EXECUTING, TaskState.BLOCKED, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.VERIFYING, TaskState.PAUSED, TaskState.BLOCKED, TaskState.TIMED_OUT, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.PAUSED, TaskState.BLOCKED, TaskState.TIMED_OUT, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PAUSED: {TaskState.RUNNING, TaskState.EXECUTING, TaskState.CANCELLED},
    TaskState.BLOCKED: {TaskState.AWAITING_APPROVAL, TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.PLANNED},
    TaskState.FAILED: {TaskState.PLANNED, TaskState.AWAITING_RETRY, TaskState.CANCELLED},
    TaskState.AWAITING_RETRY: {TaskState.PLANNED, TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.TIMED_OUT: {TaskState.PLANNED, TaskState.AWAITING_RETRY, TaskState.CANCELLED},
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


class TaskStateMachine:
    """State machine coordinator for deterministic task state transitions."""

    def __init__(self, task_id: str, initial_state: TaskState = TaskState.CREATED):
        self.task_id = task_id
        self.state = initial_state
        self.history: List[Dict[str, Any]] = [
            {"state": initial_state.value, "timestamp": time.time(), "metadata": {}}
        ]

    def transition(self, target_state: TaskState, metadata: Optional[Dict[str, Any]] = None) -> TaskState:
        validate_transition(self.state, target_state)
        self.state = target_state
        self.history.append({
            "state": target_state.value,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        return self.state
