"""Keelway Bounded Retry and Idempotency Engine.
Implements PRD-001 Edge Case: Bounded retries for idempotent queries,
and strict prevention of duplicate execution for side-effecting tools.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Set, Tuple


class NonIdempotentRetryError(Exception):
    pass


class MaxRetriesExceededError(Exception):
    pass


class IdempotentRetryHandler:
    """Manages bounded exponential retries while preventing double tool execution."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: float = 0.05,
        idempotent_actions: Optional[Set[str]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.idempotent_actions = idempotent_actions or {
            "model.query",
            "model.generate",
            "git.read",
            "git.diff",
            "eval.run",
            "audit.verify",
        }
        self._executed_idempotency_keys: Dict[str, Any] = {}

    def execute_with_retry(
        self,
        action_name: str,
        fn: Callable[[], Any],
        idempotency_key: Optional[str] = None,
    ) -> Any:
        """Executes an operation with bounded retries if idempotent."""
        # 1. If an idempotency key was supplied and already executed, return cached result
        if idempotency_key and idempotency_key in self._executed_idempotency_keys:
            return self._executed_idempotency_keys[idempotency_key]

        # 2. Check if action is allowed to retry on failure
        is_idempotent = action_name in self.idempotent_actions

        attempts = 0
        last_exception: Optional[Exception] = None

        while attempts <= self.max_retries:
            try:
                result = fn()
                if idempotency_key:
                    self._executed_idempotency_keys[idempotency_key] = result
                return result
            except Exception as e:
                attempts += 1
                last_exception = e

                # Side-effecting actions MUST NOT retry automatically
                if not is_idempotent:
                    raise NonIdempotentRetryError(
                        f"Action '{action_name}' is non-idempotent; automatic retry prohibited: {e}"
                    ) from e

                if attempts > self.max_retries:
                    break

                # Sleep bounded exponential backoff
                sleep_time = self.base_delay_seconds * (2 ** (attempts - 1))
                time.sleep(sleep_time)

        raise MaxRetriesExceededError(
            f"Action '{action_name}' failed after {self.max_retries} retries: {last_exception}"
        ) from last_exception
