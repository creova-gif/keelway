# KEEL-ENG-038 — Simulated OpenCore Response Disclosure

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / PRODUCT-TRUTH / INFERENCE` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-038-simulated-disclosure` |

## Objective
Live verification (verify-keelway stack + real Ollama `qwen3.5:latest`) showed `keelway-*` registry models return canned mock-backend text in ~12 ms while API metadata implied real local inference (`provider: local`, `routing_reason: "preferred local"`). Disclose simulation honestly.

## Evidence (pre-fix)
- `POST /v1/chat/completions {"model":"keelway-core:7b"}` → canned `"[Keelway OpenCore 7B Sovereign Engine]: Processed request…"`, `latency_ms: 12.5`, `cost_usd: 0`, no simulation flag.
- `{"model":"qwen3.5:latest"}` → real Ollama call (5.6–8.2 s) proving the adapter path works when weights exist.

## Changes
- `core/models/provider.py`: `ChatCompletionResponse.simulated: bool = False` and `StreamChunk.simulated: bool = False`; `to_openai_dict()` now always emits `keelway_metadata.simulated`; SSE payload emits `"simulated": true` when set.
- `core/opencore/serving.py`: MOCK backend branch sets `simulated=True` and `routing_reason` now reads `"SIMULATED: Keelway OpenCore mock backend (no model weights loaded)"` (non-stream + stream paths).
- `tests/test_opencore.py`: asserts `simulated` flag and metadata propagation.

## Acceptance Criteria
- [x] Mock-backend responses are machine-detectable as simulated
- [x] Real Ollama/vLLM backends unaffected (`simulated` defaults false)
- [x] Existing routing_reason substring assertions still pass

## Tests Executed
- `pytest tests/test_opencore.py tests/test_opencore_runtime.py tests/test_local_adapter.py -q`: **29 passed**
- `pytest tests/test_hybrid_routing_and_api.py tests/test_responses_and_routing_api.py -q`: **21 passed**

## Known Risks & Blockers
- `keelway-*` models still have no real weight backend — they remain mock-only until Ollama/vLLM model mappings exist. Registry vs. reality gap documented in the platform audit.
- SSE consumers must tolerate the additive `simulated` field (standard JSON, ignored by strict OpenAI parsers only if they reject unknown keys — low risk).

## Next Recommended Action
Merge to `main`. Real `keelway-*` weight backing (Ollama bridge mapping or bundled GGUF) is a separate product task.
