"""Layer 6 Unit & ASGI Integration Tests for Enterprise Tenant Governance."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.governance_routes import get_governance_engine, router as governance_router
from core.config import settings
from core.security.auth import launch_token
from core.security.tenant_governance import (
    KEY_PREFIX_LEN,
    OPENCORE_FALLBACK_MODEL,
    OPENCORE_FALLBACK_PROVIDER,
    BudgetExceededGovernanceError,
    DataResidencyZone,
    TenantGovernanceEngine,
    TenantPolicy,
    tenant_governance,
)


class FakeClock:
    def __init__(self, start_mono: float = 1000.0, start_utc: datetime | None = None) -> None:
        self.mono = start_mono
        self.utc = start_utc or datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.mono

    def now_utc(self) -> datetime:
        return self.utc

    def advance(self, seconds: float) -> None:
        self.mono += seconds
        self.utc += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def engine(clock: FakeClock) -> TenantGovernanceEngine:
    return TenantGovernanceEngine(clock=clock.monotonic, now_fn=clock.now_utc)


@pytest.fixture
def api_client(engine: TenantGovernanceEngine) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(governance_router)
    test_app.dependency_overrides[get_governance_engine] = lambda: engine
    with TestClient(test_app) as client:
        yield client


def test_singleton_preseeded_with_default_tenant_and_unknown_fails_closed(engine: TenantGovernanceEngine) -> None:
    assert tenant_governance.get_tenant("default") is not None
    assert engine.get_tenant("default") is not None
    denied = engine.evaluate_request("nonexistent", "keelway-core:7b", "local", "open_weight", 0.0, 100)
    assert not denied.allowed and denied.status_code == 403 and "fail-closed" in denied.reason


def test_local_only_residency_blocks_cloud_providers_fail_closed(engine: TenantGovernanceEngine) -> None:
    engine.create_tenant(TenantPolicy(
        tenant_id="bank-airgap", name="Sovereign Core Bank",
        allowed_categories=["open_weight", "closed_proprietary"],
        allowed_providers=["local", "gemini", "openai"],
        residency_zone=DataResidencyZone.LOCAL_ONLY,
    ))
    for cloud_provider, cloud_model in [("gemini", "gemini-3.5-flash"), ("openai", "gpt-4o")]:
        res = engine.evaluate_request("bank-airgap", cloud_model, cloud_provider, "closed_proprietary", 0.02, 500)
        assert not res.allowed and res.status_code == 403 and res.effective_model is None
        assert "local_only" in res.reason

    local_ok = engine.evaluate_request("bank-airgap", "keelway-core:7b", "local", "open_weight", 0.0, 500)
    assert local_ok.allowed and local_ok.status_code == 200 and local_ok.effective_model == "keelway-core:7b"


def test_africa_and_eu_sovereign_residency_zones(engine: TenantGovernanceEngine) -> None:
    engine.create_tenant(TenantPolicy(
        tenant_id="nairobi-gov", name="Africa Sovereign Ministry",
        allowed_categories=["open_weight", "closed_proprietary"],
        allowed_providers=["local", "vllm", "openai"],
        residency_zone=DataResidencyZone.AFRICA_SOVEREIGN,
    ))
    blocked = engine.evaluate_request("nairobi-gov", "gpt-4o", "openai", "closed_proprietary", 0.05, 400)
    assert not blocked.allowed and blocked.status_code == 403

    allowed_vllm = engine.evaluate_request("nairobi-gov", "keelway-reasoning:14b", "vllm", "open_weight", 0.0, 400)
    assert allowed_vllm.allowed and allowed_vllm.status_code == 200


def test_provider_and_category_allowlist_enforcement(engine: TenantGovernanceEngine) -> None:
    engine.create_tenant(TenantPolicy(
        tenant_id="oss-strict", name="Open-Weight Only Org",
        allowed_categories=["open_weight"], allowed_providers=["local", "gemini"],
    ))
    bad_prov = engine.evaluate_request("oss-strict", "gpt-4o", "openai", "open_weight", 0.01, 200)
    assert not bad_prov.allowed and bad_prov.status_code == 403 and "Provider" in bad_prov.reason

    bad_cat = engine.evaluate_request("oss-strict", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.01, 200)
    assert not bad_cat.allowed and bad_cat.status_code == 403 and "category" in bad_cat.reason.lower()


def test_scoped_api_key_issuance_and_zero_raw_secret_persistence(engine: TenantGovernanceEngine) -> None:
    meta, raw_key = engine.issue_key("default", "ci-runner", scopes=["inference:execute", "models:read"])
    parts = raw_key.split("_")
    assert len(parts) == 4 and parts[0] == "kw" and parts[1] == "live"
    assert len(parts[2]) == 6 and len(parts[3]) == 32
    assert len(meta.key_prefix) == KEY_PREFIX_LEN and raw_key.startswith(meta.key_prefix)

    secret_tail = parts[3]
    stored_record = engine.key_manager._records[meta.key_id]
    dumped_json = stored_record.model_dump_json()
    assert raw_key not in dumped_json and secret_tail not in dumped_json
    assert set(stored_record.model_dump().keys()) == {
        "key_id", "tenant_id", "name", "key_prefix", "secret_sha256",
        "scopes", "created_at", "expires_at", "revoked", "last_used_at",
    }
    assert len(stored_record.secret_sha256) == 64


def test_scoped_api_key_authentication_scopes_expiry_and_revocation(
    engine: TenantGovernanceEngine, clock: FakeClock
) -> None:
    meta, raw_key = engine.issue_key(
        "default", "scoped-worker", scopes=["inference:read"], expires_at=clock.now_utc() + timedelta(minutes=5),
    )
    ok = engine.verify_key(raw_key, required_scope="inference:read")
    assert ok.valid and bool(ok) and ok.status_code == 200 and ok.tenant_id == "default"
    assert engine.key_manager.list_keys("default")[0].last_used_at == clock.now_utc()

    no_scope = engine.verify_key(raw_key, required_scope="governance:admin")
    assert not no_scope.valid and not bool(no_scope) and no_scope.status_code == 403

    tampered = raw_key[:-4] + ("0000" if raw_key[-4:] != "0000" else "ffff")
    assert not engine.verify_key(tampered).valid and engine.verify_key(tampered).status_code == 401
    assert not engine.verify_key("invalid_format_token").valid

    clock.advance(301.0)
    expired = engine.verify_key(raw_key)
    assert not expired.valid and expired.status_code == 401 and "expired" in expired.reason.lower()

    meta2, raw_key2 = engine.issue_key("default", "revocable", scopes=["*"])
    assert engine.verify_key(raw_key2, required_scope="any:scope").valid
    assert engine.revoke_key(meta2.key_id).revoked is True
    after_revoke = engine.verify_key(raw_key2)
    assert not after_revoke.valid and after_revoke.status_code == 401 and "revoked" in after_revoke.reason.lower()


def test_deterministic_rpm_rate_limiting_and_refill(engine: TenantGovernanceEngine, clock: FakeClock) -> None:
    engine.create_tenant(TenantPolicy(tenant_id="rpm-tenant", name="RPM Test", requests_per_minute=3, tokens_per_minute=100_000))
    for _ in range(3):
        assert engine.evaluate_request("rpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 100).allowed

    exhausted = engine.evaluate_request("rpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 100)
    assert not exhausted.allowed and exhausted.status_code == 429
    assert exhausted.retry_after_seconds == pytest.approx(20.0, rel=1e-2)

    clock.advance(19.0)
    assert engine.evaluate_request("rpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 100).status_code == 429
    clock.advance(1.0)
    assert engine.evaluate_request("rpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 100).status_code == 200


def test_deterministic_tpm_token_rate_limiting_and_refill(engine: TenantGovernanceEngine, clock: FakeClock) -> None:
    engine.create_tenant(TenantPolicy(tenant_id="tpm-tenant", name="TPM Test", requests_per_minute=60, tokens_per_minute=6_000))
    assert engine.evaluate_request("tpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 5_000).allowed
    assert engine.evaluate_request("tpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 2_000).status_code == 429
    clock.advance(10.0)
    assert engine.evaluate_request("tpm-tenant", "keelway-core:7b", "local", "open_weight", 0.0, 2_000).status_code == 200


def test_budget_cap_hard_402_and_exception_when_fallback_disabled(engine: TenantGovernanceEngine) -> None:
    engine.create_tenant(TenantPolicy(
        tenant_id="strict-budget", name="Hard Cap Org",
        allowed_categories=["open_weight", "closed_proprietary"], allowed_providers=["local", "gemini"],
        daily_spend_limit_usd=1.00, monthly_spend_limit_usd=5.00, fallback_to_opencore_on_budget_exceeded=False,
    ))
    engine.record_spend("strict-budget", cost_usd=0.90, tokens=10_000)

    dec = engine.evaluate_request("strict-budget", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.25, 1_000)
    assert not dec.allowed and dec.status_code == 402 and "Daily spend cap exceeded" in dec.reason

    with pytest.raises(BudgetExceededGovernanceError) as exc_info:
        engine.enforce_request("strict-budget", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.25, 1_000)
    assert exc_info.value.status_code == 402

    local_dec = engine.evaluate_request("strict-budget", "keelway-core:7b", "local", "open_weight", 0.0, 1_000)
    assert local_dec.allowed and local_dec.status_code == 200


def test_budget_cap_automatic_opencore_downgrade_and_monthly_rollover(
    engine: TenantGovernanceEngine, clock: FakeClock
) -> None:
    engine.create_tenant(TenantPolicy(
        tenant_id="smart-fallback", name="Elastic Sovereign Org",
        allowed_categories=["open_weight", "closed_proprietary"], allowed_providers=["local", "gemini"],
        daily_spend_limit_usd=2.00, monthly_spend_limit_usd=3.00, fallback_to_opencore_on_budget_exceeded=True,
    ))
    engine.record_spend("smart-fallback", cost_usd=1.95, tokens=20_000)

    downgraded = engine.evaluate_request("smart-fallback", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.20, 1_500)
    assert downgraded.allowed and downgraded.status_code == 200 and downgraded.action == "downgrade_opencore"
    assert downgraded.effective_model == OPENCORE_FALLBACK_MODEL and downgraded.effective_provider == OPENCORE_FALLBACK_PROVIDER

    forbid = engine.evaluate_request("smart-fallback", "gemini-3.5-flash", "gemini", "closed_proprietary", 0.20, 1_500, forbid_open_weight=True)
    assert not forbid.allowed and forbid.status_code == 402

    clock.advance(86_400.0)
    snap = engine.spend_meter.get_spend("smart-fallback")
    assert snap.daily_spent_usd == 0.0 and snap.monthly_spent_usd == pytest.approx(1.95)
    monthly_dg = engine.evaluate_request("smart-fallback", "gemini-3.5-flash", "gemini", "closed_proprietary", 1.10, 1_500)
    assert monthly_dg.allowed and monthly_dg.action == "downgrade_opencore"


def test_prompt_logging_disabled_by_default_and_redacted_when_opted_in(engine: TenantGovernanceEngine) -> None:
    secret_prompt = "Deploy key sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdef and ghp_0123456789abcdef0123456789abcdef0123"
    engine.evaluate_request("default", "keelway-core:7b", "local", "open_weight", 0.0, 50, prompt_preview=secret_prompt)
    assert engine.audit_log.list_entries(tenant_id="default")[-1].prompt_excerpt is None

    engine.create_tenant(TenantPolicy(tenant_id="audited-org", name="Redacted Audit Org", log_redacted_prompts=True))
    engine.evaluate_request("audited-org", "keelway-core:7b", "local", "open_weight", 0.0, 50, prompt_preview=secret_prompt)
    excerpt = engine.audit_log.list_entries(tenant_id="audited-org")[-1].prompt_excerpt
    assert excerpt is not None
    assert "sk-proj-" not in excerpt and "ghp_" not in excerpt
    assert "[REDACTED_OPENAI_KEY]" in excerpt and "[REDACTED_GITHUB_TOKEN]" in excerpt


def test_hash_chained_audit_integrity_and_in_memory_tamper_detection(engine: TenantGovernanceEngine) -> None:
    engine.evaluate_request("default", "keelway-core:7b", "local", "open_weight", 0.0, 100)
    engine.evaluate_request("default", "gpt-4o", "openai", "closed_proprietary", 0.05, 500)
    engine.record_spend("default", 0.05, 500)

    assert engine.audit_log.verify_integrity() == (True, None)
    engine.audit_log._entries[1].reason = "TAMPERED_REASON"
    assert engine.audit_log.verify_integrity() == (False, 2)


def test_thread_safe_concurrent_governance_operations(engine: TenantGovernanceEngine) -> None:
    def _worker(idx: int) -> str:
        _, raw = engine.issue_key("default", f"worker-{idx}", scopes=["inference:run"])
        assert engine.verify_key(raw, required_scope="inference:run").valid
        engine.record_spend("default", 0.01, 10)
        engine.evaluate_request("default", "keelway-core:7b", "local", "open_weight", 0.0, 10)
        return raw

    with ThreadPoolExecutor(max_workers=8) as pool:
        keys: List[str] = list(pool.map(_worker, range(16)))
    assert len(set(keys)) == 16
    assert engine.spend_meter.get_spend("default").daily_spent_usd == pytest.approx(0.16)
    assert engine.audit_log.verify_integrity() == (True, None)


def test_governance_fastapi_endpoints_lifecycle(api_client: TestClient, engine: TenantGovernanceEngine) -> None:
    created = api_client.post("/v1/governance/tenants", json={
        "tenant_id": "acme-corp", "name": "Acme Enterprise",
        "allowed_categories": ["open_weight", "closed_proprietary"], "allowed_providers": ["local", "gemini"],
        "residency_zone": "global", "daily_spend_limit_usd": 1.0,
    })
    assert created.status_code == 201
    assert api_client.post("/v1/governance/tenants", json={"tenant_id": "acme-corp", "name": "Dup"}).status_code == 409
    assert any(t["tenant_id"] == "acme-corp" for t in api_client.get("/v1/governance/tenants").json())
    assert api_client.get("/v1/governance/tenants/acme-corp").status_code == 200
    assert api_client.get("/v1/governance/tenants/missing").status_code == 404

    patched = api_client.patch("/v1/governance/tenants/acme-corp", json={"daily_spend_limit_usd": 0.50})
    assert patched.status_code == 200 and patched.json()["daily_spend_limit_usd"] == 0.50

    issued = api_client.post("/v1/governance/keys", json={"tenant_id": "acme-corp", "name": "gw", "scopes": ["chat:completions"]})
    assert issued.status_code == 201
    raw_api_key, key_id = issued.json()["api_key"], issued.json()["key_id"]
    assert raw_api_key.startswith("kw_live_")

    listed = api_client.get("/v1/governance/keys", params={"tenant_id": "acme-corp"}).json()
    assert len(listed) == 1 and "api_key" not in listed[0] and "secret_sha256" not in listed[0]

    assert api_client.post("/v1/governance/keys/verify", json={"api_key": raw_api_key, "required_scope": "chat:completions"}).status_code == 200
    assert api_client.post("/v1/governance/keys/verify", json={"api_key": raw_api_key, "required_scope": "admin:all"}).status_code == 403
    assert api_client.delete(f"/v1/governance/keys/{key_id}").json()["revoked"] is True
    assert api_client.post("/v1/governance/keys/verify", json={"api_key": raw_api_key}).status_code == 401

    assert api_client.post("/v1/governance/spend/record", json={"tenant_id": "acme-corp", "cost_usd": 0.50, "tokens": 5000}).status_code == 200
    eval_resp = api_client.post("/v1/governance/evaluate", json={
        "tenant_id": "acme-corp", "requested_model": "gemini-3.5-flash",
        "provider": "gemini", "category": "closed_proprietary", "estimated_cost_usd": 0.10, "estimated_tokens": 800,
    })
    assert eval_resp.status_code == 200 and eval_resp.json()["effective_model"] == "keelway-core:7b"

    audit_resp = api_client.get("/v1/governance/audit").json()
    assert audit_resp["chain_valid"] is True and audit_resp["total"] >= 6

    engine.audit_log._entries[0].outcome = "deny"
    tampered_audit = api_client.get("/v1/governance/audit").json()
    assert tampered_audit["chain_valid"] is False and tampered_audit["broken_at_seq"] == 1


def test_evaluate_endpoint_surfaces_403_429_402_and_retry_after(api_client: TestClient) -> None:
    api_client.post("/v1/governance/tenants", json={
        "tenant_id": "edge-codes", "name": "Status Check Org",
        "allowed_categories": ["closed_proprietary"], "allowed_providers": ["gemini"],
        "residency_zone": "global", "daily_spend_limit_usd": 0.10,
        "fallback_to_opencore_on_budget_exceeded": False, "requests_per_minute": 2,
    })
    r403 = api_client.post("/v1/governance/evaluate", json={
        "tenant_id": "edge-codes", "requested_model": "gpt-4o", "provider": "openai",
        "category": "closed_proprietary", "estimated_cost_usd": 0.01, "estimated_tokens": 100,
    })
    assert r403.status_code == 403

    r402 = api_client.post("/v1/governance/evaluate", json={
        "tenant_id": "edge-codes", "requested_model": "gemini-3.5-flash", "provider": "gemini",
        "category": "closed_proprietary", "estimated_cost_usd": 0.25, "estimated_tokens": 100,
    })
    assert r402.status_code == 402

    r200 = api_client.post("/v1/governance/evaluate", json={
        "tenant_id": "edge-codes", "requested_model": "gemini-3.5-flash", "provider": "gemini",
        "category": "closed_proprietary", "estimated_cost_usd": 0.01, "estimated_tokens": 100,
    })
    assert r200.status_code == 200

    r429 = api_client.post("/v1/governance/evaluate", json={
        "tenant_id": "edge-codes", "requested_model": "gemini-3.5-flash", "provider": "gemini",
        "category": "closed_proprietary", "estimated_cost_usd": 0.01, "estimated_tokens": 100,
    })
    assert r429.status_code == 429 and "Retry-After" in r429.headers


@pytest.mark.auth
def test_governance_routes_require_authenticated_principal_when_auth_enabled(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "auth_required", True)
    assert api_client.get("/v1/governance/tenants").status_code == 401
    authed = api_client.get("/v1/governance/tenants", headers={"Authorization": f"Bearer {launch_token()}"})
    assert authed.status_code == 200
