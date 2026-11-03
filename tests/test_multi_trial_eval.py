"""Tests for Keelway Multi-Trial Evaluation Suite (PRD-001 Section 76).
Validates repeated trials, confidence interval calculations, and statistical gating.
"""
from keelway.evals.suite import MultiTrialEvalRunner


def test_multi_trial_eval_statistical_calculations_and_passing():
    runner = MultiTrialEvalRunner(trials=5, threshold=0.8)

    # Simulated trials with consistent passing scores
    simulated = [0.90, 0.95, 0.92, 0.94, 0.91]
    summary = runner.run_multi_trial(run_id="run_eval_stat_01", simulated_scores=simulated)

    assert summary.trials_count == 5
    assert summary.mean_score >= 0.9
    assert summary.median_score >= 0.9
    assert summary.std_dev < 0.05
    assert summary.passed is True
    assert summary.ci_lower_95 > 0.8
    assert summary.details["status"] == "PASS"


def test_multi_trial_eval_fails_when_scores_below_threshold():
    runner = MultiTrialEvalRunner(trials=3, threshold=0.85)

    # Flaky/failing candidate
    simulated = [0.70, 0.65, 0.80]
    summary = runner.run_multi_trial(run_id="run_eval_stat_02", simulated_scores=simulated)

    assert summary.passed is False
    assert summary.mean_score < 0.85
    assert summary.details["status"] == "FAIL"
