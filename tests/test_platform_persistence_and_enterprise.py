"""
TDD Unit & FastAPI Integration Suite for Phase 2 Workstream A:
1. Ed25519 Cryptographic Manifest Signing & Tamper Detection (`core/platform/signing.py` — `KEEL-MANIFEST-007`)
2. Crash-Safe SQLite WAL Platform Persistence (`core/platform/persistence.py` — `SQLitePlatformStore`)
   wired into `MarketplaceRegistry` & `UnifiedWorkspaceHub` without seed duplication on restart
3. Tenant-Isolated Enterprise Governance & Compliance Posture Evaluator (`core/platform/enterprise.py`)
4. FastAPI Control-Plane Routes (`/v1/platform/marketplace/verify-signature`, `/v1/platform/enterprise/*`)
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.platform import (
    CURATED_SEED_PACKAGES,
    FIRST_PARTY_SIGNING_KEY_ENV,
    SORVEX_FIRST_PARTY_KEY_ID,
    Ed25519ManifestSigner,
    EnterpriseGovernanceManager,
    EnterprisePolicyValidationError,
    MarketplaceRegistry,
    MarketplaceSecurityError,
    SQLitePlatformStore,
    UnifiedWorkspaceHub,
    generate_publisher_keypair,
)
from core.api.platform_routes import (
    get_enterprise_manager,
    get_manifest_signer,
    get_marketplace_registry,
    get_platform_hub,
)


# ---------------------------------------------------------------------------
# 1. Ed25519 Manifest Signing (`KEEL-MANIFEST-007`)
# ---------------------------------------------------------------------------


def test_ed25519_keygen_sign_verify_and_tamper_detection() -> None:
    priv_pem, pub_b64 = generate_publisher_keypair()
    assert priv_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
    assert len(pub_b64) >= 40

    signer = Ed25519ManifestSigner()
    raw_pkg_manifest = {
        "schema": "keelway.package/v1",
        "id": "acme-sec-scanner",
        "name": "Acme Security Scanner",
        "kind": "dev_tool",
        "version": "1.0.0",
        "publisher": "Acme Security",
        "publisher_tier": "verified_third_party",
        "permissions": {"read_paths": ["core/"], "write_paths": [], "network": "none"},
    }

    # Unsigned manifest fails closed with UNSIGNED_MANIFEST
    valid_unsigned, reason_unsigned = signer.verify_manifest(raw_pkg_manifest)
    assert valid_unsigned is False
    assert reason_unsigned == "UNSIGNED_MANIFEST"

    # Signed with an unregistered publisher key fails closed with UNKNOWN_PUBLISHER_KEY
    signed_pkg = signer.sign_manifest(raw_pkg_manifest, priv_pem, key_id="acme-pub-2026")
    assert "signer_key_id" not in raw_pkg_manifest  # does not mutate input dict
    assert signed_pkg["signer_key_id"] == "acme-pub-2026"
    assert signed_pkg["ed25519_signature"]

    valid_unknown, reason_unknown = signer.verify_manifest(signed_pkg)
    assert valid_unknown is False
    assert reason_unknown == "UNKNOWN_PUBLISHER_KEY"

    # Registering the publisher public key enables verification
    signer.register_trusted_key("acme-pub-2026", pub_b64)
    valid_ok, reason_ok = signer.verify_manifest(signed_pkg)
    assert valid_ok is True
    assert reason_ok == "VERIFIED_ED25519"

    # Excluded security_report metadata does not invalidate signature
    with_scan_report = {**signed_pkg, "security_report": {"passed": True, "risk_grade": "A"}}
    assert signer.verify_manifest(with_scan_report) == (True, "VERIFIED_ED25519")

    # Tampering with any top-level or nested manifest field invalidates signature
    tampered_version = {**signed_pkg, "version": "1.0.1"}
    assert signer.verify_manifest(tampered_version) == (False, "INVALID_ED25519_SIGNATURE")

    tampered_perms = {
        **signed_pkg,
        "permissions": {"read_paths": ["core/"], "write_paths": ["core/"], "network": "full"},
    }
    assert signer.verify_manifest(tampered_perms) == (False, "INVALID_ED25519_SIGNATURE")


def test_ed25519_agent_manifest_and_sorvex_first_party_seed_verification() -> None:
    priv_pem, pub_b64 = generate_publisher_keypair()
    signer = Ed25519ManifestSigner()
    signer.register_trusted_key("agent-publisher-v1", pub_b64)

    agent_manifest = {
        "schema": "keelway.agent/v1",
        "id": "compliance-sentinel",
        "name": "Compliance Sentinel Agent",
        "role_domain": "security_remediation",
        "scoped_tools": ["security.dlp_scan", "security.rbac_verify"],
        "risk_tier": "B",
    }
    signed_agent = signer.sign_manifest(agent_manifest, priv_pem, key_id="agent-publisher-v1")
    assert signer.verify_manifest(signed_agent) == (True, "VERIFIED_ED25519")

    tampered_agent = {**signed_agent, "risk_tier": "A"}
    assert signer.verify_manifest(tampered_agent) == (False, "INVALID_ED25519_SIGNATURE")


def test_first_party_seed_packages_signed_with_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    priv_pem, _ = generate_publisher_keypair()
    monkeypatch.setenv(FIRST_PARTY_SIGNING_KEY_ENV, priv_pem.decode("ascii"))

    registry = MarketplaceRegistry()
    first_party_pkgs = registry.list_packages(publisher_tier="first_party")
    assert len(first_party_pkgs) >= 3
    default_verifier = Ed25519ManifestSigner()
    for pkg in first_party_pkgs:
        assert pkg["signer_key_id"] == SORVEX_FIRST_PARTY_KEY_ID
        assert default_verifier.verify_manifest(pkg) == (True, "VERIFIED_ED25519")
        tampered = {**pkg, "price_usd": 9999.0}
        assert default_verifier.verify_manifest(tampered) == (False, "INVALID_ED25519_SIGNATURE")


def test_first_party_seed_packages_unsigned_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FIRST_PARTY_SIGNING_KEY_ENV, raising=False)
    registry = MarketplaceRegistry()
    first_party_pkgs = registry.list_packages(publisher_tier="first_party")
    assert len(first_party_pkgs) >= 3
    for pkg in first_party_pkgs:
        assert "ed25519_signature" not in pkg
        assert Ed25519ManifestSigner().verify_manifest(pkg) == (False, "UNSIGNED_MANIFEST")


def test_legacy_derivable_first_party_key_is_not_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    import base64
    import hashlib

    monkeypatch.delenv(FIRST_PARTY_SIGNING_KEY_ENV, raising=False)
    seed = hashlib.sha256(b"keelway.manifest.sorvex-labs.first-party.ed25519.v1").digest()
    prefix = bytes.fromhex("302e020100300506032b657004220420")
    legacy_pem = (
        "-----BEGIN PRIVATE KEY-----\n" + base64.b64encode(prefix + seed).decode("ascii") + "\n-----END PRIVATE KEY-----\n"
    ).encode("ascii")
    signer = Ed25519ManifestSigner()
    forged = signer.sign_manifest({"schema": "keelway.package/v1", "id": "evil"}, legacy_pem, SORVEX_FIRST_PARTY_KEY_ID)
    assert signer.verify_manifest(forged) == (False, "UNKNOWN_PUBLISHER_KEY")


def test_publishing_first_party_tier_requires_trusted_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    priv_pem, _ = generate_publisher_keypair()
    monkeypatch.setenv(FIRST_PARTY_SIGNING_KEY_ENV, priv_pem.decode("ascii"))
    registry = MarketplaceRegistry()
    payload = {"id": "impostor.agent", "kind": "ai_agent", "name": "Impostor", "publisher_tier": "first_party"}
    with pytest.raises(MarketplaceSecurityError):
        registry.publish_package(payload)
    assert "impostor.agent" not in {p["id"] for p in registry.list_packages()}


# ---------------------------------------------------------------------------
# 2. SQLite WAL Platform Store & Restart Durability
# ---------------------------------------------------------------------------


def test_sqlite_wal_store_durability_across_registry_and_hub_restarts(tmp_path: Path) -> None:
    db_file = tmp_path / "platform_state.db"
    store_1 = SQLitePlatformStore(db_file)
    assert store_1.journal_mode == "wal"

    registry_1 = MarketplaceRegistry(store=store_1)
    initial_seed_count = len(CURATED_SEED_PACKAGES)
    assert len(registry_1.list_packages()) == initial_seed_count

    custom_pkg = {
        "id": "durable-rag-auditor",
        "name": "Durable RAG Citation Auditor",
        "kind": "ai_agent",
        "version": "2.0.0",
        "publisher": "Northwind AI",
        "publisher_tier": "verified_third_party",
        "pricing_model": "monthly",
        "price_usd": 29.0,
        "description": "Verifies local citations against source chunks with zero external egress.",
        "permissions": {"read_paths": ["docs/"], "write_paths": [], "network": "none", "requires_p10_approval": False},
    }
    registry_1.publish_package(custom_pkg)
    registry_1.install_package("durable-rag-auditor", workspace_id="ws-prod", config={"strict_citations": True})

    hub_1 = UnifiedWorkspaceHub(store=store_1)
    created_prd = hub_1.create_prd(
        title="Durable SQLite WAL Persistence",
        summary="Persist workspace state across restarts.",
        workspace_id="ws-prod",
        acceptance_criteria=["WAL enabled", "No duplicate seeds"],
    )
    created_issue = hub_1.create_issue(
        title="Wire SQLitePlatformStore into workspace hub",
        workspace_id="ws-prod",
        priority="high",
        prd_id=created_prd["id"],
    )
    created_wf = hub_1.create_workflow(
        name="Nightly WAL Backup Check",
        trigger="cron:0 3 * * *",
        workspace_id="ws-prod",
        nodes=[{"id": "n1", "label": "Verify SQLite integrity", "agent": "devops-sre"}],
    )
    registered_ext = hub_1.extensions.register_extension(
        {
            "id": "ext-durable-metrics",
            "name": "Durable SLO Exporter",
            "extension_type": "tool",
            "version": "1.1.0",
            "publisher": "Ops Team",
            "description": "Exports local latency histograms.",
            "permissions": {"read_paths": ["logs/"], "write_paths": [], "network": "none"},
        }
    )

    expected_pkg_count = len(registry_1.list_packages())
    expected_issue_count = len(hub_1.list_issues("ws-prod"))
    expected_prd_count = len(hub_1.list_prds("ws-prod"))
    expected_wf_count = len(hub_1.list_workflows("ws-prod"))
    store_1.close()

    # Simulate full process restart against the same SQLite WAL database file
    store_2 = SQLitePlatformStore(db_file)
    registry_2 = MarketplaceRegistry(store=store_2)
    hub_2 = UnifiedWorkspaceHub(store=store_2)

    # Exact counts preserved (zero duplicate seed records)
    assert len(registry_2.list_packages()) == expected_pkg_count == initial_seed_count + 1
    reloaded_pkg = registry_2.get_package("durable-rag-auditor")
    assert reloaded_pkg is not None
    assert reloaded_pkg["name"] == "Durable RAG Citation Auditor"

    installed_ws = registry_2.list_installed("ws-prod")
    assert len(installed_ws) == 1
    assert installed_ws[0]["package_id"] == "durable-rag-auditor"
    assert installed_ws[0]["config"] == {"strict_citations": True}

    issues_2 = hub_2.list_issues("ws-prod")
    prds_2 = hub_2.list_prds("ws-prod")
    wfs_2 = hub_2.list_workflows("ws-prod")
    exts_2 = hub_2.extensions.list_extensions()

    assert len(issues_2) == expected_issue_count
    assert any(i["id"] == created_issue["id"] and i["prd_id"] == created_prd["id"] for i in issues_2)
    assert len(prds_2) == expected_prd_count
    assert any(p["id"] == created_prd["id"] for p in prds_2)
    assert len(wfs_2) == expected_wf_count
    assert any(w["id"] == created_wf["id"] for w in wfs_2)
    assert any(e["id"] == registered_ext["id"] for e in exts_2)

    # Default workspace seed items also not duplicated across restart
    assert len(hub_2.list_issues("default")) == 1
    assert len(hub_2.list_prds("default")) == 1
    assert len(hub_2.list_workflows("default")) == 1
    store_2.close()


def test_sqlite_store_rejects_unknown_workspace_collection(tmp_path: Path) -> None:
    with SQLitePlatformStore(tmp_path / "strict.db") as store:
        with pytest.raises(ValueError, match="collection"):
            store.upsert_record("default", "invalid_collection", "rec-1", {"x": 1})


# ---------------------------------------------------------------------------
# 3. Enterprise Governance, Retention Enforcement & Compliance Evaluator
# ---------------------------------------------------------------------------


def test_enterprise_governance_tenant_isolation_retention_and_compliance(tmp_path: Path) -> None:
    store = SQLitePlatformStore(tmp_path / "enterprise.db")
    mgr = EnterpriseGovernanceManager(store=store)

    # Invalid retention mode must be rejected
    with pytest.raises(EnterprisePolicyValidationError):
        mgr.upsert_policy("tenant-fin", {"retention_mode": "infinite_99y"})

    # Invalid deployment topology must be rejected
    with pytest.raises(EnterprisePolicyValidationError):
        mgr.upsert_policy("tenant-fin", {"retention_mode": "standard_30d", "deployment_topology": "shared_public_hobby"})

    # Configure regulated HIPAA healthcare tenant vs EU GDPR startup tenant
    hipaa_policy = mgr.upsert_policy(
        "tenant-health",
        {
            "org_display_name": "Veridian Clinical Systems",
            "retention_mode": "worm_7y",
            "audit_retention_days": 2555,
            "pii_redaction_enforced": True,
            "allow_prompt_logging": False,
            "deployment_topology": "on_prem_airgapped",
            "allowed_model_regions": ["local"],
            "sso_saml_required": True,
            "branding": {"logo_url": "/assets/veridian.svg", "accent_hex": "#2DD4BF"},
            "max_concurrent_sandboxes": 16,
            "max_workflow_minutes_per_day": 1200,
            "require_p10_for_external_webhooks": True,
        },
    )
    gdpr_weak_policy = mgr.upsert_policy(
        "tenant-eu-startup",
        {
            "org_display_name": "Berlin Labs",
            "retention_mode": "ephemeral_0d",
            "pii_redaction_enforced": False,
            "allow_prompt_logging": True,
            "deployment_topology": "local_workstation",
            "allowed_model_regions": ["us-east-1"],
            "sso_saml_required": False,
            "require_p10_for_external_webhooks": False,
        },
    )

    # Tenant isolation check + persistence across manager restart
    store.close()
    with SQLitePlatformStore(tmp_path / "enterprise.db") as store_reloaded:
        mgr_reloaded = EnterpriseGovernanceManager(store=store_reloaded)
        loaded_health = mgr_reloaded.get_policy("tenant-health")
        loaded_eu = mgr_reloaded.get_policy("tenant-eu-startup")

        assert loaded_health["org_display_name"] == "Veridian Clinical Systems"
        assert loaded_health["retention_mode"] == "worm_7y"
        assert loaded_health["deployment_topology"] == "on_prem_airgapped"
        assert loaded_health["branding"]["accent_hex"] == "#2DD4BF"
        assert loaded_health["max_concurrent_sandboxes"] == 16
        assert loaded_eu["retention_mode"] == gdpr_weak_policy["retention_mode"] == "ephemeral_0d"
        assert loaded_eu["org_display_name"] == "Berlin Labs"

        # Compliance posture evaluation across SOC2, HIPAA, ISO27001, GDPR
        for fw in ("SOC2", "HIPAA", "ISO27001"):
            posture = mgr_reloaded.evaluate_compliance_posture("tenant-health", fw)
            assert posture["passed"] is True
            assert len(posture["controls"]) >= 3
            assert posture["remediations"] == []

        gdpr_fail = mgr_reloaded.evaluate_compliance_posture("tenant-eu-startup", "GDPR")
        assert gdpr_fail["passed"] is False
        assert len(gdpr_fail["remediations"]) >= 2

        assert hipaa_policy["tenant_id"] == "tenant-health"


# ---------------------------------------------------------------------------
# 4. FastAPI Endpoints (`/v1/platform/marketplace/verify-signature` & `/enterprise/*`)
# ---------------------------------------------------------------------------


@pytest.fixture
def phase2_platform_client(tmp_path: Path):
    store = SQLitePlatformStore(tmp_path / "api_phase2.db")
    signer = Ed25519ManifestSigner()
    mp = MarketplaceRegistry(store=store, signer=signer)
    hub = UnifiedWorkspaceHub(store=store)
    ent = EnterpriseGovernanceManager(store=store)

    app.dependency_overrides[get_platform_hub] = lambda: hub
    app.dependency_overrides[get_marketplace_registry] = lambda: mp
    app.dependency_overrides[get_manifest_signer] = lambda: signer
    app.dependency_overrides[get_enterprise_manager] = lambda: ent
    try:
        with TestClient(app) as client:
            yield client, signer
    finally:
        app.dependency_overrides.pop(get_platform_hub, None)
        app.dependency_overrides.pop(get_marketplace_registry, None)
        app.dependency_overrides.pop(get_manifest_signer, None)
        app.dependency_overrides.pop(get_enterprise_manager, None)
        store.close()


def test_fastapi_verify_signature_and_enterprise_policy_routes(phase2_platform_client) -> None:
    client, signer = phase2_platform_client

    priv_pem, pub_b64 = generate_publisher_keypair()
    signer.register_trusted_key("partner-ed25519-01", pub_b64)

    manifest = {
        "schema": "keelway.package/v1",
        "id": "partner-pci-auditor",
        "name": "PCI Scope Verifier",
        "kind": "industry_enterprise_solution",
        "version": "1.0.0",
    }
    signed = signer.sign_manifest(manifest, priv_pem, "partner-ed25519-01")

    verify_ok = client.post("/v1/platform/marketplace/verify-signature", json={"manifest": signed})
    assert verify_ok.status_code == 200
    assert verify_ok.json()["valid"] is True
    assert verify_ok.json()["reason"] == "VERIFIED_ED25519"

    verify_tampered = client.post(
        "/v1/platform/marketplace/verify-signature",
        json={"manifest": {**signed, "version": "9.9.9"}},
    )
    assert verify_tampered.status_code == 200
    assert verify_tampered.json()["valid"] is False
    assert verify_tampered.json()["reason"] == "INVALID_ED25519_SIGNATURE"

    # Default GET policy for a tenant
    default_pol = client.get("/v1/platform/enterprise/policy/acme-bank")
    assert default_pol.status_code == 200
    assert default_pol.json()["tenant_id"] == "acme-bank"
    assert default_pol.json()["retention_mode"] == "standard_30d"

    # Invalid retention mode -> HTTP 422
    bad_put = client.put(
        "/v1/platform/enterprise/policy/acme-bank",
        json={"retention_mode": "forever_unbounded"},
    )
    assert bad_put.status_code == 422

    # Valid regulated policy update -> HTTP 200
    good_put = client.put(
        "/v1/platform/enterprise/policy/acme-bank",
        json={
            "org_display_name": "Acme Sovereign Bank",
            "retention_mode": "regulated_365d",
            "audit_retention_days": 365,
            "pii_redaction_enforced": True,
            "allow_prompt_logging": False,
            "deployment_topology": "dedicated_vpc",
            "allowed_model_regions": ["eu-central-1"],
            "sso_saml_required": True,
            "max_concurrent_sandboxes": 24,
            "max_workflow_minutes_per_day": 2400,
            "require_p10_for_external_webhooks": True,
        },
    )
    assert good_put.status_code == 200
    assert good_put.json()["retention_mode"] == "regulated_365d"
    assert good_put.json()["deployment_topology"] == "dedicated_vpc"

    # Compliance posture check
    soc2_resp = client.post(
        "/v1/platform/enterprise/compliance-check",
        json={"tenant_id": "acme-bank", "framework": "SOC2"},
    )
    assert soc2_resp.status_code == 200
    assert soc2_resp.json()["passed"] is True

    gdpr_resp = client.post(
        "/v1/platform/enterprise/compliance-check",
        json={"tenant_id": "acme-bank", "framework": "GDPR"},
    )
    assert gdpr_resp.status_code == 200
    assert gdpr_resp.json()["passed"] is True

    bad_fw = client.post(
        "/v1/platform/enterprise/compliance-check",
        json={"tenant_id": "acme-bank", "framework": "UNKNOWN_STD"},
    )
    assert bad_fw.status_code == 422

    # Publishing a tampered signed manifest to /v1/platform/marketplace/publish fails closed with HTTP 422
    tampered_pub = client.post(
        "/v1/platform/marketplace/publish",
        json={
            **signed,
            "publisher": "Forged Publisher",
            "permissions": {"read_paths": ["core/"], "write_paths": [], "network": "none"},
        },
    )
    assert tampered_pub.status_code == 422
    assert tampered_pub.json()["detail"]["passed"] is False

    # Direct keelway.agent/v1 manifest payload verification also supported without wrapper key
    agent_doc = signer.sign_manifest(
        {"schema": "keelway.agent/v1", "id": "agent-direct", "risk_tier": "A"},
        priv_pem,
        "partner-ed25519-01",
    )
    direct_verify = client.post("/v1/platform/marketplace/verify-signature", json=agent_doc)
    assert direct_verify.status_code == 200
    assert direct_verify.json()["valid"] is True
    assert direct_verify.json()["schema"] == "keelway.agent/v1"

