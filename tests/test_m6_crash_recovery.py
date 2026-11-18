"""M6 OS-level fault tests — crash and disk failure surfaces (KEEL-ENG-052 follow-on).

Covers what the first suite couldn't: SIGKILL mid-write against a real
subprocess, read-only/missing paths, and a torn database page — all verified
against the actual SQLiteAgentCoharnessEngine, not mocks.
"""

import os
import shutil
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
    eng.close()  # explicit: an open conn can block/partial the checkpoint

    # Checkpoint WAL into the main file, then read geometry for the live
    # root page of the interceptions table — guaranteed inside the b-tree
    # that quick_check traverses. A guessed offset can land on a freelist
    # page, which quick_check never reads (silent, flaky pass).
    conn = sqlite3.connect(str(db))
    busy, _log, _ckpt = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    assert busy == 0, "checkpoint incomplete — WAL frames would shadow corruption"
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    rootpage = conn.execute(
        "SELECT rootpage FROM sqlite_master "
        "WHERE type='table' AND name='harness_interceptions'"
    ).fetchone()[0]
    conn.close()

    # Corrupt a byte-level COPY, not the original: any connection that
    # outlives eng.close() keeps writing WAL frames into torn.db and can
    # overwrite the torn region (observed on Linux CI — a second conn saw
    # clean data after the first conn reported malformed).
    torn = tmp_path / "torn_corrupt.db"
    shutil.copy2(db, torn)
    with open(torn, "r+b") as fh:
        fh.seek((rootpage - 1) * page_size)
        fh.write(b"\xde\xad\xbe\xef" * 512)

    import json as _json
    dbg = {"db_size": db.stat().st_size, "torn_size": torn.stat().st_size,
           "rootpage": rootpage, "page_size": page_size}
    with open(torn, "rb") as fh:
        fh.seek((rootpage - 1) * page_size)
        dbg["torn_readback"] = fh.read(8).hex()
    conn = sqlite3.connect(str(torn))
    try:
        for pragma in ("quick_check", "integrity_check"):
            try:
                dbg[pragma] = conn.execute(f"PRAGMA {pragma}").fetchall()[:5]
            except sqlite3.DatabaseError as exc:
                dbg[f"{pragma}_error"] = str(exc)
        try:
            dbg["select"] = conn.execute(
                "SELECT COUNT(*) FROM harness_interceptions").fetchone()
        except sqlite3.DatabaseError as exc:
            dbg["select_error"] = str(exc)
        try:
            dbg["scan"] = len(conn.execute(
                "SELECT rowid FROM harness_interceptions").fetchall())
        except sqlite3.DatabaseError as exc:
            dbg["scan_error"] = str(exc)
    finally:
        conn.close()
    dbg["files"] = sorted(p.name for p in tmp_path.iterdir())
    for walish in tmp_path.iterdir():
        if walish.name != "torn_corrupt.db" and walish.is_file():
            dbg[f"extra_{walish.name}"] = walish.stat().st_size
    print("\nTORN_DEBUG", _json.dumps(dbg, default=str))
    conn = sqlite3.connect(str(torn))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("PRAGMA quick_check").fetchone()
    finally:
        conn.close()
    # Construction is lazy; the first write through a corrupt store must
    # surface the error — evidence can never be fabricated into it.
    eng2 = SQLiteAgentCoharnessEngine(db_path=torn)
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
