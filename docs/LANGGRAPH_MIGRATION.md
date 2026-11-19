# LangGraph → KFlow Migration

How `core/platform/langgraph_migrator.py` converts a LangGraph `StateGraph`
into a Keelway KFlow DAG blueprint, what is preserved at runtime, and what is
dropped. The migrator is a **static, zero-execution** analyzer: source code is
parsed with `ast` (Python) or regex (TypeScript) and is never executed.

## Surfaces

| Surface | Command / route |
|---|---|
| REST migrate | `POST /v1/platform/migrate/langgraph` (`agents:dispatch`) |
| REST execute | `POST /v1/platform/automation/workflows/execute` (`workflows:run`; `p10:approve` required to pass `approved_node_ids`) |
| REST run history | `GET /v1/platform/automation/runs` |
| CLI migrate | `keelway migrate-langgraph --file graph.py --json` |
| CLI execute | `keelway kflow execute --workflow-id <wf> --nodes-json <blueprint> [--approve-node <id>]` |

## End-to-end contract

1. Migrate: returns `kflow_blueprint` — a topologically ordered node list
   (`id`, `label`, `agent_id`, `kind`, `depends_on`, `requires_p10`,
   optional `bounded_retry`).
2. Execute: pass the blueprint verbatim as `nodes` to the execute route.
   Unapproved P-10 nodes pause the run (`status: "awaiting_p10"`,
   `held_node_id` set); downstream nodes are reported `pending`.
3. Approve: re-execute with `approved_node_ids: ["<gate>"]` — requires the
   `p10:approve` permission (owner, admin, operator). The run completes and
   each node records a `sha256` output digest chained to its upstreams.
4. Every run is persisted to `platform_kflow_runs` (SQLite WAL) with a
   `receipt_sha256`; `GET /v1/platform/automation/runs` lists them per
   workspace.

## Construct mapping

| LangGraph construct | KFlow result |
|---|---|
| `graph.add_node(id, fn)` / `.addNode` | blueprint node; handler name kept in `nodes[].handler` |
| `graph.add_edge(a, b)` | `b.depends_on = [a]` (START/END edges dropped) |
| `add_conditional_edges` with static map | forward targets → deps; backward targets → `bounded_retry` + `is_back_edge` edge annotation |
| handler calling `interrupt()` / throwing `NodeInterrupt` | `kind: p10_human_gate`, `requires_p10: true`, `agent_id: p10-governance-gate` |
| Cycle in the graph | `bounded_loop_policies` (max_iterations 5, timeout 60s) + `is_back_edge` edge flags |

## Dropped / advisory (honest limits)

- **`bounded_retry` and `kind` are blueprint metadata only.** The execution
  engine (`KFlowDagEngine._normalize_nodes`) keeps `id`, `label`, `agent_id`,
  `depends_on`, `requires_p10` and discards the rest — a migrated cyclic graph
  is linearized and each node runs exactly once per run. Bounded-loop
  *enforcement* is not yet implemented in the executor.
- **Handler bodies are not migrated.** Node logic (LLM calls, tools, state
  mutation) must be re-implemented against Keelway tools; the blueprint carries
  structure only. `generated_sdk_code` is a starting scaffold, not a runnable
  port.
- **State schemas, reducers, checkpointers, subgraphs, streaming** are not
  represented in the blueprint.
- **Dynamic graph construction** (nodes added in loops/conditionals,
  non-literal edge maps) may be missed — the parser only sees static calls.
- Sources with no detectable `StateGraph`/`add_node` calls are refused with
  `400 "No LangGraph StateGraph nodes detected"`.

## Legacy warnings

`legacy_warnings` flags LangChain-era anti-patterns (`LLMChain`,
`AgentExecutor`, `ConversationChain`, `initialize_agent`, `langchain.chains`
imports) with suggested KFlow/KBrain replacements. Warnings do not block
migration.
