"""KEEL-REL-051: user-facing `keelway tape list|verify` for platform flight tapes."""

import json
import sqlite3
from pathlib import Path

import pytest

from core.platform.flight_tape import SQLiteFlightTapeEngine


def _ingest(engine: SQLiteFlightTapeEngine, db_path: Path) -> str:
    res = engine.ingest_traces(
        workspace_id="ws-verify",
        workflow_name="verify-test",
        spans=[
            {"node_name": "plan", "span_kind": "llm", "model_id": "qwen3.5:latest",
             "prompt_text": "plan the fix", "output_text": "step 1 done"},
            {"node_name": "tool", "span_kind": "tool", "model_id": "qwen3.5:latest",
             "prompt_text": "git status", "output_text": "clean"},
        ],
    )
    return str(res["trace_id"])


def test_verify_tape_valid(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    engine = SQLiteFlightTapeEngine(db_path=db)
    try:
        tid = _ingest(engine, db)
        report = engine.verify_tape(workspace_id="ws-verify", trace_id=tid)
        assert report["valid"] is True
        assert report["steps_valid"] is True
        assert report["tape_valid"] is True
        assert report["total_steps"] == 2
        assert all(s["valid"] for s in report["steps"])
        assert report["tape_sha256_claimed"] == report["tape_sha256_calculated"]
    finally:
        engine.close()


def test_verify_tape_detects_step_tamper(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    engine = SQLiteFlightTapeEngine(db_path=db)
    try:
        tid = _ingest(engine, db)
    finally:
        engine.close()
    conn = sqlite3.connect(db)
    conn.execute("UPDATE platform_flight_steps SET output_text='TAMPERED' WHERE trace_id=? AND step_index=1", (tid,))
    conn.commit()
    conn.close()
    engine2 = SQLiteFlightTapeEngine(db_path=db)
    try:
        report = engine2.verify_tape(workspace_id="ws-verify", trace_id=tid)
        assert report["valid"] is False
        assert report["steps_valid"] is False
        bad = [s for s in report["steps"] if not s["valid"]]
        assert len(bad) == 1 and bad[0]["node_name"] == "tool"
    finally:
        engine2.close()


def test_verify_tape_missing_raises(tmp_path: Path) -> None:
    engine = SQLiteFlightTapeEngine(db_path=tmp_path / "t.db")
    try:
        with pytest.raises(KeyError):
            engine.verify_tape(workspace_id="ws-verify", trace_id="nope")
    finally:
        engine.close()


def _cli_rc(argv: list[str]) -> int:
    from cli import main as cli_main
    with pytest.raises(SystemExit) as exc:
        cli_main(argv)
    return int(exc.value.code or 0)


def test_cli_tape_list_and_verify(tmp_path: Path, capsys) -> None:
    db = tmp_path / "t.db"
    engine = SQLiteFlightTapeEngine(db_path=db)
    tid = _ingest(engine, db)
    engine.close()

    rc = _cli_rc(["tape", "list", "--db-path", str(db), "--workspace", "ws-verify", "--json"])
    assert rc == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["total_tapes"] == 1

    rc = _cli_rc(["tape", "verify", "--trace-id", tid, "--db-path", str(db),
                  "--workspace", "ws-verify", "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is True

    rc = _cli_rc(["tape", "verify", "--trace-id", "bogus", "--db-path", str(db),
                  "--workspace", "ws-verify", "--json"])
    assert rc == 1
    err = json.loads(capsys.readouterr().out)
    assert err["code"] == "tape_not_found"


def test_cli_tape_verify_detects_tamper_exit_1(tmp_path: Path, capsys) -> None:
    db = tmp_path / "t.db"
    engine = SQLiteFlightTapeEngine(db_path=db)
    tid = _ingest(engine, db)
    engine.close()
    conn = sqlite3.connect(db)
    conn.execute("UPDATE platform_flight_tapes SET workflow_name='forged' WHERE trace_id=?", (tid,))
    conn.commit()
    conn.close()
    rc = _cli_rc(["tape", "verify", "--trace-id", tid, "--db-path", str(db),
                  "--workspace", "ws-verify"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "TAMPER DETECTED" in out
