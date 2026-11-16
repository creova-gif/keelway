"""
Phase 19B & Integration Verification Suite — Tri-Language SDK Parity (`Python`, `TypeScript`, `Go`)
+ VS Code/Cursor Extension (`keelway.inspectDistillationReadiness`) for Semantic Prompt Cache,
Shadow Dual-Run Router & QLoRA Distillation Flywheel, Module-Size Ratchets, and `310`-Route OpenAPI Contract (`KEEL-DISTILL-026`).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List
import uuid

import httpx
from httpx import ASGITransport
import pytest

from core.main import app
from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    PermissionDeniedError,
    SyncPlatformClient,
)
from core.security.auth import launch_token

REPO_ROOT = Path(__file__).resolve().parent.parent

PHASE19_PYTHON_METHODS = (
    "evaluate_shadow_prompt",
    "list_shadow_pairs",
    "get_semantic_cache_stats",
    "compile_distillation_dataset",
    "list_distillation_datasets",
    "evaluate_distillation_promotion",
)

PHASE19_TS_METHODS = (
    "evaluateShadowPrompt",
    "listShadowPairs",
    "getSemanticCacheStats",
    "compileDistillationDataset",
    "listDistillationDatasets",
    "evaluateDistillationPromotion",
)

PHASE19_GO_METHODS = (
    "EvaluateShadowPrompt",
    "ListShadowPairs",
    "GetSemanticCacheStats",
    "CompileDistillationDataset",
    "ListDistillationDatasets",
    "EvaluateDistillationPromotion",
)


def _make_sync_mock_transport() -> httpx.MockTransport:
    cache_seen: Dict[str, Dict[str, Any]] = {}
    pairs_store: List[Dict[str, Any]] = []
    datasets_store: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else {}
        path, params = request.url.path, dict(request.url.params)

        if path == "/v1/platform/distill/shadow/evaluate" and request.method == "POST":
            ws = body.get("workspace_id", "default")
            tag = body.get("task_tag", "code-patch")
            prompt = body.get("prompt", "")
            key = f"{ws}::{tag}::{prompt.strip().lower()}"
            if not body.get("bypass_cache") and key in cache_seen:
                entry = cache_seen[key]
                entry["hits"] += 1
                return httpx.Response(
                    200,
                    json={
                        "evaluation_id": "seval-hit",
                        "pair_id": None,
                        "cache_entry_id": entry["cache_entry_id"],
                        "workspace_id": ws,
                        "task_tag": tag,
                        "verdict": "CACHE_HIT",
                        "match_type": "exact_sha256",
                        "similarity_score": 1.0,
                        "parity_score": entry["parity_score"],
                        "frontier_model": body.get("frontier_model", "claude-3-7-sonnet"),
                        "local_model": body.get("local_model", "keelway-core:7b"),
                        "scrubbed_prompt": prompt,
                        "cached_response": entry["cached_response"],
                        "cost_saved_usd": body.get("frontier_cost_usd", 0.018),
                        "latency_saved_ms": body.get("frontier_latency_ms", 840),
                        "dlp_redactions": 0,
                        "event_sha256": "sha256:" + ("a" * 64),
                        "created_at": "2026-11-16T00:00:00+00:00",
                    },
                )
            cid = f"scache-{len(cache_seen) + 1}"
            pid = f"spair-{len(pairs_store) + 1}"
            cache_seen[key] = {
                "cache_entry_id": cid,
                "ws": ws,
                "parity_score": 0.96,
                "cached_response": body.get("frontier_response", ""),
                "hits": 0,
            }
            pairs_store.append(
                {
                    "pair_id": pid,
                    "workspace_id": ws,
                    "task_tag": tag,
                    "scrubbed_prompt": prompt,
                    "scrubbed_frontier_response": body.get("frontier_response", ""),
                    "scrubbed_local_response": body.get("local_response", ""),
                    "frontier_model": body.get("frontier_model", "claude-3-7-sonnet"),
                    "local_model": body.get("local_model", "keelway-core:7b"),
                    "parity_score": 0.96,
                    "frontier_cost_usd": body.get("frontier_cost_usd", 0.018),
                    "dlp_redactions": 0,
                    "pair_sha256": "sha256:" + ("b" * 64),
                    "created_at": "2026-11-16T00:00:00+00:00",
                }
            )
            return httpx.Response(
                200,
                json={
                    "evaluation_id": f"seval-{len(pairs_store)}",
                    "pair_id": pid,
                    "cache_entry_id": cid,
                    "workspace_id": ws,
                    "task_tag": tag,
                    "verdict": "LOCAL_PARITY_READY",
                    "match_type": "cache_miss",
                    "similarity_score": 0.0,
                    "parity_score": 0.96,
                    "frontier_model": body.get("frontier_model", "claude-3-7-sonnet"),
                    "local_model": body.get("local_model", "keelway-core:7b"),
                    "scrubbed_prompt": prompt,
                    "cached_response": body.get("frontier_response", ""),
                    "cost_saved_usd": 0.0,
                    "latency_saved_ms": 0,
                    "dlp_redactions": 0,
                    "event_sha256": "sha256:" + ("c" * 64),
                    "created_at": "2026-11-16T00:00:00+00:00",
                },
            )

        if path == "/v1/platform/distill/shadow/pairs" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            tag = params.get("task_tag")
            matched = [p for p in pairs_store if p["workspace_id"] == ws and (not tag or p["task_tag"] == tag)]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "pairs": matched})

        if path == "/v1/platform/distill/cache/stats" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            entries = [e for e in cache_seen.values() if e["ws"] == ws]
            hits = sum(e["hits"] for e in entries)
            lookups = len(entries) + hits
            return httpx.Response(
                200,
                json={
                    "workspace_id": ws,
                    "entry_count": len(entries),
                    "total_hits": hits,
                    "total_lookups": lookups,
                    "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
                    "total_cost_saved_usd": round(hits * 0.018, 4),
                    "total_latency_saved_ms": hits * 840,
                    "total_dlp_redactions": 0,
                },
            )

        if path == "/v1/platform/distill/datasets/compile" and request.method == "POST":
            ws = body.get("workspace_id", "default")
            ds = {
                "dataset_id": f"qds-{len(datasets_store) + 1}",
                "workspace_id": ws,
                "task_tag": body.get("task_tag", ""),
                "export_format": body.get("export_format", "dpo_preference"),
                "target_base_model": body.get("target_base_model", "keelway-core:7b"),
                "record_count": len([p for p in pairs_store if p["workspace_id"] == ws]),
                "avg_parity_score": 0.96,
                "lora_rank": 16,
                "lora_alpha": 32,
                "dlp_redactions": 0,
                "jsonl_preview": '{"prompt":"Refactor","chosen":"ok","rejected":"ok"}',
                "dataset_sha256": "sha256:" + ("d" * 64),
                "created_at": "2026-11-16T00:00:00+00:00",
            }
            datasets_store.append(ds)
            return httpx.Response(200, json=ds)

        if path == "/v1/platform/distill/datasets" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [d for d in datasets_store if d["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "datasets": matched})

        if path == "/v1/platform/distill/promotion/evaluate" and request.method == "POST":
            ws = body.get("workspace_id", "default")
            vol = int(body.get("monthly_request_volume", 50000))
            return httpx.Response(
                200,
                json={
                    "evaluation_id": "dprom-1",
                    "workspace_id": ws,
                    "task_tag": body.get("task_tag", "code-patch"),
                    "target_local_model": body.get("target_local_model", "keelway-core:7b"),
                    "verdict": "PROMOTE_TO_OPENCORE",
                    "pair_count": 3,
                    "min_pairs": int(body.get("min_pairs", 3)),
                    "avg_parity_score": 0.96,
                    "min_avg_parity": float(body.get("min_avg_parity", 0.85)),
                    "avg_frontier_cost_usd": 0.018,
                    "monthly_request_volume": vol,
                    "projected_monthly_savings_usd": round(0.018 * vol, 2),
                    "recommendation": "Promote to keelway-core:7b.",
                    "gate_sha256": "sha256:" + ("e" * 64),
                    "evaluated_at": "2026-11-16T00:00:00+00:00",
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled mock route {request.method} {path}"})

    return httpx.MockTransport(handler)


def test_python_sdk_phase19_sync_async_signature_and_mock_parity() -> None:
    for method_name in PHASE19_PYTHON_METHODS:
        sync_fn = getattr(SyncPlatformClient, method_name, None)
        async_fn = getattr(AsyncPlatformClient, method_name, None)
        assert callable(sync_fn), f"Missing SyncPlatformClient.{method_name}"
        assert callable(async_fn), f"Missing AsyncPlatformClient.{method_name}"
        assert inspect.iscoroutinefunction(async_fn)
        assert list(inspect.signature(sync_fn).parameters.keys()) == list(inspect.signature(async_fn).parameters.keys())

    with KeelwayClient(base_url="http://127.0.0.1:7420", token="test-token", transport=_make_sync_mock_transport()) as client:
        miss = client.platform.evaluate_shadow_prompt(workspace_id="ws-p19")
        assert miss["verdict"] == "LOCAL_PARITY_READY" and miss["match_type"] == "cache_miss"

        hit = client.platform.evaluate_shadow_prompt(workspace_id="ws-p19")
        assert hit["verdict"] == "CACHE_HIT" and hit["cost_saved_usd"] == pytest.approx(0.018)

        pairs = client.platform.list_shadow_pairs(workspace_id="ws-p19", task_tag="code-patch")
        assert pairs["count"] == 1

        stats = client.platform.get_semantic_cache_stats(workspace_id="ws-p19")
        assert stats["total_hits"] == 1 and stats["entry_count"] == 1

        ds = client.platform.compile_distillation_dataset(workspace_id="ws-p19", export_format="dpo_preference")
        assert ds["record_count"] == 1 and ds["dataset_sha256"].startswith("sha256:")

        ds_list = client.platform.list_distillation_datasets(workspace_id="ws-p19")
        assert ds_list["count"] == 1

        promo = client.platform.evaluate_distillation_promotion(workspace_id="ws-p19", min_pairs=1)
        assert promo["verdict"] == "PROMOTE_TO_OPENCORE" and promo["projected_monthly_savings_usd"] == pytest.approx(900.0)


@pytest.mark.asyncio
async def test_python_async_sdk_live_asgi_shadow_cache_and_distillation() -> None:
    ws_id = f"ws-p19-asgi-{uuid.uuid4().hex[:8]}"
    token = launch_token()

    async with AsyncKeelwayClient(base_url="http://127.0.0.1:7420", token=token, transport=ASGITransport(app=app)) as client:
        ev1 = await client.platform.evaluate_shadow_prompt(
            "Explain SQLite WAL concurrency with bearer token sk-live-9876543210secret",
            workspace_id=ws_id,
            task_tag="db-ops",
            frontier_response="Use PRAGMA journal_mode=WAL for concurrent readers.",
            local_response="Use PRAGMA journal_mode=WAL for concurrent readers.",
        )
        assert ev1["verdict"] == "LOCAL_PARITY_READY" and ev1["dlp_redactions"] >= 1
        assert "sk-live-" not in ev1["scrubbed_prompt"]

        ev_hit = await client.platform.evaluate_shadow_prompt(
            "Explain SQLite WAL concurrency with bearer token sk-live-9876543210secret!",
            workspace_id=ws_id,
            task_tag="db-ops",
        )
        assert ev_hit["verdict"] == "CACHE_HIT" and ev_hit["cost_saved_usd"] > 0

        stats = await client.platform.get_semantic_cache_stats(workspace_id=ws_id)
        assert stats["total_hits"] == 1 and stats["total_dlp_redactions"] >= 1

        ds = await client.platform.compile_distillation_dataset(
            workspace_id=ws_id, task_tag="db-ops", export_format="sft_jsonl"
        )
        assert ds["record_count"] == 1 and "sk-live-" not in ds["jsonl_preview"]

        promo = await client.platform.evaluate_distillation_promotion(
            workspace_id=ws_id, task_tag="db-ops", min_pairs=1, monthly_request_volume=10000
        )
        assert promo["verdict"] == "PROMOTE_TO_OPENCORE" and promo["projected_monthly_savings_usd"] > 0

    async with AsyncKeelwayClient(base_url="http://127.0.0.1:7420", token=token, transport=ASGITransport(app=app)) as auditor_client:
        http_attr = getattr(auditor_client, "_http", None) or getattr(auditor_client, "_client")
        http_attr.headers["X-Keelway-Role"] = "auditor"
        http_attr.headers["X-Keelway-Actor"] = "auditor-actor"
        assert (await auditor_client.platform.list_shadow_pairs(workspace_id=ws_id))["count"] >= 1
        assert (await auditor_client.platform.get_semantic_cache_stats(workspace_id=ws_id))["entry_count"] >= 1
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.evaluate_shadow_prompt(workspace_id=ws_id)
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.compile_distillation_dataset(workspace_id=ws_id)
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.evaluate_distillation_promotion(workspace_id=ws_id)


def test_tri_sdk_vscode_bridge_module_caps_and_310_openapi_paths() -> None:
    new_phase19_files = (
        REPO_ROOT / "core" / "platform" / "shadow_distillation.py",
        REPO_ROOT / "core" / "api" / "platform_distill_routes.py",
        REPO_ROOT / "core" / "cli_distill.py",
        REPO_ROOT / "core" / "sdk" / "platform_distill_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platformDistill.ts",
        REPO_ROOT / "sdk" / "go" / "platform_phase19.go",
        REPO_ROOT / "dev-app" / "src" / "lib" / "platformDistillApi.ts",
        REPO_ROOT / "dev-app" / "src" / "components" / "platform" / "ShadowCacheAndDistillationPanel.tsx",
    )
    for fpath in new_phase19_files:
        assert fpath.exists(), f"Expected Phase 19 module {fpath}"
        lines = fpath.read_text(encoding="utf-8").splitlines()
        assert len(lines) < 480, f"{fpath} exceeds 480-line cap ({len(lines)} lines)"

    for shared_sdk_file in (
        REPO_ROOT / "core" / "sdk" / "platform_runtime_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "index.ts",
    ):
        assert len(shared_sdk_file.read_text(encoding="utf-8").splitlines()) < 700

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformDistill.ts").read_text(encoding="utf-8")
    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase19.go").read_text(encoding="utf-8")
    for ts_m in PHASE19_TS_METHODS:
        assert ts_m in ts_src, f"Missing TypeScript SDK method {ts_m}"
    for go_m in PHASE19_GO_METHODS:
        assert f"func (p *PlatformService) {go_m}(" in go_src, f"Missing Go SDK method {go_m}"

    vscode_pkg = (REPO_ROOT / "extensions" / "vscode-keelway" / "package.json").read_text(encoding="utf-8")
    vscode_ext = (REPO_ROOT / "extensions" / "vscode-keelway" / "src" / "extension.ts").read_text(encoding="utf-8")
    assert "keelway.inspectDistillationReadiness" in vscode_pkg
    assert "keelway.inspectDistillationReadiness" in vscode_ext

    openapi_paths = app.openapi()["paths"]
    assert len(openapi_paths) >= 310
    for route in (
        "/v1/platform/distill/shadow/evaluate",
        "/v1/platform/distill/shadow/pairs",
        "/v1/platform/distill/cache/stats",
        "/v1/platform/distill/datasets/compile",
        "/v1/platform/distill/datasets",
        "/v1/platform/distill/promotion/evaluate",
    ):
        assert route in openapi_paths, f"Missing OpenAPI route {route}"
