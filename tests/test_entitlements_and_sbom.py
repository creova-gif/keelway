"""
Tests for Keelway Entitlement Management, Privacy-Preserving Metering,
and CycloneDX SBOM / Supply Chain Provenance (WP16, WP17, WP20).
"""
import hashlib
import json
import time
import pytest
from pathlib import Path

from core.billing.entitlements import (
    EntitlementCertificate,
    EntitlementManager,
    EnterpriseFeature,
    LicenseTier,
    PrivacyPreservingMeter,
    BillingWebhookHandler,
)
from core.security.sbom import SBOMGenerator, SBOMVerifier
from core.security.receipt_verifier import ReceiptVerifier


_ENTITLEMENT_FIXTURE = b"package-c-explicit-entitlement-lifecycle-key"


def test_entitlement_certificate_lifecycle_and_grace_period():
    now = time.time()
    # 1. Active certificate signed with an explicit non-default key
    cert = EntitlementCertificate(
        org_id="org_acme_corp",
        org_name="Acme Corp",
        tier=LicenseTier.ENTERPRISE,
        seats=25,
        allowed_features=["two_human_quorum", "customer_vpc_runner"],
        issued_at=now - 100,
        expires_at=now + 86400,
        grace_period_days=14,
    )
    cert.sign(_ENTITLEMENT_FIXTURE)
    valid, status = cert.is_valid(_ENTITLEMENT_FIXTURE)
    assert valid is True
    assert status == "ACTIVE"

    # 2. Tampered signature fails
    cert_tampered = EntitlementCertificate.from_dict(cert.to_dict())
    cert_tampered.seats = 100  # unearned seat expansion
    valid_tampered, status_tampered = cert_tampered.is_valid(_ENTITLEMENT_FIXTURE)
    assert valid_tampered is False
    assert status_tampered == "INVALID_SIGNATURE"

    # 3. Grace period check (expired 3 days ago, 14-day grace)
    cert_grace = EntitlementCertificate(
        org_id="org_acme_corp",
        org_name="Acme Corp",
        tier=LicenseTier.PRO,
        seats=5,
        allowed_features=["p2p_mesh"],
        issued_at=now - (20 * 86400),
        expires_at=now - (3 * 86400),
        grace_period_days=14,
    )
    cert_grace.sign(_ENTITLEMENT_FIXTURE)
    valid_grace, status_grace = cert_grace.is_valid(_ENTITLEMENT_FIXTURE, now=now)
    assert valid_grace is True
    assert status_grace == "IN_GRACE_PERIOD"

    # 4. Completely expired (expired 20 days ago, beyond 14-day grace)
    valid_expired, status_expired = cert_grace.is_valid(_ENTITLEMENT_FIXTURE, now=now + (18 * 86400))
    assert valid_expired is False
    assert status_expired == "EXPIRED"


def test_entitlement_manager_feature_gates_and_seat_limits(tmp_path):
    mgr_file = tmp_path / "entitlements.json"
    mgr = EntitlementManager(
        storage_path=mgr_file,
        secret_key=b"package-c-explicit-entitlement-fixture-key",
    )

    # 1. Fallback Community organization
    allowed_comm, _ = mgr.check_feature_access("unknown_org", EnterpriseFeature.GUIDED_BUILDER)
    assert allowed_comm is True  # Community default feature

    denied_comm, reason_comm = mgr.check_feature_access("unknown_org", EnterpriseFeature.TWO_HUMAN_QUORUM)
    assert denied_comm is False  # Enterprise-only feature
    assert "not permitted under COMMUNITY tier" in reason_comm

    # 2. Register Enterprise certificate
    now = time.time()
    ent_cert = EntitlementCertificate(
        org_id="org_enterprise_corp",
        org_name="Enterprise Corp",
        tier=LicenseTier.ENTERPRISE,
        seats=2,
        allowed_features=["two_human_quorum", "customer_vpc_runner"],
        issued_at=now,
        expires_at=now + 10000,
    )
    ent_cert.sign(mgr.secret_key)
    ok, _ = mgr.register_certificate(ent_cert)
    assert ok is True

    # Check access granted
    allowed_ent, _ = mgr.check_feature_access("org_enterprise_corp", EnterpriseFeature.TWO_HUMAN_QUORUM)
    assert allowed_ent is True

    # 3. Seat allocation and capacity limit
    alloc1, s1 = mgr.allocate_seat("org_enterprise_corp", "alice@enterprise.com")
    assert alloc1 is True and s1 == "ALLOCATED"

    alloc2, s2 = mgr.allocate_seat("org_enterprise_corp", "bob@enterprise.com")
    assert alloc2 is True and s2 == "ALLOCATED"

    # Third seat exceeds capacity (limit: 2)
    alloc3, s3 = mgr.allocate_seat("org_enterprise_corp", "charlie@enterprise.com")
    assert alloc3 is False
    assert "Seat capacity reached" in s3


def test_privacy_preserving_meter():
    meter = PrivacyPreservingMeter()
    # Record two runs for org_1
    meter.record_usage("org_1", "qwen-2.5-coder", tokens_in=500, tokens_out=150, cost_usd=0.002, duration_ms=120.0)
    meter.record_usage("org_1", "deepseek-coder", tokens_in=800, tokens_out=300, cost_usd=0.004, duration_ms=210.0)

    usage = meter.get_org_usage("org_1")
    assert usage["total_invocations"] == 2
    assert usage["total_tokens_in"] == 1300
    assert usage["total_tokens_out"] == 450
    assert usage["total_cost_usd"] == 0.006
    assert usage["total_duration_ms"] == 330.0
    assert usage["models_used"] == ["deepseek-coder", "qwen-2.5-coder"]

    # Verify no prompt or file data retained
    for key in usage.keys():
        assert "prompt" not in key and "code" not in key and "file" not in key


def test_billing_webhook_handler_idempotency_and_signatures():
    handler = BillingWebhookHandler(secret="test_secret_12345")
    payload = {"customer_id": "cus_998", "subscription_tier": "pro", "status": "active"}
    raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    import hmac
    sig = hmac.new(b"test_secret_12345", raw_bytes, hashlib.sha256).hexdigest()

    # 1. Valid signature and first processing
    res1 = handler.handle_event("evt_001", "subscription.updated", payload, signature_header=sig)
    assert res1["status"] == "processed"
    assert res1["event_id"] == "evt_001"

    # 2. Duplicate replay rejected (idempotency)
    res2 = handler.handle_event("evt_001", "subscription.updated", payload, signature_header=sig)
    assert res2["status"] == "ignored"
    assert res2["reason"] == "duplicate_event_already_processed"

    # 3. Bad signature rejected
    res3 = handler.handle_event("evt_002", "invoice.paid", payload, signature_header="bad_sig_000")
    assert res3["status"] == "rejected"
    assert res3["reason"] == "invalid_signature"


def test_sbom_generation_and_verification(tmp_path):
    # 1. Generate SBOM
    manifest = SBOMGenerator.generate()
    assert manifest.bom_format == "CycloneDX"
    assert manifest.spec_version == "1.5"
    assert len(manifest.components) > 0
    assert len(manifest.root_digest_sha256) == 64
    assert len(manifest.provenance_signature) == 64

    # 2. Verify with SBOMVerifier
    valid, status, details = SBOMVerifier.verify(manifest.to_dict())
    assert valid is True
    assert status == "VERIFIED"
    assert details["components_count"] == len(manifest.components)

    # 3. Verify via unified ReceiptVerifier
    sbom_file = tmp_path / "test_sbom.json"
    sbom_file.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

    rep = ReceiptVerifier.verify(sbom_file)
    assert rep.is_valid is True
    assert rep.receipt_type == "sbom_manifest"
    assert rep.digest_calculated == manifest.root_digest_sha256

    # 4. Tampered SBOM detection
    tampered_data = manifest.to_dict()
    tampered_data["components"].append({
        "name": "malicious-package",
        "version": "6.6.6",
        "component_type": "library",
        "purl": "pkg:pypi/malicious@6.6.6",
        "sha256": "0" * 64,
        "supplier": "Attacker",
    })
    valid_tampered, status_tampered, _ = SBOMVerifier.verify(tampered_data)
    assert valid_tampered is False
    assert status_tampered == "ROOT_DIGEST_MISMATCH"


def test_cli_sbom_and_entitlements_commands(tmp_path):
    from cli import cmd_sbom, cmd_entitlements

    sbom_out = tmp_path / "cli_sbom.json"
    rc_gen = cmd_sbom("generate", out=sbom_out)
    assert rc_gen == 0
    assert sbom_out.exists()

    rc_ver = cmd_sbom("verify", target=str(sbom_out))
    assert rc_ver == 0

    rc_ent_status = cmd_entitlements("status", org="default-org")
    assert rc_ent_status == 0

    rc_ent_check = cmd_entitlements("check", org="default-org", feature="local_agent_loop")
    assert rc_ent_check == 1
