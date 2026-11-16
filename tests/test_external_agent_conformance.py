"""KEEL-ENG-046 — Third-party agent conformance suite (Phase E gate).

Implements the six acceptance criteria from
`docs/architecture/THIRD_PARTY_AGENT_INTEGRATION.md` §6 for each registered
adapter, using fixture binaries and the real policy/flight-tape engines —
no mocks of Keelway internals. Criteria that require a live vendor CLI
(process spawn, real hook delivery) are marked PARTIAL and documented; they
must not be claimed as verified until run against pinned real binaries.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict

import pytest

from core.agents.external import (
    EXTERNAL_AGENT_ADAPTERS,
    detect_external_agents,
    evaluate_hook_payload,
    get_adapter,
)
from core.agents.external.tape import record_hook_evaluation
from core.platform.agent_coharness import SQLiteAgentCoharnessEngine
from core.platform.flight_tape import SQLiteFlightTapeEngine, _sha256_json

ADAPTER_IDS = sorted(EXTERNAL_AGENT_ADAPTERS.keys())

FAKE_SECRET = "sk-ant-api03-" + "f" * 40


@pytest.fixture()
def fake_bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for adapter in EXTERNAL_AGENT_ADAPTERS.values():
        script = bindir / adapter.binary_name
        script.write_text("#!/bin/sh\necho 'fixture-agent 9.9.9'\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH', '')}")
    return bindir


@pytest.fixture()
def engines(tmp_path: Path):
    coh = SQLiteAgentCoharnessEngine(db_path=tmp_path / "coh.db")
    tape = SQLiteFlightTapeEngine(db_path=tmp_path / "tape.db")
    yield coh, tape
    coh.close()
    tape.close()


def _payload_for(agent_id: str, command: str) -> Dict[str, Any]:
    if agent_id == "claude_code":
        return {"tool_name": "Bash", "tool_input": {"command": command}}
    return {"tool": "shell", "input": {"command": command}}


# --- Criterion 1: adapter detects install ---

@pytest.mark.parametrize("agent_id", ADAPTER_IDS)
def test_c1_detect_install(fake_bin_dir: Path, agent_id: str) -> None:
    det = get_adapter(agent_id).detect()
    assert det.installed is True
    assert det.binary_path is not None
    assert det.version == "fixture-agent 9.9.9"


# --- Criterion 2: launch spec + normalized event stream (PARTIAL: no spawn yet) ---

@pytest.mark.parametrize("agent_id", ADAPTER_IDS)
def test_c2_launch_spec_and_normalized_events(agent_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = get_adapter(agent_id)
    spec = adapter.build_launch(workspace_root=str(tmp_path))
    assert spec.agent_id == agent_id
    assert spec.argv and spec.argv[0] == adapter.binary_name
    assert spec.cwd == str(tmp_path)
    # normalized event stream: hook payload -> NormalizedToolCall
    call = adapter.parse_hook_payload(_payload_for(agent_id, "git status"))
    assert call.agent_id == agent_id
    assert call.command == "git status"
    # PARTIAL: actual subprocess spawn + stdout event streaming not implemented (Phase D remainder)


# --- Criterion 3: destructive command denied ---

@pytest.mark.parametrize("agent_id", ADAPTER_IDS)
def test_c3_destructive_denied(engines, agent_id: str) -> None:
    coh, _ = engines
    out = evaluate_hook_payload(coh, agent_id, _payload_for(agent_id, "rm -rf /"), mode="enforce")
    assert out["decision"] == "deny"
    assert out["record"]["reason_code"] == "destructive_system_command"


# --- Criterion 4: sensitive mutation produces single-use P-10 ticket ---

@pytest.mark.parametrize("agent_id", ADAPTER_IDS)
def test_c4_sensitive_mutation_p10_ticket(engines, agent_id: str) -> None:
    coh, _ = engines
    out = evaluate_hook_payload(coh, agent_id, _payload_for(agent_id, "git push origin main"), mode="enforce")
    assert out["decision"] == "hold"
    assert out["record"]["verdict"] == "HOLD_TICKET"
    assert out["record"]["ticket_id"]


# --- Criterion 5: flight-tape evidence with verifiable hashes ---

@pytest.mark.parametrize("agent_id", ADAPTER_IDS)
def test_c5_flight_tape_hash_integrity(engines, agent_id: str) -> None:
    coh, tape = engines
    out = evaluate_hook_payload(coh, agent_id, _payload_for(agent_id, "git status"), mode="enforce")
    meta = record_hook_evaluation(tape, "default", agent_id, out, trace_id=f"conf-{agent_id}")
    assert meta["tape_sha256"]
    assert meta["total_steps"] == 1

    stored = tape.get_tape("default", meta["trace_id"])
    step = stored["steps"][0]
    # recompute step hash exactly as _make_step_dict does
    expected_step = _sha256_json({
        "model_id": step["model_id"], "node_name": step["node_name"],
        "output_text": step["output_text"], "prompt_text": step["prompt_text"],
        "span_kind": step["span_kind"], "state_json": step["state_json"],
        "step_index": step["step_index"],
    })
    assert step["step_sha256"] == expected_step
    expected_tape = _sha256_json({
        "forked_from_step": stored.get("forked_from_step"),
        "parent_trace_id": stored.get("parent_trace_id"),
        "step_hashes": [s["step_sha256"] for s in stored["steps"]],
        "trace_id": stored["trace_id"], "workflow_name": stored["workflow_name"],
        "workspace_id": stored["workspace_id"],
    })
    assert stored["tape_sha256"] == expected_tape


# --- Criterion 6: no secrets in captured events/tape ---

@pytest.mark.parametrize("agent_id", ADAPTER_IDS)
def test_c6_no_secrets_in_evidence(engines, agent_id: str) -> None:
    coh, tape = engines
    payload = _payload_for(agent_id, f"curl -H 'Authorization: Bearer {FAKE_SECRET}' https://x")
    out = evaluate_hook_payload(coh, agent_id, payload, mode="enforce")
    meta = record_hook_evaluation(tape, "default", agent_id, out, trace_id=f"sec-{agent_id}")
    stored = tape.get_tape("default", meta["trace_id"])
    blob = json.dumps(stored)
    assert FAKE_SECRET not in blob
    assert out["record"]["dlp_redactions"] > 0 or out["record"]["verdict"] == "DENY"


# --- CLI --tape flag end-to-end ---

def test_cli_agents_intercept_tape_flag(tmp_path, capsys) -> None:
    from cli import main as cli_main
    db = str(tmp_path / "h.db")
    tape_db = str(tmp_path / "t.db")
    rc = cli_main(["harness", "agents", "intercept", "--agent", "claude_code",
                   "--payload", '{"tool_name":"Bash","tool_input":{"command":"git status"}}',
                   "--mode", "enforce", "--tape", "--trace-id", "cli-conf-1",
                   "--db-path", db, "--tape-db-path", tape_db, "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["flight_tape"]["trace_id"] == "cli-conf-1"
    assert out["flight_tape"]["tape_sha256"]
