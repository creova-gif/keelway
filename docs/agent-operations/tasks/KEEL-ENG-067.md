# KEEL-ENG-067 — Ollama Wedge Guard (Beta P0-6)

**Status:** COMPLETED
**Owner:** Devin
**Date:** 2026-11-27
**Branch:** `feature/keel-beta-p0-ollama-guard`

## Objective & Acceptance Criteria

Beta P0-6: `OllamaRuntimeBridge` hardcoded `127.0.0.1:11434`, ignored
`OLLAMA_BASE_URL`, and could hang ~120s on a wedged runner.

- [x] `OLLAMA_BASE_URL` honored end-to-end (binds to `settings.ollama_base_url` via pydantic env resolution)
- [x] Request timeout bounded: `OllamaRuntimeBridge.timeout_s` default 60s → 30s; connect split capped at 5s so dead hosts fail fast
- [x] Honest error: `httpx.TimeoutException` → `ProviderError("... timed out after Ns ...", status_code=503)` instead of the generic "unreachable"
- [x] All other hardcoded Ollama URL defaults aligned (`edge_loader`, `offline_bundle.import_bundle`, `cli pull`, `keelway.models.gateway`, `RuntimeProbe.probe_ollama`)

## Files Modified

- `core/opencore/runtime.py`: env-driven `base_url` on bridge + probe; 30s default; `httpx.Timeout(ts, connect=min(ts,5))` on all clients; explicit `TimeoutException` mapping
- `core/models/edge_loader.py`, `core/models/offline_bundle.py`: `ollama_url` params default to `settings.ollama_base_url`
- `keelway/models/gateway.py`: `_default_endpoint` reads `OLLAMA_BASE_URL` env (kept dependency-free vs `core.config`)
- `cli.py`: `cmd_pull` derives pull URL from `settings.ollama_base_url`
- `tests/test_ollama_wedge_guard.py`: 3 tests (settings binding, env honoring, timeout→503 mapping)

## Tests Executed

- `pytest tests/test_ollama_wedge_guard.py tests/test_opencore.py tests/test_offline_models.py`: **19 passed in 0.83s**
- `python -m mypy` (2.4.1): **0 errors / 297 files**
- `ruff check .`: clean

## Known Risks

- Generation legitimately slower than 30s on CPU-only hosts now raises 503 instead of waiting; callers can override via `timeout_s=` — noted in known limitations
- `settings.ollama_base_url` is resolved at process start; `OLLAMA_BASE_URL` changes require restart (documented behavior of pydantic settings)
- `VLLMRuntimeBridge` keeps its 60s default (out of criterion scope) but inherits the 5s connect split via `_post_local_json`
