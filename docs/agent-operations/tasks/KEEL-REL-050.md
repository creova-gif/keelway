# KEEL-REL-050 — `agents setup` One-Command Integration

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / AGENTS / DEVEX` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-REL-050-agents-setup` |

## Objective
Release gap #3: replace manual `hooks --install-dir` + detection with a single `keelway harness agents setup <host>` command.

## Implementation
- `agents setup --agent <id> --mode enforce|audit_only --install-dir <dir>`: detects the CLI on PATH (fails closed with `agent_not_installed` if absent), renders the hook manifest, installs the host config file (`.claude/settings.local.json`, `.codex/hooks.toml`, `.cursor/hooks.json`), reports `installed_path` + `config_sha256` + hook events covered.

## Evidence
- Live: `agents setup --agent claude_code --install-dir /tmp/keel-setup-test` → detected claude 2.1.316, wrote settings.local.json containing PreToolUse+PostToolUse+SessionStart.
- 2 new tests (installed path writes all 3 hook events; missing agent → exit 1 `agent_not_installed`). 34 adapter tests pass.

## Next Recommended Action
KEEL-REL-051 (`keelway tape verify`).
