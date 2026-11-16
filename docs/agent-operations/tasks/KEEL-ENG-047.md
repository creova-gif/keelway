# KEEL-ENG-047 — Agent Process Runner (`agents run`)

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-047-agent-runner` |

## Objective
Phase D remainder: real subprocess spawn + normalized event streaming for external agent CLIs, closing conformance criterion 2's launch portion.

## Implementation
- `core/agents/external/runner.py` — `run_agent_process()`: spawns adapter `LaunchSpec` (env-scrubbed via `scrub_env`), dual reader threads normalize stdout/stderr into `AgentRunEvent`s (caps: 5000 events, 64KB/line), timeout→kill, `AgentRunResult.scrubbed_summary()` DLP-scrubs output preview, `run_result_to_tape_span()` for flight-tape ingest. `AgentRunError` on spawn failure.
- `core/cli_harness.py` — `keelway harness agents run --agent <id> [--cwd] [--timeout] [--tape] [-- agent args]`; exit 0 only on clean exit.
- Policy boundary documented: runner launches + observes; enforcement stays with installed PreToolUse hooks → `agents intercept`.

## Acceptance Criteria
- [x] Fixture binaries spawn; stdout+stderr normalized into ordered events
- [x] Secret env vars absent from child env (verified `ANTHROPIC_API_KEY` dropped)
- [x] Timeout kills process (`timed_out=True`)
- [x] Output preview DLP-scrubbed (fake `sk-ant` token absent)
- [x] Missing binary → `AgentRunError`; CLI exit codes correct
- [x] `--tape` records run summary span with `tape_sha256`
- [x] Conformance criterion 2 extended: `test_c2b_process_spawn_event_stream` per adapter
- [x] 27 adapter tests + 15 conformance tests pass (42 total)

## Known Limits
- No interposition on agent tool calls — enforcement requires installed hooks.
- No PostToolUse/SessionStart events; vendor-native stdout formats not parsed into typed events (raw lines only).
- Live vendor CLI run not performed (would consume real credentials/credits).

## Next Recommended Action
Live-vendor validation run (gated, read-only prompt) OR PostToolUse/SessionStart hook events OR Cursor adapter.
