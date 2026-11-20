# KEEL-APP-054 — Tri-SDK Parity: `kstack_execute` + Agent Manifest Registry

- **STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-052-sdk-kstack-registry-parity`
- **SCOPE**: `core/sdk/client.py`, `sdk/typescript/src|dist`, `sdk/go`, `tests/test_phase21_kstack_registry_sdk_parity.py`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] All three SDKs expose the two new `/v1` surfaces shipped in KEEL-APP-046/048/049 — the claimed tri-language SDK parity is now true for KStack execute and the agent manifest registry.
- [x] `kstack_execute` / `kstack.execute` / `KStack.Execute` → `POST /v1/kstack/execute` with `{name, inputs}` body; unwraps the real `{"proof": {...}}` envelope and returns the `SkillExecutionProof` (verified against the live ASGI endpoint — the mock-first implementation incorrectly assumed an unwrapped proof until live verification caught it).
- [x] `list_agent_registry` / `agents.listRegistry` / `Agents.ListRegistry` → `GET /v1/agents/registry` with `enabled_only` query support.
- [x] `toggle_agent_manifest` / `agents.toggleManifest` / `Agents.ToggleManifest` → `POST /v1/agents/registry/{name}/{version}/toggle` with `{enabled}` body (`APPROVE_TIER3`-gated server-side; SDK is transport-agnostic).
- [x] Python sync/async signature parity enforced by test; `inputs` defaults to `{}` on the wire.
- [x] TS dist rebuilt (`tsc`) — `dist/client.d.ts` + `dist/types.d.ts` carry the new symbols.
- [x] Go `KStackService` + `AgentsService` registered on `Client` alongside `Responses/Routing/Platform/Cluster`.

## FILES MODIFIED

- `core/sdk/client.py` — `kstack_execute`, `list_agent_registry`, `toggle_agent_manifest` on both `AsyncKeelwayClient` and `KeelwayClient`.
- `sdk/typescript/src/types.ts` — `KStackExecuteRequest`, `SkillExecutionProof`, `AgentRegistryRecord`, `AgentRegistryListResponse`, `AgentRegistryToggleResponse`.
- `sdk/typescript/src/client.ts` — `kstack` + `agents` client namespaces; `sdk/typescript/dist/` rebuilt.
- `sdk/typescript/tests/platform_phase21.test.mjs` + `package.json` test script entry — 3 tests against a Node mock server.
- `sdk/go/kstack.go`, `sdk/go/agents_registry.go`, `sdk/go/client.go`, `sdk/go/kstack_agents_test.go` — `KStackService`/`AgentsService` + httptest coverage.
- `tests/test_phase21_kstack_registry_sdk_parity.py` — phase-convention parity suite.

## TESTS & EVIDENCE

- `pytest tests/test_phase21_kstack_registry_sdk_parity.py` — 3 passed (mock-transport sync, live-ASGI async incl. real `golden-eval` sealed proof + 404 path, TS/Go source + dist symbol checks).
- `pytest tests/test_kstack_execute.py` — 24 passed (no regression).
- `pytest tests/test_phase10_sdk_parity.py` — 2 passed, 1 pre-existing env skip.
- `node --test tests/platform_phase21.test.mjs` — 3/3 pass; `tsc --noEmit` clean; `npm run build` regenerates committed dist.
- `go build ./... && go test -run TestKStack` — pass.

## HONEST LIMITS

- The SDK surfaces are read/write transports — RBAC remains server-enforced (`EXECUTE_AGENT` for execute/register, `APPROVE_TIER3` for toggle); an underprivileged token still gets the server's 403.
- `compare_to`/drift inputs flow through the generic `inputs` map — SDKs add no eval-specific typed params beyond what the API accepts.
- Process skills still return the server's 501/404; the SDK surfaces the `KeelwayError`, it does not mask it.
