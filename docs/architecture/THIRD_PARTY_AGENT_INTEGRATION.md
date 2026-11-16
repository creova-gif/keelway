# Third-Party Coding-Agent Integration — Architecture & Scope (KEEL-ENG-041)

> Status: **Scoped, not implemented.** Everything under "Verified existing" was exercised or inspected on `main` @ `2e73bb8` on 2026-11-16. Nothing below claims unverified compatibility.

## 1. Verified existing surface

| Capability | Where | Evidence |
|---|---|---|
| Keelway as **MCP server** (tool provider) | `core/orchestration/mcp.py` — JSON-RPC `2025-06-18` stdio server exposing `list_files`, `read_files`, `git_status`, `git_diff`, vault metadata, air-gap check with path guards + secret-name blocking | module + phase tests |
| External MCP server **registry** | `core/platform/mcp_registry.py` — workspace-scoped `sse`/`stdio` server records in SQLite WAL; SSRF-validated SSE endpoints; stdio command-injection defenses (`_validate_stdio_endpoint` rejects shell metacharacters/`..`); DLP redaction on results; SHA-256 call receipts | code inspection |
| MCP **builtin tool calls** | `PlatformMcpRegistry.call_tool()` — in-process dispatch with redaction + receipts | code inspection |
| **PreToolUse co-harness** for `claude_code`, `cursor`, `codex_cli` | `core/platform/agent_coharness.py` — hook manifest generation per host (`.claude/settings.local.json`, `.cursor/hooks.json`, `.codex/hooks.toml`), `intercept_tool_call` with DLP redaction, destructive-command denylist, credential-file read block, **single-use P-10 approval tickets** (PENDING→APPROVED→CONSUMED, command-SHA bound), hashed interception records | live: `cli.py harness intercept` → `ALLOW safe_readonly_or_test`; `rm -rf /` → `DENY destructive_system_command` |
| Worktree CI gate | `evaluate_worktree_ci_gate` — candidate arena (local vs frontier tiers), eval-score/cost comparison, unsafe-diff detection | phase18 tests |
| CLI/API/SDK surfaces | `keelway harness` + `keelway ci-gate` (`core/cli_harness.py`), `core/api/platform_harness_routes.py`, SDK clients | phase18 tests |

## 2. Verified gaps

1. **No agent-process launch/event streaming.** ~~Nothing spawns or wraps~~ Phase C (KEEL-ENG-043) added `core/agents/external/` — `AgentHostAdapter` contract, `ClaudeCodeAdapter`/`CodexCliAdapter` (PATH+`--version` detection, `scrub_env` launch specs, hook-payload normalization), and `evaluate_hook_payload` → `intercept_tool_call` with enforce/audit_only. Launch is spec-only; actual spawn, event streaming, and CLI/API wiring remain Phase D. The co-harness still governs only tool calls reported via hooks.
2. ~~**External MCP servers are catalog-only.**~~ **Resolved (KEEL-ENG-042):** `PlatformMcpRegistry.call_tool` now dispatches non-builtin tools to registered `stdio`/`sse` servers via `core/platform/mcp_client.py`. stdio reuses `core.orchestration.mcp_client.MCPClient` (env-scrubbed subprocess, fresh bounded session per call); sse uses streamable-HTTP JSON-RPC POST (JSON or `data:` SSE frames). `allowed_tools`/`*` enforced; ambiguous claims raise. Verified by `tests/test_mcp_remote_dispatch.py` (11 tests).
3. **No ACP support.** Agent Client Protocol (Zed/ACP) is absent; JSON-RPC MCP only.
4. **No per-agent contract tests.** Phase18 tests exercise the interception engine with synthetic payloads, not real agent CLIs.
5. **Hook coverage is partial.** Only `PreToolUse` on 3 hosts; no PostToolUse/SessionStart events, no `opencode`/`cline`/`devin`/`windsurf` hosts.

## 3. Proposed architecture — `core/agents/external/` (new package)

Keep third-party support **separate from `AutonomousAgentLoop`** per directive §3 — shared security/verification infra, independent execution.

```
AgentAdapter (protocol)
  detect()            -> installed? version? auth status?
  launch(spec)        -> subprocess spec: argv, env-scrubbed env, cwd=worktree
  policy_wrap(spec)   -> inject Keelway hook config + env (KEELWAY_* tokens)
  normalize_event(raw)-> canonical AgentEvent {tool_call, file_write, shell, approval_request}
  capabilities()      -> {hooks: [PreToolUse,...], mcp_client: bool, acp: bool}
```

- **Policy enforcement point**: reuse `SQLiteAgentCoharnessEngine.intercept_tool_call` as the single verdict authority — adapters translate native hook payloads into its `(agent_host, tool_name, command)` signature. No second policy engine.
- **Evidence**: every normalized event → flight tape (`core/platform/flight_tape.py`) + interception record (existing SHA-chained tables).
- **Sandbox**: agent subprocesses run under existing `SeatbeltBackend`/`BubblewrapBackend` where the host OS supports it; agents without hook support run in `audit_only` mode (record, don't block) until contract-tested.
- **MCP client**: extend `PlatformMcpRegistry.call_tool` to dispatch to registered `stdio`/`sse` servers via a real MCP client (spawn subprocess for stdio with the same `_validate_stdio_endpoint` rules; HTTP+SSE for sse). Builtins stay in-process.

## 4. Per-agent integration matrix (target, unverified)

| Agent | Mechanism | Policy hook point | Priority |
|---|---|---|---|
| Claude Code | `claude` CLI + `.claude/settings.local.json` hooks (exists) + MCP client config | PreToolUse → `intercept_tool_call` | P1 — hook format already generated |
| Codex CLI | `codex` CLI + `.codex/hooks.toml` (exists) | PreToolUse | P1 |
| Cursor | `cursor-agent` CLI + `.cursor/hooks.json` (exists) | PreToolUse | P2 — verify hook schema vs current Cursor version |
| OpenCode | `opencode` CLI; plugin/hook API (needs research) | plugin event | P2 |
| Cline | VS Code extension; no CLI hooks — MCP-only governance | MCP tool calls via registry | P3 |
| Devin / Windsurf | API/SDK surfaces; no local hooks | out of scope for local beta | P4 |
| ACP-compatible agents | ACP JSON-RPC session protocol | session/update events | P3 — after MCP client lands |

## 5. Phased plan

- **Phase A (this scope)**: doc + verification of existing harness (done).
- **Phase B (done, KEEL-ENG-042)**: MCP client for registered stdio/sse servers — `call_tool` now invokes them with DLP scrub + SHA-256 receipts identical to builtins.
- **Phase C (done, KEEL-ENG-043)**: `core/agents/external/` adapters + policy bridge, audit_only-first, 14 tests.
- **Phase D**: enforce mode for hook-capable agents; PostToolUse/SessionStart events; flight-tape wiring.
- **Phase E**: OpenCode/Cline/ACP; per-agent conformance suite in CI (`tests/test_external_agents.py` with fixture CLIs).

## 6. Acceptance criteria for "compatible" claims

An agent may be listed as supported only when, in CI: (1) adapter detects install, (2) launch produces a normalized event stream, (3) a destructive command is denied via `intercept_tool_call`, (4) a sensitive mutation produces a single-use P-10 ticket, (5) flight-tape records verify hash-chain integrity, (6) no secrets appear in captured events.

## 7. Risks

- Hook schemas drift per agent version → pin tested versions, `audit_only` fallback.
- Agents that bypass hooks (direct API use) can't be governed locally → document boundary honestly; cloud-side policy is Keelway Cloud scope.
- Subprocess spawning must reuse env-scrub (`core/security/env_scrub.py`) and never inherit provider keys unless BYOM-authorized.
