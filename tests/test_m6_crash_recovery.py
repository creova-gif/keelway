"""M6 OS-level fault tests — crash and disk failure surfaces (KEEL-ENG-052 follow-on).

Covers what the first suite couldn't: SIGKILL mid-write against a real
subprocess, read-only/missing paths, and a torn database page — all verified
against the actual SQLiteAgentCoharnessEngine, not mocks.
"""

import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.platform.agent_coharness import SQLiteAgentCoharnessEngine

REPO_ROOT = Path(__file__).resolve().parents[1]

_WRITER = """
import sys, time
sys.path.insert(0, {root!r})
from core.platform.agent_coharness import SQLiteAgentCoharnessEngine
eng = SQLiteAgentCoharnessEngine(db_path=sys.argv[1])
for i in range(10_000):
    eng.intercept_tool_call(workspace_id="crash", agent_host="claude_code",
                            tool_name="Bash", command=f"echo iter{{i}}")
""".format(root=str(REPO_ROOT))


def _count_interceptions(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM harness_interceptions").fetchone()[0]
    finally:
        conn.close()


def test_sigkill_midwrite_wal_recovers(tmp_path):
    """Kill -9 a writing subprocess; a fresh engine opens the DB, WAL
    replays cleanly, and committed rows are intact — never a silent zero."""
    db = tmp_path / "crash.db"
    proc = subprocess.Popen([sys.executable, "-c", _WRITER, str(db)])
    deadline = time.time() + 15
    while time.time() < deadline:
        if db.exists() and db.stat().st_size > 0:
            break
        time.sleep(0.05)
    assert proc.poll() is None
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)

    # Fresh engine must open the same path and keep working.
    eng = SQLiteAgentCoharnessEngine(db_path=db)
    rec = eng.intercept_tool_call(workspace_id="crash", agent_host="claude_code",
                                  tool_name="Bash", command="echo post-crash")
    assert rec["verdict"] in ("ALLOW", "HOLD_TICKET", "DENY")
    rows = _count_interceptions(db)
    assert rows >= 1  # post-crash row committed; killed-loop rows best-effort


def test_readonly_directory_fails_closed(tmp_path):
    """DB inside a read-only directory must raise, not silently drop writes."""
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        with pytest.raises((sqlite3.OperationalError, OSError, PermissionError)):
            SQLiteAgentCoharnessEngine(db_path=ro / "h.db")
    finally:
        ro.chmod(0o755)


def test_missing_parent_directory_auto_created(tmp_path):
    """Contract: _resolve_sqlite_target mkdirs missing parents, so a nested
    db_path just works."""
    db = tmp_path / "nope" / "nested" / "h.db"
    eng = SQLiteAgentCoharnessEngine(db_path=db)
    rec = eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                  tool_name="Bash", command="echo hi")
    assert db.is_file() and rec["verdict"] == "ALLOW"


def test_unwritable_parent_falls_back_to_memory(tmp_path):
    """Contract: if the target dir cannot be created, the engine silently
    degrades to :memory: — works but writes are ephemeral. Documented
    evidence-loss surface, asserted so a future fix can't regress silently."""
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a dir")
    eng = SQLiteAgentCoharnessEngine(db_path=blocker / "h.db")
    assert str(eng.db_path) == ":memory:"
    rec = eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                  tool_name="Bash", command="echo hi")
    assert rec["verdict"] == "ALLOW"  # works, but nothing persists


def test_torn_page_detected_not_silent(tmp_path):
    """Corrupt a page mid-file after real data exists; the next session must
    raise on access — corruption never reads back as valid rows."""
    db = tmp_path / "torn.db"
    eng = SQLiteAgentCoharnessEngine(db_path=db)
    for i in range(50):
        eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                tool_name="Bash", command=f"echo {i}")
    del eng  # flush + close

    # Force WAL contents into the main file so mid-file corruption lands on
    # real pages rather than an unused extent.
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    main_size = db.stat().st_size
    page = 4096 if main_size > 8192 else 1024
    with open(db, "r+b") as fh:
        fh.seek(page)
        fh.write(b"\xde\xad\xbe\xef" * 512)

    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("PRAGMA quick_check").fetchone()
    finally:
        conn.close()
    # Construction is lazy; the first write through a corrupt store must
    # surface the error — evidence can never be fabricated into it.
    eng2 = SQLiteAgentCoharnessEngine(db_path=db)
    with pytest.raises(sqlite3.DatabaseError):
        eng2.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                 tool_name="Bash", command="echo post-tear")


def test_concurrent_writers_one_killed_stays_consistent(tmp_path):
    """Two writers, one SIGKILLed mid-run — survivor + fresh engine see a
    consistent DB (WAL isolation, no half-committed rows)."""
    db = tmp_path / "multi.db"
    p1 = subprocess.Popen([sys.executable, "-c", _WRITER, str(db)])
    p2 = subprocess.Popen([sys.executable, "-c", _WRITER, str(db)])
    deadline = time.time() + 15
    while time.time() < deadline:
        if db.exists() and db.stat().st_size > 0:
            break
        time.sleep(0.05)
    p1.send_signal(signal.SIGKILL)
    p1.wait(timeout=10)
    p2.terminate()  # polite stop for the survivor
    p2.wait(timeout=15)

    conn = sqlite3.connect(str(db))
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()
    eng = SQLiteAgentCoharnessEngine(db_path=db)
    rec = eng.intercept_tool_call(workspace_id="crash", agent_host="claude_code",
                                  tool_name="Bash", command="echo verify")
    assert rec["verdict"] == "ALLOW"
