"""
TDD Unit, Concurrency & FastAPI Integration Suite for Phase 3A (`KEEL-CLUSTER-008`):
1. `ClusterScheduler` (`core/cluster/scheduler.py`): 4 default GPU nodes, fail-closed residency & privacy,
   queue-depth/VRAM/TP placement scoring, heartbeat, drain & restore.
2. `PostgresGovernanceAdapter` (`core/cluster/postgres_adapter.py`): PostgreSQL 16+ DDL, parameterized
   `SELECT ... FOR UPDATE` SQL builders, injected DB-API 2.0 execution, thread-safe SQLite WAL parity,
   hard USD spend caps (`fallback_opencore` / `deny_http_402`), and SHA-256 chain tamper detection.
3. `ModelLifecycleRegistry` (`core/cluster/lifecycle.py`): Canary weights, benchmark + TTFT SLO promotion
   gates, and automatic canary rollback.
4. FastAPI `/v1/cluster/*` Control-Plane Routes (`core/api/cluster_routes.py`).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from fastapi.testclient import TestClient
import pytest

from core.api.cluster_routes import (
    get_cluster_scheduler,
    get_lifecycle_registry,
    get_postgres_governance_adapter,
)
from core.cluster import (
    GENESIS_AUDIT_HASH,
    POSTGRES_GOVERNANCE_DDL,
    ClusterScheduler,
    ModelLifecycleRegistry,
    PostgresGovernanceAdapter,
    build_append_audit_chain_sql,
    build_select_budget_for_update_sql,
)
from core.main import app


# ---------------------------------------------------------------------------
# 1. ClusterScheduler — Multi-Node Placement & Fail-Closed Residency
# ---------------------------------------------------------------------------


def test_cluster_scheduler_default_fleet_and_filtering() -> None:
    scheduler = ClusterScheduler()
    all_nodes = scheduler.list_nodes()
    assert len(all_nodes) == 4
    by_id = {n.node_id: n for n in all_nodes}

    assert by_id["node-metal-local-01"].runtime == "ollama_metal"
    assert by_id["node-metal-local-01"].total_vram_gb == 32.0
    assert by_id["node-metal-local-01"].region == "airgap_local"

    assert by_id["node-vllm-us-01"].runtime == "vllm"
    assert by_id["node-vllm-us-01"].gpu_count == 2
    assert by_id["node-vllm-us-01"].total_vram_gb == 160.0
    assert by_id["node-vllm-us-01"].region == "us"

    assert by_id["node-vllm-eu-01"].runtime == "vllm"
    assert by_id["node-vllm-eu-01"].total_vram_gb == 80.0
    assert by_id["node-vllm-eu-01"].region == "eu"

    assert by_id["node-ray-af-01"].runtime == "ray_serve"
    assert by_id["node-ray-af-01"].total_vram_gb == 48.0
    assert by_id["node-ray-af-01"].region == "africa"

    assert len(scheduler.list_nodes(runtime="vllm")) == 2
    assert len(scheduler.list_nodes(region="africa")) == 1


def test_cluster_scheduler_fail_closed_privacy_residency_and_scoring() -> None:
    scheduler = ClusterScheduler()

    # Private workloads MUST route strictly to airgap_local even if global residency is requested
    private_dec = scheduler.schedule_placement(
        model_id="keelway-core:7b",
        required_vram_gb=16.0,
        region_residency="global",
        privacy_level="private",
    )
    assert private_dec.selected_node_id == "node-metal-local-01"
    assert private_dec.region == "airgap_local"
    assert len(private_dec.receipt_sha256) == 64

    # Private workload requesting 64GB (>32GB local Metal node) MUST fail closed, never leaking to US/EU
    with pytest.raises(ValueError, match="airgap_local"):
        scheduler.schedule_placement(
            model_id="deepseek-r1:70b",
            required_vram_gb=64.0,
            region_residency="global",
            privacy_level="private",
        )

    # Conflicting private + EU residency fails closed
    with pytest.raises(ValueError, match="Fail-closed residency conflict"):
        scheduler.schedule_placement(
            model_id="keelway-core:7b",
            required_vram_gb=8.0,
            region_residency="eu",
            privacy_level="private",
        )

    # Regional sovereignty pin: eu, us, africa
    eu_dec = scheduler.schedule_placement("qwen2.5-coder:7b", required_vram_gb=24.0, region_residency="eu")
    assert eu_dec.selected_node_id == "node-vllm-eu-01"

    af_dec = scheduler.schedule_placement("keelway-core:7b", required_vram_gb=24.0, region_residency="africa")
    assert af_dec.selected_node_id == "node-ray-af-01"

    # Tensor-parallel = 2 selects 2x80GB US vLLM node
    tp_dec = scheduler.schedule_placement(
        model_id="deepseek-r1:70b",
        required_vram_gb=140.0,
        region_residency="global",
        tensor_parallel=2,
    )
    assert tp_dec.selected_node_id == "node-vllm-us-01"
    assert tp_dec.tensor_parallel == 2

    # Global vLLM preference picks lower queue depth EU node (0 active) over US node (1 active)
    vllm_dec = scheduler.schedule_placement(
        model_id="qwen2.5-coder:7b",
        required_vram_gb=24.0,
        region_residency="global",
        runtime_preference="vllm",
    )
    assert vllm_dec.selected_node_id == "node-vllm-eu-01"

    # Heartbeat + drain + restore lifecycle
    scheduler.heartbeat_node("node-vllm-eu-01", active_requests=10, free_vram_gb=20.0)
    shifted = scheduler.schedule_placement(
        model_id="qwen2.5-coder:7b",
        required_vram_gb=24.0,
        region_residency="global",
        runtime_preference="vllm",
    )
    assert shifted.selected_node_id == "node-vllm-us-01"

    drained = scheduler.drain_node("node-ray-af-01")
    assert drained.status == "drained"
    assert len(scheduler.list_nodes(include_drained=False)) == 3
    with pytest.raises(ValueError):
        scheduler.schedule_placement("keelway-core:7b", required_vram_gb=8.0, region_residency="africa")

    restored = scheduler.restore_node("node-ray-af-01")
    assert restored.status == "healthy"
    assert scheduler.schedule_placement("keelway-core:7b", required_vram_gb=8.0, region_residency="africa").selected_node_id == "node-ray-af-01"


# ---------------------------------------------------------------------------
# 2. PostgresGovernanceAdapter — Row-Locked SQL, DB-API 2.0 & SQLite WAL Parity
# ---------------------------------------------------------------------------


class _FakePgState:
    def __init__(self) -> None:
        self.budgets: Dict[str, List[Any]] = {}
        self.audit: List[Tuple[Any, ...]] = []
        self.executed_sql: List[str] = []
        self.commits = 0
        self.rollbacks = 0


class _FakePgCursor:
    def __init__(self, state: _FakePgState) -> None:
        self.s = state
        self._one: Optional[Tuple[Any, ...]] = None
        self._all: List[Tuple[Any, ...]] = []

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> None:
        self.s.executed_sql.append(sql)
        norm = " ".join(sql.split())
        if norm.startswith("SELECT tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore"):
            t_id = params[0]
            self._one = tuple(self.s.budgets[t_id][:4]) if t_id in self.s.budgets else None
        elif norm.startswith("INSERT INTO keelway_tenant_budgets"):
            self.s.budgets[params[0]] = [params[0], params[1], params[2], params[3], params[4]]
        elif norm.startswith("UPDATE keelway_tenant_budgets SET monthly_limit_usd"):
            self.s.budgets[params[4]] = [params[4], params[0], params[1], params[2], params[3]]
        elif norm.startswith("UPDATE keelway_tenant_budgets SET spent_usd"):
            self.s.budgets[params[2]][2] = params[0]
            self.s.budgets[params[2]][4] = params[1]
        elif norm.startswith("SELECT seq, entry_hash FROM keelway_cluster_audit_chain"):
            self._one = (self.s.audit[-1][0], self.s.audit[-1][8]) if self.s.audit else None
        elif "INSERT INTO keelway_cluster_audit_chain" in norm:
            head_h = self.s.audit[-1][8] if self.s.audit else GENESIS_AUDIT_HASH
            assert params[9] == head_h
            seq = len(self.s.audit) + 1
            self.s.audit.append((seq, params[0], params[1], params[2], params[3], params[4], params[5], params[6], params[7], params[8]))
        elif norm.startswith("SELECT seq, tenant_id, actor"):
            self._all = list(self.s.audit)
        elif norm.startswith("SELECT COUNT(*) FROM keelway_tenant_budgets"):
            self._one = (len(self.s.budgets),)

    def fetchone(self) -> Optional[Tuple[Any, ...]]:
        return self._one

    def fetchall(self) -> List[Tuple[Any, ...]]:
        return list(self._all)

    def close(self) -> None:
        pass


class _FakePgConn:
    def __init__(self, state: _FakePgState) -> None:
        self.s = state

    def cursor(self) -> _FakePgCursor:
        return _FakePgCursor(self.s)

    def commit(self) -> None:
        self.s.commits += 1

    def rollback(self) -> None:
        self.s.rollbacks += 1


def test_postgres_ddl_row_locking_sql_and_injected_dbapi_execution() -> None:
    assert "CREATE TABLE IF NOT EXISTS keelway_tenant_budgets" in POSTGRES_GOVERNANCE_DDL
    assert "CREATE TABLE IF NOT EXISTS keelway_cluster_audit_chain" in POSTGRES_GOVERNANCE_DDL
    assert GENESIS_AUDIT_HASH in POSTGRES_GOVERNANCE_DDL

    lock_sql = build_select_budget_for_update_sql()
    assert lock_sql == (
        "SELECT tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore "
        "FROM keelway_tenant_budgets WHERE tenant_id = %s FOR UPDATE"
    )
    append_sql = build_append_audit_chain_sql()
    assert "FOR UPDATE" in append_sql
    assert "INSERT INTO keelway_cluster_audit_chain" in append_sql

    pg_state = _FakePgState()
    adapter = PostgresGovernanceAdapter(
        dsn="postgresql://keelway@localhost:5432/keelway",
        connection_factory=lambda: _FakePgConn(pg_state),
    )
    adapter.configure_tenant_budget("tenant-pg", monthly_limit_usd=20.0, fallback_to_opencore=False)
    r1 = adapter.reserve_spend_atomic("tenant-pg", amount_usd=15.0, actor="svc-a", capability="responses.create")
    assert r1.allowed is True
    assert r1.action == "reserved"
    assert r1.prev_hash == GENESIS_AUDIT_HASH

    r2 = adapter.reserve_spend_atomic("tenant-pg", amount_usd=8.0, actor="svc-a", capability="responses.create")
    assert r2.allowed is False
    assert r2.action == "deny_http_402"
    assert r2.status_code == 402
    assert r2.spent_usd == 15.0
    assert r2.prev_hash == r1.entry_hash

    assert any("FOR UPDATE" in s for s in pg_state.executed_sql)
    ver = adapter.verify_audit_chain(tenant_id="tenant-pg")
    assert ver.valid is True
    assert ver.entries_checked == 2
    status = adapter.get_adapter_status()
    assert status["mode"] == "postgres"
    assert status["backend"] == "postgres_dbapi"
    assert status["chain_valid"] is True


def test_sqlite_wal_parity_atomic_concurrency_and_tamper_detection(tmp_path: Path) -> None:
    db_file = tmp_path / "cluster_governance_wal.db"
    adapter = PostgresGovernanceAdapter(sqlite_path=db_file)
    adapter.configure_tenant_budget("acme-corp", monthly_limit_usd=25.0, fallback_to_opencore=True)

    # 10 concurrent threads attempting $5.00 each against $25.00 cap -> exactly 5 succeed, 5 fallback_opencore
    def _worker(idx: int):
        return adapter.reserve_spend_atomic("acme-corp", amount_usd=5.0, actor=f"worker-{idx}", capability="batch.run")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_worker, range(10)))

    allowed_res = [r for r in results if r.allowed]
    fallback_res = [r for r in results if not r.allowed]
    assert len(allowed_res) == 5
    assert len(fallback_res) == 5
    assert all(r.action == "fallback_opencore" and r.fallback_model_id == "keelway-core:7b" for r in fallback_res)

    ver_ok = adapter.verify_audit_chain()
    assert ver_ok.valid is True
    assert ver_ok.entries_checked == 10

    # Tamper directly with row seq=4 in SQLite and confirm SHA-256 chain catches it
    raw_conn = sqlite3.connect(str(db_file))
    try:
        raw_conn.execute("UPDATE keelway_cluster_audit_chain SET amount_usd = 0.01 WHERE seq = 4")
        raw_conn.commit()
    finally:
        raw_conn.close()

    ver_tampered = adapter.verify_audit_chain()
    assert ver_tampered.valid is False
    assert ver_tampered.broken_at_seq == 4
    assert ver_tampered.reason == "ENTRY_HASH_TAMPERED"


# ---------------------------------------------------------------------------
# 3. ModelLifecycleRegistry — Canary Promotion Gates & Rollback
# ---------------------------------------------------------------------------


def test_model_lifecycle_registry_promotion_gates_and_rollback() -> None:
    reg = ModelLifecycleRegistry()
    entries = {e.model_id: e for e in reg.list_entries()}
    assert entries["keelway-core:7b"].stage == "stable"
    assert entries["keelway-core:7b"].traffic_weight_pct == 100
    assert entries["keelway-coder:14b-v2"].stage == "canary"
    assert entries["keelway-coder:14b-v2"].traffic_weight_pct == 15
    assert entries["qwen2.5-coder:7b"].stage == "stable"

    # Healthy canary promotes cleanly to stable 100%
    promoted = reg.promote_model("keelway-coder:14b-v2", target_stage="stable", traffic_weight_pct=100)
    assert promoted.stage == "stable"
    assert promoted.traffic_weight_pct == 100

    # Canary failing benchmark pass rate (< 0.95) is blocked from stable promotion
    reg.register_entry(
        model_id="experimental-coder:7b-rc1",
        stage="canary",
        traffic_weight_pct=10,
        benchmark_pass_rate=0.91,
        ttft_p95_ms=190.0,
        ttft_slo_ms=300.0,
    )
    with pytest.raises(ValueError, match="benchmark_pass_rate"):
        reg.promote_model("experimental-coder:7b-rc1", target_stage="stable")

    # Canary breaching TTFT p95 SLO (> ttft_slo_ms) is blocked from stable promotion
    reg.register_entry(
        model_id="slow-reasoner:32b-rc1",
        stage="canary",
        traffic_weight_pct=5,
        benchmark_pass_rate=0.97,
        ttft_p95_ms=420.0,
        ttft_slo_ms=300.0,
    )
    with pytest.raises(ValueError, match="ttft_p95_ms"):
        reg.promote_model("slow-reasoner:32b-rc1", target_stage="stable")

    # Rollback halts traffic (0%), sets stage="deprecated", and records reason + timestamp
    rolled_back = reg.rollback_canary("slow-reasoner:32b-rc1", reason="TTFT p95 spiked above 400ms in canary")
    assert rolled_back.stage == "deprecated"
    assert rolled_back.traffic_weight_pct == 0
    assert rolled_back.rollback_reason == "TTFT p95 spiked above 400ms in canary"
    assert rolled_back.rolled_back_at is not None


# ---------------------------------------------------------------------------
# 4. FastAPI `/v1/cluster/*` Control-Plane End-to-End Integration
# ---------------------------------------------------------------------------


def test_fastapi_cluster_control_plane_routes(tmp_path: Path) -> None:
    isolated_scheduler = ClusterScheduler()
    isolated_lifecycle = ModelLifecycleRegistry()
    isolated_adapter = PostgresGovernanceAdapter(sqlite_path=tmp_path / "api_cluster_gov.db")

    app.dependency_overrides[get_cluster_scheduler] = lambda: isolated_scheduler
    app.dependency_overrides[get_lifecycle_registry] = lambda: isolated_lifecycle
    app.dependency_overrides[get_postgres_governance_adapter] = lambda: isolated_adapter

    try:
        client = TestClient(app)

        # 1. GET /v1/cluster/nodes + POST /v1/cluster/nodes/register + drain + restore
        r_nodes = client.get("/v1/cluster/nodes")
        assert r_nodes.status_code == 200
        assert r_nodes.json()["total"] == 4

        r_reg = client.post(
            "/v1/cluster/nodes/register",
            json={
                "node_id": "node-vllm-eu-02",
                "runtime": "vllm",
                "region": "eu",
                "total_vram_gb": 160.0,
                "gpu_count": 2,
                "gpu_model": "NVIDIA H200",
            },
        )
        assert r_reg.status_code == 201
        assert r_reg.json()["node_id"] == "node-vllm-eu-02"

        r_drain = client.post("/v1/cluster/nodes/node-vllm-eu-02/drain")
        assert r_drain.status_code == 200
        assert r_drain.json()["status"] == "drained"

        r_restore = client.post("/v1/cluster/nodes/node-vllm-eu-02/restore")
        assert r_restore.status_code == 200
        assert r_restore.json()["status"] == "healthy"

        # 2. POST /v1/cluster/schedule (success + fail-closed 503 + invalid 422)
        r_sched = client.post(
            "/v1/cluster/schedule",
            json={
                "model_id": "keelway-core:7b",
                "required_vram_gb": 16.0,
                "privacy_level": "private",
            },
        )
        assert r_sched.status_code == 200
        assert r_sched.json()["selected_node_id"] == "node-metal-local-01"

        r_unavail = client.post(
            "/v1/cluster/schedule",
            json={
                "model_id": "giant-model:405b",
                "required_vram_gb": 640.0,
                "region_residency": "global",
            },
        )
        assert r_unavail.status_code in (422, 503)

        r_bad_zone = client.post(
            "/v1/cluster/schedule",
            json={"model_id": "keelway-core:7b", "required_vram_gb": 8.0, "region_residency": "mars"},
        )
        assert r_bad_zone.status_code == 422

        # 3. Lifecycle GET + promote + rollback
        r_lc = client.get("/v1/cluster/lifecycle")
        assert r_lc.status_code == 200
        assert r_lc.json()["total"] == 3

        r_prom = client.post(
            "/v1/cluster/lifecycle/promote",
            json={"model_id": "keelway-coder:14b-v2", "target_stage": "stable", "traffic_weight_pct": 100},
        )
        assert r_prom.status_code == 200
        assert r_prom.json()["stage"] == "stable"

        r_rb = client.post(
            "/v1/cluster/lifecycle/rollback",
            json={"model_id": "keelway-coder:14b-v2", "reason": "Manual operator canary halt"},
        )
        assert r_rb.status_code == 200
        assert r_rb.json()["stage"] == "deprecated"
        assert r_rb.json()["traffic_weight_pct"] == 0

        # 4. Governance adapter status + reserve-budget (200 reserved, 200 fallback, 402 hard deny)
        r_status = client.get("/v1/cluster/governance-adapter/status")
        assert r_status.status_code == 200
        assert r_status.json()["backend"] == "sqlite_wal"
        assert r_status.json()["chain_valid"] is True

        r_res_ok = client.post(
            "/v1/cluster/governance-adapter/reserve-budget",
            json={
                "tenant_id": "fintech-eu",
                "amount_usd": 12.0,
                "monthly_limit_usd": 15.0,
                "fallback_to_opencore": False,
                "actor": "api-test",
                "capability": "responses.create",
            },
        )
        assert r_res_ok.status_code == 200
        assert r_res_ok.json()["allowed"] is True

        r_res_402 = client.post(
            "/v1/cluster/governance-adapter/reserve-budget",
            json={
                "tenant_id": "fintech-eu",
                "amount_usd": 5.0,
                "actor": "api-test",
                "capability": "responses.create",
            },
        )
        assert r_res_402.status_code == 402
        assert r_res_402.json()["allowed"] is False
        assert r_res_402.json()["action"] == "deny_http_402"
    finally:
        app.dependency_overrides.clear()
