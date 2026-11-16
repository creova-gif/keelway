# KEEL-ENG-043 — External Agent Adapters (Phase C)

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-043-agent-adapters` |

## Objective
Phase C of `THIRD_PARTY_AGENT_INTEGRATION.md`: `AgentAdapter` contract + `claude_code`/`codex_cli` adapters — detection, env-scrubbed launch specs, hook-payload normalization, policy bridge to `intercept_tool_call`. Audit_only-first per scope doc.

## Implementation
- `core/agents/external/base.py` — `AgentHostAdapter` ABC + `AgentDetection`/`LaunchSpec`/`NormalizedToolCall`.
- `core/agents/external/hosts.py` — `ClaudeCodeAdapter`, `CodexCliAdapter`, `EXTERNAL_AGENT_ADAPTERS`, `detect_external_agents()`, `get_adapter()`. Detection = `shutil.which` + `--version` (5s timeout, never raises). Launch env via `scrub_env`.
- `core/agents/external/policy.py` — `evaluate_hook_payload(engine, agent_id, payload, workspace_id, mode)` → `{decision, record}`; enforce maps DENY→deny, HOLD_TICKET→hold; audit_only always allows but records verdict.

## Acceptance Criteria
- [x] Detection works with fake binaries on PATH; missing → `installed: False`, never raises
- [x] Launch spec scrubs secret env vars (`ANTHROPIC_API_KEY` dropped, plain vars kept)
- [x] Claude + Codex payload shapes normalized (tool_input.command / file_path; codex `tool`/`input`/`approval_ticket`)
- [x] enforce: safe→allow, `rm -rf /`→deny, `git push`→hold+P-10 ticket
- [x] audit_only: destructive recorded as DENY verdict but decision=allow
- [x] Unknown agent → KeyError; bad mode → ValueError
- [x] 14 new tests + 30 combined (phase18 coharness + mcp remote) pass

## Known Limits
- `LaunchSpec` is spec-only — no subprocess spawn/event streaming yet (Phase D).
- Cursor/Cline/OpenCode/ACP not registered; hook schemas untested.
- No CLI/API surface yet for `detect_external_agents` (SDK wiring is Phase D/E).

## Next Recommended Action
Phase D: wire adapters into `keelway harness` CLI (`harness agents detect|run`) + flight-tape event recording + PostToolUse events.
