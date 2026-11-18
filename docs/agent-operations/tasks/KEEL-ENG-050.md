# KEEL-ENG-050 — OpenCode Adapter (Plugin-Based Hook Delivery)

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-17 |
| **Branch** | `fix/KEEL-ENG-050-opencode-adapter` |

## Objective
Phase E continuation: add OpenCode (`opencode` CLI) as a fourth external-agent
adapter. OpenCode has no stdin-JSON shell-hook protocol — enforcement is
delivered as a generated TypeScript plugin under `.opencode/plugins/`.

## Implementation
- `core/agents/external/hosts.py` — `OpenCodeAdapter` (`opencode` binary,
  `tool.execute.before` hook event, canonical payload
  `{tool, tool_input|input|args, session_id, call_id}`).
- `core/platform/agent_coharness.py` — `VALID_AGENT_HOSTS` +
  `_HOOK_TARGET_PATHS["opencode"] = ".opencode/plugins/keelway-guard.ts"`;
  `_build_opencode_plugin_content()` emits the plugin source: `tool.execute.before`
  calls `keelway harness agents intercept` via `Bun.spawnSync` and throws on
  DENY/HOLD (fail-closed on CLI errors/unparseable output); `tool.execute.after`
  records PostToolUse evidence best-effort. Exit codes 0/1/2 mapped to
  allow/deny/hold.
- `core/cli_harness.py` — `harness hooks --agent` accepts `opencode`;
  `agents setup --agent opencode` reports `tool.execute.*` hook events.
- `core/agents/external/__init__.py` — exports `OpenCodeAdapter`.

## Live Evidence
- `agents intercept --agent opencode` payload `{"tool":"bash","tool_input":{"command":"git push origin main"}}`
  → `decision: hold`, `HOLD_TICKET` + `ptkt-*`, exit 2 (P-10 path verified).
- `render_hook_manifest(agent_host="opencode")` → `.ts` plugin containing
  `tool.execute.before`/`after` and the intercept argv.
- Conformance suite auto-extended: all 6 criteria now run for 4 adapters
  (69 tests across adapters/conformance/phase18 green).

## Acceptance Criteria
- [x] Detection via `opencode --version` (5s timeout, never raises)
- [x] Env-scrubbed launch spec
- [x] Payload normalization into `intercept_tool_call` verdict authority
- [x] Hook delivery mechanism honestly modeled (TS plugin, not JSON config)
- [x] `agents setup --agent opencode` installs the plugin file
- [x] Tests: manifest assertions + CLI setup test + conformance parametrization

## Known Limits
- **Cline deferred**: VS Code extension, no verified CLI hook surface —
  governance path is MCP-only (registry already exists). Documented in
  THIRD_PARTY_AGENT_INTEGRATION.md.
- Plugin targets OpenCode 1.x plugin API (`tool.execute.before`/`after`);
  unverified against a live `opencode` install (binary not present on this
  host). `opencode` v2 API differs — plugin may need regeneration per major.
- P-10 HOLD surfaces as a thrown error with the ticket ID (OpenCode 1.x
  `tool.execute.before` cannot return "ask"); `permission.ask` hook could
  map HOLD→native prompt in a follow-up.
- Plugin shells out per tool call — process-spawn overhead per call;
  acceptable for v1, batch/HTTP transport is future work.
- Real vendor delivery (plugin actually loaded by opencode) unverified.

## Next Recommended Action
Cline decision (MCP-only governance doc vs. CLI contract research); ACP
adapter; live opencode install + plugin load verification when binary available.
