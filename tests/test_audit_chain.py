"""Tests for Keelway Audit Chain (FR-05, FR-09).
Validates tamper-evident hash chaining, payload digests, and fail-closed integrity checks.
"""
from keelway.audit.recorder import AuditRecorder, verify_audit_chain, GENESIS_PREV_HASH


def test_audit_chain_genesis_and_progression():
    recorder = AuditRecorder(run_id="run_test_001")
    ev1 = recorder.record_event("RUN_CREATED", {"actor": "lead_eng", "target": "main"})
    assert ev1.seq == 1
    assert ev1.prev_hash == GENESIS_PREV_HASH
    assert len(ev1.hash) == 64

    ev2 = recorder.record_event("POLICY_DECISION", {"decision": "ALLOW", "tool": "git.diff"})
    assert ev2.seq == 2
    assert ev2.prev_hash == ev1.hash

    ev3 = recorder.record_event("APPROVAL_GRANTED", {"approver": "human_alice"})
    assert ev3.seq == 3
    assert ev3.prev_hash == ev2.hash

    valid, err = recorder.verify_chain()
    assert valid is True
    assert err is None


def test_audit_chain_detects_payload_tampering():
    recorder = AuditRecorder(run_id="run_test_002")
    recorder.record_event("RUN_CREATED", {"actor": "lead_eng"})
    recorder.record_event("APPROVAL_GRANTED", {"approver": "human_alice"})

    events = recorder.events
    # Attacker attempts to modify payload without updating digest/hash
    events[1].payload["approver"] = "malicious_actor"

    valid, err = verify_audit_chain(events)
    assert valid is False
    assert "payload digest mismatch" in err


def test_audit_chain_detects_hash_tampering():
    recorder = AuditRecorder(run_id="run_test_003")
    recorder.record_event("RUN_CREATED", {"actor": "lead_eng"})
    recorder.record_event("APPROVAL_GRANTED", {"approver": "human_alice"})

    events = recorder.events
    # Attacker alters the hash directly
    events[0].hash = "a" * 64

    valid, err = verify_audit_chain(events)
    assert valid is False
    assert "hash tampering detected" in err or "prev_hash mismatch" in err


def test_audit_chain_detects_event_deletion_or_reordering():
    recorder = AuditRecorder(run_id="run_test_004")
    recorder.record_event("EV_1", {"step": 1})
    recorder.record_event("EV_2", {"step": 2})
    recorder.record_event("EV_3", {"step": 3})

    events = recorder.events
    # Remove middle event
    tampered_events = [events[0], events[2]]

    valid, err = verify_audit_chain(tampered_events)
    assert valid is False
    assert "invalid sequence" in err or "prev_hash mismatch" in err
