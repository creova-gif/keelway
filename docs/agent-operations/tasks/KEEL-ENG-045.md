# KEEL-ENG-045 — Hook Manifest Wiring to `agents intercept`

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS / CLI` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-045-hook-wiring` |

## Objective
Phase D continuation: make generated PreToolUse hook configs for adapter hosts (`claude_code`, `codex_cli`) invoke the real native-payload path (`harness agents intercept --payload -`) instead of the synthetic `--command` path, and emit Claude Code–compatible `permissionDecision` JSON.

## Implementation
- `core/platform/agent_coharness.py::_build_hook_config_content`: claude_code/codex_cli hook commands now read stdin JSON via `agents intercept`; claude_code uses `--format claude-code`, codex_cli `--format json`. Cursor unchanged (no adapter yet).
- `core/cli_harness.py`: `agents intercept --format claude-code` maps decision→`permissionDecision` (allow/deny/ask) in `hookSpecificOutput` JSON, exit 0 (host consumes JSON, not exit code).

## Live Evidence
- Rendered `.claude/settings.local.json` content verified: command = `keelway harness agents intercept --agent claude_code --payload - --mode enforce --workspace demo --format claude-code`.
- Piped a real-shaped Claude Code PreToolUse payload (`git push origin main`) → `{"permissionDecision": "ask"}` (P-10 hold), exit 0.

## Acceptance Criteria
- [x] Hook manifests for adapter hosts emit stdin-consuming commands
- [x] claude-code output format is spec-shaped and consumed correctly
- [x] Phase18 hook tests updated for per-host command expectations
- [x] 28 tests pass (adapters + phase18 coharness/sdk)

## Known Limits
- Cursor still emits legacy `harness intercept` command (no CursorAdapter; hook payload shape unverified).
- Codex `hooks.toml` consumption format remains our generated convention — untested against real codex CLI.
- No PostToolUse/SessionStart, flight-tape span bridge, or process spawning.

## Next Recommended Action
Phase E prep: pin tested CLI versions (`claude` 2.1.316, `codex` 0.160.0 observed) and build the 6-point conformance suite from the scope doc before any "compatible" claim; or Phase D remainder (flight-tape bridge, Cursor adapter).
