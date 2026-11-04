"""
Unit tests for Keelway Offline Receipt Verification Engine & Flight Replay.
"""
import hashlib
import json
import time
import pytest
from pathlib import Path

from core.orchestration.flight_recorder import FlightRecorder, FlightPlayer
from core.orchestration.p2p_mesh import LocalTeamMesh
from core.security.receipt_verifier import ReceiptVerifier
from evals.drift_detector import EvaluationReceipt


def test_verify_evaluation_receipt(tmp_path):
    receipt = EvaluationReceipt(
        eval_run_id="eval_test_001",
        timestamp_utc="2026-11-04T05:00:00Z",
        model_name="qwen-2.5-coder-7b",
        total_tasks=10,
        passed_tasks=10,
        pass_rate_pct=100.0,
        total_duration_ms=45.2,
        p50_latency_ms=4.1,
        p95_latency_ms=6.8,
        task_results=[{"task_id": "EVAL-01", "passed": True}],
    )
    receipt_data = receipt.to_dict()
    receipt_file = tmp_path / "eval_receipt.json"
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    # 1. Valid verification
    rep = ReceiptVerifier.verify(receipt_file)
    assert rep.is_valid is True
    assert rep.receipt_type == "evaluation"
    assert rep.receipt_id == "eval_test_001"
    assert rep.digest_calculated == receipt_data["receipt_sha256"]

    # 2. Tampered verification
    tampered_data = dict(receipt_data)
    tampered_data["passed_tasks"] = 9
    tampered_file = tmp_path / "eval_tampered.json"
    tampered_file.write_text(json.dumps(tampered_data), encoding="utf-8")

    rep_tampered = ReceiptVerifier.verify(tampered_file)
    assert rep_tampered.is_valid is False
    assert len(rep_tampered.errors) > 0


def test_verify_flight_tape_and_player_replay(tmp_path):
    rec = FlightRecorder(task_id="tape_test_001", recordings_dir=tmp_path)
    rec.record_event("prompt", {"text": "Fix bug in auth handler"})
    rec.record_event("tool_call", {"tool": "read_file", "path": "auth.py"})
    rec.record_event("tool_result", {"tool": "read_file", "output": "def verify(): pass"})
    rec.record_event("state_transition", {"from": "planning", "to": "executing"})
    tape_file = rec.save_tape()

    # 1. Verify via FlightPlayer directly
    player = FlightPlayer(tape_file)
    valid, calc, claimed = player.verify_integrity()
    assert valid is True
    assert calc == claimed

    # 2. Replay all
    events = player.replay_all()
    assert len(events) == 4
    assert events[0]["event_type"] == "prompt"
    assert events[1]["event_type"] == "tool_call"
    assert events[2]["event_type"] == "tool_result"
    assert events[3]["event_type"] == "state_transition"

    # 3. Verify via unified ReceiptVerifier
    rep = ReceiptVerifier.verify(tape_file)
    assert rep.is_valid is True
    assert rep.receipt_type == "flight_tape"
    assert rep.receipt_id == "tape_test_001"
    assert rep.details["total_events"] == 4

    # 4. Tampered flight tape
    raw = json.loads(tape_file.read_text(encoding="utf-8"))
    raw["events"][0]["payload"]["text"] = "Injected malicious prompt"
    tampered_file = tmp_path / "tampered.flight.json"
    tampered_file.write_text(json.dumps(raw), encoding="utf-8")

    rep_tampered = ReceiptVerifier.verify(tampered_file)
    assert rep_tampered.is_valid is False
    assert "Calculated tape digest" in rep_tampered.errors[0]


def test_verify_mesh_delegation_receipt(tmp_path):
    mesh = LocalTeamMesh(node_name="node-test", port=7430)
    receipt = mesh.delegate_task("Analyze AST complexity", min_vram_mb=2048)

    receipt_file = tmp_path / "mesh_receipt.json"
    receipt_file.write_text(json.dumps(receipt.to_dict()), encoding="utf-8")

    rep = ReceiptVerifier.verify(receipt_file, secret_key=mesh.secret_key)
    assert rep.is_valid is True
    assert rep.receipt_type == "mesh_delegation"
    assert rep.receipt_id == receipt.delegation_id

    # Wrong secret key
    rep_bad_key = ReceiptVerifier.verify(receipt_file, secret_key=b"wrong_secret_key_12345")
    assert rep_bad_key.is_valid is False


def test_verify_head_anchor_receipt(tmp_path):
    anchor_data = {
        "schema": "keelway.head_anchor/v1",
        "anchored_at": "2026-11-04T05:00:00Z",
        "entries_count": 42,
        "head_hash": "a" * 64,
    }
    # Calculate signature
    import hmac
    key = b"test_anchor_key"
    msg = f"{anchor_data['head_hash']}:{anchor_data['entries_count']}:{anchor_data['anchored_at']}".encode("utf-8")
    anchor_data["signature"] = hmac.new(key, msg, hashlib.sha256).hexdigest()

    anchor_file = tmp_path / "anchor_receipt.json"
    anchor_file.write_text(json.dumps(anchor_data), encoding="utf-8")

    rep = ReceiptVerifier.verify(anchor_file, secret_key=key)
    assert rep.is_valid is True
    assert rep.receipt_type == "head_anchor"

    # Bad signature
    anchor_data["signature"] = "b" * 64
    bad_file = tmp_path / "bad_anchor.json"
    bad_file.write_text(json.dumps(anchor_data), encoding="utf-8")
    rep_bad = ReceiptVerifier.verify(bad_file, secret_key=key)
    assert rep_bad.is_valid is False


def test_cli_receipt_and_flight_commands(tmp_path):
    from cli import cmd_receipt, cmd_flight

    rec = FlightRecorder(task_id="cli_flight_test", recordings_dir=tmp_path)
    rec.record_event("prompt", {"task": "test"})
    tape_file = rec.save_tape()

    # CLI flight verify
    rc_verify = cmd_flight("verify", str(tape_file))
    assert rc_verify == 0

    # CLI flight replay
    rc_replay = cmd_flight("replay", str(tape_file), show_events=True)
    assert rc_replay == 0

    # CLI receipt verify
    rc_receipt = cmd_receipt("verify", str(tape_file))
    assert rc_receipt == 0
