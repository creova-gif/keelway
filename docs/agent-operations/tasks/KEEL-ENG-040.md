# KEEL-ENG-040 — Ollama Thinking-Model Handling

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / INFERENCE / LOCAL-MODELS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-040-thinking-models` |

## Objective
Fix empty `content` responses from Ollama thinking models (qwen3.5, deepseek-r1): reasoning consumed `num_predict`, and the adapters ignored both the `think` parameter and `message.thinking`.

## Root Cause (live evidence)
`POST /v1/chat/completions {"model":"qwen3.5:latest","max_tokens":16}` → real Ollama call, `content: ""` — thinking trace exhausted the token budget; adapters read only `message.content`.

## Changes
- `core/models/adapters/open_weight.py` + `core/models/adapters/local.py`: Ollama payloads now send `"think"` — enabled only when the model id contains `reasoning` or `complex_reasoning` is in `required_capabilities` (mirrors the existing OpenCore bridge heuristic in `core/opencore/runtime.py`). Non-stream content falls back to `message.thinking` when `content` is empty, matching bridge semantics.

## Verification
- Live: `LocalAdapter.complete` vs real Ollama `qwen3.5:latest` now returns `"4"` in ~3.6 s (previously `""` after ~6–8 s of thinking).
- `pytest tests/test_local_adapter.py tests/test_hybrid_adapters.py tests/test_opencore_runtime.py`: 27 passed; `test_hybrid_routing_and_api.py test_opencore.py test_anthropic_adapter.py test_gemini_adapter.py`: 30 passed.

## Known Risks & Blockers
- `think` heuristic is name/capability-based; a thinking model whose id lacks "reasoning" gets thinking disabled — acceptable default (direct answers), reasoning still available via `required_capabilities=["complex_reasoning"]` or model naming.
- `message.thinking` is folded into `content` on fallback (bridge-consistent); a dedicated `reasoning` response field remains future work.
- Older Ollama versions ignore unknown `think` field (Go JSON decoding tolerates it).

## Next Recommended Action
Merge to `main`. Remaining: KEEL-PROD-041 founder decision on real `keelway-*` weights vs registry relabel.
