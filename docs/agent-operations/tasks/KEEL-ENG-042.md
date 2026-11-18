# KEEL-ENG-042 — MCP Client: Remote stdio/sse Tool Dispatch

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / MCP` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-042-mcp-client` |

## Objective
Phase B of `THIRD_PARTY_AGENT_INTEGRATION.md`: make registered external MCP servers (`platform_mcp_servers`, transports `stdio`/`sse`) actually invocable through `PlatformMcpRegistry.call_tool`.

## Implementation
- `core/platform/mcp_client.py` (new): `call_remote_tool(transport, endpoint, tool, args)` — stdio delegates to existing `core.orchestration.mcp_client.MCPClient` (env-scrubbed subprocess, fresh bounded session per call); sse does streamable-HTTP JSON-RPC POST parsing JSON or `text/event-stream` `data:` frames. `McpClientError` on all failure paths.
- `core/platform/mcp_registry.py`: `call_tool` resolves non-builtin tool names via `_resolve_remote_server` (exact or `*` in `allowed_tools_json`; ambiguity → `ValueError`); remote results flow through identical DLP scrub + SHA-256 receipt path as builtins.

## Acceptance Criteria
- [x] stdio roundtrip via fixture JSON-RPC server (initialize → tools/call) returns scrubbed result + receipt
- [x] Secret redaction applies to remote results (`redacted: true`)
- [x] `allowed_tools` enforced; unlisted tool → `KeyError`; `*` wildcard works
- [x] Ambiguous multi-server claim → `ValueError`
- [x] Spawn failure → `McpToolArgumentError` (fail closed)
- [x] SSE JSON + SSE-framed responses, HTTP 503 and JSON-RPC error paths
- [x] No regression: phase7 MCP/golden-evals, mcp_client_and_plugins, mcp_bridge, mcp_stdio suites pass

## Tests
- `tests/test_mcp_remote_dispatch.py`: 11 passed
- `tests/test_phase7_mcp_and_golden_evals.py test_mcp_client_and_plugins.py test_mcp_bridge.py test_mcp_stdio.py`: 24 passed

## Known Limits
- stdio = fresh process per call (handshake overhead); persistent sessions are a future optimization.
- sse = single POST per call (streamable-HTTP); legacy GET-stream+POST-messages SSE session protocol not implemented.
- `tools/list` for remote servers not surfaced in `list_tools` (allowed_tools is the declared surface).

## Next Recommended Action
Phase C: `AgentAdapter` interface + claude_code/codex_cli adapters (audit_only first).
