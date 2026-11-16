# KEEL-DEVX-018 — Phase 11: Flight-Tape Time-Travel Debugger, OTel GenAI Trace Wedge, 1-Click Trace-to-Eval Promotion & LangGraph Static AST Migrator

- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (3-Agent Parallel Wave: `11A`, `11B`, `11C` + Cold `verify-keelway` Proof + Live GitHub Actions CI)
- **Date**: 2026-11-15
- **Branch**: `main`

## Summary

Implements the top adoption-wedge and IDE-differentiator capabilities from the competitive roadmap: zero-cost local OpenTelemetry GenAI trace ingestion with pre-storage DLP scrubbing, deterministic Flight-Tape counterfactual time-travel forking (reusing cached upstream steps at \$0 cost), 1-click Trace-to-Golden-Eval dataset promotion, and a zero-`eval` static AST `StateGraph` -> KFlow + P-10 migrator across FastAPI `/v1/platform/*`, SQLite WAL, Sovereign CLI, Python/TypeScript/Go SDKs, and the 10-View Dev Tool (`Agents` & `Automation` views).

## Key Deliverables

1. **Flight-Tape Engine & LangGraph Static AST Migrator (`core/platform/flight_tape.py`, `core/platform/langgraph_migrator.py`, `core/api/platform_devx_routes.py`, `core/cli_devx.py`)**:
   - `SQLiteFlightTapeEngine`: Persists OTLP `resourceSpans` / `gen_ai.*` spans in `platform_flight_tapes` & `platform_flight_steps` with DLP secret redaction, supports counterfactual `replay_tape` from `from_step_index` reusing cached upstream steps (`cached_steps_reused`, `cost_delta_usd`), and promotes traces into `platform_eval_dataset_cases`.
   - `LangGraphMigrator`: Pure static Python `ast` + TypeScript parser converting `StateGraph` nodes, conditional edges, cyclic loops (`bounded_loop_policies` with `max_iterations`), and `interrupt()` calls (`p10_gates_injected`) into KFlow blueprints + SDK code while flagging legacy `LLMChain` / `AgentExecutor` anti-patterns.
2. **Tri-SDK Parity & Website `/docs` Sync (`core/sdk/platform_devx_client.py`, `sdk/typescript/src/platformDevx.ts`, `sdk/go/platform_phase11.go`, `website/src/components/docs/DocsHub.tsx`)**:
   - 6-method parity (`ingest_otel_traces`, `list_flight_tapes`, `replay_flight_tape`, `promote_trace_to_eval`, `list_eval_dataset_cases`, `migrate_langgraph_source`).
3. **10-View Dev Tool Panels (`dev-app/src/components/platform/FlightTapeDebuggerPanel.tsx`, `LangGraphMigratorPanel.tsx`)**:
   - Mounted in `Agents` and `Automation` views with full RBAC enforcement, `axe-core` WCAG 2.2 AA compliance, and cold `control-keelway` E2E proof.
