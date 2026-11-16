# TASK: KEEL-SDK-005 — Official TypeScript SDK (`@keelway/sdk`) & Next.js Product-Facts Verification Gate

## 1. METADATA
- **TASK ID**: KEEL-SDK-005
- **CATEGORY**: SDK / WEBSITE / QUALITY GATE
- **CREATOR**: Engineering Architecture Team
- **LAST ASSIGNED AGENT**: Google Antigravity
- **CURRENT STATUS**: COMPLETED
- **TARGET BRANCH**: `main`
- **BASE COMMIT**: `5b2fbc3`

---

## 2. OBJECTIVE & MOTIVATION
1. Deliver the official zero-dependency TypeScript & JavaScript client SDK (`@keelway/sdk` v1.0.0) in `sdk/typescript/` with full API and typed-error parity with the Python SDK (`core/sdk`), built exclusively on Web Standard `fetch`, `ReadableStream`, `TextDecoder`, and `AbortSignal` for Node 20+, Bun, Deno, Cloudflare Workers, and browsers.
2. Modernize `website/public/product-facts.json` (and synchronized `website/product-facts.json`) plus `tests/test_website_facts.py` so every `AVAILABLE` and `EXPERIMENTAL` feature claim, Next.js 15 App Router route, legacy `.html` permanent `308` redirect, self-hosted variable `.woff2` font, and sovereign zero-third-party-CDN invariant is continuously enforced in CI.

---

## 3. ACCEPTANCE CRITERIA
- [x] **Criterion 1**: Zero-dependency `@keelway/sdk` v1.0.0 implemented in `sdk/typescript/` with `"type": "module"`, strict TypeScript declarations, and zero runtime npm dependencies (`sdk/typescript/package.json`, `sdk/typescript/tsconfig.json`).
- [x] **Criterion 2**: Full v1 Platform & OpenCore parity implemented across `client.models`, `client.usage`, `client.chat.completions` (`create` & chunk-split-safe SSE `stream`), `client.responses` (`create`, `get`, SSE `stream`), `client.routing` (`explain`, `decisions`), `client.opencore` (`status`, `weights`, `compileModelfile`, `adapters`, `loadModel`, `unloadModel`, `adaptRecipe`), `client.governance` (`upsertPolicy` with `409 -> PATCH` idempotency, `getPolicy`, `listPolicies`, `issueKey`, `verifyAudit`, `evaluate`), and `client.swarm.evaluate` (`sdk/typescript/src/client.ts`, `sdk/typescript/src/types.ts`).
- [x] **Criterion 3**: Deterministic HTTP error hierarchy (`mapHttpError(status, body)`) implemented in `sdk/typescript/src/errors.ts` matching `core/sdk/errors.py` and `core/sdk/client.py` word-for-word (`401` -> `AuthenticationError`, `402` -> `BudgetExceededError`, `403` air-gap/egress -> `AirGapEgressError`, `403` quorum -> `QuorumRequiredError`, `403` general -> `PermissionDeniedError`, `404` -> `TaskNotFoundError`, `422` -> `PolicyViolationError`, `429` -> `RateLimitExceededError`, fallback -> `KeelwayError`, network/abort -> `ConnectionError`).
- [x] **Criterion 4**: Strict TypeScript compilation (`../../website/node_modules/.bin/tsc -p tsconfig.json`) emits clean `dist/` JS + `.d.ts` artifacts with zero diagnostics, and `node --test test/sdk.test.mjs` passes 100% against both an ephemeral `node:http` server and byte-split custom `fetchImpl` streams.
- [x] **Criterion 5**: Synchronized `website/public/product-facts.json` and `website/product-facts.json` (`version: "1.0.0"`) accurately map all 6 `AVAILABLE` capabilities to real disk source paths and test suites, and qualify `tier2_hardware_security_hal` as `EXPERIMENTAL`.
- [x] **Criterion 6**: `tests/test_website_facts.py` validates `product-facts.json` disk integrity, Next.js 15 App Router 7-route structure, permanent `308` legacy `.html` redirects, `sitemap.ts` / `robots.ts` / `public/openapi.json`, self-hosted `.woff2` fonts, zero third-party font/CSS CDNs across `website/src/` & `website/public/`, and `@keelway/sdk` test execution.

---

## 4. AFFECTED FILES & COMPONENTS
- `sdk/typescript/package.json` (New: `@keelway/sdk` v1.0.0 zero-dependency ESM package manifest)
- `sdk/typescript/tsconfig.json` (New: Strict ES2022 + DOM/DOM.Iterable TypeScript build config outputting to `./dist`)
- `sdk/typescript/README.md` (New: Quickstart, surface coverage table, and typed error mapping reference)
- `sdk/typescript/src/types.ts` (New: Request/response interfaces for Models, Usage, Chat, Responses, 4D Routing, OpenCore, Governance, and Swarm)
- `sdk/typescript/src/errors.ts` (New: Typed `KeelwayError` hierarchy and `mapHttpError` status/payload mapper)
- `sdk/typescript/src/client.ts` (New: `KeelwayClient`, `AbortSignal` timeout controller, and UTF-8/CRLF chunk-boundary-safe SSE parser)
- `sdk/typescript/src/index.ts` (New: Public barrel exporting `KeelwayClient`, error classes, and TypeScript types)
- `sdk/typescript/dist/*` (Compiled ESM `.js`, `.d.ts`, and sourcemaps emitted by `tsc`)
- `sdk/typescript/test/sdk.test.mjs` (New: 7-test `node:test` integration & unit suite over `node:http` and custom `ReadableStream` `fetchImpl`)
- `website/public/product-facts.json` (New: Public v1.0.0 verified capability manifest served at `/product-facts.json`)
- `website/product-facts.json` (New: Synchronized root mirror of `product-facts.json`)
- `tests/test_website_facts.py` (Updated: 4-test drift gate covering `product-facts.json`, Next.js 15 routes & 308 redirects, zero-CDN invariant, and `@keelway/sdk`)
- `docs/agent-operations/tasks/KEEL-SDK-005.md` (New: Canonical task specification and cross-agent handoff record)

---

## 5. EXECUTION & HANDOFF HISTORY

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-SDK-005
- **TASK TITLE**: Official TypeScript SDK (`@keelway/sdk`) & Next.js Product-Facts Verification Gate
- **CURRENT STATUS**: COMPLETED
- **LAST AGENT**: Antigravity
- **DATE**: 2026-11-13
- **BRANCH**: `main`
- **HEAD COMMIT**: `5b2fbc3` (uncommitted working tree changes per parallel multi-agent coordination rules)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Zero-dependency `@keelway/sdk` v1.0.0 compiled to `sdk/typescript/dist/` with zero TypeScript errors.
- [x] Full Python `core/sdk` endpoint & error mapping parity verified via `node --test test/sdk.test.mjs` (Bearer auth without URL leakage, split SSE frames, multi-byte UTF-8 boundary decoding, `/v1/responses` turn chaining, 4D routing, OpenCore, Governance `POST`/`409 -> PATCH` upsert, MiroFish swarm, HTTP `401`/`402`/`403`/`404`/`422`/`429`/`500`, and `AbortSignal` timeouts).
- [x] `website/public/product-facts.json` and `website/product-facts.json` synchronized at `v1.0.0` with verified `AVAILABLE` and `EXPERIMENTAL` claims.
- [x] `tests/test_website_facts.py` enforces manifest path existence, Next.js 15 App Router routes & permanent `308` legacy `.html` redirects, self-hosted `.woff2` fonts, and zero third-party CDN leaks.

#### WORK COMPLETED & FILES MODIFIED
- `sdk/typescript/package.json`: Configured `@keelway/sdk` v1.0.0 ESM exports and zero runtime dependencies.
- `sdk/typescript/tsconfig.json`: Configured strict `ES2022` compilation into `./dist` with declaration maps.
- `sdk/typescript/src/errors.ts`: Implemented `KeelwayError`, `AuthenticationError`, `BudgetExceededError`, `AirGapEgressError`, `QuorumRequiredError`, `PermissionDeniedError`, `TaskNotFoundError`, `PolicyViolationError`, `RateLimitExceededError`, `FlightRecorderError`, `ConnectionError`, and `mapHttpError`.
- `sdk/typescript/src/types.ts`: Authored strict TypeScript definitions across all v1 endpoints.
- `sdk/typescript/src/client.ts`: Implemented `KeelwayClient`, chunk-split-safe `parseSseFrames`, and `AbortSignal` timeout handling.
- `sdk/typescript/src/index.ts` & `sdk/typescript/README.md`: Exported public SDK surface and documented usage & error codes.
- `sdk/typescript/test/sdk.test.mjs`: Implemented 7 end-to-end and unit tests using `node:test` and `node:http`.
- `website/public/product-facts.json` & `website/product-facts.json`: Authored synchronized v1.0.0 capability manifests.
- `tests/test_website_facts.py`: Upgraded product-facts & Next.js 15 sovereign website verification suite.

#### TESTS EXECUTED & EVIDENCE
- `cd keelway/sdk/typescript && ../../website/node_modules/.bin/tsc -p tsconfig.json`: `exit code 0 (zero diagnostics)`
- `cd keelway/sdk/typescript && node --test test/sdk.test.mjs`: `7 passed, 0 failed in 81.90ms`
- `cd keelway && PYTHONPATH=. ../kora-ai.nosync/.venv/bin/pytest tests/test_website_facts.py -v`: `4 passed in 0.40s`

#### KNOWN RISKS & BLOCKERS
- None. Zero external network calls or runtime npm dependencies required.

#### NEXT RECOMMENDED ACTION
- Coordinator agent can run full repository verification (`./scripts/verify_engineering_gates.sh`), update `docs/agent-operations/ACTIVE_TASKS.md` with `KEEL-SDK-005`, and stage all parallel agent deliverables for commit.
