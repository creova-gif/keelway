# KEEL-ENG-044 — Harness CLI: `agents detect|intercept`

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS / CLI` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-044-harness-agents` |

## Objective
Phase D (partial) of `THIRD_PARTY_AGENT_INTEGRATION.md`: expose the KEEL-ENG-043 adapters through the sovereign CLI so host hook commands and operators can detect agents and evaluate native hook payloads.

## Implementation
- `core/cli_harness.py`: new `keelway harness agents` subcommand group —
  - `detect`: probes all adapters (PATH + `--version`), prints installations + capability declarations.
  - `intercept --agent <id> --payload <json|'@file'|'-'> --mode enforce|audit_only`: reads a native hook payload, normalizes via the adapter, evaluates through `evaluate_hook_payload` → `intercept_tool_call`; exit codes 0=allow, 1=deny, 2=hold (mirrors `harness intercept`).

## Live Evidence
- `keelway harness agents detect --json` on this host: `claude` 2.1.316 and `codex-cli` 0.160.0 both detected with real versions.
- `agents intercept` with `rm -rf /` payload → `[DENY] ... destructive_system_command`, exit 1.

## Acceptance Criteria
- [x] detect lists all adapters with honest installed/version data
- [x] intercept accepts inline JSON, `@file`, and stdin `-`
- [x] enforce: deny→1, hold→2, allow→0; audit_only→0 with verdict recorded
- [x] Interception records land in the same hash-chained `harness_interceptions` table
- [x] 5 new CLI tests; 19 adapter tests + phase18 suites pass (27 total this run)

## Known Limits
- No agent process spawn/event streaming; no PostToolUse/SessionStart; no OTLP flight-tape span bridge (interception records are the current hash-chained evidence).
- Hook manifest `render_hook_manifest` still targets the 3 built-in hosts; wiring `agents intercept` into generated hook commands is a follow-up.

## Next Recommended Action
Phase D remainder: hook-manifest integration (`keelway harness hooks` emits `agents intercept` commands), flight-tape span bridge, then Phase E conformance suite before any "compatible" claim.
