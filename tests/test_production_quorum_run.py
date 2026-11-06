"""Tests for End-to-End Production Two-Human Quorum in GovernedRunCoordinator.
Implements and verifies ADR-045 and ADR-046 in a live governed lifecycle.
"""
import os

from keelway.core.models import RunStatus
from keelway.core.runner import GovernedRunCoordinator


def test_production_run_enforces_two_human_quorum():
    os.environ["KEELWAY_APPROVAL_SIGNING_KEY"] = "package-c-explicit-approval-fixture-key"
    os.environ["KEELWAY_QUORUM_SIGNING_KEY"] = "package-c-explicit-quorum-fixture-key"
    coord = GovernedRunCoordinator(
        org_id="org_sorvex_prod",
        project_id="proj_critical_core",
        actor_id="lead_eng",
        repo_path=".",
        classification="production",  # Triggers ADR-045 Two-Human Quorum
    )

    try:
        ok, quorum_id = coord.start_run("Production critical change")
        assert ok is True
        assert coord.manifest.status == RunStatus.AWAITING_APPROVAL
        assert coord.active_quorum_id == quorum_id

        # 1. Security Lead signs
        ok_sec, msg_sec = coord.submit_quorum_approval(
            quorum_id=quorum_id,
            principal_id="alice_security_lead",
            role="Security Lead",
        )
        assert ok_sec is True
        assert "PENDING_REMAINING" in msg_sec
        # Still awaiting second approval
        assert coord.manifest.status == RunStatus.AWAITING_APPROVAL

        # 2. Platform Owner signs (distinct human)
        ok_plat, msg_plat = coord.submit_quorum_approval(
            quorum_id=quorum_id,
            principal_id="bob_platform_owner",
            role="Platform Owner",
        )
        assert ok_plat is True
        assert msg_plat == "INFO_QUORUM_ACHIEVED_FULLY_APPROVED"

        # Now fully approved!
        assert coord.manifest.status == RunStatus.APPROVED

        # 3. Create PR
        # Get backing approval request ID
        base_appr_id = list(coord.approvals._requests.keys())[0]
        ok_pr, pr_res, _ = coord.promote_to_pr(
            approval_id=base_appr_id,
            title="feat: Production change with two-human quorum",
            description="Signed by Alice (Security) and Bob (Platform)",
        )
        assert ok_pr is True
        assert pr_res.status == "OPEN"

        # 4. Verify Cryptographic Audit Chain
        valid, err = coord.audit.verify_chain()
        assert valid is True
        assert err is None

        # Check for quorum events in audit log
        kinds = [ev.kind for ev in coord.audit.events]
        assert "TWO_HUMAN_QUORUM_REQUESTED" in kinds
        assert "QUORUM_ROLE_APPROVED" in kinds
        assert "TWO_HUMAN_QUORUM_ACHIEVED" in kinds

    finally:
        coord.teardown()
