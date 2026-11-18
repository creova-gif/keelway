# KEEL-ENG-039 — `/v1/models` Installed + Simulated Flags

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / PRODUCT-TRUTH / MODELS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-039-model-flags` |

## Objective
Close the registry-vs-reality gap: `/v1/models` advertised 15 models while only installed Ollama weights are callable. Each entry now self-discloses availability.

## Changes
- `core/api/routes.py` `list_models`: per-model `installed` (live `/api/tags` match via gateway's cached `LocalAdapter` runtime; `null` for closed_proprietary) and `simulated` (`true` for `keelway-*` IDs not present in the local runtime — i.e. mock-backend responses).
- `core/models/adapters/open_weight.py`: new `local_runtime()` passthrough to the underlying `LocalAdapter` probe.
- `tests/test_hybrid_routing_and_api.py`: asserts both fields exist, `keelway-core:7b` is `simulated`, `gpt-4o` reports `installed: null`.

## Verification
- Live check: `keelway-*` → `installed: False, simulated: True`; non-installed open-weight → `installed: False`; cloud → `installed: null`.
- `pytest tests/test_hybrid_routing_and_api.py`: 7 passed; `test_local_adapter.py`, `test_full_beta_developer_journey.py`: 17 passed.

## Known Risks & Blockers
- `installed` reflects the local daemon only; `self_hosted_gpu` models report `installed: false` unless pulled locally — honest but may read as "unsupported" for vLLM deployments (follow-up: per-deployment probing).
