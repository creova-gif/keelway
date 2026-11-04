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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from core.api.schemas import Provider

PRICE_SOURCE_VERSION = "pricing_v2026.1"

# Standard reference pricing per million tokens (input, output) in USD.
REFERENCE_PRICING: Dict[str, Tuple[float, float]] = {
    Provider.ANTHROPIC.value: (3.00, 15.00),     # Claude 3.5 Sonnet
    Provider.OPENAI.value: (2.50, 10.00),        # GPT-4o
    Provider.GOOGLE.value: (0.075, 0.30),        # Gemini 1.5 Flash
    Provider.LOCAL.value: (0.0, 0.0),            # Local device ($0 billed API)
}

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
                rates = REFERENCE_PRICING.get(provider_val, (2.50, 10.00))
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
