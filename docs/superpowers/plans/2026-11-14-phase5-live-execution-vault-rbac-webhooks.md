# Phase 5 Live Execution, Encrypted Vault, Multi-Workspace RBAC, Signed Webhooks & Tri-SDK Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver real-time SSE agent/DAG execution with `P-10` human holds, an `AES-256-GCM` SQLite WAL secret vault, multi-workspace 5-role RBAC, `HMAC-SHA256` signed webhooks, Dev Tool UI integration across all 10 views, and full Python/TypeScript/Go SDK parity.

**Architecture:** Four zero-overlap workstreams build modular backend runtime components (`vault.py`, `rbac_webhooks.py`, `execution_stream.py`, `platform_runtime_routes.py`), official Python/TS/Go SDK runtime methods, and Dev App panels (`VaultAndWebhooksPanel.tsx`, `LiveExecutionDrawer.tsx`, `PlatformWorkspaceBar.tsx`), followed by lead router mounting, OpenAPI 3.1 export, and full 8-gate verification.

**Tech Stack:** Python 3.11+ (`FastAPI`, `Pydantic v2`, `sqlite3` WAL, `cryptography` `AESGCM`/`HKDF`), TypeScript 5 (`@keelway/sdk` zero-dep `fetch`), Go 1.22+ (`keelway-go` stdlib `net/http`), React 19 + Vite + Vitest + `axe-core`.

**Spec:** `docs/superpowers/specs/2026-11-14-phase5-live-execution-vault-rbac-webhooks-design.md`

## Global Constraints
- Every created or modified source and test file MUST remain strictly `<750` lines.
- `LocalSecretVault` MUST encrypt secret values with `AES-256-GCM` (random 12-byte nonce + `HKDF-SHA256`) and NEVER expose raw plaintext in SQLite columns or HTTP list/create/rotate responses.
- `SignedWebhookBus` MUST block SSRF destinations (`169.254.169.254`, `metadata.google.internal`, `100.100.100.200`, `file://`, `ftp://`, `gopher://`) and sign canonical payloads with `X-Keelway-Signature-256: sha256=<hex>`.
- `P-10` human-only checkpoints MUST pause execution (`awaiting_p10_approval`) until an explicit human `approve`/`deny` action is submitted (never via `⌘K` Command Palette).
- All Dev App screens MUST pass `axe-core` WCAG 2.2 AA (`0` violations) and maintain strict local-first CSP (`'self'`, zero external CDNs).

## Review Focus
1. **Plaintext secret leakage:** Storing `sk-live-secret-12345` in `POST /v1/platform/vault/secrets` must store non-plaintext `AES-256-GCM` ciphertext in SQLite and return only masked `sk-l****2345` + `fingerprint_sha256` over `POST`/`GET`; tampering with SQLite ciphertext bytes must fail authentication cleanly (`InvalidTag`).
2. **SSRF & replay attacks on webhooks:** Registering `http://169.254.169.254/latest/meta-data` must fail with HTTP `400`; `POST /v1/platform/webhooks/verify` must reject altered payload bytes or expired timestamps (`>300s`).
3. **RBAC privilege escalation:** `viewer` role must be denied (`allowed=False`, HTTP `403` when enforced) for `secrets:write`, `webhooks:manage`, and `p10:approve`, while `owner` and `admin` are permitted.
4. **Chunk-split SSE parsing across SDKs:** SSE streams split mid-line across TCP chunks must decode cleanly in Python, TypeScript, Go, and `dev-app` without dropping `p10.held` or `run.completed` events.
5. **Offline/Air-Gap Dev App resilience:** When network/daemon requests fail or run unmocked in Vitest, workspace switching, RBAC badges, masked vault entries, webhook test receipts, and live execution streams degrade gracefully with `0` uncaught rejections and `0` `axe-core` violations.

---

### Task 1 (Workstream 5A): Backend Vault, RBAC, Webhooks, SSE Execution & FastAPI Router

**Files:**
- Create: `core/platform/vault.py` (`<340` lines)
- Create: `core/platform/rbac_webhooks.py` (`<420` lines)
- Create: `core/platform/execution_stream.py` (`<360` lines)
- Create: `core/api/platform_runtime_routes.py` (`<520` lines)
- Create: `tests/test_phase5_runtime_vault_rbac_webhooks.py` (`<600` lines)

**Interfaces:**
- Produces FastAPI `router` (`prefix="/v1/platform"`) with:
  - `GET /v1/platform/workspaces`, `POST /v1/platform/workspaces`
  - `GET /v1/platform/rbac/members`, `POST /v1/platform/rbac/members`, `POST /v1/platform/rbac/check`
  - `GET /v1/platform/vault/secrets`, `POST /v1/platform/vault/secrets`, `POST /v1/platform/vault/secrets/{name}/rotate`, `DELETE /v1/platform/vault/secrets/{name}`
  - `GET /v1/platform/webhooks`, `POST /v1/platform/webhooks`, `DELETE /v1/platform/webhooks/{webhook_id}`, `POST /v1/platform/webhooks/{webhook_id}/test`, `POST /v1/platform/webhooks/verify`
  - `POST /v1/platform/execution/runs`, `GET /v1/platform/execution/runs/{run_id}/events`, `POST /v1/platform/execution/runs/{run_id}/p10`

- [ ] **Step 1:** Write failing unit & FastAPI integration tests in `tests/test_phase5_runtime_vault_rbac_webhooks.py` covering all 5 Review Focus items.
- [ ] **Step 2:** Implement `LocalSecretVault`, `WorkspaceRbacController`, `SignedWebhookBus`, `LiveExecutionStreamer`, and `core/api/platform_runtime_routes.py`.
- [ ] **Step 3:** Run `../kora-ai.nosync/.venv/bin/pytest tests/test_phase5_runtime_vault_rbac_webhooks.py -v` and verify 100% pass.

---

### Task 2 (Workstream 5B): Official Python SDK Phase 4 + Phase 5 Parity

**Files:**
- Create: `core/sdk/platform_runtime_client.py` (`<380` lines)
- Modify: `core/sdk/platform_client.py` (`<520` lines)
- Create: `tests/test_sdk_phase5_parity.py` (`<450` lines)

**Interfaces:**
- Extends `SyncPlatformClient` & `AsyncPlatformClient` (`client.platform`) with:
  - `list_docs`, `create_doc`, `update_doc`, `update_issue`, `list_feedback`, `create_feedback`, `scan_workspace_security`
  - `list_workspaces`, `create_workspace`, `list_rbac_members`, `upsert_rbac_member`, `check_rbac`
  - `list_secrets`, `put_secret`, `rotate_secret`, `delete_secret`
  - `list_webhooks`, `create_webhook`, `delete_webhook`, `test_webhook`, `verify_webhook`
  - `start_execution_run`, `stream_execution_events`, `resolve_execution_p10`

- [ ] **Step 1:** Write `tests/test_sdk_phase5_parity.py` with `httpx.MockTransport` testing sync + async parity and chunked SSE event streaming.
- [ ] **Step 2:** Implement `core/sdk/platform_runtime_client.py` mixin/delegate and wire into `core/sdk/platform_client.py`.
- [ ] **Step 3:** Run `../kora-ai.nosync/.venv/bin/pytest tests/test_sdk_platform.py tests/test_sdk_phase5_parity.py -v`.

---

### Task 3 (Workstream 5C): Official TypeScript (`@keelway/sdk`) & Go (`keelway-go`) SDK Parity

**Files:**
- Create: `sdk/typescript/src/platform-runtime.ts` (`<360` lines)
- Modify: `sdk/typescript/src/platform-types.ts`, `sdk/typescript/src/platform.ts`, `sdk/typescript/src/index.ts`
- Create: `sdk/typescript/test/platform-runtime.test.mjs` (`<360` lines)
- Create: `sdk/go/platform_runtime.go` (`<380` lines)
- Create: `sdk/go/platform_runtime_test.go` (`<380` lines)

**Interfaces:**
- TypeScript `client.platform` methods: `listDocs`, `createDoc`, `updateDoc`, `updateIssue`, `listFeedback`, `createFeedback`, `scanWorkspaceSecurity`, `listWorkspaces`, `createWorkspace`, `listRbacMembers`, `upsertRbacMember`, `checkRbac`, `listSecrets`, `putSecret`, `rotateSecret`, `deleteSecret`, `listWebhooks`, `createWebhook`, `deleteWebhook`, `testWebhook`, `verifyWebhook`, `startExecutionRun`, `streamExecutionEvents`, `resolveExecutionP10`.
- Go `client.Platform` methods: `ListDocs`, `CreateDoc`, `UpdateDoc`, `UpdateIssue`, `ListFeedback`, `CreateFeedback`, `ScanWorkspaceSecurity`, `ListWorkspaces`, `CreateWorkspace`, `ListRBACMembers`, `UpsertRBACMember`, `CheckRBAC`, `ListSecrets`, `PutSecret`, `RotateSecret`, `DeleteSecret`, `ListWebhooks`, `CreateWebhook`, `DeleteWebhook`, `TestWebhook`, `VerifyWebhook`, `StartExecutionRun`, `StreamExecutionEvents`, `ResolveExecutionP10`.

- [ ] **Step 1:** Write failing Node test `sdk/typescript/test/platform-runtime.test.mjs` and Go test `sdk/go/platform_runtime_test.go`.
- [ ] **Step 2:** Implement zero-dependency TypeScript & Go methods + chunk-safe SSE line readers.
- [ ] **Step 3:** Run `(cd sdk/typescript && npm run build && npm test)` and `(cd sdk/go && /usr/local/go/bin/go test ./...)`.

---

### Task 4 (Workstream 5D): Dev Tool UI — Multi-Workspace RBAC Bar, Vault & Webhooks Panel, and Live Execution Stream Console

**Files:**
- Create: `dev-app/src/lib/platformRuntimeApi.ts` (`<340` lines)
- Create: `dev-app/src/components/platform/VaultAndWebhooksPanel.tsx` (`<390` lines)
- Create: `dev-app/src/components/platform/LiveExecutionDrawer.tsx` (`<360` lines)
- Modify: `dev-app/src/components/platform/PlatformWorkspaceBar.tsx` (`<260` lines)
- Modify: `dev-app/src/components/platform/SecurityWorkspaceView.tsx` (`<420` lines)
- Modify: `dev-app/src/components/platform/AgentsWorkspaceView.tsx` (`<490` lines)
- Modify: `dev-app/src/components/platform/AutomationAndOpsViews.tsx` (`<610` lines)

- [ ] **Step 1:** Implement `platformRuntimeApi.ts` (`/v1/platform/*` guard + offline-resilient SSE stream simulator).
- [ ] **Step 2:** Implement `VaultAndWebhooksPanel.tsx` (masked `AES-256-GCM` secret manager + `HMAC-SHA256` webhook builder with SSRF validation) and mount inside `SecurityWorkspaceView.tsx`.
- [ ] **Step 3:** Implement `LiveExecutionDrawer.tsx` (live SSE event stream + `P-10` human `Approve & Resume` / `Deny` controls) and mount inside `AgentsWorkspaceView.tsx` & `AutomationWorkspaceView`.
- [ ] **Step 4:** Upgrade `PlatformWorkspaceBar.tsx` with Multi-Workspace Switcher (`default`, `hipaa-intake`, `+ New Workspace`) and Active RBAC Role selector (`Owner`, `Admin`, `Builder`, `Operator`, `Viewer`).
- [ ] **Step 5:** Run `(cd dev-app && npm run typecheck && npm test)` -> `0` TS errors, all existing `55/55` tests green.

---

### Task 5 (Lead Integration): Router Mount, State Wiring, Phase 5 E2E Tests, OpenAPI Sync & Production Push

**Files:**
- Modify: `core/main.py`, `dev-app/src/components/platform/useUnifiedPlatformState.tsx`, `dev-app/src/App.tsx`
- Create: `dev-app/src/__tests__/phase5-runtime-vault-rbac.test.tsx` (`<420` lines)
- Modify: `website/openapi.json`, `website/public/openapi.json`, `website/product-facts.json`, `website/public/product-facts.json`
- Create/Modify: `docs/agent-operations/tasks/KEEL-RUNTIME-012.md`, `docs/agent-operations/ACTIVE_TASKS.md`

- [ ] **Step 1:** Mount `platform_runtime_router` in `core/main.py` and wire active workspace & RBAC role props through `useUnifiedPlatformState.tsx` and `App.tsx`.
- [ ] **Step 2:** Write `dev-app/src/__tests__/phase5-runtime-vault-rbac.test.tsx` (`axe-core` + workspace switching + RBAC role checks + Vault masked secret lifecycle + Webhook SSRF/ping + Live SSE execution `P-10` hold/resume) and build `core/dev_app_dist`.
- [ ] **Step 3:** Export OpenAPI 3.1 schema, sync `product-facts.json` and `ACTIVE_TASKS.md`, run `./scripts/verify_engineering_gates.sh` (`[1/8]`–`[8/8]`), `(cd sdk/go && /usr/local/go/bin/go test ./...)`, and `(cd website && npm run typecheck && npm run build)`.
- [ ] **Step 4:** Commit, push to `origin/main`, and smoke-test live Vercel production routes.
