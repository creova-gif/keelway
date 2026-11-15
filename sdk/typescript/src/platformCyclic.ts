/**
 * Keelway Official TypeScript SDK — Phase 15 Bounded Cyclic & Conditional KFlow Sub-Graphs,
 * Saga Compensation & Pre-Run Cost/Privacy Autopilot (`client.platform` / `client.platform.cyclic`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type CyclicLoopCondition = "critic_score_lt" | "retry_on_error" | "until_converged";
export type AutopilotPrivacyPolicy = "hybrid_balanced" | "airgap_strict" | "eu_residency";

export interface CyclicKflowNodeInput {
  id: string;
  agent_id?: string;
  model?: string;
  depends_on?: string[];
  fan_out_items?: number;
  timeout_ms?: number;
  compensation_handler?: string;
  base_cost_usd?: number;
  ttft_ms?: number;
  requires_p10?: boolean;
  [key: string]: unknown;
}

export interface CyclicLoopEdgeInput {
  from_node: string;
  to_node: string;
  condition?: CyclicLoopCondition;
  threshold?: number;
  max_iterations?: number;
  [key: string]: unknown;
}

export interface ValidateCyclicKflowRequest {
  workspace_id?: string;
  workflow_id?: string;
  nodes?: CyclicKflowNodeInput[];
  loop_edges?: CyclicLoopEdgeInput[];
}

export interface CyclicKflowValidationResponse {
  workspace_id: string;
  workflow_id: string;
  valid: boolean;
  node_count: number;
  loop_edge_count: number;
  max_worst_case_steps: number;
  topological_spine: string[];
  compensation_handlers: string[];
  spec_sha256: string;
  [key: string]: unknown;
}

export interface ExecuteCyclicKflowRequest {
  workspace_id?: string;
  workflow_id?: string;
  nodes?: CyclicKflowNodeInput[];
  loop_edges?: CyclicLoopEdgeInput[];
  max_iterations_override?: number;
  critic_threshold?: number;
  fan_out_shards?: number;
  simulate_timeout?: boolean;
  initial_state?: Record<string, unknown>;
  approved_node_ids?: string[];
}

export interface CyclicIterationTraceEntry {
  iteration: number;
  node_id: string;
  agent_id: string;
  model: string;
  critic_score: number;
  shard_count: number;
  status: string;
  cost_usd: number;
  latency_ms: number;
  [key: string]: unknown;
}

export interface CyclicCompensationLogEntry {
  node_id: string;
  handler: string;
  reason: string;
  status: string;
  [key: string]: unknown;
}

export interface CyclicKflowRunRecord {
  run_id: string;
  workspace_id: string;
  workflow_id: string;
  status: string;
  iterations_executed: number;
  max_iterations: number;
  converged: boolean;
  final_critic_score: number;
  critic_threshold: number;
  fan_out_shards: number;
  total_cost_usd: number;
  total_latency_ms: number;
  iteration_trace: CyclicIterationTraceEntry[];
  compensation_log: CyclicCompensationLogEntry[];
  held_node_id: string | null;
  run_sha256: string;
  created_at: string;
  [key: string]: unknown;
}

export interface ListCyclicKflowRunsParams {
  workspace_id?: string;
  workflow_id?: string;
  limit?: number;
}

export interface CyclicKflowRunListResponse {
  workspace_id: string;
  count: number;
  runs: CyclicKflowRunRecord[];
  [key: string]: unknown;
}

export interface SimulateKflowAutopilotRequest {
  workspace_id?: string;
  workflow_id?: string;
  nodes?: CyclicKflowNodeInput[];
  loop_edges?: CyclicLoopEdgeInput[];
  budget_cap_usd?: number;
  privacy_policy?: AutopilotPrivacyPolicy;
  expected_loop_multiplier?: number;
}

export interface AutopilotNodePlanEntry {
  node_id: string;
  original_model: string;
  selected_model: string;
  rewritten: boolean;
  reason: string;
  p50_cost_usd: number;
  p95_cost_usd: number;
  data_boundary: string;
  [key: string]: unknown;
}

export interface AutopilotSimulationRecord {
  simulation_id: string;
  workspace_id: string;
  workflow_id: string;
  privacy_policy: AutopilotPrivacyPolicy;
  budget_cap_usd: number;
  expected_loop_multiplier?: number;
  baseline_p50_usd: number;
  baseline_p95_usd: number;
  baseline_ttft_ms: number;
  optimized_p50_usd: number;
  optimized_p95_usd: number;
  savings_pct: number;
  optimized_ttft_ms: number;
  privacy_compliant: boolean;
  violations_resolved: number;
  node_plan: AutopilotNodePlanEntry[];
  simulation_sha256: string;
  created_at: string;
  [key: string]: unknown;
}

export interface ListAutopilotSimulationsParams {
  workspace_id?: string;
  workflow_id?: string;
  limit?: number;
}

export interface AutopilotSimulationListResponse {
  workspace_id: string;
  count: number;
  simulations: AutopilotSimulationRecord[];
  [key: string]: unknown;
}

function assertPrivacyPolicy(policy: AutopilotPrivacyPolicy): AutopilotPrivacyPolicy {
  switch (policy) {
    case "hybrid_balanced":
    case "airgap_strict":
    case "eu_residency":
      return policy;
    default: {
      const _exhaustive: never = policy;
      throw new Error(`Invalid privacy_policy '${String(_exhaustive)}'.`);
    }
  }
}

function encodePathSeg(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

function buildGraphBody(req: ValidateCyclicKflowRequest): Record<string, unknown> {
  const workflowId = (req.workflow_id ?? "WF-CYCLIC-01").trim();
  if (!workflowId) throw new Error("workflow_id must be non-empty.");
  const body: Record<string, unknown> = {
    workspace_id: req.workspace_id ?? "default",
    workflow_id: workflowId,
  };
  if (req.nodes !== undefined) body.nodes = req.nodes;
  if (req.loop_edges !== undefined) body.loop_edges = req.loop_edges;
  return body;
}

function buildListQuery(params: { workspace_id?: string; workflow_id?: string; limit?: number }): Record<string, string> {
  const limit = params.limit ?? 25;
  if (!Number.isInteger(limit) || limit < 1) throw new Error("limit must be >= 1.");
  const query: Record<string, string> = {
    workspace_id: params.workspace_id ?? "default",
    limit: String(limit),
  };
  if (params.workflow_id !== undefined && params.workflow_id.trim() !== "") {
    query.workflow_id = params.workflow_id.trim();
  }
  return query;
}

export class PlatformCyclicClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public validateCyclicKflow(
    req: ValidateCyclicKflowRequest = {},
    options?: RequestOptions,
  ): Promise<CyclicKflowValidationResponse> {
    return this.requestJson("POST", "/v1/platform/kflow/cyclic/validate", { body: buildGraphBody(req), options });
  }

  public executeCyclicKflow(
    req: ExecuteCyclicKflowRequest = {},
    options?: RequestOptions,
  ): Promise<CyclicKflowRunRecord> {
    const body = buildGraphBody(req);
    const threshold = req.critic_threshold ?? 0.85;
    if (threshold < 0 || threshold > 1) throw new Error("critic_threshold must be between 0.0 and 1.0.");
    if (req.max_iterations_override !== undefined) {
      if (!Number.isInteger(req.max_iterations_override) || req.max_iterations_override < 1 || req.max_iterations_override > 10) {
        throw new Error("max_iterations_override must be between 1 and 10.");
      }
      body.max_iterations_override = req.max_iterations_override;
    }
    if (req.fan_out_shards !== undefined) {
      if (!Number.isInteger(req.fan_out_shards) || req.fan_out_shards < 1 || req.fan_out_shards > 16) {
        throw new Error("fan_out_shards must be between 1 and 16.");
      }
      body.fan_out_shards = req.fan_out_shards;
    }
    body.critic_threshold = threshold;
    body.simulate_timeout = req.simulate_timeout ?? false;
    if (req.initial_state !== undefined) body.initial_state = req.initial_state;
    if (req.approved_node_ids !== undefined) body.approved_node_ids = req.approved_node_ids;
    return this.requestJson("POST", "/v1/platform/kflow/cyclic/execute", { body, options });
  }

  public listCyclicKflowRuns(
    params: ListCyclicKflowRunsParams = {},
    options?: RequestOptions,
  ): Promise<CyclicKflowRunListResponse> {
    return this.requestJson("GET", "/v1/platform/kflow/cyclic/runs", { query: buildListQuery(params), options });
  }

  public getCyclicKflowRun(
    runId: string,
    workspaceId: string = "default",
    options?: RequestOptions,
  ): Promise<CyclicKflowRunRecord> {
    const seg = encodePathSeg(runId, "run_id");
    const query: Record<string, string> = { workspace_id: workspaceId || "default" };
    return this.requestJson("GET", `/v1/platform/kflow/cyclic/runs/${seg}`, { query, options });
  }

  public simulateKflowAutopilot(
    req: SimulateKflowAutopilotRequest = {},
    options?: RequestOptions,
  ): Promise<AutopilotSimulationRecord> {
    const body = buildGraphBody(req);
    const budgetCap = req.budget_cap_usd ?? 0.15;
    if (budgetCap < 0) throw new Error("budget_cap_usd must be >= 0.0.");
    const multiplier = req.expected_loop_multiplier ?? 2;
    if (!Number.isInteger(multiplier) || multiplier < 1) throw new Error("expected_loop_multiplier must be >= 1.");
    body.budget_cap_usd = budgetCap;
    body.privacy_policy = assertPrivacyPolicy(req.privacy_policy ?? "hybrid_balanced");
    body.expected_loop_multiplier = multiplier;
    return this.requestJson("POST", "/v1/platform/kflow/autopilot/simulate", { body, options });
  }

  public listKflowAutopilotSimulations(
    params: ListAutopilotSimulationsParams = {},
    options?: RequestOptions,
  ): Promise<AutopilotSimulationListResponse> {
    return this.requestJson("GET", "/v1/platform/kflow/autopilot/simulations", { query: buildListQuery(params), options });
  }
}

export { PlatformCyclicClient as PlatformCyclicDelegate };
