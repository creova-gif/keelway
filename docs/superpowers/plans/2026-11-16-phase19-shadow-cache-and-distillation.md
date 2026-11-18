# Semantic Prompt Cache, Shadow Dual-Run Router & QLoRA Distillation Flywheel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deterministic local Semantic Prompt Cache + Shadow Dual-Run Parity Router (`keelway shadow`) and Frontier-to-OpenCore QLoRA Distillation Compiler & Canary Promotion Gate (`keelway distill`) across Keelway Core, CLI, Python/TS/Go SDKs, VS Code/Cursor Bridge, and `:7420/app` Agents Studio.

**Architecture:** `SQLiteShadowDistillationEngine` (`core/platform/shadow_distillation.py`) persists exact + 3-gram shingle Jaccard semantic prompt cache entries (`semantic_prompt_cache`), DLP-scrubbed Frontier-vs-Local shadow evaluations (`shadow_distill_pairs`), and SHA-256-signed SFT/DPO QLoRA dataset manifests (`qlora_distill_datasets`) in `platform_runtime.db` (`PRAGMA journal_mode=WAL`). Zero files under `website/**` are touched.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite WAL, TypeScript (`@keelway/sdk` + VS Code/Cursor Extension + React 19 + Vitest + `axe-core`), Go 1.22+ (`keelway-go`).

**Spec:** `/Users/justinmafie/.gemini/antigravity/brain/4fc93daa-32c3-4fbe-a51e-f37db6591901/phase19_shadow_cache_and_distillation_design.md`

## Global Constraints

- **STRICT ZERO `website/` TOUCH:** Never create, edit, or stage any file under `website/**` or `tests/test_website_facts.py` (owned exclusively by conversation `8fde1df8-a4b6-4789-bc4a-1e4c108741a3`).
- **STRICT ZERO BRAND-SHELL TOUCH:** Do not touch `DESIGN.md`, `web-console/index.html`, `dev-app/src/components/shell/DevAppShell.tsx`, `dev-app/src/components/platform/PlatformWorkspaceBar.tsx`, `dev-app/src/components/platform/BidirectionalKflowStudioPanel.tsx`, `dev-app/src/components/platform/FlightTapeScrubberAndRadar.tsx`, `dev-app/src/styles/tokens.css`, or `dev-app/src/components/ui/BrandMark.tsx`.
- **Module-Size Ratchets:** Every new file strictly `< 480` lines; `core/sdk/platform_runtime_client.py < 700` lines; `sdk/typescript/src/platform.ts < 700` lines; `sdk/typescript/src/index.ts < 700` lines.
- **Coding Rules:** Top-level imports only (zero inline imports inside function/method bodies); TypeScript exhaustive `never` check in `default:` case of `switch` over union/enum types; never run `uv run` (use `.venv/bin/pytest`, `.venv/bin/python`, `uvx ruff check`).

## Review Focus

1. **Cross-Task / Cross-Workspace Cache Isolation:** A cached prompt in `(workspace_a, task_tag="sql-gen")` must NEVER produce a `CACHE_HIT` for `workspace_b` or `task_tag="code-review"`.
2. **Pre-Storage DLP Secret Scrubbing on Cache, Pairs & Compiled JSONL:** Prompts or responses containing inline secrets (`sk-live-...`, `ghp_...`, `AKIA...`, `BEGIN PRIVATE KEY`) must be scrubbed to `[REDACTED_SECRET]` (or `LocalDLPSanitizer` tokens) BEFORE writing to `semantic_prompt_cache`, `shadow_distill_pairs`, or `qlora_distill_datasets` JSONL previews.
3. **Near-Duplicate Semantic Cache Hit via 3-Gram Shingles:** Minor whitespace/punctuation/casing or minor phrasing overlap (`similarity >= similarity_threshold`, default `0.82`) within the same `(workspace_id, task_tag)` must deterministically return `verdict: "CACHE_HIT"` (`match_type: "semantic_shingle"` or `"exact_sha256"`) and increment `hit_count`, `cost_saved_usd`, and `latency_saved_ms`.
4. **Canary Promotion Gate Verdicts (`PROMOTE_TO_OPENCORE`, `NEEDS_MORE_PAIRS`, `HOLD_ON_FRONTIER`):** Fewer than `min_pairs` captured pairs returns `NEEDS_MORE_PAIRS`; `pair_count >= min_pairs` with `avg_parity_score < min_avg_parity` returns `HOLD_ON_FRONTIER`; `pair_count >= min_pairs` with `avg_parity_score >= min_avg_parity` returns `PROMOTE_TO_OPENCORE` with positive `projected_monthly_savings_usd`.
5. **Read-Only RBAC Enforcement:** Roles `auditor` and `viewer` can read shadow pairs (`GET /shadow/pairs`), cache stats (`GET /cache/stats`), and datasets (`GET /datasets`), but receive `HTTP 403` on mutating endpoints (`/shadow/evaluate`, `/datasets/compile`, `/promotion/evaluate`) and have disabled mutation buttons in `:7420/app`.

---

## Exact Wire Contract (`/v1/platform/distill/*` — 6 New OpenAPI Paths -> `310` Total)

1. `POST /v1/platform/distill/shadow/evaluate` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), task_tag?: string (default "code-patch"), prompt?: string (default "Refactor retry loop with bounded exponential backoff in Python"), frontier_model?: string (default "claude-3-7-sonnet"), local_model?: string (default "keelway-core:7b"), frontier_response?: string (default "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))"), local_response?: string (default "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))"), frontier_cost_usd?: number (default 0.018), frontier_latency_ms?: number (default 840), local_latency_ms?: number (default 95), similarity_threshold?: number (default 0.82), bypass_cache?: boolean (default false) }`
   - Response (`ShadowEvaluationRecord`):
     `{ evaluation_id: string, pair_id: string | null, cache_entry_id: string, workspace_id: string, task_tag: string, verdict: "CACHE_HIT" | "LOCAL_PARITY_READY" | "SHADOW_CAPTURED", match_type: "exact_sha256" | "semantic_shingle" | "cache_miss", similarity_score: number, parity_score: number, frontier_model: string, local_model: string, scrubbed_prompt: string, cached_response: string, cost_saved_usd: number, latency_saved_ms: number, dlp_redactions: number, event_sha256: string, created_at: string }`

2. `GET /v1/platform/distill/shadow/pairs?workspace_id=default&task_tag=&limit=25` (`read:all`):
   - Response (`ShadowPairListResponse`): `{ workspace_id: string, count: number, pairs: ShadowDistillPairRecord[] }`
   - `ShadowDistillPairRecord`:
     `{ pair_id: string, workspace_id: string, task_tag: string, scrubbed_prompt: string, scrubbed_frontier_response: string, scrubbed_local_response: string, frontier_model: string, local_model: string, parity_score: number, frontier_cost_usd: number, dlp_redactions: number, pair_sha256: string, created_at: string }`

3. `GET /v1/platform/distill/cache/stats?workspace_id=default` (`read:all`):
   - Response (`SemanticCacheStatsResponse`):
     `{ workspace_id: string, entry_count: number, total_hits: number, total_lookups: number, hit_rate: number, total_cost_saved_usd: number, total_latency_saved_ms: number, total_dlp_redactions: number }`

4. `POST /v1/platform/distill/datasets/compile` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), task_tag?: string (default ""), export_format?: "sft_jsonl" | "dpo_preference" (default "dpo_preference"), target_base_model?: string (default "keelway-core:7b"), min_parity_score?: number (default 0.0) }`
   - Response (`DistillationDatasetRecord`):
     `{ dataset_id: string, workspace_id: string, task_tag: string, export_format: "sft_jsonl" | "dpo_preference", target_base_model: string, record_count: number, avg_parity_score: number, lora_rank: number, lora_alpha: number, dlp_redactions: number, jsonl_preview: string, dataset_sha256: string, created_at: string }`

5. `GET /v1/platform/distill/datasets?workspace_id=default&limit=25` (`read:all`):
   - Response (`DistillationDatasetListResponse`): `{ workspace_id: string, count: number, datasets: DistillationDatasetRecord[] }`

6. `POST /v1/platform/distill/promotion/evaluate` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), task_tag?: string (default "code-patch"), target_local_model?: string (default "keelway-core:7b"), min_pairs?: number (default 3), min_avg_parity?: number (default 0.85), monthly_request_volume?: number (default 50000) }`
   - Response (`DistillationPromotionEvaluation`):
     `{ evaluation_id: string, workspace_id: string, task_tag: string, target_local_model: string, verdict: "PROMOTE_TO_OPENCORE" | "NEEDS_MORE_PAIRS" | "HOLD_ON_FRONTIER", pair_count: number, min_pairs: number, avg_parity_score: number, min_avg_parity: number, avg_frontier_cost_usd: number, monthly_request_volume: number, projected_monthly_savings_usd: number, recommendation: string, gate_sha256: string, evaluated_at: string }`

---

## Parallel Tasks & Exclusive File Ownership

- [ ] **Task 1 (Workstream `19A` — Semantic Cache, Shadow Dual-Run & QLoRA Distillation Backend, FastAPI & CLI):**
  - Exclusive files:
    - `core/platform/shadow_distillation.py` (`< 450` lines)
    - `core/api/platform_distill_routes.py` (`< 240` lines)
    - `core/cli_distill.py` (`< 220` lines)
    - `core/main.py` (`310` OpenAPI paths) & `core/cli_runtime.py`
    - `tests/test_phase19_shadow_cache_and_distill_cli.py` (`< 380` lines)

- [ ] **Task 2 (Workstream `19B` — Tri-Language SDK Parity + VS Code/Cursor Bridge):**
  - Exclusive files:
    - `core/sdk/platform_distill_client.py` (`< 240` lines) + `core/sdk/platform_runtime_client.py` (`< 700` lines)
    - `sdk/typescript/src/platformDistill.ts` (`< 290` lines) + `sdk/typescript/src/platform.ts` (`< 700` lines) + `sdk/typescript/src/index.ts` (`< 700` lines) + `sdk/typescript/package.json` + `sdk/typescript/tests/platform_phase19.test.mjs` (`< 240` lines)
    - `sdk/go/platform_phase19.go` (`< 260` lines) + `sdk/go/platform_phase19_test.go` (`< 240` lines)
    - `extensions/vscode-keelway/package.json`, `extensions/vscode-keelway/src/bridgeClient.ts`, `extensions/vscode-keelway/src/extension.ts`, `extensions/vscode-keelway/test/extension.test.mjs` (`keelway.inspectDistillationReadiness`)

- [ ] **Task 3 (Workstream `19C` — `:7420/app` Agents Studio Shadow Cache & Distillation UI):**
  - Exclusive files:
    - `dev-app/src/lib/platformDistillApi.ts` (`< 250` lines)
    - `dev-app/src/components/platform/ShadowCacheAndDistillationPanel.tsx` (`< 430` lines)
    - `dev-app/src/components/platform/AgentsWorkspaceView.tsx` (`< 520` lines — mount inside `AgentsWorkspaceView`)
    - `dev-app/src/__tests__/phase19-shadow-cache-and-distill.test.tsx` (`< 310` lines)

- [ ] **Task 4 (Lead Integration, Cold Headless Chromium + SQLite WAL Proof & Selective CI Ship):**
  - Create `tests/test_phase19_sdk_and_vscode_distill.py` (`< 340` lines) & wire Phase 19 suites into `scripts/verify_engineering_gates.sh`.
  - Run `uvx ruff check .` & `./scripts/verify_engineering_gates.sh` (`8/8` stages).
  - Run cold headless Chromium + CLI + SQLite WAL proof (`verify-keelway-phase19-proof/`).
  - Selectively stage ONLY Phase 19 files (zero `website/**` or brand-touched files), commit, push, and verify `5/5` GitHub Actions CI green.
