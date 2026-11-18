# Phase 5: Live Streaming Execution, Encrypted Secret Vault, Multi-Workspace RBAC, Signed Webhooks & Tri-SDK Parity — Design Spec

- **Date:** 2026-11-14
- **Task ID:** `KEEL-RUNTIME-012`
- **Status:** Approved by user via Phase 5 selection

## 1. Intent & Why
With all 10 local Dev Tool workspace views live at `:7420/app` (`6fb8375`), Phase 5 upgrades Keelway from request/response workspace persistence to a real-time, multi-workspace, enterprise-governed runtime:
1. Operators dispatching agents or KFlow DAGs in the Dev Tool see live Server-Sent Event (SSE) execution traces and can approve or deny held `P-10` checkpoints mid-stream.
2. BYOM API credentials, plugin tokens, and webhook keys are stored in an authenticated `AES-256-GCM` SQLite WAL vault (`LocalSecretVault`) that never returns plaintext secrets over HTTP or logs.
3. Multi-workspace switching and a 5-role RBAC matrix (`owner`, `admin`, `builder`, `operator`, `viewer`) govern sensitive actions across the platform.
4. External plugins and enterprise integrations receive `HMAC-SHA256` signed webhook envelopes (`SignedWebhookBus`) with SSRF protection.
5. Official Python (`core.sdk`), TypeScript (`@keelway/sdk`), and Go (`keelway-go`) SDKs achieve 100% parity across all Phase 4 + Phase 5 `/v1/platform/*` endpoints.

## 2. Goals, Non-Goals & Anti-Goals
- **Goals:**
  - `AES-256-GCM` secret encryption at rest in SQLite WAL (`platform_secrets`), masked `****` previews, key rotation, and tamper detection.
  - Multi-workspace CRUD + 5-role RBAC enforcement (`owner`, `admin`, `builder`, `operator`, `viewer`) persisted in SQLite WAL.
  - `HMAC-SHA256` signed webhooks (`X-Keelway-Signature-256`, `X-Keelway-Timestamp`, `X-Keelway-Event-Id`) blocking SSRF targets (`169.254.169.254`, `metadata.google.internal`, `file://`).
  - Live SSE execution stream (`/v1/platform/execution/runs` & `/events`) with mid-run `P-10` human-only hold and resume (`/p10`).
  - Full Dev Tool UI integration (`PlatformWorkspaceBar` workspace/RBAC switcher, `VaultAndWebhooksPanel` in `Security`, `LiveExecutionDrawer` in `Agents` & `Automation`) with `0` `axe-core` WCAG 2.2 AA violations.
  - Full Python, zero-dependency TypeScript, and zero-dependency Go SDK parity.
- **Non-Goals:**
  - External cloud KMS dependencies (vault runs 100% offline/local-first using `cryptography` `AESGCM` + `HKDF`).
  - Adding any `/playground` or private engineering details to the public marketing website (`website/`).
- **Anti-Goals:**
  - Returning raw secret plaintext in any `GET`/`POST` list or metadata response.
  - Allowing `P-10` approvals to be triggered via `⌘K` Command Palette or keyboard auto-focus steal.
  - Any source or test file exceeding `750` lines.

## 3. Approaches Considered
1. **Selected — Modular Runtime Subsystem + Dedicated FastAPI Router + Tri-SDK Extensions (4 Parallel Workstreams):**
   - Separate focused modules (`vault.py`, `rbac_webhooks.py`, `execution_stream.py`, `platform_runtime_routes.py`, `platform_runtime_client.py`, `platform-runtime.ts`, `platform_runtime.go`, `VaultAndWebhooksPanel.tsx`, `LiveExecutionDrawer.tsx`). Keeps every file `<600` lines and enables zero-conflict parallel execution.
2. **Rejected — Monolithic Expansion of `workspace_hub.py` and `platform_routes.py`:**
   - Both files are already ~695 lines; adding Phase 5 directly into them would breach the 750-line modularity limit.
3. **Rejected — WebSocket-Only Execution Streaming:**
   - Standard HTTP SSE (`text/event-stream`) works natively across Python `httpx`, browser `fetch` `ReadableStream`, TypeScript `fetch`, and Go `net/http` without extra dependencies.

## 4. Architecture & API Contract (`/v1/platform/*`)
- **Workspaces & RBAC:**
  - `GET /v1/platform/workspaces` -> `{"workspaces": [...], "total": int}`
  - `POST /v1/platform/workspaces` -> creates workspace (`id`, `name`, `branch`, `isolation_mode`)
  - `GET /v1/platform/rbac/members?workspace_id=...` -> `{"members": [...], "roles": [...]}`
  - `POST /v1/platform/rbac/members` -> assigns `actor_id` to `role` (`owner`|`admin`|`builder`|`operator`|`viewer`)
  - `POST /v1/platform/rbac/check` -> evaluates `(workspace_id, actor_id, role, permission)` -> `{"allowed": bool, "role": str, "permission": str, "reason": str}`
- **Encrypted Secret Vault (`AES-256-GCM`):**
  - `GET /v1/platform/vault/secrets?workspace_id=...` -> masked metadata list (`name`, `namespace`, `masked_preview`, `fingerprint_sha256`, `version`, `updated_at`)
  - `POST /v1/platform/vault/secrets` -> encrypts `secret_value` (`AES-256-GCM` + 12B nonce), returns masked metadata (`status=201`)
  - `POST /v1/platform/vault/secrets/{name}/rotate` -> re-encrypts new `secret_value`, increments `version`
  - `DELETE /v1/platform/vault/secrets/{name}?workspace_id=...` -> revokes secret
- **HMAC-SHA256 Signed Webhooks:**
  - `GET /v1/platform/webhooks?workspace_id=...` -> lists registered webhooks & recent deliveries
  - `POST /v1/platform/webhooks` -> registers webhook (`url`, `events`, `description`, optional `secret`), enforces SSRF blocklist
  - `DELETE /v1/platform/webhooks/{webhook_id}` -> removes webhook
  - `POST /v1/platform/webhooks/{webhook_id}/test` -> signs & records deterministic test event receipt (`X-Keelway-Signature-256`)
  - `POST /v1/platform/webhooks/verify` -> verifies `(payload, signature, secret, timestamp)`
- **Live Streaming Agent & DAG Execution:**
  - `POST /v1/platform/execution/runs` -> starts run (`kind`: `"agent"` | `"workflow"`, `target_id`, `objective`, `requires_p10`, `stream`: `bool`); when `stream=True`, returns `text/event-stream` SSE (`data: {...}\n\n` + `data: [DONE]\n\n`); when `stream=False`, returns JSON run snapshot with `events`
  - `GET /v1/platform/execution/runs/{run_id}/events` -> streams SSE events for `run_id`
  - `POST /v1/platform/execution/runs/{run_id}/p10` -> records human `approve` or `deny` decision, appends completion/abort events, and emits webhook event
