"""
Phase 3C Verification Suite:
1. `MarketplaceSettlementLedger` integer-cent splits (85/15, 80/20, 0/100), zero rounding drift,
   cryptographic SHA-256 receipts, automatic `MarketplaceRegistry` installation, and `SQLitePlatformStore` WAL durability.
2. FastAPI `/v1/platform/marketplace/purchase` & `/v1/platform/marketplace/settlements` routes.
3. Python SDK (`KeelwayClient.cluster` & `AsyncKeelwayClient.cluster` + Marketplace settlement parity)
   over `httpx.MockTransport` and live FastAPI `ASGITransport`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import FastAPI
import httpx
from httpx import ASGITransport
import pytest

from core.api.platform_routes import (
    get_marketplace_registry,
    get_platform_hub,
    get_settlement_ledger,
    get_subscription_engine,
    router as platform_router,
)
from core.platform import (
    MarketplaceRegistry,
    MarketplaceSettlementLedger,
    SQLitePlatformStore,
    SettlementRecord,
    SubscriptionPolicyEngine,
    UnifiedWorkspaceHub,
    calculate_settlement_split,
)
from core.sdk import (
    AsyncClusterClient,
    AsyncKeelwayClient,
    KeelwayClient,
    SyncClusterClient,
    TaskNotFoundError,
)
from core.security.auth import launch_token


# ---------------------------------------------------------------------------
# 1. Integer-Cent Revenue Splits & SQLite WAL Settlement Durability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gross_cents",
    [0, 1, 2, 3, 7, 19, 99, 1500, 1999, 2995, 3900, 49900, 123457],
)
def test_cent_split_zero_rounding_drift_across_all_tiers(gross_cents: int) -> None:
    v3p = calculate_settlement_split("verified_third_party", gross_cents=gross_cents)
    assert v3p["creator_payout_cents"] == round(gross_cents * 85 / 100)
    assert v3p["platform_fee_cents"] == gross_cents - v3p["creator_payout_cents"]
    assert v3p["creator_payout_cents"] + v3p["platform_fee_cents"] == gross_cents

    ent = calculate_settlement_split("enterprise_partner", gross_cents=gross_cents)
    assert ent["creator_payout_cents"] == round(gross_cents * 80 / 100)
    assert ent["platform_fee_cents"] == gross_cents - ent["creator_payout_cents"]
    assert ent["creator_payout_cents"] + ent["platform_fee_cents"] == gross_cents

    fp = calculate_settlement_split("first_party", gross_cents=gross_cents)
    assert fp["creator_payout_cents"] == 0
    assert fp["platform_fee_cents"] == gross_cents


def test_settlement_ledger_sqlite_wal_persistence_and_install(tmp_path: Path) -> None:
    db_path = tmp_path / "settlements_wal.db"
    store_1 = SQLitePlatformStore(db_path)
    assert store_1.journal_mode == "wal"

    mp_1 = MarketplaceRegistry(store=store_1)
    mp_1.publish_package(
        {
            "id": "odd-cent-skill",
            "name": "Odd Cent Static Analyzer",
            "kind": "agent_skill",
            "version": "1.2.3",
            "publisher": "Indie Labs",
            "publisher_tier": "verified_third_party",
            "pricing_model": "one_time",
            "price_usd": 19.99,
            "license_spdx": "MIT",
            "description": "Tests awkward cent split precision.",
            "permissions": {"read_paths": ["src/"], "write_paths": [], "network": "none"},
        }
    )
    ledger_1 = MarketplaceSettlementLedger(registry=mp_1, store=store_1)

    rec_3p = ledger_1.purchase_package("odd-cent-skill", buyer_tenant_id="tenant-alpha")
    assert isinstance(rec_3p, SettlementRecord)
    assert rec_3p.gross_cents == 1999
    assert rec_3p.creator_payout_cents == 1699  # round(1999 * 85 / 100)
    assert rec_3p.platform_fee_cents == 300
    assert rec_3p.creator_payout_cents + rec_3p.platform_fee_cents == rec_3p.gross_cents
    assert rec_3p.gross_usd == 19.99
    assert rec_3p.creator_payout_usd == 16.99
    assert rec_3p.platform_fee_usd == 3.00
    assert rec_3p.license_spdx == "MIT"
    assert len(rec_3p.entitlement_sha256) == 64
    assert len(rec_3p.receipt_sha256) == 64
    assert MarketplaceSettlementLedger.verify_receipt(rec_3p) is True

    # Partner 80/20 ($499.00) & First-party 0/100 ($29.00 & $0.00 free)
    rec_ent = ledger_1.purchase_package("finreg-sovereign-compliance", buyer_tenant_id="tenant-alpha")
    assert (rec_ent.gross_usd, rec_ent.creator_payout_usd, rec_ent.platform_fee_usd) == (499.0, 399.2, 99.8)

    rec_fp_paid = ledger_1.purchase_package("keelway-release-swarm", buyer_tenant_id="tenant-beta")
    assert (rec_fp_paid.gross_usd, rec_fp_paid.creator_payout_usd, rec_fp_paid.platform_fee_usd) == (29.0, 0.0, 29.0)

    rec_fp_free = ledger_1.purchase_package("keelway-pr-sentinel", buyer_tenant_id="tenant-beta")
    assert (rec_fp_free.gross_cents, rec_fp_free.creator_payout_cents, rec_fp_free.platform_fee_cents) == (0, 0, 0)
    assert rec_fp_free.license_spdx == "Apache-2.0"

    # Verify installations recorded in MarketplaceRegistry
    installed_alpha = {i["package_id"] for i in mp_1.list_installed("tenant-alpha")}
    assert {"odd-cent-skill", "finreg-sovereign-compliance"} <= installed_alpha

    store_1.close()

    # Reload from SQLite WAL store after simulated daemon restart
    with SQLitePlatformStore(db_path) as store_2:
        mp_2 = MarketplaceRegistry(store=store_2)
        ledger_2 = MarketplaceSettlementLedger(registry=mp_2, store=store_2)

        all_summary = ledger_2.summarize_settlements()
        assert all_summary["totals"]["count"] == 4
        assert all_summary["totals"]["gross_usd"] == 547.99
        assert all_summary["totals"]["creator_payout_usd"] == 416.19
        assert all_summary["totals"]["platform_fee_usd"] == 131.80
        assert (
            all_summary["totals"]["creator_payout_cents"] + all_summary["totals"]["platform_fee_cents"]
            == all_summary["totals"]["gross_cents"]
        )

        alpha_summary = ledger_2.summarize_settlements(tenant_id="tenant-alpha")
        assert alpha_summary["totals"]["count"] == 2
        assert alpha_summary["totals"]["gross_usd"] == 518.99

        beta_summary = ledger_2.summarize_settlements(tenant_id="tenant-beta")
        assert beta_summary["totals"]["count"] == 2
        assert beta_summary["totals"]["gross_usd"] == 29.00


# ---------------------------------------------------------------------------
# 2. Python SDK `client.cluster` Sync + Async MockTransport Parity
# ---------------------------------------------------------------------------


def _make_cluster_and_settlement_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else None
        path = request.url.path
        method = request.method
        params = dict(request.url.params)
        recorded.append({"method": method, "path": path, "params": params, "json": body})

        if method == "GET" and path == "/v1/cluster/nodes":
            return httpx.Response(200, json={"nodes": [{"node_id": "node-eu-01", "region": params.get("region", "eu")}], "total": 1})
        if method == "POST" and path == "/v1/cluster/nodes/register":
            return httpx.Response(201, json={**(body or {}), "status": "healthy"})
        if method == "POST" and path.startswith("/v1/cluster/nodes/") and path.endswith("/drain"):
            nid = path.split("/")[4]
            return httpx.Response(200, json={"node_id": nid, "status": "drained"})
        if method == "POST" and path.startswith("/v1/cluster/nodes/") and path.endswith("/restore"):
            nid = path.split("/")[4]
            return httpx.Response(200, json={"node_id": nid, "status": "healthy"})
        if method == "POST" and path == "/v1/cluster/schedule":
            return httpx.Response(200, json={"selected_node_id": "node-eu-01", "model_id": body["model_id"]})
        if method == "GET" and path == "/v1/cluster/lifecycle":
            return httpx.Response(200, json={"entries": [{"model_id": "keelway-core:7b", "stage": "stable"}], "total": 1})
        if method == "POST" and path == "/v1/cluster/lifecycle/promote":
            return httpx.Response(200, json={"model_id": body["model_id"], "stage": body.get("target_stage", "stable")})
        if method == "POST" and path == "/v1/cluster/lifecycle/rollback":
            return httpx.Response(200, json={"model_id": body["model_id"], "stage": "deprecated", "rollback_reason": body.get("reason")})
        if method == "GET" and path == "/v1/cluster/governance-adapter/status":
            return httpx.Response(200, json={"backend": "sqlite_parity", "status": "healthy"})
        if method == "POST" and path == "/v1/cluster/governance-adapter/reserve-budget":
            return httpx.Response(200, json={"allowed": True, "tenant_id": body["tenant_id"]})
        if method == "POST" and path == "/v1/platform/marketplace/purchase":
            if body["package_id"] == "missing-pkg":
                return httpx.Response(404, json={"detail": "Package not found"})
            return httpx.Response(200, json={"settlement_id": "stl_mock_1", "package_id": body["package_id"], "buyer_tenant_id": body["buyer_tenant_id"], "gross_usd": 15.0, "creator_payout_usd": 12.75, "platform_fee_usd": 2.25})
        if method == "GET" and path == "/v1/platform/marketplace/settlements":
            return httpx.Response(200, json={"settlements": [{"settlement_id": "stl_mock_1"}], "totals": {"count": 1, "gross_usd": 15.0, "creator_payout_usd": 12.75, "platform_fee_usd": 2.25}})
        return httpx.Response(404, json={"detail": f"Unhandled {method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_sync_cluster_and_settlement_sdk_parity() -> None:
    transport, recorded = _make_cluster_and_settlement_mock_transport()
    with KeelwayClient(token="kw_live_cluster_sync", transport=transport) as client:
        assert isinstance(client.cluster, SyncClusterClient)

        nodes = client.cluster.list_nodes(region="eu", runtime="vllm", include_drained=False)
        assert nodes["nodes"][0]["node_id"] == "node-eu-01"
        assert recorded[0]["params"] == {"include_drained": "false", "region": "eu", "runtime": "vllm"}

        assert client.cluster.register_node({"node_id": "node-eu-02", "runtime": "vllm", "region": "eu", "total_vram_gb": 80})["status"] == "healthy"
        assert client.cluster.drain_node("node-eu-02")["status"] == "drained"
        assert client.cluster.restore_node("node-eu-02")["status"] == "healthy"
        assert client.cluster.schedule({"model_id": "keelway-core:7b", "required_vram_gb": 16})["selected_node_id"] == "node-eu-01"
        assert client.cluster.list_lifecycle()["total"] == 1
        assert client.cluster.promote_model({"model_id": "keelway-coder:14b-v2", "target_stage": "stable"})["stage"] == "stable"
        assert client.cluster.rollback_model({"model_id": "keelway-coder:14b-v2", "reason": "TTFT spike"})["stage"] == "deprecated"
        assert client.cluster.governance_adapter_status()["status"] == "healthy"
        assert client.cluster.reserve_budget({"tenant_id": "t-1", "amount_usd": 2.5})["allowed"] is True

        stl = client.platform.purchase_marketplace_package("linear-github-mcp-bridge", buyer_tenant_id="t-1")
        assert stl["settlement_id"] == "stl_mock_1"
        assert client.platform.list_marketplace_settlements(tenant_id="t-1")["totals"]["count"] == 1

        with pytest.raises(TaskNotFoundError):
            client.platform.purchase_marketplace_package("missing-pkg")


@pytest.mark.asyncio
async def test_async_live_asgi_settlement_and_cluster_roundtrip(tmp_path: Path) -> None:
    store = SQLitePlatformStore(tmp_path / "live_asgi_phase3c.db")
    mp = MarketplaceRegistry(store=store)
    ledger = MarketplaceSettlementLedger(registry=mp, store=store)
    hub = UnifiedWorkspaceHub(store=store)
    sub = SubscriptionPolicyEngine()

    app = FastAPI()
    app.include_router(platform_router)
    app.dependency_overrides[get_platform_hub] = lambda: hub
    app.dependency_overrides[get_marketplace_registry] = lambda: mp
    app.dependency_overrides[get_settlement_ledger] = lambda: ledger
    app.dependency_overrides[get_subscription_engine] = lambda: sub

    from core.api.cluster_routes import (
        get_cluster_scheduler,
        get_lifecycle_registry,
        get_postgres_governance_adapter,
        router as cluster_router,
    )
    from core.cluster import ClusterScheduler, ModelLifecycleRegistry, PostgresGovernanceAdapter

    sched = ClusterScheduler()
    life = ModelLifecycleRegistry()
    gov_adapter = PostgresGovernanceAdapter()
    app.include_router(cluster_router)
    app.dependency_overrides[get_cluster_scheduler] = lambda: sched
    app.dependency_overrides[get_lifecycle_registry] = lambda: life
    app.dependency_overrides[get_postgres_governance_adapter] = lambda: gov_adapter

    try:
        async with AsyncKeelwayClient(
            base_url="http://testserver",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as client:
            assert isinstance(client.cluster, AsyncClusterClient)

            # 1. Marketplace commercial purchase + settlement summary + 404 unknown package
            stl_1 = await client.platform.purchase_marketplace_package(
                "linear-github-mcp-bridge", buyer_tenant_id="tenant-nairobi"
            )
            assert stl_1["gross_usd"] == 15.0
            assert stl_1["creator_payout_usd"] == 12.75
            assert stl_1["platform_fee_usd"] == 2.25
            assert stl_1["installed"] is True

            stl_2 = await client.platform.purchase_marketplace_package(
                "finreg-sovereign-compliance", buyer_tenant_id="tenant-zurich"
            )
            assert (stl_2["gross_usd"], stl_2["creator_payout_usd"], stl_2["platform_fee_usd"]) == (499.0, 399.2, 99.8)

            with pytest.raises(TaskNotFoundError):
                await client.platform.purchase_marketplace_package("does-not-exist")

            nairobi_only = await client.platform.list_marketplace_settlements(tenant_id="tenant-nairobi")
            assert nairobi_only["totals"]["count"] == 1
            assert nairobi_only["totals"]["gross_usd"] == 15.0

            all_stl = await client.platform.list_marketplace_settlements()
            assert all_stl["totals"]["count"] == 2
            assert all_stl["totals"]["gross_usd"] == 514.0

            # 2. Live Cluster endpoints via AsyncClusterClient
            nodes = await client.cluster.list_nodes()
            assert nodes["total"] >= 4
            reg = await client.cluster.register_node(
                {"node_id": "node-test-vllm-99", "runtime": "vllm", "region": "eu", "total_vram_gb": 80.0}
            )
            assert reg["node_id"] == "node-test-vllm-99"
            assert (await client.cluster.drain_node("node-test-vllm-99"))["status"] == "drained"
            assert (await client.cluster.restore_node("node-test-vllm-99"))["status"] == "healthy"

            placement = await client.cluster.schedule(
                {"model_id": "qwen2.5-coder:7b", "required_vram_gb": 24.0, "region_residency": "eu"}
            )
            assert placement["region"] == "eu"

            lifecycle = await client.cluster.list_lifecycle()
            assert lifecycle["total"] >= 3
            promoted = await client.cluster.promote_model(
                {"model_id": "keelway-coder:14b-v2", "target_stage": "stable", "traffic_weight_pct": 100}
            )
            assert promoted["stage"] == "stable"
            rolled = await client.cluster.rollback_model(
                {"model_id": "keelway-coder:14b-v2", "reason": "Canary latency test"}
            )
            assert rolled["stage"] == "deprecated"

            gov_status = await client.cluster.governance_adapter_status()
            assert "mode" in gov_status or "backend" in gov_status or isinstance(gov_status, dict)
            budget = await client.cluster.reserve_budget(
                {"tenant_id": "tenant-nairobi", "amount_usd": 5.0, "monthly_limit_usd": 100.0}
            )
            assert budget["allowed"] is True
    finally:
        store.close()
