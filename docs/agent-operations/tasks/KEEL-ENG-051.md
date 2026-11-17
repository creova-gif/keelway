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

## Real-Agent Verification (2026-11-17)

- **`hermes-acp 0.22.5+2996` — real `session/request_permission`
  VERIFIED.** A live `agents acp --agent hermes_acp --mode enforce`
  session prompted a `write_file` edit on `.env` (Hermes' sensitive-path
  rule forces an ask under any auto-approve policy). The request flowed
  through real NDJSON JSON-RPC → `intercept_tool_call` → ALLOW
  (interception `hint-9a33253240b2`, `safe_readonly_or_test`) → the
  `approve` option was returned and Hermes wrote the file (86
  `session/update` events, `stop_reason=end_turn`).
- HOLD/DENY mapping remains fixture-verified: Hermes does not classify
  `git push` as a dangerous command (attempted exec, 0 permission
  requests), so the terminal-approval path was not exercisable live.
- `gemini --acp` dead on this host — Google EOL'd Gemini Code Assist
  OAuth for individuals ("migrate to Antigravity"); error observed at
  `session/new` (-32000).
- No specific agent is claimed broadly "ACP-compatible"; `hermes_acp`
  is verified for the session + permission surfaces described above.

## Known Limits

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
Contract-test further ACP agents (claude-code-acp) once available;
decide Cline governance path (MCP-only vs. CLI research).
