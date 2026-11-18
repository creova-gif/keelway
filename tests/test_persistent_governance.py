"""Integration & Durability Tests for SQLite WAL Multi-Tenant Governance (KEEL-GOV-004)."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.governance_routes import get_governance_engine, router as governance_router
from core.security.governance_store import GENESIS_GOVERNANCE_HASH, SQLiteGovernanceStore
from core.security.tenant_governance import (
    OPENCORE_FALLBACK_MODEL,
    OPENCORE_FALLBACK_PROVIDER,
    BudgetExceededGovernanceError,
    DataResidencyZone,
    HashChainedGovernanceAuditLog,
    ScopedAPIKeyManager,
    TenantGovernanceController,
    TenantPolicy,
    TenantSpendMeter,
    get_governance_controller,
)


class DeterministicClock:
    def __init__(self, start_mono: float = 5000.0, start_utc: datetime | None = None) -> None:
        self.mono = start_mono
        self.utc = start_utc or datetime(2026, 11, 13, 14, 0, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.mono

    def now_utc(self) -> datetime:
        return self.utc

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.utc += timedelta(seconds=seconds)


def _read_all_sqlite_disk_bytes(db_path: Path) -> bytes:
    """Concatenate raw bytes of the SQLite DB file plus any active `-wal` / `-shm` sidecars."""
    chunks: List[bytes] = []
    for candidate in (
        db_path,
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
    ):
        if candidate.exists():
            chunks.append(candidate.read_bytes())
    return b"\n".join(chunks)


def test_sqlite_wal_pragmas_and_schema_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "gov_schema.db"
    with SQLiteGovernanceStore(db_path) as store:
        assert store.journal_mode == "wal"
        with sqlite3.connect(db_path) as raw_conn:
            tables = {
                row[0]
                for row in raw_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            assert {
                "governance_meta",
                "tenant_policies",
                "scoped_api_keys",
                "tenant_spend_events",
                "governance_audit_chain",
            }.issubset(tables)

            indexes = {
                row[0]
                for row in raw_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            assert "idx_tenant_spend_tenant_recorded" in indexes


def test_full_restart_durability_keys_spend_opencore_downgrade_and_audit_chain(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "gov.db"
    clock = DeterministicClock()

    # --- Lifecycle #1: Populate policies, keys, spend, revocations, and audit chain ---
    ctrl1 = TenantGovernanceController(
        db_path=db_path, clock=clock.monotonic, now_fn=clock.now_utc
    )
    ctrl1.upsert_policy(
        TenantPolicy(
            tenant_id="elastic-bank",
            name="Elastic Sovereign Bank",
            allowed_categories=["open_weight", "closed_proprietary"],
            allowed_providers=["local", "gemini"],
            residency_zone=DataResidencyZone.GLOBAL,
            daily_spend_limit_usd=1.00,
            monthly_spend_limit_usd=2.50,
            fallback_to_opencore_on_budget_exceeded=True,
        )
    )
    ctrl1.upsert_policy(
        TenantPolicy(
            tenant_id="hard-cap",
            name="Strict Hard Cap Tenant",
            allowed_categories=["open_weight", "closed_proprietary"],
            allowed_providers=["local", "gemini"],
            residency_zone=DataResidencyZone.GLOBAL,
            daily_spend_limit_usd=1.00,
            monthly_spend_limit_usd=2.50,
            fallback_to_opencore_on_budget_exceeded=False,
        )
    )

    active_meta, active_raw_key = ctrl1.issue_key(
        "elastic-bank", "prod-gateway", scopes=["inference:execute", "models:read"]
    )
    revoked_meta, revoked_raw_key = ctrl1.issue_key(
        "elastic-bank", "compromised-worker", scopes=["inference:execute"]
    )

    clock.advance(15.0)
    auth_ok_1 = ctrl1.authenticate(active_raw_key, required_scope="inference:execute")
    assert auth_ok_1.valid and auth_ok_1.status_code == 200
    first_used_ts = clock.now_utc()

    ctrl1.revoke_key(revoked_meta.key_id)

    ctrl1.record_spend(
        "elastic-bank", cost_usd=0.95, tokens=12_000, model_id="gemini-3.5-flash", provider="gemini"
    )
    ctrl1.record_spend(
        "hard-cap", cost_usd=0.95, tokens=8_000, model_id="gemini-3.5-flash", provider="gemini"
    )

    dg_1 = ctrl1.evaluate_request(
        "elastic-bank", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.20, 1_500
    )
    assert dg_1.allowed and dg_1.action == "downgrade_opencore"
    assert dg_1.effective_model == OPENCORE_FALLBACK_MODEL

    ctrl1_head = ctrl1.chain_head
    ctrl1_count = ctrl1.audit_log.count_entries()
    assert ctrl1_head != GENESIS_GOVERNANCE_HASH
    assert ctrl1_count >= 7
    assert ctrl1.verify_audit_chain() == (True, None)

    ctrl1.close()
    del ctrl1

    # --- Lifecycle #2: Cold restart on identical `gov.db` ---
    clock.advance(30.0)
    ctrl2 = TenantGovernanceController(
        db_path=db_path, clock=clock.monotonic, now_fn=clock.now_utc
    )

    # 1. Policies & prior `last_used_at` hydrated accurately
    restored_policy = ctrl2.get_tenant("elastic-bank")
    assert restored_policy is not None and restored_policy.daily_spend_limit_usd == 1.00
    hydrated_keys = {k.key_id: k for k in ctrl2.key_manager.list_keys("elastic-bank")}
    assert hydrated_keys[active_meta.key_id].last_used_at == first_used_ts
    assert hydrated_keys[revoked_meta.key_id].revoked is True

    # 2. Active key authenticates (HMAC/salted SHA-256 salt survived restart); revoked key stays 401
    auth_ok_2 = ctrl2.authenticate(active_raw_key, required_scope="inference:execute")
    assert auth_ok_2.valid and auth_ok_2.status_code == 200
    auth_revoked = ctrl2.authenticate(revoked_raw_key, required_scope="inference:execute")
    assert not auth_revoked.valid and auth_revoked.status_code == 401
    assert "revoked" in auth_revoked.reason.lower()

    # 3. Spend totals survived restart: enforce 402 on hard-cap & OpenCore downgrade on elastic-bank
    eb_spend = ctrl2.spend_meter.get_spend("elastic-bank")
    assert eb_spend.daily_spent_usd == pytest.approx(0.95)
    assert eb_spend.monthly_spent_usd == pytest.approx(0.95)
    assert eb_spend.total_tokens == 12_000

    dg_2 = ctrl2.evaluate_request(
        "elastic-bank", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.15, 900
    )
    assert dg_2.allowed and dg_2.action == "downgrade_opencore"
    assert dg_2.effective_model == OPENCORE_FALLBACK_MODEL
    assert dg_2.effective_provider == OPENCORE_FALLBACK_PROVIDER

    hard_denied = ctrl2.evaluate_request(
        "hard-cap", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.15, 900
    )
    assert not hard_denied.allowed and hard_denied.status_code == 402
    with pytest.raises(BudgetExceededGovernanceError) as exc_info:
        ctrl2.enforce_request(
            "hard-cap", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.15, 900
        )
    assert exc_info.value.status_code == 402

    # 4. New audit events in Controller #2 chain onto Controller #1's head (no Genesis reset!)
    all_entries = ctrl2.audit_log.list_entries(limit=500)
    assert len(all_entries) > ctrl1_count
    first_post_restart_entry = all_entries[ctrl1_count]
    assert first_post_restart_entry.seq == ctrl1_count + 1
    assert first_post_restart_entry.prev_hash == ctrl1_head
    assert first_post_restart_entry.prev_hash != GENESIS_GOVERNANCE_HASH
    assert ctrl2.verify_audit_chain() == (True, None)
    assert ctrl2.store is not None
    assert ctrl2.store.verify_persisted_chain() == (True, len(all_entries), None)

    ctrl2.close()

    # --- Lifecycle #3: Next-day restart preserves monthly spend while rolling over daily spend ---
    clock.advance(86_400.0)
    with TenantGovernanceController(
        db_path=db_path, clock=clock.monotonic, now_fn=clock.now_utc
    ) as ctrl3:
        next_day_spend = ctrl3.spend_meter.get_spend("elastic-bank")
        assert next_day_spend.daily_spent_usd == 0.0
        assert next_day_spend.monthly_spent_usd == pytest.approx(0.95)
        # Monthly cap ($2.50) still catches a $1.75 request after daily rollover
        monthly_dg = ctrl3.evaluate_request(
            "elastic-bank", "gemini-3.5-flash", "gemini", "closed_proprietary", 1.75, 2_000
        )
        assert monthly_dg.allowed and monthly_dg.action == "downgrade_opencore"
        assert ctrl3.verify_audit_chain() == (True, None)


def test_direct_sqlite_tampering_mutation_and_row_deletion_detected(tmp_path: Path) -> None:
    # Case A: Mutate `detail` on middle row directly in SQLite
    db_mutate = tmp_path / "tamper_mutate.db"
    ctrl_a = TenantGovernanceController(db_path=db_mutate)
    ctrl_a.evaluate_request("default", "keelway-core:7b", "local", "open_weight", 0.0, 100)
    ctrl_a.record_spend("default", cost_usd=0.05, tokens=500, model_id="gpt-4o", provider="openai")
    ctrl_a.evaluate_request("default", "gpt-4o", "openai", "closed_proprietary", 0.05, 500)
    assert ctrl_a.verify_audit_chain() == (True, None)

    with sqlite3.connect(db_mutate) as raw_conn:
        raw_conn.execute(
            "UPDATE governance_audit_chain SET detail = 'TAMPERED_SQL_DETAIL' WHERE seq = 2"
        )
        raw_conn.commit()

    # Live controller immediately detects out-of-band SQLite tampering at seq=2
    live_status = ctrl_a.verify_audit_chain()
    assert not live_status
    assert live_status == (False, 2)
    ctrl_a.close()

    # Freshly restarted controller also detects tampering at seq=2
    with TenantGovernanceController(db_path=db_mutate) as ctrl_a_reloaded:
        reloaded_status = ctrl_a_reloaded.verify_audit_chain()
        assert not reloaded_status
        assert reloaded_status == (False, 2)
        assert ctrl_a_reloaded.store is not None
        ok, broken_seq, err_msg = ctrl_a_reloaded.store.verify_persisted_chain()
        assert ok is False and broken_seq == 2 and err_msg is not None

    # Case B: Delete a middle row directly in SQLite
    db_delete = tmp_path / "tamper_delete.db"
    with TenantGovernanceController(db_path=db_delete) as ctrl_b:
        for i in range(4):
            ctrl_b.evaluate_request(
                "default", "keelway-core:7b", "local", "open_weight", 0.0, 50 + i
            )
        assert ctrl_b.verify_audit_chain() == (True, None)

    with sqlite3.connect(db_delete) as raw_conn:
        raw_conn.execute("DELETE FROM governance_audit_chain WHERE seq = 3")
        raw_conn.commit()

    with TenantGovernanceController(db_path=db_delete) as ctrl_b_reloaded:
        del_status = ctrl_b_reloaded.verify_audit_chain()
        assert not del_status
        assert del_status == (False, 3)

    # Case C: Truncate the tail row directly in SQLite
    db_truncate = tmp_path / "tamper_truncate.db"
    with TenantGovernanceController(db_path=db_truncate) as ctrl_c:
        for _ in range(3):
            ctrl_c.evaluate_request("default", "keelway-core:7b", "local", "open_weight", 0.0, 40)
        assert ctrl_c.verify_audit_chain() == (True, None)

    with sqlite3.connect(db_truncate) as raw_conn:
        raw_conn.execute("DELETE FROM governance_audit_chain WHERE seq = 3")
        raw_conn.commit()

    with TenantGovernanceController(db_path=db_truncate) as ctrl_c_reloaded:
        trunc_status = ctrl_c_reloaded.verify_audit_chain()
        assert not trunc_status
        assert trunc_status == (False, 3)


def test_secret_hygiene_zero_raw_keys_or_prompt_secrets_in_db_or_wal_bytes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "hygiene_gov.db"
    raw_openai_secret = "sk-proj-SuperSecretOpenAIKey9876543210ZYXWVUTSRQ"
    raw_google_secret = "AIzaSyDaGmWKa4JsXZ-UltraSecretGeminiKey99887"
    raw_github_secret = "ghp_fedcba9876543210fedcba98765432109999"

    ctrl = TenantGovernanceController(db_path=db_path)
    ctrl.upsert_policy(
        TenantPolicy(
            tenant_id="redacted-audit-org",
            name="Opt-In Redacted Prompt Org",
            log_redacted_prompts=True,
        )
    )
    ctrl.upsert_policy(
        TenantPolicy(
            tenant_id="zero-prompt-org",
            name="Default Silent Prompt Org",
            log_redacted_prompts=False,
        )
    )

    _, raw_kw_key = ctrl.issue_key(
        "redacted-audit-org", "secret-probe", scopes=["inference:execute"]
    )
    kw_secret_tail = raw_kw_key.split("_")[-1]
    assert len(kw_secret_tail) == 32

    sensitive_prompt = (
        f"Use OpenAI {raw_openai_secret}, Gemini {raw_google_secret}, "
        f"GitHub {raw_github_secret}, and Keelway token {raw_kw_key} now."
    )
    ctrl.evaluate_request(
        "redacted-audit-org",
        "keelway-core:7b",
        "local",
        "open_weight",
        0.0,
        120,
        prompt_preview=sensitive_prompt,
    )
    ctrl.evaluate_request(
        "zero-prompt-org",
        "keelway-core:7b",
        "local",
        "open_weight",
        0.0,
        120,
        prompt_preview=sensitive_prompt,
    )

    # Check raw bytes BEFORE close (including live `.db-wal` / `.db-shm` pages)
    live_disk_bytes = _read_all_sqlite_disk_bytes(db_path)
    for forbidden in (
        raw_kw_key.encode("utf-8"),
        kw_secret_tail.encode("utf-8"),
        raw_openai_secret.encode("utf-8"),
        raw_google_secret.encode("utf-8"),
        raw_github_secret.encode("utf-8"),
    ):
        assert forbidden not in live_disk_bytes

    # Check raw bytes AFTER WAL checkpoint & close
    ctrl.close()
    checkpointed_bytes = _read_all_sqlite_disk_bytes(db_path)
    for forbidden in (
        raw_kw_key.encode("utf-8"),
        kw_secret_tail.encode("utf-8"),
        raw_openai_secret.encode("utf-8"),
        raw_google_secret.encode("utf-8"),
        raw_github_secret.encode("utf-8"),
    ):
        assert forbidden not in checkpointed_bytes

    # Verify redacted placeholders persisted for opt-in tenant and `None` for opt-out tenant
    with TenantGovernanceController(db_path=db_path) as reloaded:
        opt_in_entry = reloaded.audit_log.list_entries(tenant_id="redacted-audit-org")[-1]
        assert opt_in_entry.prompt_excerpt is not None
        assert "[REDACTED_OPENAI_KEY]" in opt_in_entry.prompt_excerpt
        assert "[REDACTED_GOOGLE_KEY]" in opt_in_entry.prompt_excerpt
        assert "[REDACTED_GITHUB_TOKEN]" in opt_in_entry.prompt_excerpt
        assert "[REDACTED_KEELWAY_KEY]" in opt_in_entry.prompt_excerpt

        opt_out_entry = reloaded.audit_log.list_entries(tenant_id="zero-prompt-org")[-1]
        assert opt_out_entry.prompt_excerpt is None


def test_standalone_managers_accept_optional_sqlite_store(tmp_path: Path) -> None:
    db_path = tmp_path / "subcomponents.db"
    with SQLiteGovernanceStore(db_path) as store1:
        km1 = ScopedAPIKeyManager(store=store1)
        sm1 = TenantSpendMeter(store=store1)
        al1 = HashChainedGovernanceAuditLog(store=store1)

        meta, raw_key = km1.issue_key("team-alpha", "runner", scopes=["eval:run"])
        sm1.record_spend("team-alpha", 0.42, tokens=1234, model_id="gpt-4o", provider="openai")
        ev = al1.append("team-alpha", "custom.event", "allow", "Standalone manager test.")
        head1 = ev.entry_hash

    with SQLiteGovernanceStore(db_path) as store2:
        km2 = ScopedAPIKeyManager(store=store2)
        sm2 = TenantSpendMeter(store=store2)
        al2 = HashChainedGovernanceAuditLog(store=store2)

        assert km2.authenticate(raw_key, required_scope="eval:run").valid
        assert km2.list_keys("team-alpha")[0].key_id == meta.key_id
        assert sm2.get_spend("team-alpha").daily_spent_usd == pytest.approx(0.42)
        assert al2.chain_head == head1
        assert al2.verify_integrity() == (True, None)


def test_concurrent_multithreaded_sqlite_wal_durability(tmp_path: Path) -> None:
    db_path = tmp_path / "concurrent_wal.db"
    with TenantGovernanceController(db_path=db_path) as ctrl:

        def _worker(idx: int) -> str:
            _, raw_key = ctrl.issue_key("default", f"worker-{idx}", scopes=["inference:run"])
            assert ctrl.authenticate(raw_key, required_scope="inference:run").valid
            ctrl.record_spend(
                "default", 0.02, tokens=25, model_id="gemini-3.5-flash", provider="gemini"
            )
            ctrl.evaluate_request("default", "keelway-core:7b", "local", "open_weight", 0.0, 25)
            return raw_key

        with ThreadPoolExecutor(max_workers=8) as pool:
            issued_keys = list(pool.map(_worker, range(16)))

    with TenantGovernanceController(db_path=db_path) as reloaded:
        for raw_key in issued_keys:
            assert reloaded.key_manager.authenticate(raw_key, required_scope="inference:run").valid
        assert reloaded.spend_meter.get_spend("default").daily_spent_usd == pytest.approx(0.32)
        assert reloaded.spend_meter.get_spend("default").total_tokens == 400
        assert reloaded.verify_audit_chain() == (True, None)


def test_persistence_endpoint_and_env_configured_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "api_gov.db"
    persistent_ctrl = TenantGovernanceController(db_path=db_path)
    persistent_ctrl.upsert_policy(TenantPolicy(tenant_id="api-org", name="API Org"))
    persistent_ctrl.issue_key("api-org", "svc", scopes=["chat:completions"])

    app = FastAPI()
    app.include_router(governance_router)
    app.dependency_overrides[get_governance_engine] = lambda: persistent_ctrl

    with TestClient(app) as client:
        resp = client.get("/v1/governance/persistence")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {
            "persistent",
            "backend",
            "tenants_count",
            "keys_count",
            "audit_events_count",
            "chain_verified",
            "chain_head",
        }
        assert body["persistent"] is True
        assert body["backend"] == "sqlite_wal"
        assert body["tenants_count"] == 2  # "default" + "api-org"
        assert body["keys_count"] == 1
        assert body["audit_events_count"] >= 2
        assert body["chain_verified"] is True
        assert len(body["chain_head"]) == 64 and body["chain_head"] != GENESIS_GOVERNANCE_HASH
        # Never leak filesystem paths in telemetry response
        assert str(db_path) not in resp.text and "api_gov.db" not in resp.text

        # Out-of-band SQLite tampering flips `chain_verified` to False on `/v1/governance/persistence`
        with sqlite3.connect(db_path) as raw_conn:
            raw_conn.execute(
                "UPDATE governance_audit_chain SET detail = 'CORRUPTED' WHERE seq = 1"
            )
            raw_conn.commit()

        tampered_resp = client.get("/v1/governance/persistence")
        assert tampered_resp.status_code == 200
        assert tampered_resp.json()["chain_verified"] is False

        audit_resp = client.get("/v1/governance/audit")
        assert audit_resp.status_code == 200
        assert audit_resp.json()["chain_valid"] is False
        assert audit_resp.json()["broken_at_seq"] == 1

    persistent_ctrl.close()

    # In-memory mode telemetry check
    mem_ctrl = TenantGovernanceController(db_path=None)
    app.dependency_overrides[get_governance_engine] = lambda: mem_ctrl
    with TestClient(app) as mem_client:
        mem_resp = mem_client.get("/v1/governance/persistence")
        assert mem_resp.status_code == 200
        mem_body = mem_resp.json()
        assert mem_body["persistent"] is False
        assert mem_body["backend"] == "memory"
        assert mem_body["chain_verified"] is True
        assert mem_body["chain_head"] == GENESIS_GOVERNANCE_HASH

    # `KEELWAY_GOVERNANCE_DB_PATH` singleton binding check
    env_db = tmp_path / "singleton_env.db"
    monkeypatch.setenv("KEELWAY_GOVERNANCE_DB_PATH", str(env_db))
    env_ctrl = get_governance_controller()
    assert env_ctrl.is_persistent is True
    env_ctrl.upsert_policy(TenantPolicy(tenant_id="env-tenant", name="Env Singleton Tenant"))
    monkeypatch.delenv("KEELWAY_GOVERNANCE_DB_PATH", raising=False)
    restored_mem_ctrl = get_governance_controller()
    assert restored_mem_ctrl.is_persistent is False

    with TenantGovernanceController(db_path=env_db) as check_env_db:
        assert check_env_db.get_tenant("env-tenant") is not None


def test_key_expiration_and_default_policy_mutation_survive_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "expiry_and_default.db"
    clock = DeterministicClock()

    with TenantGovernanceController(
        db_path=db_path, clock=clock.monotonic, now_fn=clock.now_utc
    ) as ctrl1:
        ctrl1.update_tenant(
            "default",
            {
                "daily_spend_limit_usd": 0.25,
                "residency_zone": DataResidencyZone.LOCAL_ONLY,
            },
        )
        _, expiring_key = ctrl1.issue_key(
            "default",
            "short-lived-token",
            scopes=["inference:execute"],
            expires_at=clock.now_utc() + timedelta(minutes=5),
        )

    clock.advance(120.0)
    with TenantGovernanceController(
        db_path=db_path, clock=clock.monotonic, now_fn=clock.now_utc
    ) as ctrl2:
        default_pol = ctrl2.get_tenant("default")
        assert default_pol is not None
        assert default_pol.daily_spend_limit_usd == 0.25
        assert default_pol.residency_zone == DataResidencyZone.LOCAL_ONLY
        assert ctrl2.authenticate(expiring_key, required_scope="inference:execute").valid

        clock.advance(200.0)
        expired_res = ctrl2.authenticate(expiring_key, required_scope="inference:execute")
        assert not expired_res.valid and expired_res.status_code == 401
        assert "expired" in expired_res.reason.lower()


def test_store_defense_in_depth_rejects_raw_key_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "defense_in_depth.db"
    forged_raw_key = "kw_live_abcdef_0123456789abcdef0123456789abcdef"
    with SQLiteGovernanceStore(db_path) as store:
        with pytest.raises(ValueError, match="unhashed"):
            store.insert_scoped_key(
                key_id="key_bad_1",
                tenant_id="default",
                name="bad",
                key_prefix="kw_live_abcdef",
                secret_sha256=forged_raw_key,
                scopes=["read"],
                created_at="2026-11-13T12:00:00+00:00",
            )
        with pytest.raises(ValueError, match="unredacted"):
            store.append_audit_event(
                seq=1,
                event_id="evt_bad_1",
                timestamp="2026-11-13T12:00:00+00:00",
                tenant_id="default",
                action="test",
                outcome="allow",
                model_id=None,
                provider=None,
                cost_usd=0.0,
                detail=f"Leaked {forged_raw_key}",
                redacted_prompt_preview=None,
                prev_hash=GENESIS_GOVERNANCE_HASH,
                event_hash="a" * 64,
            )

