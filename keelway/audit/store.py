"""Keelway Persistent SQLite Audit Store.
Implements crash-resilient append-only audit persistence with WAL mode
and strict monotonic sequence checks.
"""
from __future__ import annotations

import json
import sqlite3
from typing import List, Optional, Tuple

from keelway.audit.recorder import GENESIS_PREV_HASH, verify_audit_chain
from keelway.core.models import AuditEvent


class AuditStoreError(Exception):
    pass


class ChainDiscontinuityError(AuditStoreError):
    pass


class SQLiteAuditStore:
    """Crash-resilient append-only SQLite store for Keelway audit chains."""

    def __init__(self, db_path: str = "keelway_audit.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(run_id, seq)
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_run_seq ON audit_events(run_id, seq);
                """
            )
            conn.commit()

    def append_event(self, event: AuditEvent) -> None:
        """Appends an event to the persistent chain with strict link verification."""
        with self._get_connection() as conn:
            # Check latest event for this run
            cursor = conn.cursor()
            cursor.execute(
                "SELECT seq, hash FROM audit_events WHERE run_id = ? ORDER BY seq DESC LIMIT 1;",
                (event.run_id,),
            )
            latest = cursor.fetchone()

            if latest is None:
                # First event in run must be seq 1 with GENESIS_PREV_HASH
                if event.seq != 1:
                    raise ChainDiscontinuityError(
                        f"First event in run {event.run_id} must have seq=1, got seq={event.seq}"
                    )
                if event.prev_hash != GENESIS_PREV_HASH:
                    raise ChainDiscontinuityError(
                        f"First event in run {event.run_id} must have prev_hash={GENESIS_PREV_HASH}"
                    )
            else:
                expected_seq = latest["seq"] + 1
                expected_prev_hash = latest["hash"]
                if event.seq != expected_seq:
                    raise ChainDiscontinuityError(
                        f"Sequence gap in run {event.run_id}: expected {expected_seq}, got {event.seq}"
                    )
                if event.prev_hash != expected_prev_hash:
                    raise ChainDiscontinuityError(
                        f"Hash chain broken in run {event.run_id}: expected prev_hash {expected_prev_hash}, got {event.prev_hash}"
                    )

            conn.execute(
                """
                INSERT INTO audit_events (
                    id, run_id, seq, kind, payload_digest, prev_hash, hash, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.run_id,
                    event.seq,
                    event.kind,
                    event.payload_digest,
                    event.prev_hash,
                    event.hash,
                    event.created_at,
                    json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
                ),
            )
            conn.commit()

    def get_events(self, run_id: str) -> List[AuditEvent]:
        """Retrieves all events for a run ordered by sequence."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_events WHERE run_id = ? ORDER BY seq ASC;",
                (run_id,),
            )
            rows = cursor.fetchall()
            events = []
            for r in rows:
                events.append(
                    AuditEvent(
                        id=r["id"],
                        run_id=r["run_id"],
                        seq=r["seq"],
                        kind=r["kind"],
                        payload_digest=r["payload_digest"],
                        prev_hash=r["prev_hash"],
                        hash=r["hash"],
                        created_at=r["created_at"],
                        payload=json.loads(r["payload_json"]),
                    )
                )
            return events

    def verify_persisted_chain(self, run_id: str) -> Tuple[bool, Optional[str]]:
        """Reads persisted events and cryptographically verifies the chain."""
        events = self.get_events(run_id)
        if not events:
            return False, "No events found for run"
        return verify_audit_chain(events)
