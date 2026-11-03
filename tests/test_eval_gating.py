"""Tests for Keelway Evaluation Engine (FR-06).
Validates paired evaluation runner, baseline vs candidate thresholds, and failure gating.
"""
from keelway.evals.engine import EvalEngine


def test_eval_engine_scores_passing_candidate():
    engine = EvalEngine(threshold=0.8)
    res = engine.evaluate(run_id="run_301", force_candidate_score=0.95)
    assert res.passed is True
    assert res.baseline_score == 1.0
    assert res.candidate_score == 0.95
    assert res.threshold == 0.8
    assert res.dataset_digest is not None


def test_eval_engine_fails_candidate_below_threshold():
    engine = EvalEngine(threshold=0.8)
    res = engine.evaluate(run_id="run_302", force_candidate_score=0.6)
    assert res.passed is False
    assert res.details["status"] == "FAIL"


def test_eval_engine_runs_fixtures_with_candidate_fn():
    engine = EvalEngine(threshold=0.6)

    # Candidate function that only handles ping
    def candidate_fn(in_data):
        if in_data.get("cmd") == "ping":
            return "pong"
        return "wrong"

    res = engine.evaluate(run_id="run_303", candidate_fn=candidate_fn)
    # 1 of 3 cases passed = 0.333 < 0.6 threshold -> Fails
    assert res.passed is False
