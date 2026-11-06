"""Tests for Keelway Two-Human Quorum Approval Engine (ADR-045, ADR-046).
Validates multi-role separation of duties, self-quorum prohibition, and agent rejection.
"""
from keelway.approvals.quorum import TwoHumanQuorumService

_FIXTURE_KEY = b"package-c-explicit-quorum-fixture-key"


def test_quorum_happy_path_both_distinct_humans_approve():
    service = TwoHumanQuorumService(signing_key=_FIXTURE_KEY)
    patch_hash = "sha256:production_patch_abc123"

    req = service.create_quorum_request(
        run_id="run_prod_01",
        patch_hash=patch_hash,
        environment="production",
    )
    assert req.status == "PENDING"
    assert req.is_fully_approved is False

    # 1. Security Lead approves
    ok1, msg1 = service.submit_role_approval(
        request_id=req.id,
        principal_id="alice_security_lead",
        role="Security Lead",
        current_patch_hash=patch_hash,
    )
    assert ok1 is True
    assert "PENDING_REMAINING" in msg1
    assert req.status == "PENDING"
    assert req.is_fully_approved is False

    # 2. Platform Owner approves (distinct human)
    ok2, msg2 = service.submit_role_approval(
        request_id=req.id,
        principal_id="bob_platform_owner",
        role="Platform Owner",
        current_patch_hash=patch_hash,
    )
    assert ok2 is True
    assert msg2 == "INFO_QUORUM_ACHIEVED_FULLY_APPROVED"
    assert req.status == "APPROVED"
    assert req.is_fully_approved is True
    assert len(req.signatures) == 2


def test_quorum_prohibits_same_person_satisfying_both_roles():
    service = TwoHumanQuorumService(signing_key=_FIXTURE_KEY)
    patch_hash = "sha256:patch_02"
    req = service.create_quorum_request(run_id="run_prod_02", patch_hash=patch_hash)

    # Alice approves as Security Lead
    ok1, _ = service.submit_role_approval(
        request_id=req.id,
        principal_id="alice_superadmin",
        role="Security Lead",
        current_patch_hash=patch_hash,
    )
    assert ok1 is True

    # Alice attempts to also approve as Platform Owner (Self-Quorum / Role Overlap)
    ok2, msg2 = service.submit_role_approval(
        request_id=req.id,
        principal_id="alice_superadmin",
        role="Platform Owner",
        current_patch_hash=patch_hash,
    )
    assert ok2 is False
    assert "ERR_SELF_QUORUM_PROHIBITED" in msg2
    assert req.status == "PENDING"
    assert req.is_fully_approved is False


def test_quorum_rejects_agent_or_bot_identities():
    service = TwoHumanQuorumService(signing_key=_FIXTURE_KEY)
    patch_hash = "sha256:patch_03"
    req = service.create_quorum_request(run_id="run_prod_03", patch_hash=patch_hash)

    for forbidden_id in ["coding_agent_v1", "github-actions-ci-bot", "sorvex-support-agent"]:
        ok, msg = service.submit_role_approval(
            request_id=req.id,
            principal_id=forbidden_id,
            role="Security Lead",
            current_patch_hash=patch_hash,
        )
        assert ok is False
        assert "ERR_INELIGIBLE_APPROVER_IDENTITY" in msg


def test_quorum_invalidates_if_patch_mutates_mid_review():
    service = TwoHumanQuorumService(signing_key=_FIXTURE_KEY)
    patch_hash = "sha256:original_hash"
    req = service.create_quorum_request(run_id="run_prod_04", patch_hash=patch_hash)

    # First approval succeeds on original patch
    service.submit_role_approval(
        request_id=req.id,
        principal_id="alice_sec",
        role="Security Lead",
        current_patch_hash=patch_hash,
    )

    # Code in repository mutates before second approval
    ok2, msg2 = service.submit_role_approval(
        request_id=req.id,
        principal_id="bob_platform",
        role="Platform Owner",
        current_patch_hash="sha256:tampered_or_rebased_hash",
    )
    assert ok2 is False
    assert "ERR_PATCH_HASH_MUTATED_QUORUM_INVALIDATED" in msg2
    assert req.status == "INVALIDATED"
