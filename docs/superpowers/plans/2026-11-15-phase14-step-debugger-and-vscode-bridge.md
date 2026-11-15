# Phase 14: Live Step-Through Debugger Breakpoints & Official VS Code / Cursor Extension Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Chrome-DevTools-style live conditional breakpoints, paused frame stepping (`step_over`, `step_into`, `continue`), DLP-guarded in-place variable mutation, 4D Routing CodeLens, and an official zero-dependency VS Code & Cursor Companion Extension (`extensions/vscode-keelway`) across FastAPI (`/v1/platform/debugger/*`), CLI (`keelway debug`), Python/TS/Go SDKs, `:7420/app`, and Website OpenAPI/Product-Facts (`280` paths, `22` features).

**Architecture:** `SQLiteStepDebuggerEngine` (`core/platform/step_debugger.py`) persists workspace-scoped `debugger_breakpoints` and `debugger_sessions` in SQLite WAL (`KEELWAY_PLATFORM_DB_PATH` fallback), enforcing pre-storage DLP secret rejection on `mutate_state` and SHA-256 frame receipts. `core/api/platform_debugger_routes.py` exposes 7 RBAC-guarded endpoints (`/v1/platform/debugger/*`). `extensions/vscode-keelway` communicates exclusively via its Node Extension Host (`Authorization: Bearer <token>`, no browser `Origin` header, preserving `core/security/origin.py`) and drives its CSP-locked Studio Webview over `postMessage`.

**Tech Stack:** Python 3.11–3.14, FastAPI, SQLite WAL, TypeScript 5 (`tsc --strict`), Node `node:test`, Go 1.23 (`go test -race`), React 19 + Vite + Vitest + `axe-core`, Next.js 15.

---

### Canonical Wire Contract (`/v1/platform/debugger/*`)

All 3 workstreams (`14A`, `14B`, `14C`) implement this exact JSON schema:

1. **`POST /v1/platform/debugger/breakpoints`** (`workflows:write`)
   - Request:
     ```json
     {
       "workspace_id": "default",
       "workflow_id": "WF-STUDIO-01",
       "node_id": "approve_payout",
       "file_path": "workflows/refund_agent.py",
       "line_number": 14,
       "condition_type": "cost_usd_gt",
       "threshold": 0.25,
       "enabled": true,
       "label": "Pause when step spend > $0.25"
     }
     ```
     Supported `condition_type`: `"always" | "cost_usd_gt" | "hybrid_score_lt" | "before_shell_tool" | "before_p10_gate" | "line_match"`.
   - Response (`200`):
     ```json
     {
       "breakpoint_id": "bp-...",
       "workspace_id": "default",
       "workflow_id": "WF-STUDIO-01",
       "node_id": "approve_payout",
       "file_path": "workflows/refund_agent.py",
       "line_number": 14,
       "condition_type": "cost_usd_gt",
       "threshold": 0.25,
       "enabled": true,
       "label": "Pause when step spend > $0.25",
       "created_at": "..."
     }
     ```
2. **`GET /v1/platform/debugger/breakpoints?workspace_id=default&workflow_id=...`** (`workspace:read`)
   - Response (`200`): `{"workspace_id": "default", "count": 1, "breakpoints": [...]}`
3. **`DELETE /v1/platform/debugger/breakpoints/{breakpoint_id}?workspace_id=default`** (`workflows:write`)
   - Response (`200`): `{"deleted": true, "breakpoint_id": "bp-...", "workspace_id": "default"}`
4. **`POST /v1/platform/debugger/sessions`** (`agents:execute`)
   - Request:
     ```json
     {
       "workspace_id": "default",
       "workflow_id": "WF-STUDIO-01",
       "steps": [
         {"node_id": "triage_claim", "agent_id": "intake-router", "tool_name": "kbrain_query", "cost_usd": 0.04, "hybrid_score": 0.88, "requires_p10": false, "line_number": 8, "variables": {"claim_id": "CLM-402", "refund_usd": 180}},
         {"node_id": "verify_ledger", "agent_id": "shell-auditor", "tool_name": "shell_exec", "cost_usd": 0.31, "hybrid_score": 0.42, "requires_p10": false, "line_number": 14, "variables": {"ledger_ok": true}},
         {"node_id": "approve_payout", "agent_id": "treasury-guard", "tool_name": "stripe_refund", "cost_usd": 0.09, "hybrid_score": 0.94, "requires_p10": true, "line_number": 21, "variables": {"approved": false}}
       ],
       "initial_state": {"tenant": "acme", "dry_run": true}
     }
     ```
     *(If `steps` is omitted or empty, seed the 3 canonical default steps above so 1-click session launch works out of the box.)*
   - Response (`200`):
     ```json
     {
       "session_id": "dbg-...",
       "workspace_id": "default",
       "workflow_id": "WF-STUDIO-01",
       "status": "PAUSED",
       "current_step_index": 1,
       "step_depth": 0,
       "total_steps": 3,
       "hit_breakpoint_id": "bp-...",
       "hit_reason": "cost_usd_gt (0.31 > 0.25)",
       "active_step": {...},
       "variables": {"tenant": "acme", "dry_run": true, "claim_id": "CLM-402", "refund_usd": 180, "ledger_ok": true},
       "call_stack": [{"depth": 0, "node_id": "verify_ledger", "agent_id": "shell-auditor", "line_number": 14}],
       "mutation_count": 0,
       "mutations": [],
       "frame_sha256": "64-hex-chars",
       "updated_at": "..."
     }
     ```
5. **`GET /v1/platform/debugger/sessions?workspace_id=default&limit=20`** (`workspace:read`)
   - Response (`200`): `{"workspace_id": "default", "count": 1, "sessions": [...]}`
6. **`POST /v1/platform/debugger/sessions/{session_id}/step`** (`agents:execute`)
   - Request:
     ```json
     {
       "workspace_id": "default",
       "action": "step_over",
       "state_patch": {"override_route": "keelway-core:7b"}
     }
     ```
     Supported `action`: `"step_over" | "step_into" | "continue" | "mutate_state"`.
     *(If `state_patch` contains secret material matching `sk-[A-Za-z0-9_-]{12,}`, `AKIA[0-9A-Z]{12,}`, `ghp_[A-Za-z0-9]{16,}`, or `-----BEGIN .*PRIVATE KEY-----`, reject with HTTP `422` `PolicyViolationError` and do NOT persist raw secrets!)*
   - Response (`200`): Updated session object (`status` in `"PAUSED" | "COMPLETED"`, recomputed `frame_sha256`).
7. **`GET /v1/platform/debugger/codelens?workspace_id=default&workflow_id=WF-STUDIO-01&file_path=workflows/refund_agent.py`** (`workspace:read`)
   - Response (`200`):
     ```json
     {
       "workspace_id": "default",
       "workflow_id": "WF-STUDIO-01",
       "file_path": "workflows/refund_agent.py",
       "bridge": {
         "protocol_version": "2026-11-15",
         "extension_id": "keelway.vscode-keelway",
         "loopback_Origin_policy": "extension-host-bearer-only",
         "vscode_attach_uri": "vscode://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01",
         "cursor_attach_uri": "cursor://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01"
       },
       "lenses": [
         {
           "symbol": "triage_claim",
           "line_start": 6,
           "model_checkpoint": "keelway-core:7b",
           "p50_ms": 142,
           "avg_cost_usd": 0.0,
           "provenance_4d": "Apache-2.0 · Local Metal · Self-Operated · Zero-Egress",
           "attached_breakpoints": 0
         }
       ]
     }
     ```

---

### Task 1 (Workstream 14A): SQLite WAL Step-Debugger Engine, FastAPI Router & Sovereign CLI

**Files:**
- Create: `core/platform/step_debugger.py`
- Create: `core/api/platform_debugger_routes.py`
- Create: `core/cli_debugger.py`
- Modify: `core/main.py`
- Modify: `core/cli_runtime.py`
- Modify: `tests/test_phase13_homepage_studio_and_release.py`
- Test: `tests/test_phase14_step_debugger_and_cli.py`

- [ ] **Step 1:** Write `tests/test_phase14_step_debugger_and_cli.py` testing all 6 breakpoint conditions, session pause/resume (`step_over`, `step_into`, `continue`), DLP secret rejection (`422`) on `mutate_state`, `Viewer` RBAC `403` enforcement, SQLite WAL persistence across engine re-instantiation, CodeLens + IDE bridge URIs, and `keelway debug` CLI `--json` commands.
- [ ] **Step 2:** Implement `SQLiteStepDebuggerEngine` in `core/platform/step_debugger.py` (`< 480` lines, top-of-file imports only, `PRAGMA journal_mode=WAL`, `KEELWAY_PLATFORM_DB_PATH` resolution matching `sandbox_blast_radius.py`).
- [ ] **Step 3:** Implement `core/api/platform_debugger_routes.py` (`< 280` lines) and mount `platform_debugger_router` in `core/main.py`.
- [ ] **Step 4:** Implement `core/cli_debugger.py` (`< 240` lines) and wire into `core/cli_runtime.py`; relax exact route/feature count assertions in `tests/test_phase13_homepage_studio_and_release.py` (`>= 21` features, `>= 273` paths).
- [ ] **Step 5:** Run `../kora-ai.nosync/.venv/bin/python -m pytest tests/test_phase14_step_debugger_and_cli.py tests/test_phase13_homepage_studio_and_release.py -v` and `uvx ruff check core/platform/step_debugger.py core/api/platform_debugger_routes.py core/cli_debugger.py tests/test_phase14_step_debugger_and_cli.py`.

---

### Task 2 (Workstream 14B): Official VS Code / Cursor Extension (`extensions/vscode-keelway`) & Tri-Language SDK Parity

**Files:**
- Create: `extensions/vscode-keelway/package.json`, `tsconfig.json`, `README.md`
- Create: `extensions/vscode-keelway/src/vscodeTypes.ts`, `src/bridgeClient.ts`, `src/codeLensProvider.ts`, `src/studioWebview.ts`, `src/extension.ts`
- Create: `extensions/vscode-keelway/test/extension.test.mjs`
- Create: `core/sdk/platform_debugger_client.py`
- Modify: `core/sdk/platform_runtime_client.py`
- Create: `sdk/typescript/src/platformDebugger.ts`, `sdk/typescript/tests/platform_phase14.test.mjs`
- Modify: `sdk/typescript/src/platform.ts`, `sdk/typescript/src/index.ts`, `sdk/typescript/package.json`
- Create: `sdk/go/platform_phase14.go`, `sdk/go/platform_phase14_test.go`

- [ ] **Step 1:** Scaffold `extensions/vscode-keelway/` with strict TypeScript (`tsconfig.json`), exhaustive `never` switch checks on Webview/command union types, nonce-locked `default-src 'none'` CSP in `studioWebview.ts`, zero-Origin Extension Host `KeelwayBridgeClient`, Python/TS AST symbol scanner in `codeLensProvider.ts`, and `test/extension.test.mjs`.
- [ ] **Step 2:** Compile & test `extensions/vscode-keelway` via `./website/node_modules/.bin/tsc -p extensions/vscode-keelway/tsconfig.json && npm --prefix extensions/vscode-keelway test`.
- [ ] **Step 3:** Add 7 sync + async methods to Python SDK (`core/sdk/platform_debugger_client.py` mixed into `core/sdk/platform_runtime_client.py`), TypeScript SDK (`sdk/typescript/src/platformDebugger.ts` + `platform_phase14.test.mjs`), and Go SDK (`sdk/go/platform_phase14.go` + `platform_phase14_test.go`).
- [ ] **Step 4:** Verify `./website/node_modules/.bin/tsc -p sdk/typescript/tsconfig.json && npm --prefix sdk/typescript test` and `(cd sdk/go && go vet ./... && go test ./... -race)`.

---

### Task 3 (Workstream 14C): `:7420/app` Live Step-Debugger, 4D CodeLens & IDE Bridge Panel

**Files:**
- Create: `dev-app/src/lib/platformDebuggerApi.ts`
- Create: `dev-app/src/components/platform/StepDebuggerAndBridgePanel.tsx`
- Modify: `dev-app/src/components/platform/AgentsWorkspaceView.tsx`
- Test: `dev-app/src/__tests__/phase14-step-debugger-bridge.test.tsx`

- [ ] **Step 1:** Implement `dev-app/src/lib/platformDebuggerApi.ts` (`< 280` lines) with live `/v1/platform/debugger/*` requests + deterministic offline fallback enforcing `Viewer` RBAC `403` and DLP secret `422` errors, using exhaustive `never` checks on step actions and condition types.
- [ ] **Step 2:** Implement `dev-app/src/components/platform/StepDebuggerAndBridgePanel.tsx` (`< 460` lines) with conditional breakpoint creator, `Start Debug Session`, `Step Over (F10)`, `Step Into (F11)`, `Continue (F5)`, DLP-guarded variable mutator, 4D CodeLens list, and `Attach in Cursor` / `Attach in VS Code` deep-links; mount in `AgentsWorkspaceView.tsx`.
- [ ] **Step 3:** Write `dev-app/src/__tests__/phase14-step-debugger-bridge.test.tsx` covering conditional pause, `F10`/`F11`/`F5` stepping, variable mutation + DLP secret block, `Viewer` RBAC block, IDE attach URIs, and `axe-core` WCAG 2.2 AA zero violations.
- [ ] **Step 4:** Run `(cd dev-app && npm run build && npm test)`.

---

### Task 4 (Lead Integration): Website OpenAPI/Facts Sync, Cross-Stack Parity Gate, Cold E2E & CI Ship

**Files:**
- Modify: `website/openapi.json`, `website/public/openapi.json` (`280` paths)
- Modify: `website/product-facts.json`, `website/public/product-facts.json` (`22` features)
- Modify: `website/src/app/docs/page.tsx`, `website/src/components/layout/CommandPalette.tsx`, `website/src/app/api/search-index/route.ts`
- Create: `tests/test_phase14_sdk_and_vscode_bridge.py`
- Modify: `scripts/verify_engineering_gates.sh`, `.github/workflows/ci.yml`

- [ ] **Step 1:** Export deterministic `openapi.json` (`280` paths) to `website/openapi.json` and `website/public/openapi.json`; add `step_through_debugger_and_ide_extension_bridge` (`22` total features) to `product-facts.json` & `public/product-facts.json` and update Docs + `Cmd+K` search index.
- [ ] **Step 2:** Write `tests/test_phase14_sdk_and_vscode_bridge.py` verifying ASGI Python SDK sync/async parity, TS/Go SDK parity, `extensions/vscode-keelway` manifest/CSP/test execution, and `280`-route + `22`-feature parity; wire Phase 14 checks into `scripts/verify_engineering_gates.sh` and `.github/workflows/ci.yml`.
- [ ] **Step 3:** Execute `./scripts/verify_engineering_gates.sh`, `(cd website && npm run typecheck && npm run build)`, `uvx ruff check .`, and cold headless Chromium E2E against `:7420/app` (`Agents` -> `#step-debugger-bridge-panel`) with visual screenshot inspection.
- [ ] **Step 4:** Commit, push to `origin main`, and verify `5/5` green GitHub Actions CI jobs + live Vercel deployment.
