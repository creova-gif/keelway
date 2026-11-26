"""
Unit and integration tests for Keelway Model Economics, Rate Cards, and ROI Analytics.
"""

import json
import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.api.schemas import Provider
from core.models.cost_ledger import (
    CostLedger,
    cost_ledger,
    resolve_model_rates,
)
from cli import cmd_cost


def test_resolve_model_rates():
    assert resolve_model_rates("anthropic", "claude-3-7-sonnet") == (3.00, 15.00)
    assert resolve_model_rates("openai", "gpt-4o") == (2.50, 10.00)
    assert resolve_model_rates("openai", "gpt-4o-mini") == (0.15, 0.60)
    assert resolve_model_rates("google", "gemini-2.5-flash") == (0.10, 0.40)
    assert resolve_model_rates("deepseek", "deepseek-v3") == (0.14, 0.28)
    assert resolve_model_rates("local", "qwen2.5-coder:7b") == (0.0, 0.0)
    assert resolve_model_rates("ollama", "llama-3.3:70b") == (0.0, 0.0)


def test_economics_report_arbitrage_roi_and_sei():
    ledger = CostLedger()

    # Record 3 local inferences (zero cloud cost, positive savings)
    for _ in range(3):
        ledger.record_completion(
            provider=Provider.LOCAL,
            model="qwen2.5-coder:7b",
            usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
            latency_ms=45.0,
        )

    # Record 1 cloud inference (billed external cloud tokens)
    ledger.record_completion(
        provider=Provider.ANTHROPIC,
        model="claude-3-7-sonnet",
        usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        latency_ms=450.0,
    )

    report = ledger.get_economics_report()
    assert report["total_inferences"] == 4
    assert report["local_inferences"] == 3
    assert report["cloud_inferences"] == 1
    assert report["local_inference_ratio"] == 0.75
    assert report["total_tokens"] == 6000
    assert report["billed_cloud_expenditure_usd"] > 0
    assert report["quantified_local_savings_usd"] > 0
    assert report["net_economic_benefit_usd"] > 0
    assert report["sovereign_roi_percent"] > 0
    assert 0.0 <= report["sovereign_efficiency_index"] <= 100.0

    # Model breakdown checks
    assert "local/qwen2.5-coder:7b" in report["by_model"]
    assert "anthropic/claude-3-7-sonnet" in report["by_model"]
    local_m = report["by_model"]["local/qwen2.5-coder:7b"]
    assert local_m["inferences"] == 3
    assert local_m["cost_usd"] == 0.0
    assert local_m["savings_usd"] > 0.0


@pytest.mark.asyncio
async def test_api_models_economics_endpoint():
    cost_ledger.reset()
    cost_ledger.record_completion(
        provider=Provider.LOCAL,
        model="qwen2.5-coder:7b",
        usage={"prompt_tokens": 2000, "completion_tokens": 800, "total_tokens": 2800},
        latency_ms=52.0,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/v1/models/economics")
        assert r.status_code == 200
        data = r.json()
        assert "price_source_version" in data
        assert "sovereign_efficiency_index" in data
        assert "net_economic_benefit_usd" in data
        assert "rate_cards" in data
        assert data["total_inferences"] == 1
        assert data["local_inferences"] == 1
        assert data["quantified_local_savings_usd"] > 0.0


def test_cli_cmd_cost(capsys):
    cost_ledger.reset()
    cost_ledger.record_completion(
        provider=Provider.LOCAL,
        model="qwen2.5-coder:7b",
        usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        latency_ms=30.0,
    )

    # Test summary CLI output
    code = cmd_cost(summary_only=False, json_out=False)
    assert code == 0
    captured = capsys.readouterr().out
    assert "KEELWAY SOVEREIGN MODEL ECONOMICS" in captured
    assert "Sovereign Efficiency Idx" in captured
    assert "qwen2.5-coder:7b" in captured

    # Test JSON CLI output
    code_json = cmd_cost(json_out=True)
    assert code_json == 0
    json_captured = capsys.readouterr().out
    parsed = json.loads(json_captured)
    assert parsed["total_inferences"] == 1
    assert parsed["local_inferences"] == 1
