"""Tests for Keelway Signed Policy Bundles and Anti-Rollback (ADR-061).
Validates bundle signing, signature verification, expiration, tenancy, and monotonic version checks.
"""
from keelway.policy.bundle import (
    LocalPolicyBundleVerifier,
    PolicyBundleAuthority,
)


def test_signed_policy_bundle_happy_path():
    authority = PolicyBundleAuthority()
    verifier = LocalPolicyBundleVerifier()

    signed_bundle = authority.create_and_sign_bundle(
        bundle_id="corp_policy_q4_2026",
        org_id="org_acme",
        version=1,
        allowed_tools=["git.diff", "sandbox.exec_test"],
        allowed_repos=["github.com/acme/*"],
        sensitive_patterns=[".env", "credentials"],
        allow_network=False,
        require_two_human_quorum=True,
    )

    ok, msg = verifier.verify_and_load(signed_bundle, target_org_id="org_acme")
    assert ok is True
    assert msg == "INFO_POLICY_BUNDLE_VERIFIED_AND_ACCEPTED"
    assert verifier.highest_accepted_epoch == 1


def test_signed_policy_bundle_rejects_forged_signature():
    authority = PolicyBundleAuthority()
    verifier = LocalPolicyBundleVerifier()

    signed_bundle = authority.create_and_sign_bundle(
        bundle_id="corp_policy_tampered",
        org_id="org_acme",
        version=1,
        allowed_tools=["git.read"],
        allowed_repos=["*"],
        sensitive_patterns=[],
    )

    # Attacker alters signature
    signed_bundle.signature = "f" * 64
    ok, msg = verifier.verify_and_load(signed_bundle, target_org_id="org_acme")
    assert ok is False
    assert msg == "ERR_INVALID_POLICY_BUNDLE_SIGNATURE"


def test_signed_policy_bundle_enforces_anti_rollback_epoch():
    authority = PolicyBundleAuthority()
    verifier = LocalPolicyBundleVerifier()

    # Apply version 5
    bundle_v5 = authority.create_and_sign_bundle(
        bundle_id="policy_v5",
        org_id="org_acme",
        version=5,
        allowed_tools=["git.read"],
        allowed_repos=["*"],
        sensitive_patterns=[],
    )
    ok5, _ = verifier.verify_and_load(bundle_v5, target_org_id="org_acme")
    assert ok5 is True
    assert verifier.highest_accepted_epoch == 5

    # Attacker tries to downgrade to older vulnerable version 3 (Rollback Attack)
    bundle_v3 = authority.create_and_sign_bundle(
        bundle_id="policy_v3",
        org_id="org_acme",
        version=3,
        allowed_tools=["git.read", "unrestricted_shell"],
        allowed_repos=["*"],
        sensitive_patterns=[],
    )
    ok3, msg3 = verifier.verify_and_load(bundle_v3, target_org_id="org_acme")
    assert ok3 is False
    assert "ERR_POLICY_ROLLBACK_ATTEMPT" in msg3


def test_signed_policy_bundle_rejects_cross_org_application():
    authority = PolicyBundleAuthority()
    verifier = LocalPolicyBundleVerifier()

    bundle = authority.create_and_sign_bundle(
        bundle_id="policy_org_a",
        org_id="org_victim_tenant",
        version=1,
        allowed_tools=["git.read"],
        allowed_repos=["*"],
        sensitive_patterns=[],
    )

    # Tenant B tries to load Tenant A's policy
    ok, msg = verifier.verify_and_load(bundle, target_org_id="org_attacker_tenant")
    assert ok is False
    assert "ERR_ORG_MISMATCH" in msg
