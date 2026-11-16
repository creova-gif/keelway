"""KEEL-ENG-043 — Third-party agent adapter tests (Phase C, audit_only first).

Covers detection via fake CLI binaries on PATH, env-scrubbed launch specs,
host hook-payload normalization (Claude Code + Codex shapes), and policy
evaluation through the real `SQLiteAgentCoharnessEngine` verdict authority.
"""

from __future__ import annotations

import io
import os
import stat
from pathlib import Path
from typing import Dict

import pytest

from core.agents.external import (
    ClaudeCodeAdapter,
    CodexCliAdapter,
    detect_external_agents,
    evaluate_hook_payload,
    get_adapter,
)
from core.platform.agent_coharness import SQLiteAgentCoharnessEngine


@pytest.fixture()
def fake_bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("claude", "codex"):
        script = bindir / name
        script.write_text("#!/bin/sh\necho 'fixture-agent 1.2.3'\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH', '')}")
    return bindir


@pytest.fixture()
def engine() -> SQLiteAgentCoharnessEngine:
    eng = SQLiteAgentCoharnessEngine()
    yield eng
    eng.close()


# --- detection ---

def test_detect_installed(fake_bin_dir: Path) -> None:
    results = {d.agent_id: d for d in detect_external_agents()}
    assert results["claude_code"].installed is True
    assert results["claude_code"].binary_path is not None
    assert results["claude_code"].version == "fixture-agent 1.2.3"
    assert results["codex_cli"].installed is True


def test_detect_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    results = {d.agent_id: d for d in detect_external_agents()}
    assert results["claude_code"].installed is False
    assert results["codex_cli"].installed is False


# --- launch specs ---

def test_launch_spec_scrubs_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret")
    monkeypatch.setenv("MY_PLAIN_VAR", "hello")
    spec = ClaudeCodeAdapter().build_launch(workspace_root="/tmp/ws", extra_args=["--help"])
    assert spec.argv == ["claude", "--help"]
    assert spec.cwd == "/tmp/ws"
    assert "ANTHROPIC_API_KEY" not in spec.env
    assert spec.env.get("MY_PLAIN_VAR") == "hello"


# --- payload normalization ---

def test_claude_payload_normalization() -> None:
    payload = {
        "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git status"}, "cwd": "/repo",
    }
    call = ClaudeCodeAdapter().parse_hook_payload(payload)
    assert call.agent_id == "claude_code"
    assert call.tool_name == "Bash"
    assert call.command == "git status"


def test_claude_edit_payload_uses_file_path() -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "/repo/a.py"}}
    call = ClaudeCodeAdapter().parse_hook_payload(payload)
    assert call.command == "/repo/a.py"


def test_codex_payload_normalization() -> None:
    payload = {"tool": "shell", "input": {"command": "pytest -q"},
               "approval_ticket": "ptkt-abc"}
    call = CodexCliAdapter().parse_hook_payload(payload)
    assert call.agent_id == "codex_cli"
    assert call.tool_name == "shell"
    assert call.command == "pytest -q"
    assert call.ticket_id == "ptkt-abc"


# --- policy evaluation ---

def _claude_payload(command: str) -> Dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_enforce_allows_safe_command(engine: SQLiteAgentCoharnessEngine) -> None:
    out = evaluate_hook_payload(engine, "claude_code", _claude_payload("git status"), mode="enforce")
    assert out["decision"] == "allow"
    assert out["record"]["verdict"] == "ALLOW"
    assert out["record"]["event_sha256"].startswith("sha256:") or len(out["record"]["event_sha256"]) == 64


def test_enforce_denies_destructive(engine: SQLiteAgentCoharnessEngine) -> None:
    out = evaluate_hook_payload(engine, "claude_code", _claude_payload("rm -rf /"), mode="enforce")
    assert out["decision"] == "deny"
    assert out["record"]["reason_code"] == "destructive_system_command"


def test_enforce_holds_sensitive_mutation(engine: SQLiteAgentCoharnessEngine) -> None:
    out = evaluate_hook_payload(engine, "codex_cli",
                                {"tool": "shell", "input": {"command": "git push origin main"}},
                                mode="enforce")
    assert out["decision"] == "hold"
    assert out["record"]["verdict"] == "HOLD_TICKET"
    assert out["record"]["ticket_id"]


def test_audit_only_records_but_allows(engine: SQLiteAgentCoharnessEngine) -> None:
    out = evaluate_hook_payload(engine, "claude_code", _claude_payload("rm -rf /"), mode="audit_only")
    assert out["decision"] == "allow"
    assert out["record"]["verdict"] == "DENY"  # verdict still recorded for evidence


def test_single_use_ticket_consumed(engine: SQLiteAgentCoharnessEngine) -> None:
    cmd = "git push origin main"
    held = evaluate_hook_payload(engine, "claude_code", _claude_payload(cmd), mode="enforce")
    tid = held["record"]["ticket_id"]
    # Approve the ticket directly through the engine's review path is not exposed
    # here; simulate by issuing via intercept with a matching APPROVED ticket is
    # covered by phase18 tests — here we assert HOLD then DENY on replay w/o approval.
    replay = evaluate_hook_payload(engine, "claude_code",
                                   {"tool_name": "Bash", "tool_input": {"command": cmd},
                                    "ticket_id": tid}, mode="enforce")
    assert replay["decision"] == "hold"  # still PENDING


def test_unknown_agent_raises(engine: SQLiteAgentCoharnessEngine) -> None:
    with pytest.raises(KeyError):
        evaluate_hook_payload(engine, "not_an_agent", {}, mode="enforce")


def test_bad_mode_raises(engine: SQLiteAgentCoharnessEngine) -> None:
    with pytest.raises(ValueError):
        evaluate_hook_payload(engine, "claude_code", _claude_payload("ls"), mode="bogus")


def test_get_adapter() -> None:
    assert isinstance(get_adapter("claude_code"), ClaudeCodeAdapter)
    assert isinstance(get_adapter("codex_cli"), CodexCliAdapter)
    with pytest.raises(KeyError):
        get_adapter("cursor")


# --- CLI surface (KEEL-ENG-044) ---

def test_cli_agents_detect(capsys) -> None:
    from cli import main as cli_main
    rc = cli_main(["harness", "agents", "detect", "--json"])
    assert rc == 0
    import json as _json
    out = _json.loads(capsys.readouterr().out)
    ids = {a["agent_id"] for a in out["agents"]}
    assert ids == {"claude_code", "codex_cli"}
    assert "capabilities" in out


def test_cli_agents_intercept_enforce_deny(tmp_path, capsys) -> None:
    from cli import main as cli_main
    db = str(tmp_path / "h.db")
    rc = cli_main(["harness", "agents", "intercept", "--agent", "claude_code",
                   "--payload", '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}',
                   "--mode", "enforce", "--db-path", db, "--json"])
    assert rc == 1
    import json as _json
    out = _json.loads(capsys.readouterr().out)
    assert out["decision"] == "deny"
    assert out["record"]["reason_code"] == "destructive_system_command"


def test_cli_agents_intercept_audit_only_allows(tmp_path, capsys) -> None:
    from cli import main as cli_main
    db = str(tmp_path / "h.db")
    rc = cli_main(["harness", "agents", "intercept", "--agent", "codex_cli",
                   "--payload", '{"tool":"shell","input":{"command":"rm -rf /"}}',
                   "--mode", "audit_only", "--db-path", db, "--json"])
    assert rc == 0
    import json as _json
    out = _json.loads(capsys.readouterr().out)
    assert out["decision"] == "allow"
    assert out["record"]["verdict"] == "DENY"


def test_cli_agents_intercept_payload_file_and_stdin(tmp_path, capsys, monkeypatch) -> None:
    from cli import main as cli_main
    db = str(tmp_path / "h.db")
    pf = tmp_path / "hook.json"
    pf.write_text('{"tool_name":"Bash","tool_input":{"command":"git status"}}')
    rc = cli_main(["harness", "agents", "intercept", "--agent", "claude_code",
                   "--payload", f"@{pf}", "--mode", "enforce", "--db-path", db, "--json"])
    assert rc == 0
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO(
        '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'))
    rc = cli_main(["harness", "agents", "intercept", "--agent", "claude_code",
                   "--payload", "-", "--mode", "enforce", "--db-path", db, "--json"])
    assert rc == 0


def test_cli_agents_intercept_hold_exit_code(tmp_path, capsys) -> None:
    from cli import main as cli_main
    db = str(tmp_path / "h.db")
    rc = cli_main(["harness", "agents", "intercept", "--agent", "claude_code",
                   "--payload", '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}',
                   "--mode", "enforce", "--db-path", db, "--json"])
    assert rc == 2
