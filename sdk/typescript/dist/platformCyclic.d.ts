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
export declare class PlatformCyclicClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    validateCyclicKflow(req?: ValidateCyclicKflowRequest, options?: RequestOptions): Promise<CyclicKflowValidationResponse>;
    executeCyclicKflow(req?: ExecuteCyclicKflowRequest, options?: RequestOptions): Promise<CyclicKflowRunRecord>;
    listCyclicKflowRuns(params?: ListCyclicKflowRunsParams, options?: RequestOptions): Promise<CyclicKflowRunListResponse>;
    getCyclicKflowRun(runId: string, workspaceId?: string, options?: RequestOptions): Promise<CyclicKflowRunRecord>;
    simulateKflowAutopilot(req?: SimulateKflowAutopilotRequest, options?: RequestOptions): Promise<AutopilotSimulationRecord>;
    listKflowAutopilotSimulations(params?: ListAutopilotSimulationsParams, options?: RequestOptions): Promise<AutopilotSimulationListResponse>;
}
export { PlatformCyclicClient as PlatformCyclicDelegate };
//# sourceMappingURL=platformCyclic.d.ts.map