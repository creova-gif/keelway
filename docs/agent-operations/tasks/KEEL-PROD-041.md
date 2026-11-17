# KEEL-PROD-041 — OpenCore Weights Decision: Runtime Aliases for Flagship, Simulated for Niche

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` (founder decision recorded + implemented) |
| **Category** | `PRODUCT / MODELS / HONEST-CLAIMS` |
| **Agent** | Devin (decision by founder Justin Mafie, 2026-11-16) |
| **Branch** | `fix/KEEL-PROD-041-runtime-aliases` |

## Decision (founder-approved)

**Hybrid**: flagship `keelway-*` tiers alias to real installed local runtime
models; niche/experimental tiers remain explicitly simulated.

- `keelway-core:7b`, `keelway-coder:7b`, `keelway-reasoning:14b` →
  `runtime_alias=True`: when a compatible model is installed in local Ollama
  (or vLLM), requests are served by **real weights** via
  `LocalRuntimeDiscovery` bindings. The resolved runtime model is disclosed in
  `routing_reason` (`runtime_model=...`).
- `keelway-nano:1.5b` → `runtime_alias=False`: always mock-served, labeled
  simulated everywhere.
- When no compatible runtime model is installed, flagship models fall back to
  the mock backend and are **still labeled `simulated: true`** — the flag now
  means "would be mock-served," computed from live runtime state.

## What this does NOT claim

- The canonical GGUF manifests remain **placeholder artifacts**
  (`artifact_verified: false`): checksums are not real digests and
  `weights.keelway.ai` URIs are unpublished. No "verified sovereign weights"
  or downloadable-bundle claim is made. Verified artifact hosting is tracked
  as follow-up work.
- `keelway-*` IDs are **aliases**, not proprietary weights. Marketing must say
  "aliases to your installed local models," never "our trained weights."

## Implementation

- `core/opencore/weights.py`: `WeightManifest.runtime_alias` field; `False` on
  the nano manifest only.
- `core/opencore/serving.py`: `_select_backend()` auto-picks OLLAMA → VLLM →
  MOCK for alias-capable models when `backend` is unspecified; `_ensure_ready`
  re-probes a stale MOCK load at most once per 60s so a runtime that comes up
  later is picked up. Explicit `backend=` is still honored.
- `core/api/routes.py` `/v1/models`: `simulated` now reflects live binding
  availability; new `runtime_alias` and `resolved_model` fields.
- `core/api/opencore_routes.py` `/weights`: per-manifest `runtime_alias`,
  `simulated = not runtime_alias`, `artifact_verified: false`.
- Studio: weights panel shows "Runtime alias — served via installed local
  model" for flagship, "Simulated weights" for nano; Agents model selector
  relabeled `(Local alias)` / `(Simulated)` and fixed stale
  `keelway-reasoner:14b` option IDs → `keelway-reasoning:14b`.
- Website Model Explorer: `LOCAL RUNTIME ALIAS` chip on flagship cards,
  `SIMULATED` only on nano.

## Evidence

- `tests/test_opencore_runtime_alias.py` (5 tests): auto-alias to mocked
  Ollama, mock fallback when runtime down, nano never aliases, explicit
  backend honored, streaming alias.
- Live verification on this machine: `keelway-core:7b` → real
  `qwen3.5:latest` completion in ~6.3s, `simulated: false`,
  `routing_reason` discloses `runtime_model=qwen3.5:latest`.
- `pytest tests/test_opencore*.py tests/test_hybrid_routing_and_api.py`:
  32 passed. Env-dependent tests pinned to dead transports / patched runtime.

## Follow-ups

- KEEL-PROD-042 (new): real verified GGUF artifacts + checksum manifests if
  proprietary weights are ever shipped.
- ~~Fixture drift~~ **DONE 2026-11-17**: `keelway-reasoner:*` →
  `keelway-reasoning:*` swept across dev-app fixtures/tests and the
  `reasoner-14b` display label → `reasoning-14b`; dist bundle rebuilt.
