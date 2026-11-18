"""Policy bridge: host hook payloads -> co-harness verdicts.

`evaluate_hook_payload` is the single entry point adapters/host hook
commands use. It normalizes the payload via the adapter, delegates the
verdict to `SQLiteAgentCoharnessEngine.intercept_tool_call` (the same
authority used by `keelway harness intercept`), and maps the verdict to a
host-actionable decision.

Modes:
- `enforce`: DENY/HOLD verdicts block or hold the tool call.
- `audit_only`: the call is always permitted to proceed, but the verdict is
  still recorded in the hash-chained interception log for evidence.
"""

from __future__ import annotations

from typing import Any, Dict

from core.agents.external.base import AgentHostAdapter, NormalizedToolCall
from core.agents.external.hosts import get_adapter
from core.platform.agent_coharness import SQLiteAgentCoharnessEngine

_VALID_MODES = ("enforce", "audit_only")


def _host_decision(verdict: str, mode: str) -> str:
    """Map a co-harness verdict to a host-facing allow/deny/hold decision."""
    if mode == "audit_only":
        return "allow"
    if verdict in ("DENY",):
        return "deny"
    if verdict in ("HOLD_TICKET",):
        return "hold"
    return "allow"


def evaluate_hook_payload(
    engine: SQLiteAgentCoharnessEngine,
    agent_id: str,
    payload: Dict[str, Any],
    workspace_id: str = "default",
    mode: str = "audit_only",
    adapter: AgentHostAdapter | None = None,
) -> Dict[str, Any]:
    """Evaluate a host-native PreToolUse payload against Keelway policy.

    Returns a dict with `decision` (allow|deny|hold), the raw co-harness
    `record` (verdict, reason_code, ticket_id, event_sha256), and the
    normalized call. Raises KeyError for unknown agents, ValueError for bad mode.
    """
    clean_mode = str(mode or "").strip()
    if clean_mode not in _VALID_MODES:
        raise ValueError(f"Unsupported hook mode '{mode}'. Expected {_VALID_MODES}.")
    ad = adapter or get_adapter(agent_id)
    normalized: NormalizedToolCall = ad.parse_hook_payload(payload)
    record = engine.intercept_tool_call(
        workspace_id=workspace_id,
        agent_host=normalized.agent_id,
        tool_name=normalized.tool_name,
        command=normalized.command,
        ticket_id=normalized.ticket_id,
    )
    return {
        "decision": _host_decision(str(record.get("verdict") or ""), clean_mode),
        "mode": clean_mode,
        "agent_id": normalized.agent_id,
        "tool_name": normalized.tool_name,
        "record": record,
    }
