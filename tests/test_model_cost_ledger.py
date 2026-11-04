"""
Unit and integration tests for Keelway Model Cost Ledger and Economics.
"""

import csv
import json
import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.api.schemas import Provider
from core.models.cost_ledger import CostLedger, LedgerEntry, cost_ledger


def test_local_model_inference_zero_cloud_cost_with_arbitrage_savings():
    ledger = CostLedger()
    entry = ledger.record_completion(
        provider=Provider.LOCAL,
        model="qwen2.5-coder:7b",
        usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        latency_ms=120.5,
        routing_reason="local-first: $0.00 inference",
    )

    assert entry.provider == "local"
    assert entry.model == "qwen2.5-coder:7b"
    assert entry.prompt_tokens == 1000
    assert entry.completion_tokens == 500
    assert entry.total_tokens == 1500
    assert entry.latency_ms == 120.5
    assert entry.estimated_external_cost_usd == 0.0
    assert entry.billing_label == "no billed external API tokens"
    # 1000 * 3.0 / 1e6 + 500 * 15.0 / 1e6 = 0.003 + 0.0075 = 0.0105
    assert entry.estimated_cloud_savings_usd == 0.0105


def test_cloud_model_inference_billed_cost():
    ledger = CostLedger()
    entry = ledger.record_completion(
        provider=Provider.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        usage={"prompt_tokens": 2000, "completion_tokens": 800, "total_tokens": 2800},
        latency_ms=850.0,
        routing_reason="escalated to cloud for complex_reasoning",
    )

    assert entry.provider == "anthropic"
    assert entry.model == "claude-3-5-sonnet-20241022"
    assert entry.estimated_external_cost_usd > 0.0
    assert entry.billing_label == "billed external cloud tokens"
    assert entry.estimated_cloud_savings_usd == 0.0


def test_summary_and_percentiles():
    ledger = CostLedger()
    # Record 5 entries with distinct latencies
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
    for lat in latencies:
        ledger.record_completion(
            provider=Provider.LOCAL,
            model="qwen2.5-coder:7b",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=lat,
        )

    summary = ledger.get_summary()
    assert summary["total_inferences"] == 5
    assert summary["local_inferences"] == 5
    assert summary["cloud_inferences"] == 0
    assert summary["local_inference_ratio"] == 1.0
    assert summary["total_prompt_tokens"] == 500
    assert summary["total_completion_tokens"] == 250
    assert summary["total_tokens"] == 750
    assert summary["total_external_cost_usd"] == 0.0
    assert summary["total_cloud_savings_usd"] > 0.0

    # Percentiles for [10, 20, 30, 40, 50]
    assert summary["latency_p50_ms"] == 30.0
    assert summary["latency_p90_ms"] == 46.0
    assert summary["latency_p95_ms"] == 48.0
    assert summary["latency_p99_ms"] == 49.6


def test_ledger_exports_json_jsonl_csv():
    ledger = CostLedger()
    ledger.record_completion(
        provider=Provider.LOCAL,
        model="qwen2.5-coder:7b",
        usage={"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700},
        latency_ms=95.0,
        routing_reason="local-first",
    )
    ledger.record_completion(
        provider=Provider.OPENAI,
        model="gpt-4o",
        usage={"prompt_tokens": 300, "completion_tokens": 100, "total_tokens": 400},
        latency_ms=450.0,
        routing_reason="preferred openai",
    )

    # JSON export
    json_str = ledger.export("json")
    json_data = json.loads(json_str)
    assert "summary" in json_data
    assert len(json_data["entries"]) == 2

    # JSONL export
    jsonl_str = ledger.export("jsonl")
    lines = [line for line in jsonl_str.strip().split("\n") if line]
    assert len(lines) == 2
    parsed_first = json.loads(lines[0])
    assert parsed_first["provider"] == "local"

    # CSV export
    csv_str = ledger.export("csv")
    reader = csv.DictReader(csv_str.strip().split("\n"))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["provider"] == "local"
    assert rows[0]["billing_label"] == "no billed external API tokens"
    assert rows[1]["provider"] == "openai"


@pytest.mark.asyncio
async def test_api_models_ledger_endpoints():
    cost_ledger.reset()
    # Seed one entry
    cost_ledger.record_completion(
        provider=Provider.LOCAL,
        model="qwen2.5-coder:7b",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        latency_ms=45.0,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET ledger
        r = await client.get("/v1/models/ledger")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "entries" in data
        assert data["summary"]["total_inferences"] == 1
        assert data["entries"][0]["billing_label"] == "no billed external API tokens"

        # GET export as jsonl
        r_exp = await client.get("/v1/models/ledger/export?format=jsonl")
        assert r_exp.status_code == 200
        assert "application/x-ndjson" in r_exp.headers.get("content-type", "")
        assert "qwen2.5-coder:7b" in r_exp.text

        # GET export as csv
        r_csv = await client.get("/v1/models/ledger/export?format=csv")
        assert r_csv.status_code == 200
        assert "text/csv" in r_csv.headers.get("content-type", "")
        assert "billing_label" in r_csv.text

        # POST reset
        r_reset = await client.post("/v1/models/ledger/reset")
        assert r_reset.status_code == 200
        assert r_reset.json()["status"] == "ok"

        # Verify ledger is now empty
        r_after = await client.get("/v1/models/ledger")
        assert r_after.json()["summary"]["total_inferences"] == 0
