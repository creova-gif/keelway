"""M6 reliability: fault-injection and performance-baseline tests.

Fault injection exercises real failure surfaces — malformed input, SQL
metacharacters, DB corruption, ticket-consumption races, and tape tampering —
against the SQLite co-harness and flight-tape engines. Performance baselines
measure real latency/throughput ceilings and assert generous bounds; these are
baselines, not SLO claims.
"""
import sqlite3
import threading
import time

import pytest

from core.platform.agent_coharness import (
    AgentCoharnessValidationError,
    SQLiteAgentCoharnessEngine,
)
from core.platform.flight_tape import SQLiteFlightTapeEngine


# ---------------------------------------------------------------- faults ---


def test_workspace_id_sql_metachars_rejected(tmp_path):
    """SQL metacharacters in workspace_id are rejected at validation —
    injection payloads never reach the SQL layer."""
    eng = SQLiteAgentCoharnessEngine(db_path=tmp_path / "h.db")
    for evil_ws in ("x'; DROP TABLE harness_interceptions;--",
                    'w" OR 1=1 --',
                    "w\x00drop"):
        with pytest.raises(AgentCoharnessValidationError):
            eng.intercept_tool_call(
                workspace_id=evil_ws, agent_host="claude_code",
                tool_name="Bash", command="echo hi",
            )
    # Metachars in the command itself are data, not syntax — stored verbatim.
    rec = eng.intercept_tool_call(
        workspace_id="w", agent_host="claude_code",
        tool_name="Bash", command="echo 'x'; -- comment",
    )
    assert rec["verdict"] in ("ALLOW", "HOLD_TICKET", "DENY")


def test_empty_and_oversized_commands(tmp_path):
    eng = SQLiteAgentCoharnessEngine(db_path=tmp_path / "h.db")
    with pytest.raises(AgentCoharnessValidationError):
        eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                tool_name="Bash", command="   ")
    big = "echo " + "A" * 200_000
    rec = eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                  tool_name="Bash", command=big)
    assert rec["verdict"] in ("ALLOW", "HOLD_TICKET", "DENY")


def test_single_use_ticket_consumed_exactly_once(tmp_path):
    """Two threads racing one APPROVED ticket: exactly one may consume it."""
    eng = SQLiteAgentCoharnessEngine(db_path=tmp_path / "h.db")
    cmd = "git push origin main"
    held = eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                   tool_name="Bash", command=cmd)
    assert held["verdict"] == "HOLD_TICKET"
    tid = held["ticket_id"]
    eng.decide_ticket(workspace_id="w", ticket_id=tid, decision="APPROVED")

    verdicts = []

    def consume():
        rec = eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                      tool_name="Bash", command=cmd, ticket_id=tid)
        verdicts.append(rec["verdict"])

    threads = [threading.Thread(target=consume) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(verdicts) == ["ALLOW_WITH_TICKET", "DENY"], verdicts


def test_corrupted_db_fails_closed(tmp_path):
    """A garbage-byte DB must raise, never fabricate a verdict."""
    bad = tmp_path / "corrupt.db"
    bad.write_bytes(b"\x00\xffgarbage-not-sqlite" * 64)
    with pytest.raises(sqlite3.DatabaseError):
        SQLiteAgentCoharnessEngine(db_path=bad)


def test_tape_tamper_detected(tmp_path):
    """Mutating a stored step's payload must break verification."""
    eng = SQLiteFlightTapeEngine(db_path=tmp_path / "t.db")
    meta = eng.ingest_traces(
        workspace_id="w", workflow_name="wf", source_framework="test",
        spans=[{"span_name": "s1", "span_type": "llm",
                "attributes": {"gen_ai.request.model": "m"},
                "prompt_text": "p", "output_text": "o"}],
    )
    tid = meta["trace_id"]
    assert eng.verify_tape(workspace_id="w", trace_id=tid)["valid"] is True

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("UPDATE platform_flight_steps SET output_text='forged' WHERE trace_id=?", (tid,))
    conn.commit()
    conn.close()
    report = eng.verify_tape(workspace_id="w", trace_id=tid)
    assert report["valid"] is False
    assert report["steps_valid"] is False


# ------------------------------------------------------ perf baselines -----


def _percentile(values, pct):
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round(pct / 100.0 * len(ordered))) - 1))
    return ordered[idx]


def test_intercept_latency_baseline(tmp_path):
    """Baseline: local SQLite intercept should stay well under 250ms p95."""
    eng = SQLiteAgentCoharnessEngine(db_path=tmp_path / "h.db")
    lat = []
    for i in range(200):
        t0 = time.perf_counter()
        eng.intercept_tool_call(workspace_id="w", agent_host="claude_code",
                                tool_name="Bash", command=f"echo iter{i}")
        lat.append((time.perf_counter() - t0) * 1000.0)
    p50, p95 = _percentile(lat, 50), _percentile(lat, 95)
    print(f"\nintercept p50={p50:.2f}ms p95={p95:.2f}ms n=200")
    assert p95 < 250.0


def test_concurrent_intercept_integrity(tmp_path):
    """8 threads x 20 interceptions: all succeed, all IDs unique, hash-safe."""
    eng = SQLiteAgentCoharnessEngine(db_path=tmp_path / "h.db")
    ids, errors = set(), []

    def worker(n):
        try:
            for i in range(20):
                rec = eng.intercept_tool_call(
                    workspace_id="w", agent_host="claude_code",
                    tool_name="Bash", command=f"echo w{n}i{i}")
                ids.add(rec["interception_id"])
        except Exception as exc:  # noqa: BLE001 - record, assert after join
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    elapsed = time.perf_counter() - t0
    print(f"\nconcurrent intercept: {len(ids)} unique ids in {elapsed:.2f}s")
    assert not errors
    assert len(ids) == 160


def test_audit_chain_write_and_verify_throughput(tmp_path):
    """500-event chain: record + verify completes inside a sane bound."""
    from keelway.audit.recorder import AuditRecorder, verify_audit_chain
    rec = AuditRecorder(run_id="perf_run")
    t0 = time.perf_counter()
    for i in range(500):
        rec.record_event("POLICY_DECISION", {"i": i, "decision": "ALLOW"})
    valid, err = verify_audit_chain(rec.events)
    elapsed = time.perf_counter() - t0
    print(f"\naudit chain 500 events record+verify: {elapsed:.2f}s")
    assert valid is True and err is None
    assert elapsed < 5.0


def test_tape_ingest_and_verify_throughput(tmp_path):
    """100-span tape ingest + recompute verification inside a sane bound."""
    eng = SQLiteFlightTapeEngine(db_path=tmp_path / "t.db")
    spans = [
        {"span_name": f"s{i}", "span_type": "llm",
         "attributes": {"gen_ai.request.model": "m"},
         "prompt_text": f"p{i}", "output_text": f"o{i}"}
        for i in range(100)
    ]
    t0 = time.perf_counter()
    meta = eng.ingest_traces(workspace_id="w", workflow_name="wf",
                           source_framework="test", spans=spans)
    report = eng.verify_tape(workspace_id="w", trace_id=meta["trace_id"])
    elapsed = time.perf_counter() - t0
    print(f"\ntape ingest+verify 100 spans: {elapsed:.2f}s")
    assert report["valid"] is True
    assert elapsed < 5.0
