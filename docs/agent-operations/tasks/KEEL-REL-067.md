# KEEL-REL-067 — LangGraph Adapter: Complete + Verify End-to-End (OD-4)

| Field | Value |
|---|---|
| **Status** | `QUEUED` |
| **Category** | `RELEASE / ADAPTERS` |
| **Agent** | unassigned |
| **Date** | 2026-11-18 |

## Objective
Per OD-4, LangGraph is first on the adapter roadmap because
`core/platform/langgraph_migrator.py` (645 LOC) already exists.

## Acceptance criteria
1. A real LangGraph agent graph imports into a Keelway governed run
   end-to-end through the public surface (CLI or `/v1`) — no mocks for
   the import path.
2. Imported runs honor P-10 approval gates, workspace confinement, and
   flight-tape evidence identically to native Keelway runs.
3. Tests prove: graph→task translation, tool-call mapping, approval
   pause/resume, and a negative path (malformed graph refuses honestly).
4. Honest docs: what constructs map, what is dropped/unsupported.

## Context
Existing infra: `core/platform/langgraph_migrator.py`,
`core/agents/external/` (ACP bridge, subprocess runner, policy gate,
tape). Sequence next: OpenAI Agents SDK, then Google ADK.
