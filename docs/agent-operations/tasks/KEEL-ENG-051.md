# KEEL-ENG-051 — ACP Session Bridge (Agent Client Protocol)

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-17 |
| **Branch** | `fix/KEEL-ENG-051-acp-bridge` |

## Objective
Phase E continuation: Agent Client Protocol (ACP) transport + permission
bridge — the remaining protocol-level gap from
THIRD_PARTY_AGENT_INTEGRATION.md.

## Implementation
- `core/agents/external/acp.py` — `AcpClient`: NDJSON JSON-RPC 2.0 over
  stdio; `initialize` → `session/new` → `session/prompt`; dispatches
  `session/update` notifications as normalized events and answers
  `session/request_permission` via a pluggable `PermissionEvaluator`.
  Permission mapping: ALLOW*→allow option, DENY/unknown→reject option or
  cancelled, HOLD→cancelled (ACP has no native "ask"; ticket ID preserved
  in the decision record). Evaluator exceptions fail closed.
- `core/cli_harness.py` — `agents acp --agent <id> --prompt <text>
  [--mode enforce|audit_only] [--cwd] [--timeout] [--tape] [-- args]`.
  Launch argv comes from the adapter's env-scrubbed `LaunchSpec`;
  permission requests route through `engine.intercept_tool_call`
  (workspace-scoped, P-10/DLP/destructive-command authority). audit_only
  records evidence but never blocks. `--tape` records an `acp_session`
  flight-tape span.

## Live Evidence
- Fixture ACP agent (`tests/fixtures/fake_acp_agent.py`, real subprocess,
  real NDJSON JSON-RPC — not mocks): allow→`selected`/`allow-once`,
  deny→`refusal`, hold→`cancelled`+ticket, evaluator error→fail-closed.
- CLI `--tape` path writes a verifiable flight-tape span.
- 76 tests green across ACP + adapters + conformance + phase18.

## Acceptance Criteria
- [x] ACP initialize/session/prompt handshake works against a real
      JSON-RPC stdio peer
- [x] `session/request_permission` routed through co-harness verdicts
- [x] session/update events normalized + optional tape evidence
- [x] audit_only never blocks; enforce maps verdicts to ACP outcomes
- [x] Fail-closed on evaluator errors, timeouts, missing binaries

## Known Limits
- **No specific agent registered as ACP-capable yet** — `agents acp`
  works with any adapter whose binary speaks ACP, but real candidates
  (`claude-code-acp`, `gemini --experimental-acp`) are unverified;
  contract test against a pinned binary is required before any
  compatibility claim.
- ACP `protocolVersion=1` per current spec; version negotiation is
  minimal (server version echoed, no downgrade logic).
- `fs`/`terminal` client capabilities declared false — agents needing
  client-side file/terminal ops will not work through this bridge yet.
- Permission options matched by `kind` (`allow_once` etc.) with
  first-option fallback; agents with exotic option shapes may need
  adapter-specific mapping.
- stderr of the agent is discarded (ACP is stdout JSON-RPC); debugging
  relies on events/errors surfaced in the result.

## Next Recommended Action
Contract-test a real ACP agent (claude-code-acp or gemini
--experimental-acp) once available; decide Cline governance path
(MCP-only vs. CLI research).
