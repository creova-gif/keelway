"""Flight-tape bridge for external-agent hook evaluations (KEEL-ENG-046).

Records each `evaluate_hook_payload` result as a `tool` span in the Keelway
flight tape (`SQLiteFlightTapeEngine.ingest_traces`), producing a tape with
`step_sha256`/`tape_sha256` integrity hashes — the evidence record required by
the third-party-agent compatibility acceptance criteria. All span text passes
through the flight tape's own `scrub_flight_text` DLP pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.platform.flight_tape import SQLiteFlightTapeEngine


def record_hook_evaluation(
    flight_engine: SQLiteFlightTapeEngine,
    workspace_id: str,
    agent_id: str,
    eval_result: Dict[str, Any],
    trace_id: Optional[str],
) -> Dict[str, Any]:
    """Ingest one external-agent tool-call evaluation as a flight-tape span.

    `eval_result` is the dict returned by `evaluate_hook_payload`
    (`decision`, `record`, `agent_id`, `tool_name`). Returns the tape meta
    including `trace_id` and `tape_sha256`.
    """
    record = eval_result.get("record") or {}
    span = {
        "span_kind": "tool",
        "node_name": f"{agent_id}:{eval_result.get('tool_name') or record.get('tool_name') or 'tool'}",
        "model_id": f"external-agent:{agent_id}",
        "prompt": record.get("scrubbed_command") or "",
        "output": {
            "decision": eval_result.get("decision"),
            "verdict": record.get("verdict"),
            "reason_code": record.get("reason_code"),
            "ticket_id": record.get("ticket_id"),
            "interception_event_sha256": record.get("event_sha256"),
        },
        "state": {
            "agent_id": agent_id,
            "mode": eval_result.get("mode"),
            "command_sha256": record.get("command_sha256"),
        },
        "tool_name": eval_result.get("tool_name") or record.get("tool_name"),
    }
    return flight_engine.ingest_traces(
        workspace_id=workspace_id,
        workflow_name=f"external-agent:{agent_id}",
        source_framework="keelway-agent-adapter",
        spans=[span],
        trace_id=trace_id,
    )
