"""Tests for Keelway Human Approval Gate (FR-07).
Validates human-in-the-loop gating, agent self-approval prevention, patch hash binding,
and single-use consumption.
"""
import time
from keelway.approvals.service import ApprovalDecision, ApprovalService

_FIXTURE_KEY = b"package-c-explicit-approval-fixture-key"


def test_approval_happy_path():
    service = ApprovalService(ttl_seconds=300, signing_key=_FIXTURE_KEY)
    req = service.create_request(
        run_id="run_201",
        patch_hash="sha256:abc12345",
        diff_content="+ def hello(): pass",
        eval_score=0.95,
        eval_passed=True,
        estimated_cost_cents=2,
    )
    assert req.status == "PENDING"

    decision = ApprovalDecision(
        approval_id=req.id,
        decision="APPROVED",
        approver_id="human_security_lead",
        patch_hash="sha256:abc12345",
    )
    ok, msg = service.submit_decision(decision, current_patch_hash="sha256:abc12345")
    assert ok is True
    assert msg == "INFO_APPROVAL_RECORDED"
    assert req.status == "APPROVED"
    assert req.decision_signature is not None


def test_agent_self_approval_is_strictly_prohibited():
    service = ApprovalService(signing_key=_FIXTURE_KEY)
    req = service.create_request(
        run_id="run_202",
        patch_hash="sha256:patch_hash_1",
        diff_content="+ code",
        eval_score=1.0,
        eval_passed=True,
        estimated_cost_cents=1,
    )

    # An agent tries to approve its own patch
    decision = ApprovalDecision(
        approval_id=req.id,
        decision="APPROVED",
        approver_id="coding_agent_gpt4",
        patch_hash="sha256:patch_hash_1",
    )
    ok, msg = service.submit_decision(decision, current_patch_hash="sha256:patch_hash_1")
    assert ok is False
    assert msg == "ERR_AGENT_SELF_APPROVAL_PROHIBITED"
    assert req.status == "PENDING"


def test_patch_mutation_invalidates_approval():
    service = ApprovalService(signing_key=_FIXTURE_KEY)
    original_patch_hash = "sha256:original_patch_hash"
    req = service.create_request(
        run_id="run_203",
        patch_hash=original_patch_hash,
        diff_content="+ original code",
        eval_score=1.0,
        eval_passed=True,
        estimated_cost_cents=1,
    )

    # Repository was modified or rebased after approval request was made
    mutated_patch_hash = "sha256:mutated_malicious_patch_hash"
    decision = ApprovalDecision(
        approval_id=req.id,
        decision="APPROVED",
        approver_id="human_platform_lead",
        patch_hash=original_patch_hash,
    )
    ok, msg = service.submit_decision(decision, current_patch_hash=mutated_patch_hash)
    assert ok is False
    assert msg == "ERR_PATCH_HASH_MUTATED_APPROVAL_INVALIDATED"
    assert req.status == "INVALIDATED"


def test_two_attempts_cannot_consume_same_one_time_approval():
    service = ApprovalService(signing_key=_FIXTURE_KEY)
    patch_hash = "sha256:safe_patch"
    req = service.create_request(
        run_id="run_204",
        patch_hash=patch_hash,
        diff_content="+ code",
        eval_score=1.0,
        eval_passed=True,
        estimated_cost_cents=1,
    )

    decision = ApprovalDecision(
        approval_id=req.id,
        decision="APPROVED",
        approver_id="human_security_lead",
        patch_hash=patch_hash,
    )
    # First consumption succeeds
    ok1, msg1 = service.submit_decision(decision, current_patch_hash=patch_hash)
    assert ok1 is True

    # Second consumption fails
    ok2, msg2 = service.submit_decision(decision, current_patch_hash=patch_hash)
    assert ok2 is False
    assert msg2 == "ERR_APPROVAL_ALREADY_CONSUMED"


def test_cannot_approve_failed_eval():
    service = ApprovalService(signing_key=_FIXTURE_KEY)
    patch_hash = "sha256:failing_code"
    req = service.create_request(
        run_id="run_205",
        patch_hash=patch_hash,
        diff_content="+ buggy code",
        eval_score=0.4,
        eval_passed=False,  # Failed evaluation
        estimated_cost_cents=1,
    )

    decision = ApprovalDecision(
        approval_id=req.id,
        decision="APPROVED",
        approver_id="human_engineer",
        patch_hash=patch_hash,
    )
    ok, msg = service.submit_decision(decision, current_patch_hash=patch_hash)
    assert ok is False
    assert msg == "ERR_CANNOT_APPROVE_FAILED_EVALUATION"
