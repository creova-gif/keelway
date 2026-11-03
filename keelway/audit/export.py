"""Keelway Audit Bundle Exporter.
Implements FR-09: Exportable audit verification package and redacted trace data.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from keelway.audit.recorder import verify_audit_chain
from keelway.core.models import AuditEvent, RunManifest

EXPORT_SIGNING_KEY = b"keelway_audit_export_verification_key_v1"


class ExportBundle(BaseModel):
    schema_version: str = "1.0"
    exported_at: str
    run_id: str
    org_id: str
    project_id: str
    source_commit_sha: str
    chain_root_hash: str
    total_events: int
    chain_verified: bool
    verification_signature: str
    events: List[Dict[str, Any]]


class AuditExporter:
    """Produces exportable and portable audit verification bundles."""

    def __init__(self, signing_key: bytes = EXPORT_SIGNING_KEY):
        self.signing_key = signing_key

    def sign_root_hash(self, run_id: str, root_hash: str) -> str:
        """Signs the final chain root hash to seal the audit package."""
        msg = f"{run_id}:{root_hash}"
        return hmac.new(self.signing_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_bundle_signature(self, bundle: ExportBundle) -> bool:
        """Verifies the cryptographic seal on an exported audit bundle."""
        expected = self.sign_root_hash(bundle.run_id, bundle.chain_root_hash)
        return hmac.compare_digest(bundle.verification_signature, expected)

    def export(
        self,
        manifest: RunManifest,
        events: List[AuditEvent],
        redact_prompts: bool = True,
    ) -> ExportBundle:
        """Generates a verified, portable audit export package."""
        verified, err = verify_audit_chain(events)
        root_hash = events[-1].hash if events else "GENESIS"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sig = self.sign_root_hash(manifest.run_id, root_hash)

        exported_events = []
        for ev in events:
            ev_dict = ev.model_dump()
            if redact_prompts and "prompt" in ev_dict.get("payload", {}):
                # Redact raw prompt while preserving payload digest for proof
                ev_dict["payload"]["prompt"] = "[REDACTED_BY_KEELWAY_POLICY]"
            exported_events.append(ev_dict)

        return ExportBundle(
            exported_at=now,
            run_id=manifest.run_id,
            org_id=manifest.org_id,
            project_id=manifest.project_id,
            source_commit_sha=manifest.source_commit_sha,
            chain_root_hash=root_hash,
            total_events=len(events),
            chain_verified=verified,
            verification_signature=sig,
            events=exported_events,
        )
