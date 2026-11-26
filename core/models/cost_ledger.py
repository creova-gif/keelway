"""
Keelway Model Economics & Cost Ledger.

Tracks every model inference across local and cloud providers with append-only
audit entries, cumulative token accounting, latency percentiles (p50/p90/p95/p99),
cloud API billing, and quantified local-first savings.

Local inference is explicitly labeled: "no billed external API tokens".
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from core.api.schemas import Provider

PRICE_SOURCE_VERSION = "pricing_v2026.1"

# Standard reference pricing per million tokens (input, output) in USD.
REFERENCE_PRICING: Dict[str, Tuple[float, float]] = {
    Provider.ANTHROPIC.value: (3.00, 15.00),     # Claude 3.5 / 3.7 Sonnet
    Provider.OPENAI.value: (2.50, 10.00),        # GPT-4o
    Provider.GOOGLE.value: (0.075, 0.30),        # Gemini 1.5 Flash
    Provider.LOCAL.value: (0.0, 0.0),            # Local device ($0 billed API)
    Provider.OPEN_WEIGHT.value: (0.0, 0.0),      # Self-hosted open weights
    "deepseek": (0.14, 0.28),                    # DeepSeek V3
    "ollama": (0.0, 0.0),                        # Local Ollama runner
    "vllm": (0.0, 0.0),                          # Local vLLM runner
}

# Granular model rate cards per million tokens: (input_usd, output_usd)
MODEL_RATE_CARDS: Dict[str, Tuple[float, float]] = {
    # Anthropic
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o1": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    # Google
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    # DeepSeek
    "deepseek-v3": (0.14, 0.28),
    "deepseek-r1": (0.55, 2.19),
    # Local & Sovereign (Ollama / vLLM / llama.cpp / Apple Silicon / CUDA) - $0.00 external API billing
    "qwen2.5-coder": (0.0, 0.0),
    "llama-3.3": (0.0, 0.0),
    "deepseek-r1-distill": (0.0, 0.0),
    "local": (0.0, 0.0),
}


def resolve_model_rates(provider: str, model: str) -> Tuple[float, float]:
    """Resolve token rates (input_usd_per_mtok, output_usd_per_mtok) by model name or provider fallback."""
    provider_clean = (provider.value if isinstance(provider, Provider) else str(provider)).lower().strip()
    model_clean = (model or "").lower().strip()

    if model_clean in MODEL_RATE_CARDS:
        return MODEL_RATE_CARDS[model_clean]
    for key, rates in MODEL_RATE_CARDS.items():
        if key in model_clean or model_clean.startswith(key):
            return rates

    if provider_clean in (Provider.LOCAL.value, "ollama", "vllm", "llama.cpp", Provider.OPEN_WEIGHT.value):
        return (0.0, 0.0)
    return REFERENCE_PRICING.get(provider_clean, (2.50, 10.00))

# Baseline cloud model against which local savings are quantified
SAVINGS_BASELINE_NAME = "claude-3-5-sonnet-20241022"
SAVINGS_BASELINE_RATE = (3.00, 15.00)  # $3.00 / MTok in, $15.00 / MTok out


@dataclass
class LedgerEntry:
    id: str
    timestamp: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_external_cost_usd: float
    billing_label: str
    price_source_version: str
    estimated_cloud_savings_usd: float
    routing_reason: Optional[str] = None
    model_revision: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 2)
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


class CostLedger:
    """Thread-safe, append-only model usage and economics accounting engine."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self._lock = Lock()
        self._entries: List[LedgerEntry] = []
        self._counter: int = 0
        self.persistence_path = persistence_path

        if self.persistence_path and self.persistence_path.exists():
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if self.persistence_path is None:
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._entries.append(LedgerEntry(**data))
            self._counter = len(self._entries)
        except Exception:
            pass

    def record_completion(
        self,
        provider: Provider | str,
        model: str,
        usage: Optional[Dict[str, int]] = None,
        latency_ms: float = 0.0,
        cost_usd: Optional[float] = None,
        routing_reason: Optional[str] = None,
        model_revision: Optional[str] = None,
    ) -> LedgerEntry:
        """Record an inference event with exact cost accounting and savings attribution."""
        provider_val = provider.value if isinstance(provider, Provider) else str(provider)
        usage = usage or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        is_local = (provider_val == Provider.LOCAL.value)

        # External API cost calculation
        if is_local:
            external_cost = 0.0
            billing_label = "no billed external API tokens"
            # Calculate what this would have cost on the baseline cloud model
            base_in, base_out = SAVINGS_BASELINE_RATE
            cloud_savings = round((prompt_tokens * base_in + completion_tokens * base_out) / 1_000_000, 6)
        else:
            billing_label = "billed external cloud tokens"
            if cost_usd is not None:
                external_cost = round(cost_usd, 6)
            else:
                rates = resolve_model_rates(provider_val, model)
                external_cost = round((prompt_tokens * rates[0] + completion_tokens * rates[1]) / 1_000_000, 6)
            cloud_savings = 0.0

        with self._lock:
            self._counter += 1
            entry_id = f"kw-inf-{self._counter:06d}"
            entry = LedgerEntry(
                id=entry_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                provider=provider_val,
                model=model or "unknown",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=round(latency_ms, 2),
                estimated_external_cost_usd=external_cost,
                billing_label=billing_label,
                price_source_version=PRICE_SOURCE_VERSION,
                estimated_cloud_savings_usd=cloud_savings,
                routing_reason=routing_reason,
                model_revision=model_revision,
            )
            self._entries.append(entry)

            # Optional persistence
            if self.persistence_path:
                try:
                    self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.persistence_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry.to_dict()) + "\n")
                except Exception:
                    pass

            return entry

    def get_summary(self) -> Dict[str, Any]:
        """Generate high-level aggregated metrics and latency percentiles."""
        with self._lock:
            entries = list(self._entries)

        total_inferences = len(entries)
        total_prompt_tokens = sum(e.prompt_tokens for e in entries)
        total_completion_tokens = sum(e.completion_tokens for e in entries)
        total_tokens = sum(e.total_tokens for e in entries)
        total_external_cost_usd = round(sum(e.estimated_external_cost_usd for e in entries), 6)
        total_cloud_savings_usd = round(sum(e.estimated_cloud_savings_usd for e in entries), 6)

        local_entries = [e for e in entries if e.provider == Provider.LOCAL.value]
        cloud_entries = [e for e in entries if e.provider != Provider.LOCAL.value]

        local_count = len(local_entries)
        cloud_count = len(cloud_entries)
        total_local_duration_ms = round(sum(e.latency_ms for e in local_entries), 2)

        all_latencies = [e.latency_ms for e in entries]

        # By provider breakdown
        by_provider: Dict[str, Dict[str, Any]] = {}
        for p in Provider:
            p_entries = [e for e in entries if e.provider == p.value]
            p_latencies = [e.latency_ms for e in p_entries]
            by_provider[p.value] = {
                "inferences": len(p_entries),
                "prompt_tokens": sum(e.prompt_tokens for e in p_entries),
                "completion_tokens": sum(e.completion_tokens for e in p_entries),
                "total_tokens": sum(e.total_tokens for e in p_entries),
                "cost_usd": round(sum(e.estimated_external_cost_usd for e in p_entries), 6),
                "savings_usd": round(sum(e.estimated_cloud_savings_usd for e in p_entries), 6),
                "latency_p50_ms": _percentile(p_latencies, 0.50),
                "latency_p95_ms": _percentile(p_latencies, 0.95),
            }

        return {
            "price_source_version": PRICE_SOURCE_VERSION,
            "savings_baseline_model": f"{SAVINGS_BASELINE_NAME} ({PRICE_SOURCE_VERSION})",
            "total_inferences": total_inferences,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_external_cost_usd": total_external_cost_usd,
            "total_cloud_savings_usd": total_cloud_savings_usd,
            "local_inferences": local_count,
            "cloud_inferences": cloud_count,
            "local_inference_ratio": round(local_count / total_inferences, 4) if total_inferences > 0 else 1.0,
            "total_local_duration_ms": total_local_duration_ms,
            "latency_p50_ms": _percentile(all_latencies, 0.50),
            "latency_p90_ms": _percentile(all_latencies, 0.90),
            "latency_p95_ms": _percentile(all_latencies, 0.95),
            "latency_p99_ms": _percentile(all_latencies, 0.99),
            "by_provider": by_provider,
        }

    def get_economics_report(self) -> Dict[str, Any]:
        """Comprehensive sovereign AI economics analytics report."""
        summary = self.get_summary()
        total_inf = summary["total_inferences"]
        local_inf = summary["local_inferences"]
        cloud_inf = summary["cloud_inferences"]
        ext_cost = summary["total_external_cost_usd"]
        savings = summary["total_cloud_savings_usd"]

        net_benefit = round(savings - ext_cost, 6)
        if ext_cost > 0:
            roi_pct = round((savings / ext_cost) * 100, 2)
        elif savings > 0:
            roi_pct = 100.0
        else:
            roi_pct = 0.0

        # Sovereign Efficiency Index: composite score 0..100
        # Weighted: 50% local autonomy ratio, 30% positive economic benefit, 20% latency responsiveness
        local_ratio = summary["local_inference_ratio"]
        p95 = summary["latency_p95_ms"]
        latency_score = 100.0 if p95 <= 100 else max(0.0, 100.0 - (p95 - 100) / 10)
        benefit_factor = 1.0 if net_benefit >= 0 else max(0.0, 1.0 + (net_benefit / 10.0))
        sei_score = round((local_ratio * 50.0) + (benefit_factor * 30.0) + (latency_score * 0.2), 1)
        sei_score = min(100.0, max(0.0, sei_score))

        # Model breakdown
        with self._lock:
            entries = list(self._entries)

        by_model: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            m_key = f"{e.provider}/{e.model}"
            if m_key not in by_model:
                by_model[m_key] = {
                    "provider": e.provider,
                    "model": e.model,
                    "inferences": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "savings_usd": 0.0,
                    "_latencies": [],
                }
            bm = by_model[m_key]
            bm["inferences"] += 1
            bm["prompt_tokens"] += e.prompt_tokens
            bm["completion_tokens"] += e.completion_tokens
            bm["total_tokens"] += e.total_tokens
            bm["cost_usd"] = round(bm["cost_usd"] + e.estimated_external_cost_usd, 6)
            bm["savings_usd"] = round(bm["savings_usd"] + e.estimated_cloud_savings_usd, 6)
            bm["_latencies"].append(e.latency_ms)

        for bm in by_model.values():
            lats = bm.pop("_latencies")
            bm["latency_p50_ms"] = _percentile(lats, 0.50)
            bm["latency_p95_ms"] = _percentile(lats, 0.95)

        projected_monthly_savings_usd = round(savings * 30, 2)
        projected_annual_savings_usd = round(savings * 365, 2)

        return {
            "price_source_version": PRICE_SOURCE_VERSION,
            "savings_baseline_model": summary["savings_baseline_model"],
            "total_inferences": total_inf,
            "local_inferences": local_inf,
            "cloud_inferences": cloud_inf,
            "local_inference_ratio": local_ratio,
            "total_prompt_tokens": summary["total_prompt_tokens"],
            "total_completion_tokens": summary["total_completion_tokens"],
            "total_tokens": summary["total_tokens"],
            "billed_cloud_expenditure_usd": ext_cost,
            "quantified_local_savings_usd": savings,
            "net_economic_benefit_usd": net_benefit,
            "sovereign_roi_percent": roi_pct,
            "sovereign_efficiency_index": sei_score,
            "latency_percentiles": {
                "p50_ms": summary["latency_p50_ms"],
                "p90_ms": summary["latency_p90_ms"],
                "p95_ms": summary["latency_p95_ms"],
                "p99_ms": summary["latency_p99_ms"],
            },
            "by_provider": summary["by_provider"],
            "by_model": by_model,
            "rate_cards": {
                name: {"input_per_mtok_usd": r[0], "output_per_mtok_usd": r[1]}
                for name, r in MODEL_RATE_CARDS.items()
            },
            "projections": {
                "run_rate_basis": f"{total_inf} inference(s)",
                "projected_monthly_savings_usd": projected_monthly_savings_usd,
                "projected_annual_savings_usd": projected_annual_savings_usd,
            },
        }

    def list_entries(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            slice_entries = self._entries[offset : offset + limit]
            return [e.to_dict() for e in slice_entries]

    def export(self, export_format: str = "json") -> str:
        """Export full ledger in json, jsonl, or csv format."""
        with self._lock:
            entries = [e.to_dict() for e in self._entries]

        export_format = export_format.lower().strip()
        if export_format == "jsonl":
            return "\n".join(json.dumps(e) for e in entries) + ("\n" if entries else "")
        elif export_format == "csv":
            if not entries:
                return "id,timestamp,provider,model,prompt_tokens,completion_tokens,total_tokens,latency_ms,estimated_external_cost_usd,billing_label,price_source_version,estimated_cloud_savings_usd,routing_reason\n"
            output = io.StringIO()
            fieldnames = [
                "id",
                "timestamp",
                "provider",
                "model",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "latency_ms",
                "estimated_external_cost_usd",
                "billing_label",
                "price_source_version",
                "estimated_cloud_savings_usd",
                "routing_reason",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for e in entries:
                writer.writerow(e)
            return output.getvalue()
        else:  # json
            return json.dumps({
                "summary": self.get_summary(),
                "entries": entries,
            }, indent=2)

    def reset(self) -> None:
        """Clear ledger entries (useful for session isolation and tests)."""
        with self._lock:
            self._entries.clear()
            self._counter = 0
            if self.persistence_path and self.persistence_path.exists():
                try:
                    os.remove(self.persistence_path)
                except Exception:
                    pass


# Default singleton instance
cost_ledger = CostLedger()
