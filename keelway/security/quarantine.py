"""Keelway Security Quarantine and Credential Revocation Service.
Implements fail-closed quarantine, credential revocation, and forensic audit retention
(PRD-001 Edge Cases & ADR-060 Deny-Old-Before-Enable-New).
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel

from keelway.audit.recorder import AuditRecorder


class RevocationRecord(BaseModel):
    revoked_id: str
    kind: str  # "ACTOR", "TOKEN", "RUNNER", "KEY"
    reason: str
    revoked_at: str
    revoked_by: str


class QuarantineService:
    """Manages active run quarantines and compromised credential revocations."""

    def __init__(self, audit_recorder: Optional[AuditRecorder] = None):
        self.audit_recorder = audit_recorder
        self._revoked_items: Dict[str, RevocationRecord] = {}
        self._quarantined_runs: Set[str] = set()

    def revoke_credential(
        self,
        identifier: str,
        kind: str,
        reason: str,
        revoked_by: str = "security_lead",
    ) -> RevocationRecord:
        """Revokes a compromised actor, runner, or token, immediately fencing access."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec = RevocationRecord(
            revoked_id=identifier,
            kind=kind,
            reason=reason,
            revoked_at=now,
            revoked_by=revoked_by,
        )
        self._revoked_items[identifier] = rec

        if self.audit_recorder:
            self.audit_recorder.record_event(
                "CREDENTIAL_REVOKED",
                {
                    "revoked_id": identifier,
                    "kind": kind,
                    "reason": reason,
                    "revoked_by": revoked_by,
                },
            )
        return rec

    def is_revoked(self, identifier: str) -> bool:
        """Fail-closed check for revoked credentials."""
        return identifier in self._revoked_items

    def quarantine_run(
        self,
        run_id: str,
        reason: str,
        compromised_actor_id: Optional[str] = None,
        quarantined_by: str = "security_lead",
    ) -> None:
        """Quarantines a suspicious or compromised run, halting all side effects."""
        self._quarantined_runs.add(run_id)

        if compromised_actor_id:
            self.revoke_credential(
                identifier=compromised_actor_id,
                kind="ACTOR",
                reason=f"Compromised in quarantined run {run_id}: {reason}",
                revoked_by=quarantined_by,
            )

        if self.audit_recorder:
            self.audit_recorder.record_event(
                "RUN_QUARANTINED",
                {
                    "run_id": run_id,
                    "reason": reason,
                    "compromised_actor_id": compromised_actor_id,
                    "quarantined_by": quarantined_by,
                    "status": "FROZEN",
                },
            )

    def is_quarantined(self, run_id: str) -> bool:
        """True if the run is currently quarantined."""
        return run_id in self._quarantined_runs
