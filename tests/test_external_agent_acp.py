"""Tests for the ACP (Agent Client Protocol) session bridge (KEEL-ENG-051).

Uses a fixture ACP agent (tests/fixtures/fake_acp_agent.py) that speaks
newline-delimited JSON-RPC 2.0 over stdio: initialize, session/new,
session/update notifications, session/request_permission, session/prompt.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from core.agents.external.acp import run_acp_session

FIXTURE = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


@pytest.fixture()
def fake_acp_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a fake `claude` binary that runs the ACP fixture agent."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "claude"
    script.write_text(
        f"#!/bin/sh\nexec {sys.executable} {FIXTURE} \"$@\"\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH', '')}")
    return bindir


def _evaluator_record(verdict: str, reason: str = "test", ticket: str | None = None):
    def _eval(tool_name: str, command: str, ticket_id):
        return {"verdict": verdict, "reason_code": reason,
                "ticket_id": ticket or ticket_id, "tool_name": tool_name,
                "command": command}
    return _eval


def test_acp_session_allow_permission(fake_acp_agent: Path) -> None:
    result = run_acp_session(
        ["claude"], "say hi", agent_id="claude_code",
        permission_evaluator=_evaluator_record("ALLOW_WITH_TICKET"),
        rpc_timeout=15.0,
    )
    assert result.error is None, result.error
    assert result.stop_reason == "end_turn"
    assert len(result.permission_decisions) == 1
    dec = result.permission_decisions[0]
    assert dec.outcome == "selected"
    assert dec.option_id == "allow-once"
    assert dec.verdict.startswith("ALLOW")
    kinds = [e["kind"] for e in result.events]
    assert "agent_message_chunk" in kinds
    assert "tool_call" in kinds


def test_acp_session_deny_permission(fake_acp_agent: Path) -> None:
    result = run_acp_session(
        ["claude"], "do bad", agent_id="claude_code",
        permission_evaluator=_evaluator_record("DENY", "destructive_system_command"),
        rpc_timeout=15.0,
    )
    assert result.error is None, result.error
    dec = result.permission_decisions[0]
    assert dec.verdict.startswith("DENY")
    assert dec.reason_code == "destructive_system_command"
    # Fixture agent observes rejection and stops with "refusal".
    assert result.stop_reason == "refusal"


def test_acp_session_hold_ticket(fake_acp_agent: Path) -> None:
    result = run_acp_session(
        ["claude"], "git push", agent_id="claude_code",
        permission_evaluator=_evaluator_record("HOLD_TICKET", "p10_ticket_required",
                                               ticket="ptkt-test123"),
        rpc_timeout=15.0,
    )
    assert result.error is None, result.error
    dec = result.permission_decisions[0]
    assert dec.verdict.startswith("HOLD")
    assert dec.ticket_id == "ptkt-test123"
    assert dec.outcome == "cancelled"
    assert result.stop_reason == "refusal"


def test_acp_evaluator_error_fails_closed(fake_acp_agent: Path) -> None:
    def _boom(tool_name, command, ticket_id):
        raise RuntimeError("policy engine exploded")

    result = run_acp_session(
        ["claude"], "anything", agent_id="claude_code",
        permission_evaluator=_boom, rpc_timeout=15.0,
    )
    assert result.error is None, result.error
    dec = result.permission_decisions[0]
    assert dec.verdict == "DENY_POLICY_ERROR"
    assert result.stop_reason == "refusal"


def test_acp_no_evaluator_defaults_allow(fake_acp_agent: Path) -> None:
    result = run_acp_session(["claude"], "hi", agent_id="claude_code",
                             permission_evaluator=None, rpc_timeout=15.0)
    assert result.error is None, result.error
    assert result.permission_decisions[0].outcome == "selected"
    assert result.stop_reason == "end_turn"


def test_acp_missing_binary_errors() -> None:
    result = run_acp_session(["definitely-not-an-acp-agent-xyz"], "hi",
                             agent_id="missing", rpc_timeout=5.0)
    assert result.error is not None


def test_acp_extract_tool_call_folds_edit_body() -> None:
    """rawInput edit bodies reach the evaluated string (KEEL-ENG-053)."""
    from core.agents.external.acp import AcpClient
    tool_name, evaluated = AcpClient._extract_tool_call({
        "toolCall": {"title": "Approve edit: .env",
                     "kind": "edit",
                     "rawInput": {"path": ".env",
                                  "content": "KEY=sk-live-EXAMPLE_DLP_000"}},
    })
    assert tool_name == "edit"
    assert "path=.env" in evaluated
    assert "sk-live-EXAMPLE_DLP_000" in evaluated
    # Command tools unchanged: command wins over title, no content folding.
    tn2, ev2 = AcpClient._extract_tool_call({
        "toolCall": {"title": "bash: rm -rf /tmp/x", "kind": "execute",
                     "rawInput": {"command": "rm -rf /tmp/x"}},
    })
    assert tn2 == "execute" and ev2 == "rm -rf /tmp/x"


def test_acp_content_dlp_deny_e2e(fake_acp_agent: Path, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """An edit whose body contains a secret is DENYed by real co-harness
    content-DLP — closes the titles-only gap (KEEL-ENG-053)."""
    from core.platform.agent_coharness import SQLiteAgentCoharnessEngine
    monkeypatch.setenv("FAKE_ACP_TOOL_CALL_JSON", json.dumps({
        "title": "Approve edit: .env", "kind": "edit",
        "rawInput": {"path": ".env",
                     "content": "SERVICE_KEY=sk-live-EXAMPLE_DLP_LEAK_000"}}))
    engine = SQLiteAgentCoharnessEngine(db_path=tmp_path / "h.db")

    def _eval(tool_name: str, command: str, ticket_id):
        return engine.intercept_tool_call(
            workspace_id="acp-dlp", agent_host="hermes_acp",
            tool_name=tool_name, command=command, ticket_id=ticket_id)

    result = run_acp_session(
        ["claude"], "write env", agent_id="hermes_acp",
        permission_evaluator=_eval, rpc_timeout=15.0,
    )
    assert result.error is None, result.error
    dec = result.permission_decisions[0]
    assert dec.verdict.startswith("DENY")
    assert dec.reason_code == "dlp_secret_detected"
    assert result.stop_reason == "refusal"


def test_acp_tape_span_recorded(fake_acp_agent: Path, tmp_path: Path) -> None:
    from cli import main as cli_main
    tape_db = tmp_path / "tape.db"
    rc = cli_main([
        "harness", "agents", "acp", "--agent", "claude_code",
        "--prompt", "hello", "--mode", "audit_only",
        "--db-path", str(tmp_path / "h.db"),
        "--tape", "--tape-db-path", str(tape_db), "--json",
    ])
    assert rc == 0
    # tape file created and non-empty
    assert tape_db.exists() and tape_db.stat().st_size > 0
