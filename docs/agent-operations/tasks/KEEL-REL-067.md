# KEEL-REL-067 — LangGraph Adapter: Complete + Verify End-to-End (OD-4)

| Field | Value |
|---|---|
| **Status** | `READY_FOR_REVIEW` |
| **Category** | `RELEASE / ADAPTERS` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `feature/KEEL-REL-067-langgraph-adapter` |

## Objective
Per OD-4, LangGraph is first on the adapter roadmap because
`core/platform/langgraph_migrator.py` already exists.

## Findings (orient)
The adapter was ~90% built: `POST /v1/platform/migrate/langgraph` emits a
`kflow_blueprint` whose shape is the native input of
`KFlowDagEngine.execute_dag` (`POST /v1/platform/automation/workflows/execute`),
which enforces `p10:approve` RBAC on `approved_node_ids`, pauses on
`awaiting_p10`, and persists receipted runs to SQLite WAL. The real gaps were:

1. Graphless source returned a hollow `200` with empty blueprint — now refuses
   `400 "No LangGraph StateGraph nodes detected"`.
2. No public-surface E2E proof (migrate → execute → approve → receipt) —
   engine-level compat was tested but the HTTP/CLI chain was not.
3. No docs stating what maps vs what is dropped.

## Acceptance criteria
- [x] Real LangGraph graph imports into a governed run through `/v1` —
      `test_langgraph_import_to_governed_run_e2e` drives
      migrate → execute → `awaiting_p10` → approve → `completed` → persisted
      receipts; no mocks.
- [x] P-10 gates / workspace RBAC / evidence identical to native runs —
      builder denied 403 on `approved_node_ids`, operator allowed; run
      receipts + `platform_kflow_runs` rows verified via
      `GET /v1/platform/automation/runs`.
- [x] Tests: graph→task translation (existing), pause/resume (new E2E),
      RBAC-gated approval (new), malformed + graphless refusals (new).
- [x] Honest docs: `docs/LANGGRAPH_MIGRATION.md` — construct map +
      dropped/advisory list (`bounded_retry`, `kind`, handlers, state
      schemas are NOT runtime-enforced today).

## Files modified
- `core/platform/langgraph_migrator.py`: +5 — refuse source with zero parsed
  StateGraph nodes (`ValueError` → 400 on the route).
- `tests/test_phase11_flight_tape_otel_and_langgraph_migrator.py`: new
  `test_langgraph_import_to_governed_run_e2e` (HTTP journey incl. RBAC denial)
  + CLI chain appended to existing CLI test (migrate → `kflow execute` →
  `--approve-node` → `kflow runs`).
- `docs/LANGGRAPH_MIGRATION.md`: new — surfaces, construct map,
  dropped/advisory limits.

## Tests executed
- `pytest tests/test_phase11_flight_tape_otel_and_langgraph_migrator.py
  tests/test_phase8_kflow_crdt_and_sbom.py -q` → **10 passed**
- `ruff check core/platform/langgraph_migrator.py
  tests/test_phase11_flight_tape_otel_and_langgraph_migrator.py` → clean

## Known limits (documented, not bugs)
- `bounded_retry` and `kind` are blueprint metadata; `KFlowDagEngine` executes
  each node once per run — bounded-loop *enforcement* is future work.
- Handler bodies are not ported; `generated_sdk_code` is a scaffold.
- Run evidence = `receipt_sha256` + WAL rows, not OTel tape entries.

## Next recommended action
Merge on green CI → close task `VERIFIED_COMPLETE`. Next queued: REL-068
(IdP interop), OD-3 `approval_rules` carve-out evaluation.
