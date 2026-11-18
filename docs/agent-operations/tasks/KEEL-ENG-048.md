# KEEL-ENG-048 — Lifecycle Events + Cursor Adapter

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-048-events-cursor` |

## Objective
Phase D remainder: PostToolUse/SessionStart(/SessionEnd) observational events to the flight tape + Cursor agent adapter.

## Implementation
- `core/agents/external/events.py` — `record_agent_event()`: normalizes posttooluse/sessionstart/sessionend payloads into flight-tape spans (`VALID_AGENT_EVENTS`); posttooluse extracts tool context via adapter parser.
- `core/agents/external/hosts.py` — `CursorAgentAdapter` (`cursor-agent` binary, Claude-compatible payload assumption, audit_only until contract-tested).
- `core/cli_harness.py` — `agents event --agent <id> --event <name> --payload <json|@file|->`; `--agent` choices now dynamic from `EXTERNAL_AGENT_ADAPTERS`.
- `agent_coharness._build_hook_config_content` — manifests for all 3 adapter hosts now emit PreToolUse (`agents intercept`) + PostToolUse + SessionStart (`agents event`) commands; codex TOML gained matching sections.

## Live Evidence
- `agents detect`: `cursor-agent` 2026.04.28-e984b46 detected alongside claude 2.1.316 / codex 0.160.0.
- `agents event --event sessionstart` → tape recorded, `tape_sha256` returned.

## Acceptance Criteria
- [x] All 3 adapter hosts' manifests include all three hook events
- [x] Cursor adapter registered, detects, parses, evaluates through same policy path
- [x] Lifecycle events land in flight tape with hash integrity
- [x] 62 tests pass (adapters + conformance + phase18)

## Known Limits
- Cursor payload shape assumed Claude-compatible — audit_only until pinned-version contract test.
- `agents event` records evidence only; no policy verdict on PostToolUse (by design).
- Real vendor hook delivery still gated on quota reset.

## Next Recommended Action
Release-readiness assessment (UI/UX, journeys, onboarding) — separate workstream; or live hook-delivery validation post Nov 20.
