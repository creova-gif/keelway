/**
 * Keelway Official TypeScript SDK — Phase 12 Golden-Thread Bidirectional KFlow Studio,
 * Sandbox Blast-Radius Radar & Prompt Regression Gate (`client.platform` / `client.platform.studio`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type StudioKflowDirection = "code_to_graph" | "graph_to_code";
export type StudioKflowLanguage = "python" | "typescript";
export type PromptGateVerdict = "PASS" | "BLOCK";
export interface StudioKflowNodeInput {
    id: string;
    label?: string;
    agent_id?: string;
    depends_on?: string[];
    requires_p10?: boolean;
    line_start?: number;
    line_end?: number;
    wave?: number;
    x?: number;
    y?: number;
    [key: string]: unknown;
}
export interface StudioKflowNode {
    id: string;
    label: string;
    agent_id: string;
    depends_on: string[];
    requires_p10: boolean;
    line_start: number;
    line_end: number;
    wave: number;
    x: number;
    y: number;
    [key: string]: unknown;
}
export interface StudioKflowEdge {
    from: string;
    to: string;
    is_cycle: boolean;
}
export interface StudioKflowCycleEdge {
    from: string;
    to: string;
}
export interface SyncKflowStudioRequest {
    workspace_id?: string;
    direction?: StudioKflowDirection;
    language?: StudioKflowLanguage;
    workflow_id?: string;
    source_code?: string;
    nodes?: StudioKflowNodeInput[];
    persist?: boolean;
}
export interface StudioKflowSyncResult {
    workspace_id: string;
    workflow_id: string;
    direction: string;
    language: string;
    nodes: StudioKflowNode[];
    edges: StudioKflowEdge[];
    cycle_back_edges: StudioKflowCycleEdge[];
    p10_locked_nodes: string[];
    source_code: string;
    persisted: boolean;
    sync_sha256: string;
    [key: string]: unknown;
}
export interface RecordBlastRadiusRequest {
    workspace_id?: string;
    trace_id?: string;
    workflow_id?: string;
    fs_reads?: string[];
    fs_writes?: string[];
    blocked_paths?: string[];
    egress_attempts?: number;
    blocked_egress_hosts?: string[];
    p10_gates_triggered?: number;
    seatbelted?: boolean;
}
export interface BlastRadiusAuditRecord {
    audit_id: string;
    workspace_id: string;
    trace_id?: string | null;
    workflow_id?: string | null;
    fs_reads: string[];
    fs_writes: string[];
    blocked_paths: string[];
    egress_attempts: number;
    blocked_egress_hosts: string[];
    p10_gates_triggered: number;
    seatbelted: boolean;
    zero_unapproved_egress: boolean;
    syscalls_audited: number;
    risk_tier: string;
    audit_sha256: string;
    recorded_at: string;
    [key: string]: unknown;
}
export interface ListBlastRadiusAuditsParams {
    workspace_id?: string;
    trace_id?: string;
    limit?: number;
}
export interface BlastRadiusAuditListResponse {
    workspace_id: string;
    count: number;
    audits: BlastRadiusAuditRecord[];
    [key: string]: unknown;
}
export interface EvaluatePromptGateRequest {
    workspace_id?: string;
    candidate_prompt_version: string;
    candidate_model_id: string;
    candidate_prompt_text?: string;
    required_json_keys?: string[];
    min_pass_rate?: number;
}
export interface PromptGateEvaluationResult {
    gate_run_id: string;
    workspace_id: string;
    candidate_prompt_version: string;
    candidate_model_id: string;
    verdict: PromptGateVerdict;
    cases_evaluated: number;
    passed_cases: number;
    pass_rate: number;
    min_pass_rate: number;
    schema_valid_count: number;
    dlp_violations: number;
    cost_delta_usd: number;
    dataset_source: string;
    gate_sha256: string;
    evaluated_at: string;
    [key: string]: unknown;
}
export interface ListPromptGateRunsParams {
    workspace_id?: string;
    limit?: number;
}
export interface PromptGateRunListResponse {
    workspace_id: string;
    count: number;
    runs: PromptGateEvaluationResult[];
    [key: string]: unknown;
}
export declare class PlatformStudioClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    syncKflowStudio(payload?: SyncKflowStudioRequest, options?: RequestOptions): Promise<StudioKflowSyncResult>;
    recordBlastRadius(payload?: RecordBlastRadiusRequest, options?: RequestOptions): Promise<BlastRadiusAuditRecord>;
    listBlastRadiusAudits(paramsOrWorkspaceId?: ListBlastRadiusAuditsParams | string, options?: RequestOptions): Promise<BlastRadiusAuditListResponse>;
    evaluatePromptGate(payload: EvaluatePromptGateRequest, options?: RequestOptions): Promise<PromptGateEvaluationResult>;
    listPromptGateRuns(paramsOrWorkspaceId?: ListPromptGateRunsParams | string, options?: RequestOptions): Promise<PromptGateRunListResponse>;
}
export { PlatformStudioClient as PlatformStudioDelegate };
//# sourceMappingURL=platformStudio.d.ts.map