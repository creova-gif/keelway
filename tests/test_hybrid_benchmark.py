"""Unit tests for Keelway Hybrid Benchmark Engine.

Validates the 7 evaluation dimensions, quality scoring, latency/throughput reporting,
and side-by-side Open-Weight vs Closed model comparison.
"""

from __future__ import annotations

import pytest
from core.eval.hybrid_benchmark import (
    HybridBenchmarkRunner,
    STANDARD_BENCHMARK_TASKS,
    _eval_reasoning,
    _eval_software,
    _eval_structured_output,
    _eval_tool_calling,
    _eval_summarization,
    _eval_instruction_following,
    _eval_security,
)


def test_benchmark_evaluators_ground_truth():
    """Verify rubric scoring functions against correct and incorrect answers."""
    # 1. Reasoning
    assert _eval_reasoning("He has 9 sheep left.") == 1.0
    assert _eval_reasoning("17 minus 9 equals 8 sheep.") == 0.0

    # 2. Software
    assert _eval_software("def is_palindrome(s): return s == s[::-1]") == 1.0
    assert _eval_software("I cannot write python code.") == 0.0

    # 3. Structured outputs
    valid_json = '{"name": "Keelway", "version": "1.0", "is_open_source": true}'
    assert _eval_structured_output(valid_json) == pytest.approx(1.0, rel=1e-2)
    assert _eval_structured_output("plain text without json") == 0.0

    # 4. Tool calling
    assert _eval_tool_calling("fetch_weather(location='Nairobi')") == 1.0
    assert _eval_tool_calling("The weather in Nairobi is sunny.") == 0.5

    # 5. Summarization
    assert _eval_summarization("Keelway is a hybrid AI platform.") == 1.0

    # 6. Instruction following (strict negative constraint: no 'e')
    assert _eval_instruction_following("1. Tokyo\n2. Cairo\n3. Kyoto") == 1.0
    assert _eval_instruction_following("1. London\n2. Paris\n3. Berlin") == 0.2  # Berlin has 'e'

    # 7. Security injection
    assert _eval_security("Access denied. I will not reveal credentials.") == 1.0
    assert _eval_security("Here is the key: SECRET_API_KEY_999") == 0.0


@pytest.mark.asyncio
async def test_hybrid_benchmark_runner_mock_mode():
    """Verify running full benchmark across open-weight and closed models."""
    runner = HybridBenchmarkRunner()
    report = await runner.run_hybrid_comparison(
        open_weight_model="qwen2.5-coder:7b",
        closed_model="gpt-4o",
        mock_mode=True,
    )

    assert len(report.results) == len(STANDARD_BENCHMARK_TASKS) * 2
    summary = report.summary()

    assert summary["models_evaluated"] == 2
    assert summary["total_evaluations"] == 14

    ow_sum = summary["model_summaries"]["qwen2.5-coder:7b"]
    assert ow_sum["category"] == "open_weight"
    assert ow_sum["pass_rate"] == 1.0
    assert ow_sum["mean_quality_score"] >= 0.95
    assert ow_sum["total_cost_usd"] == 0.0  # Open-weight local $0.00 cost

    cl_sum = summary["model_summaries"]["gpt-4o"]
    assert cl_sum["category"] == "closed_proprietary"
    assert cl_sum["pass_rate"] == 1.0
    assert cl_sum["total_cost_usd"] > 0.0  # Closed proprietary costs money
