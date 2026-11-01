"""
Standard library unittest verification for Keelway Task State Machine.
Runs in clean Python environments without third-party dependencies.
"""

import unittest
from core.orchestration.state import (
    TaskState,
    InvalidStateTransitionError,
    can_transition,
    validate_transition,
)


class TestTaskStateMachine(unittest.TestCase):
    def test_happy_path(self):
        self.assertTrue(can_transition(TaskState.CREATED, TaskState.PLANNED))
        self.assertTrue(can_transition(TaskState.PLANNED, TaskState.AWAITING_APPROVAL))
        self.assertTrue(can_transition(TaskState.AWAITING_APPROVAL, TaskState.RUNNING))
        self.assertTrue(can_transition(TaskState.RUNNING, TaskState.VERIFYING))
        self.assertTrue(can_transition(TaskState.VERIFYING, TaskState.COMPLETED))

    def test_retry_path(self):
        self.assertTrue(can_transition(TaskState.RUNNING, TaskState.FAILED))
        self.assertTrue(can_transition(TaskState.FAILED, TaskState.PLANNED))

    def test_cancellation(self):
        self.assertTrue(can_transition(TaskState.CREATED, TaskState.CANCELLED))
        self.assertTrue(can_transition(TaskState.PLANNED, TaskState.CANCELLED))
        self.assertTrue(can_transition(TaskState.AWAITING_APPROVAL, TaskState.CANCELLED))
        self.assertTrue(can_transition(TaskState.RUNNING, TaskState.CANCELLED))

    def test_illegal_transition(self):
        with self.assertRaises(InvalidStateTransitionError):
            validate_transition(TaskState.CREATED, TaskState.COMPLETED)

        with self.assertRaises(InvalidStateTransitionError):
            validate_transition(TaskState.COMPLETED, TaskState.RUNNING)

        with self.assertRaises(InvalidStateTransitionError):
            validate_transition(TaskState.CANCELLED, TaskState.PLANNED)


if __name__ == "__main__":
    unittest.main()
