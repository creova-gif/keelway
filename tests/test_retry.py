"""Tests for Keelway Bounded Retry and Idempotency Handler (PRD-001).
Validates bounded retries for idempotent actions and prohibition of double tool execution.
"""
import pytest

from keelway.core.retry import (
    IdempotentRetryHandler,
    MaxRetriesExceededError,
    NonIdempotentRetryError,
)


def test_retry_succeeds_on_transient_failure_for_idempotent_action():
    handler = IdempotentRetryHandler(max_retries=2, base_delay_seconds=0.01)
    call_count = 0

    def flaky_model_call():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("Upstream timeout")
        return "model_output_success"

    result = handler.execute_with_retry("model.generate", flaky_model_call)
    assert result == "model_output_success"
    assert call_count == 2


def test_retry_prohibits_automatic_retry_for_side_effecting_action():
    handler = IdempotentRetryHandler(max_retries=3)
    call_count = 0

    def failing_write():
        nonlocal call_count
        call_count += 1
        raise IOError("Disk write glitch")

    # git.write_patch is NOT in the idempotent actions set
    with pytest.raises(NonIdempotentRetryError) as exc_info:
        handler.execute_with_retry("git.write_patch", failing_write)

    assert "automatic retry prohibited" in str(exc_info.value)
    # Proves no double tool execution occurred
    assert call_count == 1


def test_retry_idempotency_key_deduplication():
    handler = IdempotentRetryHandler()
    call_count = 0

    def perform_action():
        nonlocal call_count
        call_count += 1
        return f"result_{call_count}"

    # First call with idempotency key
    res1 = handler.execute_with_retry(
        "git.diff", perform_action, idempotency_key="key_diff_1"
    )
    assert res1 == "result_1"
    assert call_count == 1

    # Second call with same idempotency key returns cached result without re-executing
    res2 = handler.execute_with_retry(
        "git.diff", perform_action, idempotency_key="key_diff_1"
    )
    assert res2 == "result_1"
    assert call_count == 1
