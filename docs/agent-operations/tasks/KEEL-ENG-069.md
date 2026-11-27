# KEEL-ENG-069 — `swarm run` offline determinism (beta P1-1)

- **Status**: COMPLETED
- **Agent**: Devin
- **Date**: 2026-11-27
- **Branch**: `fix/keel-eng-069-swarm-deadlock`

## Objective & acceptance

Backlog P1-1: `test_cli_swarm_offline_benchmark_json` hangs on clean HEAD —
"test passes deterministically or quarantined with reason."

## Root cause (measured, not a deadlock)

Reproduced end-to-end: the run **completes** in ~24s against `_run_cli`'s
30s subprocess timeout — a marginal flake, not an event-loop deadlock.
Stage timing showed `build_seed_world_and_personas` alone at ~10s;
per-call timing showed each local `complete` taking ~3-6s.

Cause: offline mode wired `OpenWeightProviderAdapter(127.0.0.1:9)` as the
citizen/draft provider. `keelway-*` requests short-circuit into
`opencore_serving_engine.forward_inference`, whose `_select_backend`
prefers a real runtime — so on hosts with live Ollama, the "offline"
benchmark executes real model inference (environment-dependent latency).
On hosts without it, probes fall back to mock — fast. Either way, runtime
depended on ambient machine state → nondeterministic.

## Fix

- `core/cli_ai.py`: new `_OfflineMockLocalProvider` (Provider.LOCAL /
  OPEN_WEIGHT, `simulated=True`, `cost_usd=0.0`) mirrors the existing
  `_OfflineMockCloudProvider` contract — deterministic JSON for persona
  and action prompts.
- `_handle_swarm` offline branch uses it for the LOCAL gateway adapter
  and draft provider; `--live` path untouched (still real adapters).
- Security invariants under test are unaffected: prompt-injection block
  and air-gap egress checks run in the gateway/enforcer, not the adapter.

## Evidence

- `cli.py swarm run --rounds 1 --json`: 23.8s → **0.63s**; identical
  report fields (6 calls, 4 open-weight, all 3 security checks true).
- `pytest tests/test_cli_ai.py`: 5 passed in 3.91s (previously timed out).
- mypy 2.4.1: 0 errors / 297 files; ruff clean.
