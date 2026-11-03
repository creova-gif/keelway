"""Tests for Keelway Security Quarantine and Credential Revocation (PRD-001 & ADR-060).
Validates credential fencing, run freezing, and forensic audit event retention.
"""
from keelway.audit.recorder import AuditRecorder
from keelway.security.quarantine import QuarantineService


def test_quarantine_service_revocation_and_fencing():
    audit = AuditRecorder(run_id="run_quarantine_01")
    service = QuarantineService(audit_recorder=audit)

    assert service.is_revoked("compromised_api_token_123") is False

    # Revoke compromised credential
    rec = service.revoke_credential(
        identifier="compromised_api_token_123",
        kind="TOKEN",
        reason="Exposed in public telemetry log",
        revoked_by="security_lead_alice",
    )
    assert rec.revoked_id == "compromised_api_token_123"
    assert service.is_revoked("compromised_api_token_123") is True

    # Confirm forensic audit event
    assert len(audit.events) == 1
    assert audit.events[0].kind == "CREDENTIAL_REVOKED"
    assert audit.events[0].payload["revoked_id"] == "compromised_api_token_123"


def test_quarantine_service_run_freezing():
    audit = AuditRecorder(run_id="run_quarantine_02")
    service = QuarantineService(audit_recorder=audit)

    # Quarantine an active run with a rogue actor
    service.quarantine_run(
        run_id="run_quarantine_02",
        reason="Suspicious directory traversal detected",
        compromised_actor_id="rogue_runner_agent",
        quarantined_by="security_lead_alice",
    )

    assert service.is_quarantined("run_quarantine_02") is True
    assert service.is_revoked("rogue_runner_agent") is True

    # Confirm forensic events logged
    kinds = [ev.kind for ev in audit.events]
    assert "CREDENTIAL_REVOKED" in kinds
    assert "RUN_QUARANTINED" in kinds
