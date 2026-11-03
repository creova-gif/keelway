"""Keelway Multi-Trial Evaluation Suite with Statistical Gating.
Implements PRD-001 Edge Case: Repeated trials, deterministic golden replay,
and confidence intervals to resolve eval nondeterminism.
"""
from __future__ import annotations

import math
import statistics
import uuid
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel

from keelway.evals.engine import EvalEngine


class MultiTrialEvalSummary(BaseModel):
    eval_id: str
    run_id: str
    dataset_id: str
    trials_count: int
    scores: List[float]
    mean_score: float
    median_score: float
    std_dev: float
    ci_lower_95: float
    ci_upper_95: float
    threshold: float
    passed: bool
    details: Dict[str, Any]


class MultiTrialEvalRunner:
    """Executes repeated evaluation trials over versioned datasets."""

    def __init__(self, engine: Optional[EvalEngine] = None, trials: int = 3, threshold: float = 0.8):
        self.engine = engine or EvalEngine(threshold=threshold)
        self.trials = max(1, trials)
        self.threshold = threshold

    def run_multi_trial(
        self,
        run_id: str,
        candidate_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        simulated_scores: Optional[List[float]] = None,
    ) -> MultiTrialEvalSummary:
        """Executes repeated trials and calculates mean, standard deviation, and confidence intervals."""
        scores: List[float] = []

        if simulated_scores:
            scores = simulated_scores
        else:
            for _ in range(self.trials):
                res = self.engine.evaluate(run_id=run_id, candidate_fn=candidate_fn)
                scores.append(res.candidate_score)

        mean_val = statistics.mean(scores)
        median_val = statistics.median(scores)
        std_val = statistics.stdev(scores) if len(scores) > 1 else 0.0

        # Compute 95% confidence interval: mean +/- 1.96 * (std / sqrt(n))
        se = std_val / math.sqrt(len(scores)) if len(scores) > 1 else 0.0
        ci_lower = max(0.0, round(mean_val - 1.96 * se, 4))
        ci_upper = min(1.0, round(mean_val + 1.96 * se, 4))

        # Gating condition: mean score meets threshold AND median meets threshold
        passed = (mean_val >= self.threshold) and (median_val >= self.threshold)

        return MultiTrialEvalSummary(
            eval_id=str(uuid.uuid4()),
            run_id=run_id,
            dataset_id=self.engine.dataset_id,
            trials_count=len(scores),
            scores=scores,
            mean_score=round(mean_val, 4),
            median_score=round(median_val, 4),
            std_dev=round(std_val, 4),
            ci_lower_95=ci_lower,
            ci_upper_95=ci_upper,
            threshold=self.threshold,
            passed=passed,
            details={
                "dataset_digest": self.engine.get_dataset_digest(),
                "status": "PASS" if passed else "FAIL",
                "trials_raw": scores,
            },
        )
