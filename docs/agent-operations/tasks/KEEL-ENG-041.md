# KEEL-ENG-041 — Third-Party Agent Integration Scoping

| Field | Value |
|---|---|
| **Status** | `SCOPED` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `docs/KEEL-ENG-041-agent-integration-scope` |

## Objective
Scope third-party coding-agent integration (Claude Code, Codex, Cursor, OpenCode, Cline, ACP) per Platform Directive §3 — separate from `AutonomousAgentLoop`, reusing shared policy/verification infra.

## Deliverable
`docs/architecture/THIRD_PARTY_AGENT_INTEGRATION.md` — verified inventory, gap analysis, `AgentAdapter` protocol proposal, per-agent mechanism matrix, phased plan (B–E), compatibility acceptance criteria, risks.

## Verified this session
- `cli.py harness intercept` live: `git status` → ALLOW; `rm -rf /` → DENY `destructive_system_command`.
- Confirmed gaps: no agent-process adapters; external MCP servers catalog-only (no MCP client); no ACP; partial hook coverage.

## Next Recommended Action
Phase B: real MCP client for registered stdio/sse servers (makes existing registry invocable) — smallest verified increment. Requires founder go-ahead to leave `SCOPED` status.
