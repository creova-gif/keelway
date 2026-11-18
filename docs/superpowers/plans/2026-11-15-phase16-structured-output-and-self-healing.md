# Phase 16 Implementation Plan (`KEEL-HEAL-023`): Typed Structured-Output & Content-Block Normalizer + Autonomous Self-Healing Failure Root-Causer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver strict cross-provider JSON-Schema enforcement + `.content_blocks` normalization (`Tier 1 #3`) and an autonomous Flight-Tape failure root-causer with verified replay + Golden Eval promotion (`Tier 3 #1`) across SQLite WAL, FastAPI (`292` OpenAPI paths), Sovereign CLI, Python/TypeScript/Go SDKs, and `:7420/app` Agents Studio.

**Architecture:** `SQLiteStructuredHealingEngine` (`core/platform/structured_self_healing.py`) shares `platform_runtime.db` (`PRAGMA journal_mode=WAL`) via `resolve_kbrain_db_target`, normalizing OpenCore/OpenAI/Anthropic/Gemini payloads into canonical content blocks with DLP secret scrubbing, enforcing JSON-Schema contracts into `structured_output_runs`, and diagnosing failed traces into `self_healing_diagnoses` with deterministic patch replay and Golden Eval case promotion (`platform_eval_dataset_cases`).

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite WAL, TypeScript (`@keelway/sdk` + React 19 + Vitest + `axe-core`), Go 1.22+ (`keelway-go`).

---

## Exact Wire Contract (`/v1/platform/healing/*`)

All 6 routes live under `/v1/platform/healing` (`core/api/platform_healing_routes.py`, mounted in `core/main.py` -> `292` total OpenAPI 3.1 paths):

1. `POST /v1/platform/healing/content-blocks/normalize` (`read:all`):
   - Request:
     `{ workspace_id?: string (default "default"), provider_format: "deepseek_opencore" | "openai" | "anthropic" | "gemini", model_id?: string (default "keelway-core:7b"), raw_payload: Record<string, any> | string }`
   - Response (`NormalizedContentEnvelope`):
     `{ workspace_id, provider_format, model_id, block_count, content_blocks: Array<{ index: number, kind: "reasoning" | "text" | "tool_call" | "citation" | "structured_json", content: string, tool_name?: string | null, tool_call_id?: string | null, tool_args?: Record<string, any> | null, source_uri?: string | null, structured_data?: Record<string, any> | null }>, dlp_redactions: number, envelope_sha256: string }`
   - Rejects (`HTTP 422`): unsupported `provider_format` (`code: "healing_validation_error"`). Raw secrets (`sk-...`, `AKIA...`, `ghp_...`, `PRIVATE KEY`, `Bearer ...`) are scrubbed into `[REDACTED_SECRET]` and counted in `dlp_redactions`.

2. `POST /v1/platform/healing/structured/enforce` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), schema_name?: string (default "AgentDecisionContract"), provider_format?: string (default "deepseek_opencore"), model_id?: string (default "keelway-core:7b"), json_schema: Record<string, any>, raw_output: string | Record<string, any>, strict_mode?: boolean (default false), fail_closed?: boolean (default true) }`
   - Response (`StructuredOutputRunRecord`):
     `{ run_id, workspace_id, schema_name, provider_format, model_id, status: "VALID" | "REPAIRED_VALID" | "SCHEMA_REJECTED", repair_applied: boolean, repair_actions: string[], validated_data: Record<string, any> | null, validation_errors: string[], dlp_redactions: number, run_sha256: string, created_at: string }`
   - Behavior:
     - Validates `type` (`object`, `array`, `string`, `integer`, `number`, `boolean`), `required`, `properties`, `enum`, `additionalProperties`, `minimum`/`maximum`, `minItems`/`maxItems`.
     - When `strict_mode=false`, performs deterministic single-pass repair: strips `<think>...</think>` prefix and markdown ```` ```json ... ``` ```` fences, removes trailing commas before `}`/`]`, and coerces unambiguous scalar strings (`"42"` -> `42`, `"0.91"` -> `0.91`, `"true"` -> `true`) to match target property types (`status: "REPAIRED_VALID"`).
     - Persists every attempt in `structured_output_runs`. If validation still fails and `fail_closed=true`, returns `HTTP 422` JSON `{ detail: string, code: "structured_schema_rejected", run: StructuredOutputRunRecord }`; if `fail_closed=false`, returns `HTTP 200` `StructuredOutputRunRecord` with `status: "SCHEMA_REJECTED"`.

3. `GET /v1/platform/healing/structured/runs?workspace_id=default&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, runs: StructuredOutputRunRecord[] }`

4. `POST /v1/platform/healing/root-cause/diagnose` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), trace_id?: string | null, workflow_name?: string (default "invoice-triage-agent"), failed_step?: { step_index?: number, node_name?: string, model_id?: string, prompt_text?: string, output_text?: string, error_message?: string, expected_schema?: Record<string, any> | null } | null }`
   - Response (`SelfHealingDiagnosisRecord`):
     `{ diagnosis_id, workspace_id, trace_id, workflow_name, failure_class: "schema_mismatch" | "context_truncation" | "prompt_ambiguity" | "kbrain_conflict" | "airgap_egress_blocked", status: "DIAGNOSED" | "VERIFIED_HEALED", confidence: number, failed_node: string, diagnostic_model: string, summary: string, root_cause_evidence: string[], proposed_patch: { target_surface: "json_schema" | "system_prompt" | "routing_policy" | "kbrain_memory", recommended_model: string, unified_diff: string, patched_prompt: string }, verification_replay_trace_id: string | null, promoted_eval_case_id: string | null, dlp_redactions: number, diagnosis_sha256: string, created_at: string }`
   - Note: If `trace_id` references an existing tape in `platform_flight_tapes` (`platform_flight_steps`), inspects its steps automatically; if `trace_id` is omitted or synthetic, diagnoses `failed_step` (with sensible deterministic defaults if fields are omitted). Rejects missing `trace_id` when `failed_step` is also absent and `trace_id` is explicitly provided (`HTTP 404`).

5. `POST /v1/platform/healing/root-cause/{diagnosis_id}/apply` (`workflows:run`):
   - Request: `{ workspace_id?: string (default "default"), promote_to_eval?: boolean (default true), eval_title?: string | null }`
   - Response (`ApplySelfHealingResponse`):
     `{ diagnosis: SelfHealingDiagnosisRecord, verified_healed: boolean, cached_steps_reused: number, replay_cost_usd: number, promoted_eval_case: { case_id: string, title: string, case_sha256: string } | null }`
   - Behavior: Transitions diagnosis `status` to `"VERIFIED_HEALED"`, sets `verification_replay_trace_id`, inserts a deterministic Golden Eval regression case into `platform_eval_dataset_cases` when `promote_to_eval=true` (reusing `FlightTapeStore.promote_to_eval` or compatible schema), and updates `self_healing_diagnoses`. Returns `HTTP 404` if `diagnosis_id` does not exist in `workspace_id`.

6. `GET /v1/platform/healing/root-cause/diagnoses?workspace_id=default&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, diagnoses: SelfHealingDiagnosisRecord[] }`

---

## Parallel Workstreams & Strict File Ownership

- [ ] **Task 1 (Workstream 16A — Backend SQLite WAL Engine, FastAPI Routes & CLI):**
  - Own exclusively:
    - `core/platform/structured_self_healing.py` (`< 480` lines)
    - `core/api/platform_healing_routes.py` (`< 250` lines)
    - `core/cli_healing.py` (`< 230` lines)
    - `core/main.py` & `core/cli_runtime.py`
    - `tests/test_phase16_structured_and_healing_cli.py` (`< 380` lines)
  - Verify with: `pytest tests/test_phase16_structured_and_healing_cli.py -v` and `uvx ruff check core/platform/structured_self_healing.py core/api/platform_healing_routes.py core/cli_healing.py tests/test_phase16_structured_and_healing_cli.py`

- [ ] **Task 2 (Workstream 16B — Tri-Language SDK Parity: Python, TypeScript, Go):**
  - Own exclusively:
    - `core/sdk/platform_healing_client.py` (`< 250` lines) + `core/sdk/platform_runtime_client.py` (`< 700` lines)
    - `sdk/typescript/src/platformHealing.ts` (`< 300` lines) + `sdk/typescript/src/platform.ts` (**MUST stay `< 700` lines!** Compact multi-line method wrappers if needed) + `sdk/typescript/src/index.ts` (`< 700` lines) + `sdk/typescript/package.json` + `sdk/typescript/tests/platform_phase16.test.mjs` (`< 240` lines)
    - `sdk/go/platform_phase16.go` (`< 270` lines) + `sdk/go/platform_phase16_test.go` (`< 250` lines)
  - Verify with: `npm --prefix sdk/typescript run typecheck && npm --prefix sdk/typescript test` and `(cd sdk/go && go test -v -race ./...)`

- [ ] **Task 3 (Workstream 16C — `:7420/app` Structured Output & Self-Healing Panel):**
  - Own exclusively:
    - `dev-app/src/lib/platformHealingApi.ts` (`< 280` lines)
    - `dev-app/src/components/platform/StructuredOutputAndSelfHealingPanel.tsx` (`< 440` lines)
    - `dev-app/src/components/platform/AgentsWorkspaceView.tsx` (`< 540` lines)
    - `dev-app/src/__tests__/phase16-structured-self-healing.test.tsx` (`< 320` lines)
  - Verify with: `npm --prefix dev-app run typecheck && npm --prefix dev-app test`

- [ ] **Task 4 (Lead Integration, OpenAPI/Website Sync, Cold Headless Chromium E2E & Release Gates):**
  - Relax `== 286` / `== 23` in `tests/test_phase15_sdk_and_website_sync.py` to `>= 286` / `>= 23`.
  - Export `website/openapi.json` & `website/public/openapi.json` (`292` paths).
  - Update `website/product-facts.json` & `website/public/product-facts.json` (`24` features adding `structured_output_normalizer_and_self_healing_root_causer`), `DocsHub.tsx` (`< 500` lines!), `CommandPalette.tsx`, and `website/src/app/api/search-index/route.ts`.
  - Create `tests/test_phase16_sdk_and_website_sync.py` (`< 360` lines) & wire Phase 16 suites into `scripts/verify_engineering_gates.sh`.
  - Rebuild `core/dev_app_dist/` & `sdk/typescript/dist/`, run `uvx ruff check .`, `./scripts/verify_engineering_gates.sh` (`8/8` green), `npm --prefix website run typecheck && npm --prefix website run build`, execute cold headless Chromium + SQLite WAL proof (`verify-keelway-phase16-proof/`), commit, push to `origin/main`, and verify GitHub Actions + Vercel.
