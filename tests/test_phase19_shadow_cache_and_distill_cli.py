"""
Phase 19A Verification Suite — Semantic Prompt Cache, Shadow Dual-Run Router & QLoRA Distillation
Flywheel (`/v1/platform/distill/*`), 3-Gram Shingle Jaccard Hits, Cross-Workspace/Task Isolation,
Pre-Storage DLP Scrubbing, SFT/DPO Dataset Compilation, Promotion Gate, FastAPI RBAC (`310` OpenAPI
paths), SQLite WAL Persistence, and Sovereign CLI (`shadow`, `distill`).
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_distill_routes import get_shadow_distillation_engine, platform_distill_router
from core.api.platform_runtime_routes import get_rbac_controller, router as platform_runtime_router
from core.main import app as live_app
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.shadow_distillation import (
    SQLiteShadowDistillationEngine,
    ShadowDistillationValidationError,
)
from core.security.auth import launch_token


def test_exact_and_semantic_shingle_cache_hits_and_isolation(tmp_path: Path) -> None:
    eng = SQLiteShadowDistillationEngine(db_path=tmp_path / "cache_isolation.db")
    base_prompt = "Refactor retry loop with bounded exponential backoff in Python"
    code_out = "def retry_with_backoff(n: int = 3) -> float:\n    return min(4.0, 0.25 * (2 ** n))"
    try:
        miss = eng.evaluate_shadow_prompt(
            workspace_id="ws-alpha",
            task_tag="sql-gen",
            prompt=base_prompt,
            frontier_response=code_out,
            local_response=code_out,
            frontier_cost_usd=0.024,
            frontier_latency_ms=910,
        )
        assert miss["verdict"] == "LOCAL_PARITY_READY"
        assert miss["match_type"] == "cache_miss"
        assert miss["pair_id"] is not None and miss["pair_id"].startswith("spair-")
        assert miss["cache_entry_id"].startswith("scache-")
        assert miss["parity_score"] == 1.0
        assert miss["cost_saved_usd"] == 0.0 and miss["latency_saved_ms"] == 0

        # Exact normalized SHA-256 cache hit (extra whitespace collapsed)
        exact_hit = eng.evaluate_shadow_prompt(
            workspace_id="ws-alpha",
            task_tag="sql-gen",
            prompt="  Refactor   retry loop with bounded exponential backoff in Python  ",
            frontier_cost_usd=0.024,
            frontier_latency_ms=880,
        )
        assert exact_hit["verdict"] == "CACHE_HIT" and exact_hit["match_type"] == "exact_sha256"
        assert exact_hit["similarity_score"] == 1.0 and exact_hit["pair_id"] is None
        assert exact_hit["cache_entry_id"] == miss["cache_entry_id"]
        assert exact_hit["cost_saved_usd"] == pytest.approx(0.024)
        assert exact_hit["latency_saved_ms"] == 880

        # Near-duplicate 3-gram shingle Jaccard hit (casing + punctuation + minor article tweak)
        shingle_hit = eng.evaluate_shadow_prompt(
            workspace_id="ws-alpha",
            task_tag="sql-gen",
            prompt="refactor the retry loop with bounded exponential backoff in python!",
            frontier_latency_ms=790,
        )
        assert shingle_hit["verdict"] == "CACHE_HIT" and shingle_hit["match_type"] == "semantic_shingle"
        assert shingle_hit["similarity_score"] >= 0.82 and shingle_hit["pair_id"] is None
        assert shingle_hit["cached_response"] == code_out

        # Cross-task-tag isolation: same workspace, different task_tag MUST miss
        other_tag = eng.evaluate_shadow_prompt(
            workspace_id="ws-alpha",
            task_tag="code-review",
            prompt=base_prompt,
            frontier_response=code_out,
            local_response="# incomplete review",
            frontier_cost_usd=0.015,
        )
        assert other_tag["match_type"] == "cache_miss" and other_tag["verdict"] == "SHADOW_CAPTURED"
        assert other_tag["parity_score"] < 0.85

        # Cross-workspace isolation: different workspace, same task_tag MUST miss
        other_ws = eng.evaluate_shadow_prompt(
            workspace_id="ws-beta",
            task_tag="sql-gen",
            prompt=base_prompt,
            frontier_response=code_out,
            local_response=code_out,
        )
        assert other_ws["match_type"] == "cache_miss" and other_ws["verdict"] == "LOCAL_PARITY_READY"

        # bypass_cache=True forces shadow dual-run even when cached
        bypassed = eng.evaluate_shadow_prompt(
            workspace_id="ws-alpha",
            task_tag="sql-gen",
            prompt=base_prompt,
            frontier_response=code_out,
            local_response="",
            bypass_cache=True,
        )
        assert bypassed["match_type"] == "cache_miss" and bypassed["parity_score"] == 0.0
        assert bypassed["verdict"] == "SHADOW_CAPTURED"

        stats = eng.get_cache_stats(workspace_id="ws-alpha")
        assert stats["entry_count"] == 3
        assert stats["total_hits"] == 2 and stats["total_lookups"] == 5
        assert stats["hit_rate"] == pytest.approx(0.4)
        assert stats["total_cost_saved_usd"] == pytest.approx(0.048)
        assert stats["total_latency_saved_ms"] == 880 + 790
    finally:
        eng.close()


def test_dlp_scrubbing_across_sqlite_wal_pairs_and_sft_dpo_datasets(tmp_path: Path) -> None:
    db_file = tmp_path / "dlp_distill.db"
    eng = SQLiteShadowDistillationEngine(db_path=db_file)
    sk_secret = "sk-live-9988776655abcdefSECRET"
    gh_secret = "ghp_11223344556677889900aabbccddeeff"
    aws_secret = "AKIAIOSFODNN7EXAMPLE"
    pem_secret = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEAsecret\n-----END RSA PRIVATE KEY-----"
    try:
        ev = eng.evaluate_shadow_prompt(
            workspace_id="ws-dlp",
            task_tag="sec-patch",
            prompt=f"Rotate key {sk_secret} and token {gh_secret} safely",
            frontier_response=f"Use vault ref instead of {aws_secret}",
            local_response=f"Never hardcode {pem_secret}",
        )
        assert ev["dlp_redactions"] >= 4
        assert "[REDACTED_SECRET]" in ev["scrubbed_prompt"]
        assert "[REDACTED_SECRET]" in ev["cached_response"]

        pairs = eng.list_shadow_pairs(workspace_id="ws-dlp", task_tag="sec-patch")
        assert pairs["count"] == 1
        pair_blob = json.dumps(pairs)

        dpo_ds = eng.compile_distillation_dataset(
            workspace_id="ws-dlp",
            task_tag="sec-patch",
            export_format="dpo_preference",
            target_base_model="keelway-core:7b",
        )
        assert dpo_ds["dataset_id"].startswith("qds-")
        assert dpo_ds["record_count"] == 1
        assert dpo_ds["lora_rank"] == 16 and dpo_ds["lora_alpha"] == 32
        dpo_row = json.loads(dpo_ds["jsonl_preview"].splitlines()[0])
        assert set(dpo_row.keys()) == {"prompt", "chosen", "rejected"}

        sft_ds = eng.compile_distillation_dataset(
            workspace_id="ws-dlp",
            task_tag="sec-patch",
            export_format="sft_jsonl",
            target_base_model="keelway-reasoning:14b",
        )
        sft_row = json.loads(sft_ds["jsonl_preview"].splitlines()[0])
        assert set(sft_row.keys()) == {"prompt", "completion"}

        empty_ds = eng.compile_distillation_dataset(workspace_id="ws-dlp", task_tag="nonexistent-tag")
        assert empty_ds["record_count"] == 0 and empty_ds["jsonl_preview"] == ""

        ds_list = eng.list_distillation_datasets(workspace_id="ws-dlp", limit=10)
        assert ds_list["count"] == 3

        with sqlite3.connect(db_file) as raw_conn:
            assert raw_conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            dump_blob = "\n".join(raw_conn.iterdump())
            for raw_secret in (sk_secret, gh_secret, aws_secret, "MIIEpAIBAAKCAQEAsecret", "BEGIN RSA PRIVATE KEY"):
                assert raw_secret not in pair_blob
                assert raw_secret not in dpo_ds["jsonl_preview"]
                assert raw_secret not in sft_ds["jsonl_preview"]
                assert raw_secret not in dump_blob
    finally:
        eng.close()


def test_promotion_gate_verdicts_and_validation_errors(tmp_path: Path) -> None:
    eng = SQLiteShadowDistillationEngine(db_path=tmp_path / "promo_gate.db")
    good_code = "def clamp(val: int, lo: int, hi: int) -> int: return max(lo, min(hi, val))"
    try:
        # 1. NEEDS_MORE_PAIRS (only 1 pair vs min_pairs=3)
        eng.evaluate_shadow_prompt(
            workspace_id="ws-gate", task_tag="code-patch", prompt="Write clamp helper v1",
            frontier_response=good_code, local_response=good_code, frontier_cost_usd=0.02,
        )
        needs_more = eng.evaluate_promotion_gate(workspace_id="ws-gate", task_tag="code-patch", min_pairs=3)
        assert needs_more["verdict"] == "NEEDS_MORE_PAIRS"
        assert needs_more["pair_count"] == 1 and needs_more["projected_monthly_savings_usd"] == 0.0
        assert needs_more["gate_sha256"].startswith("sha256:")

        # 2. PROMOTE_TO_OPENCORE (3 high-parity pairs @ $0.02 -> $1,000.00/mo @ 50k reqs)
        for idx in (2, 3):
            eng.evaluate_shadow_prompt(
                workspace_id="ws-gate", task_tag="code-patch", prompt=f"Implement distinct clamp function variant {idx}00",
                frontier_response=good_code, local_response=good_code, frontier_cost_usd=0.02, bypass_cache=True,
            )
        promote = eng.evaluate_promotion_gate(
            workspace_id="ws-gate", task_tag="code-patch", min_pairs=3, min_avg_parity=0.85, monthly_request_volume=50000
        )
        assert promote["verdict"] == "PROMOTE_TO_OPENCORE"
        assert promote["pair_count"] == 3 and promote["avg_parity_score"] >= 0.85
        assert promote["projected_monthly_savings_usd"] == pytest.approx(1000.0)

        # 3. HOLD_ON_FRONTIER (3 low-parity pairs)
        for idx in (1, 2, 3):
            eng.evaluate_shadow_prompt(
                workspace_id="ws-gate", task_tag="complex-arch", prompt=f"Design Raft consensus state machine {idx}",
                frontier_response="class RaftNode:\n    def append_entries(self, term: int, entries: list) -> bool: return True",
                local_response="pass",
                frontier_cost_usd=0.04,
                bypass_cache=True,
            )
        hold = eng.evaluate_promotion_gate(workspace_id="ws-gate", task_tag="complex-arch", min_pairs=3, min_avg_parity=0.85)
        assert hold["verdict"] == "HOLD_ON_FRONTIER"
        assert hold["avg_parity_score"] < 0.85 and hold["projected_monthly_savings_usd"] == 0.0

        for bad_call in (
            lambda: eng.evaluate_shadow_prompt(workspace_id="../escape"),
            lambda: eng.evaluate_shadow_prompt(workspace_id="ws-gate", task_tag="../bad"),
            lambda: eng.evaluate_shadow_prompt(workspace_id="ws-gate", prompt="   "),
            lambda: eng.evaluate_shadow_prompt(workspace_id="ws-gate", similarity_threshold=1.5),
            lambda: eng.compile_distillation_dataset(workspace_id="ws-gate", export_format="csv"),
        ):
            with pytest.raises(ShadowDistillationValidationError):
                bad_call()
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_fastapi_distill_rbac_403_422_and_openapi_310_paths(tmp_path: Path) -> None:
    openapi_paths = live_app.openapi()["paths"]
    assert len(openapi_paths) >= 310
    for route in (
        "/v1/platform/distill/shadow/evaluate",
        "/v1/platform/distill/shadow/pairs",
        "/v1/platform/distill/cache/stats",
        "/v1/platform/distill/datasets/compile",
        "/v1/platform/distill/datasets",
        "/v1/platform/distill/promotion/evaluate",
    ):
        assert route in openapi_paths

    db_file = tmp_path / "api_phase19.db"
    d_eng = SQLiteShadowDistillationEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_distill_router)
    test_app.dependency_overrides[get_shadow_distillation_engine] = lambda: d_eng
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-user"}
        for r in ("owner", "admin", "developer", "operator", "auditor", "viewer")
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            for read_role in ("auditor", "viewer"):
                assert (await client.get("/v1/platform/distill/shadow/pairs?workspace_id=default", headers=headers[read_role])).status_code == 200
                assert (await client.get("/v1/platform/distill/cache/stats?workspace_id=default", headers=headers[read_role])).status_code == 200
                assert (await client.get("/v1/platform/distill/datasets?workspace_id=default", headers=headers[read_role])).status_code == 200
                assert (await client.post("/v1/platform/distill/shadow/evaluate", headers=headers[read_role], json={"workspace_id": "default"})).status_code == 403
                assert (await client.post("/v1/platform/distill/datasets/compile", headers=headers[read_role], json={"workspace_id": "default"})).status_code == 403
                assert (await client.post("/v1/platform/distill/promotion/evaluate", headers=headers[read_role], json={"workspace_id": "default"})).status_code == 403

            ev_resp = await client.post("/v1/platform/distill/shadow/evaluate", headers=headers["developer"], json={"workspace_id": "default"})
            assert ev_resp.status_code == 200 and ev_resp.json()["verdict"] == "LOCAL_PARITY_READY"

            hit_resp = await client.post("/v1/platform/distill/shadow/evaluate", headers=headers["developer"], json={"workspace_id": "default"})
            assert hit_resp.status_code == 200 and hit_resp.json()["verdict"] == "CACHE_HIT"

            comp_resp = await client.post("/v1/platform/distill/datasets/compile", headers=headers["operator"], json={"workspace_id": "default", "export_format": "sft_jsonl"})
            assert comp_resp.status_code == 200 and comp_resp.json()["record_count"] == 1

            prom_resp = await client.post("/v1/platform/distill/promotion/evaluate", headers=headers["owner"], json={"workspace_id": "default", "min_pairs": 1})
            assert prom_resp.status_code == 200 and prom_resp.json()["verdict"] == "PROMOTE_TO_OPENCORE"

            err_422 = await client.post(
                "/v1/platform/distill/shadow/evaluate",
                headers=headers["owner"],
                json={"workspace_id": "../escape", "similarity_threshold": 1.9},
            )
            assert err_422.status_code == 422
    finally:
        d_eng.close()
        rbac.close()


def test_sovereign_cli_shadow_and_distill_exit_codes(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase19.db")

    # 0 pairs -> NEEDS_MORE_PAIRS (exit code 2)
    assert cli_main(["distill", "promote", "--task-tag", "code-patch", "--min-pairs", "2", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["verdict"] == "NEEDS_MORE_PAIRS"

    # Low parity pairs -> HOLD_ON_FRONTIER (exit code 1)
    for idx in (1, 2):
        assert cli_main([
            "shadow", "evaluate", "--prompt", f"Complex distributed lock {idx}",
            "--frontier-response", "def acquire_lock(redis, key, ttl=30): return redis.set(key, '1', nx=True, ex=ttl)",
            "--local-response", "todo", "--task-tag", "lock-gen",
            "--bypass-cache", "--workspace", "ws-cli19", "--db-path", db_file, "--json",
        ]) == 0
        capsys.readouterr()

    assert cli_main(["distill", "promote", "--task-tag", "lock-gen", "--min-pairs", "2", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "HOLD_ON_FRONTIER"

    # High parity pairs + cache hit + PROMOTE_TO_OPENCORE (exit code 0)
    for idx in (1, 2):
        assert cli_main([
            "shadow", "evaluate", "--prompt", f"Retry helper function {idx}",
            "--task-tag", "code-patch", "--bypass-cache", "--workspace", "ws-cli19", "--db-path", db_file, "--json",
        ]) == 0
        capsys.readouterr()

    assert cli_main(["shadow", "evaluate", "--prompt", "Retry helper function 1", "--task-tag", "code-patch", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "CACHE_HIT"

    assert cli_main(["shadow", "pairs", "--task-tag", "code-patch", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2

    assert cli_main(["shadow", "stats", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["total_hits"] == 1

    assert cli_main(["distill", "compile", "--task-tag", "code-patch", "--format", "dpo_preference", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["record_count"] == 2

    assert cli_main(["distill", "datasets", "--limit", "5", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    assert cli_main(["distill", "promote", "--task-tag", "code-patch", "--min-pairs", "2", "--monthly-volume", "10000", "--workspace", "ws-cli19", "--db-path", db_file, "--json"]) == 0
    prom_out = json.loads(capsys.readouterr().out)
    assert prom_out["verdict"] == "PROMOTE_TO_OPENCORE" and prom_out["projected_monthly_savings_usd"] > 0
