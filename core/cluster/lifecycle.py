"""
Model Lifecycle Registry (`KEEL-CLUSTER-008`).

Manages canary traffic weights (`0`–`100%`), benchmark + TTFT SLO promotion gates
(`benchmark_pass_rate >= 0.95` and `ttft_p95_ms <= ttft_slo_ms`), and automatic
canary rollback to deprecated state.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

VALID_LIFECYCLE_STAGES = frozenset({"canary", "stable", "deprecated", "retired"})
LifecycleStage = Literal["canary", "stable", "deprecated", "retired"]
MIN_STABLE_BENCHMARK_PASS_RATE = 0.95


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LifecycleModelNotFoundError(ValueError):
    """Raised when referencing an unregistered model in the lifecycle registry."""


class LifecycleGateError(ValueError):
    """Raised when a model promotion violates benchmark pass-rate or TTFT SLO gates."""


class _SubscriptableModel(BaseModel):
    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)


class ModelLifecycleEntry(_SubscriptableModel):
    """Tracked deployment stage, canary split, and SLO metrics for a registered model."""

    model_id: str = Field(..., min_length=1, max_length=255)
    stage: LifecycleStage
    traffic_weight_pct: int = Field(..., ge=0, le=100)
    benchmark_pass_rate: float = Field(..., ge=0.0, le=1.0)
    ttft_p95_ms: float = Field(..., gt=0.0)
    ttft_slo_ms: float = Field(..., gt=0.0)
    fallback_model_id: Optional[str] = None
    rollback_reason: Optional[str] = None
    rolled_back_at: Optional[str] = None
    updated_at: str


DEFAULT_LIFECYCLE_ENTRIES: List[Dict[str, Any]] = [
    {
        "model_id": "keelway-core:7b",
        "stage": "stable",
        "traffic_weight_pct": 100,
        "benchmark_pass_rate": 0.98,
        "ttft_p95_ms": 145.0,
        "ttft_slo_ms": 250.0,
        "fallback_model_id": None,
    },
    {
        "model_id": "keelway-coder:14b-v2",
        "stage": "canary",
        "traffic_weight_pct": 15,
        "benchmark_pass_rate": 0.97,
        "ttft_p95_ms": 210.0,
        "ttft_slo_ms": 300.0,
        "fallback_model_id": "qwen2.5-coder:7b",
    },
    {
        "model_id": "qwen2.5-coder:7b",
        "stage": "stable",
        "traffic_weight_pct": 100,
        "benchmark_pass_rate": 0.96,
        "ttft_p95_ms": 165.0,
        "ttft_slo_ms": 250.0,
        "fallback_model_id": "keelway-core:7b",
    },
]


class ModelLifecycleRegistry:
    """Thread-safe model deployment lifecycle registry with benchmark & latency promotion gates."""

    def __init__(self, seed_defaults: bool = True) -> None:
        self._lock = threading.RLock()
        self._entries: Dict[str, ModelLifecycleEntry] = {}
        if seed_defaults:
            for spec in DEFAULT_LIFECYCLE_ENTRIES:
                self.register_entry(**spec)

    def list_entries(self, stage: Optional[str] = None) -> List[ModelLifecycleEntry]:
        """List tracked model lifecycle entries, optionally filtered by stage."""
        with self._lock:
            items = list(self._entries.values())
        if stage is not None:
            items = [entry for entry in items if entry.stage == stage]
        return [entry.model_copy(deep=True) for entry in items]

    def get_entry(self, model_id: str) -> ModelLifecycleEntry:
        """Return a model lifecycle entry or raise LifecycleModelNotFoundError."""
        with self._lock:
            entry = self._entries.get(model_id)
            if entry is None:
                raise LifecycleModelNotFoundError(f"Model '{model_id}' is not registered in lifecycle registry.")
            return entry.model_copy(deep=True)

    def register_entry(
        self,
        model_id: str,
        stage: str = "canary",
        traffic_weight_pct: int = 10,
        benchmark_pass_rate: float = 0.96,
        ttft_p95_ms: float = 180.0,
        ttft_slo_ms: float = 300.0,
        fallback_model_id: Optional[str] = "keelway-core:7b",
    ) -> ModelLifecycleEntry:
        """Register or update telemetry/stage metadata for a model."""
        clean_id = model_id.strip()
        if not clean_id:
            raise ValueError("model_id must be a non-empty string.")
        if stage not in VALID_LIFECYCLE_STAGES:
            raise ValueError(f"Unsupported stage '{stage}'. Must be one of {sorted(VALID_LIFECYCLE_STAGES)}.")
        if not (0 <= int(traffic_weight_pct) <= 100):
            raise ValueError("traffic_weight_pct must be between 0 and 100.")
        if not (0.0 <= float(benchmark_pass_rate) <= 1.0):
            raise ValueError("benchmark_pass_rate must be between 0.0 and 1.0.")
        if ttft_p95_ms <= 0 or ttft_slo_ms <= 0:
            raise ValueError("ttft_p95_ms and ttft_slo_ms must be greater than 0.")

        entry = ModelLifecycleEntry(
            model_id=clean_id,
            stage=stage,  # type: ignore[arg-type]
            traffic_weight_pct=int(traffic_weight_pct),
            benchmark_pass_rate=round(float(benchmark_pass_rate), 4),
            ttft_p95_ms=round(float(ttft_p95_ms), 2),
            ttft_slo_ms=round(float(ttft_slo_ms), 2),
            fallback_model_id=fallback_model_id,
            updated_at=_utc_now_iso(),
        )
        with self._lock:
            self._entries[clean_id] = entry
            return entry.model_copy(deep=True)

    def promote_model(
        self,
        model_id: str,
        target_stage: str = "stable",
        traffic_weight_pct: int = 100,
    ) -> ModelLifecycleEntry:
        """
        Promote a model to target_stage after enforcing benchmark >= 0.95 and TTFT SLO gates.

        Raises ValueError (LifecycleGateError / LifecycleModelNotFoundError) if gates fail.
        """
        if target_stage not in VALID_LIFECYCLE_STAGES:
            raise ValueError(f"Unsupported target_stage '{target_stage}'.")
        if not (0 <= int(traffic_weight_pct) <= 100):
            raise ValueError("traffic_weight_pct must be between 0 and 100.")

        with self._lock:
            entry = self._entries.get(model_id)
            if entry is None:
                raise LifecycleModelNotFoundError(f"Model '{model_id}' is not registered in lifecycle registry.")
            if entry.stage == "retired":
                raise LifecycleGateError(f"Cannot promote retired model '{model_id}' without re-registration.")

            if target_stage == "stable":
                if entry.benchmark_pass_rate < MIN_STABLE_BENCHMARK_PASS_RATE:
                    raise LifecycleGateError(
                        f"Promotion gate failed for '{model_id}': benchmark_pass_rate "
                        f"{entry.benchmark_pass_rate:.3f} < {MIN_STABLE_BENCHMARK_PASS_RATE:.2f}."
                    )
                if entry.ttft_p95_ms > entry.ttft_slo_ms:
                    raise LifecycleGateError(
                        f"Promotion gate failed for '{model_id}': ttft_p95_ms "
                        f"({entry.ttft_p95_ms:.1f}ms) exceeds ttft_slo_ms ({entry.ttft_slo_ms:.1f}ms)."
                    )

            updated = entry.model_copy(
                update={
                    "stage": target_stage,
                    "traffic_weight_pct": int(traffic_weight_pct),
                    "rollback_reason": None if target_stage in ("canary", "stable") else entry.rollback_reason,
                    "rolled_back_at": None if target_stage in ("canary", "stable") else entry.rolled_back_at,
                    "updated_at": _utc_now_iso(),
                },
                deep=True,
            )
            self._entries[model_id] = updated
            return updated.model_copy(deep=True)

    def rollback_canary(self, model_id: str, reason: str) -> ModelLifecycleEntry:
        """Immediately halt traffic (`0%`), mark model `deprecated`, and record rollback reason + timestamp."""
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValueError("Rollback reason must be a non-empty string.")

        now_iso = _utc_now_iso()
        with self._lock:
            entry = self._entries.get(model_id)
            if entry is None:
                raise LifecycleModelNotFoundError(f"Model '{model_id}' is not registered in lifecycle registry.")
            updated = entry.model_copy(
                update={
                    "stage": "deprecated",
                    "traffic_weight_pct": 0,
                    "rollback_reason": clean_reason,
                    "rolled_back_at": now_iso,
                    "updated_at": now_iso,
                },
                deep=True,
            )
            self._entries[model_id] = updated
            return updated.model_copy(deep=True)


model_lifecycle_registry = ModelLifecycleRegistry()
