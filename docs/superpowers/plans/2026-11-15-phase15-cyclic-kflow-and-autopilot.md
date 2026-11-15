# Phase 15 Implementation Plan (`KEEL-KFLOW-022`): Bounded Cyclic & Conditional KFlow Sub-Graphs + Pre-Run Cost/Privacy Autopilot

> **For agentic workers:** Follow `subagent-driven-development` with strict non-overlapping file ownership across `15A` (SQLite WAL Cyclic KFlow + Autopilot + OpenAPI 3.1 + CLI), `15B` (Tri-Language SDK Parity), and `15C` (`:7420/app` Cyclic KFlow & Autopilot Studio UI), followed by Lead integration, OpenAPI/facts export, and cold headless Chromium E2E proof.

## Exact Wire Contract (`/v1/platform/kflow/*`)

All 6 new routes live under `/v1/platform/kflow` (`core/api/platform_cyclic_routes.py`, mounted in `core/main.py` -> `286` total OpenAPI 3.1 paths):

1. `POST /v1/platform/kflow/cyclic/validate` (`read:all`):
   - Request: `{ workspace_id, workflow_id, nodes, loop_edges }`
   - Response: `{ workspace_id, workflow_id, valid: true, node_count, loop_edge_count, max_worst_case_steps, topological_spine, compensation_handlers, spec_sha256 }`
   - Rejects (`HTTP 422`): unbounded cycles (`max_iterations < 1` or `max_iterations > 10`), unknown `from_node`/`to_node`, invalid `condition` (must be `"critic_score_lt" | "retry_on_error" | "until_converged"`), `fan_out_items < 1` or `> 16`, or unguarded graph cycles not declared in `loop_edges`.

2. `POST /v1/platform/kflow/cyclic/execute` (`workflows:run`; `p10:approve` when `approved_node_ids` is non-empty):
   - Request: `{ workspace_id, workflow_id, nodes, loop_edges, max_iterations_override?, critic_threshold?, fan_out_shards?, simulate_timeout?, initial_state?, approved_node_ids? }`
   - Response (`CyclicKFlowRunRecord`):
     `{ run_id, workspace_id, workflow_id, status ("CONVERGED" | "COMPENSATED" | "HELD_P10"), iterations_executed, max_iterations, converged, final_critic_score, critic_threshold, fan_out_shards, total_cost_usd, total_latency_ms, iteration_trace: [{ iteration, node_id, agent_id, critic_score, shard_count, status, cost_usd, latency_ms }], compensation_log: [{ node_id, handler, reason, status }], held_node_id, run_sha256, created_at }`
   - Rejects (`HTTP 422`): DLP secret patterns (`sk-...`, `AKIA...`, `ghp_...`, `PRIVATE KEY`) in `initial_state` or invalid cycle bounds before SQLite persistence.

3. `GET /v1/platform/kflow/cyclic/runs?workspace_id=default&workflow_id=...&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, runs: CyclicKFlowRunRecord[] }`

4. `GET /v1/platform/kflow/cyclic/runs/{run_id}?workspace_id=default` (`read:all`):
   - Response: `CyclicKFlowRunRecord` (`404` if missing).

5. `POST /v1/platform/kflow/autopilot/simulate` (`workflows:run`):
   - Request: `{ workspace_id, workflow_id, nodes?, loop_edges?, budget_cap_usd (default 0.15), privacy_policy ("hybrid_balanced" | "airgap_strict" | "eu_residency"), expected_loop_multiplier? }`
   - Response (`AutopilotSimulationRecord`):
     `{ simulation_id, workspace_id, workflow_id, privacy_policy, budget_cap_usd, baseline_p50_usd, baseline_p95_usd, optimized_p50_usd, optimized_p95_usd, savings_pct, baseline_ttft_ms, optimized_ttft_ms, privacy_compliant, violations_resolved, node_plan: [{ node_id, original_model, selected_model, rewritten, reason, p50_cost_usd, p95_cost_usd, data_boundary }], simulation_sha256, created_at }`

6. `GET /v1/platform/kflow/autopilot/simulations?workspace_id=default&workflow_id=...&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, simulations: AutopilotSimulationRecord[] }`

## Parallel Workstreams & Strict File Ownership

- **Workstream 15A (`core/` & `tests/test_phase15_cyclic_kflow_and_cli.py`)**:
  - `core/platform/kflow_cyclic_autopilot.py` (`< 480` lines)
  - `core/api/platform_cyclic_routes.py` (`< 260` lines)
  - `core/cli_cyclic.py` (`< 240` lines)
  - `core/main.py` & `core/cli_runtime.py`
  - `tests/test_phase14_step_debugger_and_cli.py` & `tests/test_phase14_sdk_and_vscode_bridge.py` (`== 280` -> `>= 280`, `== 22` -> `>= 22`)
  - `tests/test_phase15_cyclic_kflow_and_cli.py` (`< 380` lines)

- **Workstream 15B (Tri-SDK Parity: Python, TypeScript, Go)**:
  - `core/sdk/platform_cyclic_client.py` (`< 260` lines) + `core/sdk/platform_runtime_client.py`
  - `sdk/typescript/src/platformCyclic.ts` (`< 310` lines) + `sdk/typescript/src/platform.ts` + `sdk/typescript/src/index.ts` + `sdk/typescript/package.json` + `sdk/typescript/tests/platform_phase15.test.mjs` (`< 240` lines)
  - `sdk/go/platform_phase15.go` (`< 270` lines) + `sdk/go/platform_phase15_test.go` (`< 250` lines)

- **Workstream 15C (`dev-app/src/*`)**:
  - `dev-app/src/lib/platformCyclicApi.ts` (`< 280` lines)
  - `dev-app/src/components/platform/CyclicKflowAndAutopilotPanel.tsx` (`< 450` lines)
  - `dev-app/src/components/platform/AutomationAndOpsViews.tsx`
  - `dev-app/src/__tests__/phase15-cyclic-kflow-autopilot.test.tsx` (`< 320` lines)

- **Lead Integration**:
  - Export `website/openapi.json` & `website/public/openapi.json` (`286` paths)
  - Update `website/product-facts.json` & `website/public/product-facts.json` (`23` features) + `DocsHub.tsx` + `CommandPalette.tsx` + `search-index/route.ts`
  - Create `tests/test_phase15_sdk_and_website_sync.py` & update `scripts/verify_engineering_gates.sh`
  - Build `core/dev_app_dist/` & `sdk/typescript/dist/`, run all `8/8` gates + website build + cold Chromium E2E proof, and commit `KEEL-KFLOW-022`.
