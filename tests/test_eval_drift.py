"""
Tests for Keelway Evaluation Receipts & Drift Detection Engine (WP13 / Section 13).
Verifies golden benchmark receipt issuance, cryptographic seals, historic storage,
and drift detection for both Pass@1 accuracy drops and latency percentiles.
"""
import copy
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from evals.drift_detector import (
    EvaluationReceipt,
    DriftAnalysis,
    EvaluationReceiptStore,
    DriftDetector,
)
from core.main import app


@pytest.mark.asyncio
async def test_evaluation_receipt_generation(tmp_path):
    store = EvaluationReceiptStore(receipts_dir=tmp_path / "receipts")
    receipt = await DriftDetector.run_evaluation_and_create_receipt(
        model_name="test-local-model",
        eval_run_id="eval_test_01",
        store=store,
    )
    assert receipt.eval_run_id == "eval_test_01"
    assert receipt.total_tasks == 10
    assert receipt.passed_tasks == 9
    assert receipt.pass_rate_pct == 90.0
    assert len(receipt.receipt_sha256) == 64
    assert receipt.receipt_sha256 == receipt.calculate_sha256()

    # Verify persistence
    saved_file = tmp_path / "receipts" / "eval_test_01.receipt.json"
    assert saved_file.exists()

    loaded = store.get_receipt("eval_test_01")
    assert loaded is not None
    assert loaded.receipt_sha256 == receipt.receipt_sha256


def test_receipt_store_operations(tmp_path):
    store = EvaluationReceiptStore(receipts_dir=tmp_path / "receipts")

    r1 = EvaluationReceipt(
        eval_run_id="run_01",
        timestamp_utc="2026-11-04T00:00:00Z",
        model_name="model-a",
        total_tasks=10,
        passed_tasks=10,
        pass_rate_pct=100.0,
        total_duration_ms=4.0,
        p50_latency_ms=0.3,
        p95_latency_ms=0.7,
        task_results=[{"task_id": "EVAL-01", "passed": True}],
    )
    store.save_receipt(r1)

    r2 = EvaluationReceipt(
        eval_run_id="run_02",
        timestamp_utc="2026-11-04T01:00:00Z",
        model_name="model-b",
        total_tasks=10,
        passed_tasks=9,
        pass_rate_pct=90.0,
        total_duration_ms=5.0,
        p50_latency_ms=0.4,
        p95_latency_ms=0.9,
        task_results=[{"task_id": "EVAL-01", "passed": False}],
    )
    store.save_receipt(r2)

    receipts = store.list_receipts()
    assert len(receipts) == 2
    # Ordered descending by timestamp
    assert receipts[0]["eval_run_id"] == "run_02"
    assert receipts[1]["eval_run_id"] == "run_01"

    latest = store.get_latest_baseline()
    assert latest.eval_run_id == "run_02"


def test_drift_detector_clean_pass():
    r1 = EvaluationReceipt(
        eval_run_id="base",
        timestamp_utc="2026-11-04T00:00:00Z",
        model_name="model-a",
        total_tasks=2,
        passed_tasks=2,
        pass_rate_pct=100.0,
        total_duration_ms=2.0,
        p50_latency_ms=0.2,
        p95_latency_ms=0.4,
        task_results=[{"task_id": "EVAL-01", "passed": True}, {"task_id": "EVAL-02", "passed": True}],
    )
    r2 = copy.deepcopy(r1)
    r2.eval_run_id = "cand"

    analysis = DriftDetector.compare(r1, r2)
    assert analysis.drift_detected is False
    assert analysis.drift_severity == "NONE"
    assert analysis.pass_rate_delta == 0.0
    assert len(analysis.regressed_tasks) == 0


def test_drift_detector_detects_task_regression():
    r1 = EvaluationReceipt(
        eval_run_id="base",
        timestamp_utc="2026-11-04T00:00:00Z",
        model_name="model-a",
        total_tasks=2,
        passed_tasks=2,
        pass_rate_pct=100.0,
        total_duration_ms=2.0,
        p50_latency_ms=0.2,
        p95_latency_ms=0.4,
        task_results=[{"task_id": "EVAL-01", "passed": True}, {"task_id": "EVAL-02", "passed": True}],
    )
    r2 = EvaluationReceipt(
        eval_run_id="cand",
        timestamp_utc="2026-11-04T01:00:00Z",
        model_name="model-b",
        total_tasks=2,
        passed_tasks=1,
        pass_rate_pct=50.0,
        total_duration_ms=2.0,
        p50_latency_ms=0.2,
        p95_latency_ms=0.4,
        task_results=[{"task_id": "EVAL-01", "passed": True}, {"task_id": "EVAL-02", "passed": False}],
    )

    analysis = DriftDetector.compare(r1, r2)
    assert analysis.drift_detected is True
    assert analysis.drift_severity == "CRITICAL"
    assert "EVAL-02" in analysis.regressed_tasks
    assert analysis.pass_rate_delta == -50.0


def test_drift_detector_detects_latency_degradation():
    r1 = EvaluationReceipt(
        eval_run_id="base",
        timestamp_utc="2026-11-04T00:00:00Z",
        model_name="model-a",
        total_tasks=1,
        passed_tasks=1,
        pass_rate_pct=100.0,
        total_duration_ms=1.0,
        p50_latency_ms=10.0,
        p95_latency_ms=15.0,
        task_results=[{"task_id": "EVAL-01", "passed": True}],
    )
    r2 = EvaluationReceipt(
        eval_run_id="cand",
        timestamp_utc="2026-11-04T01:00:00Z",
        model_name="model-a-slow",
        total_tasks=1,
        passed_tasks=1,
        pass_rate_pct=100.0,
        total_duration_ms=2.0,
        p50_latency_ms=20.0,  # +100% latency increase
        p95_latency_ms=25.0,
        task_results=[{"task_id": "EVAL-01", "passed": True}],
    )

    analysis = DriftDetector.compare(r1, r2, max_latency_degradation_pct=25.0)
    assert analysis.drift_detected is True
    assert analysis.drift_severity == "MEDIUM"
    assert analysis.latency_p50_delta_pct == 100.0
    assert any("p50 latency degraded by 100.0%" in a for a in analysis.alert_reasons)


def test_eval_api_endpoints():
    client = TestClient(app)

    # 1. Run evaluation
    res_run = client.post("/v1/evals/run", json={"model_name": "api-eval-model", "save_receipt": True})
    assert res_run.status_code == 200
    cand_data = res_run.json()
    assert cand_data["pass_rate_pct"] == 90.0
    assert len(cand_data["receipt_sha256"]) == 64
    cand_id = cand_data["eval_run_id"]

    # 2. List history
    res_hist = client.get("/v1/evals/history")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert any(h["eval_run_id"] == cand_id for h in history)

    # 3. Drift compare
    # Run a second eval to establish baseline + candidate
    res_run2 = client.post("/v1/evals/run", json={"model_name": "api-eval-model-2", "save_receipt": True})
    assert res_run2.status_code == 200
    cand2_id = res_run2.json()["eval_run_id"]

    res_comp = client.post(
        "/v1/evals/drift/compare",
        json={"candidate_run_id": cand2_id, "baseline_run_id": cand_id},
    )
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["candidate_run_id"] == cand2_id
    assert comp_data["baseline_run_id"] == cand_id
    assert "drift_detected" in comp_data
