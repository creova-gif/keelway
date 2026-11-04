"""
Comprehensive unit and integration tests for Speculative Decoding Edge Benchmark & Token Arbitrage Engine.
Tests SpeculativeBenchmark calculations, REST route POST /v1/models/speculative/benchmark, and CLI dispatch.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from cli import build_parser, cmd_models
from core.api import routes
from core.main import app
from core.models.speculative import SpeculativeBenchmark
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Safely isolates workspace filesystem and restores state in a try...finally block."""
    prev_fs = routes._workspace_fs
    monkeypatch.chdir(tmp_path)
    routes.set_workspace_fs(WorkspaceFilesystem(root_dir=str(tmp_path)))
    try:
        yield tmp_path
    finally:
        routes.set_workspace_fs(prev_fs)


def test_speculative_benchmark_engine_calculations():
    """Verify SpeculativeBenchmark generates valid speedup ratios, latency reductions, and cost savings."""
    res = SpeculativeBenchmark.benchmark(
        draft_model="qwen2.5-coder:0.5b",
        target_model="qwen2.5-coder:7b",
        prompt="def optimize_query():",
        lookahead_k=4,
        iterations=5,
    )

    assert res["draft_model"] == "qwen2.5-coder:0.5b"
    assert res["target_model"] == "qwen2.5-coder:7b"
    assert res["prompt"] == "def optimize_query():"
    assert res["lookahead_k"] == 4
    assert res["iterations"] == 5

    spec = res["speculative_result"]
    assert spec["tokens_generated"] > 0
    assert spec["draft_tokens_proposed"] > 0
    assert spec["draft_tokens_accepted"] > 0
    assert 0.0 <= spec["acceptance_rate"] <= 1.0
    assert spec["effective_speedup_ratio"] >= 1.5
    assert spec["latency_ms"] > 0.0

    assert res["baseline_latency_ms"] > spec["latency_ms"]
    assert res["latency_reduction_pct"] > 0.0
    assert res["target_cloud_cost_usd"] > 0.0
    assert res["edge_cost_usd"] == 0.0
    assert res["savings_usd"] == res["target_cloud_cost_usd"]


def test_speculative_benchmark_rest_api_endpoint(workspace_env: Path):
    """Verify POST /v1/models/speculative/benchmark endpoint returns benchmark results."""
    with TestClient(app) as client:
        # 1. Full custom payload
        payload = {
            "draft_model": "qwen2.5-coder:1.5b",
            "target_model": "qwen2.5-coder:14b",
            "prompt": "def quicksort(arr):",
            "lookahead_k": 3,
            "iterations": 4,
        }
        resp = client.post("/v1/models/speculative/benchmark", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["draft_model"] == "qwen2.5-coder:1.5b"
        assert data["target_model"] == "qwen2.5-coder:14b"
        assert data["lookahead_k"] == 3
        assert data["iterations"] == 4

        spec = data["speculative_result"]
        assert spec["tokens_generated"] > 0
        assert spec["effective_speedup_ratio"] >= 1.0
        assert data["baseline_latency_ms"] >= spec["latency_ms"]
        assert data["edge_cost_usd"] == 0.0
        assert data["savings_usd"] == data["target_cloud_cost_usd"]

        # 2. Default payload
        default_resp = client.post("/v1/models/speculative/benchmark", json={})
        assert default_resp.status_code == 200
        def_data = default_resp.json()
        assert def_data["draft_model"] == "qwen2.5-coder:0.5b"
        assert def_data["target_model"] == "qwen2.5-coder:7b"
        assert def_data["lookahead_k"] == 4


def test_speculative_benchmark_cli_parser():
    """Verify CLI argument parsing for keelway models bench-speculative."""
    parser = build_parser()
    args = parser.parse_args([
        "models", "bench-speculative",
        "--draft", "custom-draft:0.5b",
        "--target", "custom-target:7b",
        "--prompt", "def binary_search():",
        "--k", "5",
    ])

    assert args.command == "models"
    assert args.models_command == "bench-speculative"
    assert args.draft == "custom-draft:0.5b"
    assert args.target == "custom-target:7b"
    assert args.prompt == "def binary_search():"
    assert args.k == 5


def test_speculative_benchmark_cli_execution(capsys: pytest.CaptureFixture):
    """Verify CLI execution prints pretty-printed speedup and token arbitrage report."""
    rc = cmd_models(
        action="bench-speculative",
        draft="qwen2.5-coder:0.5b",
        target="qwen2.5-coder:7b",
        prompt="def optimize_query():",
        k=4,
    )
    assert rc == 0

    captured = capsys.readouterr()
    assert "⚡ KEELWAY SPECULATIVE DECODING & TOKEN ARBITRAGE BENCHMARK" in captured.out
    assert "Effective Speedup Ratio" in captured.out
    assert "Latency Reduction" in captured.out
    assert "Target Cloud Cost" in captured.out
    assert "Net Avoided Cost" in captured.out
    assert "100% savings" in captured.out
