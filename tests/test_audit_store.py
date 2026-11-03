"""Tests for Keelway Persistent SQLite Audit Store (Milestone 2).
Validates SQLite WAL persistence, crash recovery, and anti-tamper constraints.
"""
import os
import sqlite3
import tempfile
import pytest

from keelway.audit.recorder import AuditRecorder
from keelway.audit.store import ChainDiscontinuityError, SQLiteAuditStore


def test_sqlite_audit_store_persistence_and_wal():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "audit_test.db")
        store = SQLiteAuditStore(db_path=db_path)

        # Confirm WAL journal mode
        with sqlite3.connect(db_path) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert mode.lower() == "wal"

        # Record events through recorder backed by SQLite store
        recorder = AuditRecorder(run_id="run_store_01", store=store)
        recorder.record_event("RUN_CREATED", {"project": "keelway"})
        recorder.record_event("POLICY_DECISION", {"decision": "ALLOW"})
        recorder.record_event("APPROVAL_REQUESTED", {"patch_hash": "sha256:1234"})

        # Verify from store directly
        persisted_events = store.get_events("run_store_01")
        assert len(persisted_events) == 3
        assert persisted_events[0].kind == "RUN_CREATED"
        assert persisted_events[1].kind == "POLICY_DECISION"
        assert persisted_events[2].kind == "APPROVAL_REQUESTED"

        valid, err = store.verify_persisted_chain("run_store_01")
        assert valid is True
        assert err is None


def test_sqlite_audit_store_crash_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "recovery_test.db")
        store1 = SQLiteAuditStore(db_path=db_path)

        rec1 = AuditRecorder(run_id="run_recover_01", store=store1)
        rec1.record_event("EV_1", {"msg": "first"})
        rec1.record_event("EV_2", {"msg": "second"})

        # Simulate process crash and restart by creating fresh store and recorder from DB
        store2 = SQLiteAuditStore(db_path=db_path)
        recovered_rec = AuditRecorder.from_store(run_id="run_recover_01", store=store2)

        assert len(recovered_rec.events) == 2
        assert recovered_rec._seq == 2
        assert recovered_rec._last_hash == rec1.events[-1].hash

        # Continue appending after recovery
        ev3 = recovered_rec.record_event("EV_3", {"msg": "third"})
        assert ev3.seq == 3
        assert ev3.prev_hash == rec1.events[-1].hash

        valid, err = store2.verify_persisted_chain("run_recover_01")
        assert valid is True
        assert err is None


def test_sqlite_audit_store_rejects_discontinuity():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "gap_test.db")
        store = SQLiteAuditStore(db_path=db_path)

        rec = AuditRecorder(run_id="run_gap_01")
        ev = rec.record_event("EV_1", {"msg": "first"})
        # Tamper seq to create gap
        ev.seq = 5

        with pytest.raises(ChainDiscontinuityError):
            store.append_event(ev)
