"""Agent lifecycle/tool-event recording for external agents (KEEL-ENG-048).

Observational events (`PostToolUse`, `SessionStart`, `SessionEnd`) carry no
policy verdict — they are evidence. `record_agent_event` normalizes the
payload and ingests it as a flight-tape span so every external-agent session
leaves hash-chained records alongside `PreToolUse` interceptions.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.agents.external.base import AgentHostAdapter
from core.agents.external.hosts import get_adapter
from core.platform.flight_tape import SQLiteFlightTapeEngine

VALID_AGENT_EVENTS = ("posttooluse", "sessionstart", "sessionend")
_EVENT_NODE = {"posttooluse": "PostToolUse", "sessionstart": "SessionStart", "sessionend": "SessionEnd"}


def _payload_excerpt(payload: Dict[str, Any], limit: int = 2000) -> str:
    try:
        text = json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError):
        text = str(payload)
    return text[:limit]


def record_agent_event(
    flight_engine: SQLiteFlightTapeEngine,
    agent_id: str,
    event_name: str,
    payload: Dict[str, Any],
    workspace_id: str = "default",
    trace_id: Optional[str] = None,
    adapter: Optional[AgentHostAdapter] = None,
) -> Dict[str, Any]:
    """Record an external-agent lifecycle/tool event as a flight-tape span.

    `event_name` must be one of `VALID_AGENT_EVENTS`. For `posttooluse` the
    adapter's `parse_hook_payload` extracts tool context when the payload
    carries `tool_name`/`tool_input`; other events store a scrubbed payload
    excerpt. Returns the tape meta (`trace_id`, `tape_sha256`, ...).
    """
    clean_event = str(event_name or "").strip().lower()
    if clean_event not in VALID_AGENT_EVENTS:
        raise ValueError(f"Unsupported agent event '{event_name}'. Expected {list(VALID_AGENT_EVENTS)}.")
    ad = adapter or get_adapter(agent_id)

    tool_name = ""
    command = ""
    if clean_event == "posttooluse":
        try:
            call = ad.parse_hook_payload(payload)
            tool_name, command = call.tool_name, call.command
        except Exception:
            tool_name = str(payload.get("tool_name") or "")
    if not tool_name:
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "")

    span = {
        "span_kind": "tool" if clean_event == "posttooluse" else "agent",
        "node_name": f"{ad.agent_id}:{_EVENT_NODE[clean_event]}",
        "model_id": f"external-agent:{ad.agent_id}",
        "prompt": command or _payload_excerpt(payload),
        "output": {
            "event": _EVENT_NODE[clean_event],
            "tool_name": tool_name,
            "payload_excerpt": _payload_excerpt(payload, limit=1000),
        },
        "state": {"agent_event": clean_event, "agent_id": ad.agent_id},
        "tool_name": tool_name or None,
    }
    return flight_engine.ingest_traces(
        workspace_id=workspace_id,
        workflow_name=f"external-agent:{ad.agent_id}",
        source_framework="keelway-agent-adapter",
        spans=[span],
        trace_id=trace_id,
    )
