"""Keelway Tamper-Evident Hash-Chained Audit Recorder.
Implements FR-05, FR-09, and cryptographic verification of append-only audit events.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from keelway.core.models import AuditEvent

if TYPE_CHECKING:
    from keelway.audit.store import SQLiteAuditStore

GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def canonical_json(data: Any) -> str:
    """Produces canonical deterministic JSON serialization for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_digest(content: str) -> str:
    """Calculates SHA-256 hex digest of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class AuditRecorder:
    """In-memory and durable hash-chained event recorder."""

    def __init__(self, run_id: str, store: Optional[SQLiteAuditStore] = None):
        self.run_id = run_id
        self.store = store
        self._events: List[AuditEvent] = []
        self._last_hash = GENESIS_PREV_HASH
        self._seq = 0

    @classmethod
    def from_store(cls, run_id: str, store: SQLiteAuditStore) -> AuditRecorder:
        """Restores a recorder from an existing SQLite audit chain."""
        recorder = cls(run_id, store=store)
        persisted_events = store.get_events(run_id)
        if persisted_events:
            valid, err = verify_audit_chain(persisted_events)
            if not valid:
                raise ValueError(f"Cannot restore corrupted audit chain for run {run_id}: {err}")
            recorder._events = persisted_events
            recorder._seq = persisted_events[-1].seq
            recorder._last_hash = persisted_events[-1].hash
        return recorder

    @property
    def events(self) -> List[AuditEvent]:
        return list(self._events)

    def record_event(self, kind: str, payload: Dict[str, Any]) -> AuditEvent:
        """Appends an event to the chain, computing strict SHA-256 hashes."""
        self._seq += 1
        payload_json = canonical_json(payload)
        payload_digest = compute_digest(payload_json)
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Compute hash: seq:kind:payload_digest:prev_hash
        hash_preimage = f"{self._seq}:{kind}:{payload_digest}:{self._last_hash}"
        event_hash = compute_digest(hash_preimage)

        event = AuditEvent(
            id=str(uuid.uuid4()),
            run_id=self.run_id,
            seq=self._seq,
            kind=kind,
            payload_digest=payload_digest,
            prev_hash=self._last_hash,
            hash=event_hash,
            created_at=created_at,
            payload=payload,
        )

        # Durably append to SQLite store if configured
        if self.store:
            self.store.append_event(event)

        self._events.append(event)
        self._last_hash = event_hash
        return event

    def verify_chain(self) -> Tuple[bool, Optional[str]]:
        """Verifies the integrity of the in-memory chain."""
        return verify_audit_chain(self._events)


def verify_audit_chain(events: List[AuditEvent]) -> Tuple[bool, Optional[str]]:
    """Strict verification of a hash-chained audit event list.
    
    Returns:
        (True, None) if completely intact.
        (False, error_description) if any tampering or discontinuity is detected.
    """
    if not events:
        return True, None

    expected_prev_hash = GENESIS_PREV_HASH

    for idx, ev in enumerate(events):
        expected_seq = idx + 1
        if ev.seq != expected_seq:
            return False, f"Event at index {idx} has invalid sequence {ev.seq}, expected {expected_seq}"

        # Verify payload digest
        recomputed_payload_digest = compute_digest(canonical_json(ev.payload))
        if ev.payload_digest != recomputed_payload_digest:
            return False, (
                f"Event {ev.seq} payload digest mismatch: "
                f"expected {recomputed_payload_digest}, got {ev.payload_digest}"
            )

        # Verify prev_hash
        if ev.prev_hash != expected_prev_hash:
            return False, (
                f"Event {ev.seq} prev_hash mismatch: "
                f"expected {expected_prev_hash}, got {ev.prev_hash}"
            )

        # Verify event hash
        expected_hash = compute_digest(
            f"{ev.seq}:{ev.kind}:{ev.payload_digest}:{ev.prev_hash}"
        )
        if ev.hash != expected_hash:
            return False, (
                f"Event {ev.seq} hash tampering detected: "
                f"expected {expected_hash}, got {ev.hash}"
            )

        expected_prev_hash = ev.hash

    return True, None
