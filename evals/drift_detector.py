"""
Keelway Evaluation Receipts & Drift Detection Engine (WP13 / Section 13).
Tracks Pass@1 benchmark stability, latency percentiles, and detects quality regressions
across model revisions, prompts, and local runtime updates with cryptographic receipts.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from evals.eval_runner import ProductionEvalHarness


@dataclass
class EvaluationReceipt:
    eval_run_id: str
    timestamp_utc: str
    model_name: str
    total_tasks: int
    passed_tasks: int
    pass_rate_pct: float
    total_duration_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    task_results: List[Dict[str, Any]]
    receipt_sha256: str = ""

    def calculate_sha256(self) -> str:
        payload = {
            "eval_run_id": self.eval_run_id,
            "timestamp_utc": self.timestamp_utc,
            "model_name": self.model_name,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "pass_rate_pct": self.pass_rate_pct,
            "total_duration_ms": self.total_duration_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "task_results": self.task_results,
        }
        canonical_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data.get("receipt_sha256"):
            data["receipt_sha256"] = self.calculate_sha256()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvaluationReceipt:
        receipt = cls(
            eval_run_id=data["eval_run_id"],
            timestamp_utc=data["timestamp_utc"],
            model_name=data.get("model_name", "keelway-local-default"),
            total_tasks=data["total_tasks"],
            passed_tasks=data["passed_tasks"],
            pass_rate_pct=data["pass_rate_pct"],
            total_duration_ms=data["total_duration_ms"],
            p50_latency_ms=data.get("p50_latency_ms", 0.0),
            p95_latency_ms=data.get("p95_latency_ms", 0.0),
            task_results=data.get("task_results", []),
            receipt_sha256=data.get("receipt_sha256", ""),
        )
        if not receipt.receipt_sha256:
            receipt.receipt_sha256 = receipt.calculate_sha256()
        return receipt


@dataclass
class DriftAnalysis:
    baseline_run_id: str
    candidate_run_id: str
    baseline_pass_rate: float
    candidate_pass_rate: float
    pass_rate_delta: float
    baseline_p50_ms: float
    candidate_p50_ms: float
    latency_p50_delta_pct: float
    drift_detected: bool
    drift_severity: str  # "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    regressed_tasks: List[str]
    alert_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvaluationReceiptStore:
    """Persistent storage and retrieval for signed evaluation receipts."""

    def __init__(self, receipts_dir: Optional[Path] = None):
        self.receipts_dir = Path(receipts_dir or ".keelway/evals/receipts").resolve()
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def save_receipt(self, receipt: EvaluationReceipt) -> Path:
        """Persist evaluation receipt to disk with SHA-256 seal."""
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        if not receipt.receipt_sha256:
            receipt.receipt_sha256 = receipt.calculate_sha256()
        file_path = self.receipts_dir / f"{receipt.eval_run_id}.receipt.json"
        file_path.write_text(json.dumps(receipt.to_dict(), indent=2), encoding="utf-8")
        return file_path

    def get_receipt(self, eval_run_id: str) -> Optional[EvaluationReceipt]:
        """Load an evaluation receipt by run ID."""
        file_path = self.receipts_dir / f"{eval_run_id}.receipt.json"
        if not file_path.exists():
            return None
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return EvaluationReceipt.from_dict(data)

    def list_receipts(self) -> List[Dict[str, Any]]:
        """List all stored evaluation receipts ordered by timestamp descending."""
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        receipts = []
        for f in self.receipts_dir.glob("*.receipt.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                receipts.append({
                    "eval_run_id": data.get("eval_run_id"),
                    "timestamp_utc": data.get("timestamp_utc"),
                    "model_name": data.get("model_name"),
                    "pass_rate_pct": data.get("pass_rate_pct"),
                    "p50_latency_ms": data.get("p50_latency_ms"),
                    "total_duration_ms": data.get("total_duration_ms"),
                    "receipt_sha256": data.get("receipt_sha256"),
                    "file_path": str(f),
                })
            except Exception:
                pass
        receipts.sort(key=lambda r: r.get("timestamp_utc", ""), reverse=True)
        return receipts

    def get_latest_baseline(self) -> Optional[EvaluationReceipt]:
        """Fetch the most recent receipt to serve as comparative baseline."""
        all_r = self.list_receipts()
        if not all_r:
            return None
        return self.get_receipt(all_r[0]["eval_run_id"])


class DriftDetector:
    """Compares candidate evaluation receipts against historic baseline to detect drift."""

    @classmethod
    def compute_percentiles(cls, latencies: List[float]) -> Tuple[float, float]:
        if not latencies:
            return 0.0, 0.0
        sorted_l = sorted(latencies)
        p50 = statistics.median(sorted_l)
        idx_95 = int(len(sorted_l) * 0.95)
        p95 = sorted_l[min(idx_95, len(sorted_l) - 1)]
        return round(p50, 2), round(p95, 2)

    @classmethod
    async def run_evaluation_and_create_receipt(
        cls,
        model_name: str = "keelway-local-default",
        eval_run_id: Optional[str] = None,
        store: Optional[EvaluationReceiptStore] = None,
    ) -> EvaluationReceipt:
        """Execute the 10-task golden benchmark and generate a sealed EvaluationReceipt."""
        harness = ProductionEvalHarness()
        summary = await harness.run_all()

        latencies = [t["duration_ms"] for t in summary["tasks"]]
        p50, p95 = cls.compute_percentiles(latencies)

        now_iso = datetime.now(timezone.utc).isoformat()
        run_id = eval_run_id or f"eval_{int(time.time() * 1000)}"

        receipt = EvaluationReceipt(
            eval_run_id=run_id,
            timestamp_utc=now_iso,
            model_name=model_name,
            total_tasks=summary["total_tasks"],
            passed_tasks=summary["passed_tasks"],
            pass_rate_pct=summary["pass_rate_pct"],
            total_duration_ms=summary["total_duration_ms"],
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            task_results=summary["tasks"],
        )
        receipt.receipt_sha256 = receipt.calculate_sha256()

        if store is not None:
            store.save_receipt(receipt)

        return receipt

    @classmethod
    def compare(
        cls,
        baseline: EvaluationReceipt,
        candidate: EvaluationReceipt,
        max_latency_degradation_pct: float = 25.0,
    ) -> DriftAnalysis:
        """Analyze differences between baseline and candidate for regressions or drift."""
        pass_rate_delta = round(candidate.pass_rate_pct - baseline.pass_rate_pct, 2)
        
        # Latency delta
        if baseline.p50_latency_ms > 0:
            lat_delta_pct = round(((candidate.p50_latency_ms - baseline.p50_latency_ms) / baseline.p50_latency_ms) * 100.0, 1)
        else:
            lat_delta_pct = 0.0

        # Check task regressions: passed in baseline, failed in candidate
        base_tasks = {t["task_id"]: t["passed"] for t in baseline.task_results}
        cand_tasks = {t["task_id"]: t["passed"] for t in candidate.task_results}

        regressed: List[str] = []
        for tid, base_passed in base_tasks.items():
            cand_passed = cand_tasks.get(tid, False)
            if base_passed and not cand_passed:
                regressed.append(tid)

        alerts: List[str] = []
        severity = "NONE"
        drift_detected = False

        if regressed:
            drift_detected = True
            severity = "CRITICAL"
            alerts.append(f"Golden benchmark task regression detected: {', '.join(regressed)} failed in candidate!")

        if pass_rate_delta < 0:
            drift_detected = True
            if severity != "CRITICAL":
                severity = "HIGH"
            alerts.append(f"Pass@1 rate dropped by {abs(pass_rate_delta)}% (from {baseline.pass_rate_pct}% to {candidate.pass_rate_pct}%)")

        if lat_delta_pct > max_latency_degradation_pct:
            drift_detected = True
            if severity not in ("CRITICAL", "HIGH"):
                severity = "MEDIUM"
            alerts.append(f"p50 latency degraded by {lat_delta_pct}% (threshold: +{max_latency_degradation_pct}%)")

        return DriftAnalysis(
            baseline_run_id=baseline.eval_run_id,
            candidate_run_id=candidate.eval_run_id,
            baseline_pass_rate=baseline.pass_rate_pct,
            candidate_pass_rate=candidate.pass_rate_pct,
            pass_rate_delta=pass_rate_delta,
            baseline_p50_ms=baseline.p50_latency_ms,
            candidate_p50_ms=candidate.p50_latency_ms,
            latency_p50_delta_pct=lat_delta_pct,
            drift_detected=drift_detected,
            drift_severity=severity,
            regressed_tasks=regressed,
            alert_reasons=alerts,
        )
