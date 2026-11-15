/**
 * Keelway Official TypeScript SDK — Phase 14 Live Step-Through Debugger,
 * Conditional Gutter Breakpoints, DLP-Guarded State Mutation & 4D Routing CodeLens
 * (`client.platform` / `client.platform.debugger`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type DebuggerConditionType = "always" | "cost_usd_gt" | "hybrid_score_lt" | "before_shell_tool" | "before_p10_gate" | "line_match";
export type DebuggerStepAction = "step_over" | "step_into" | "continue" | "mutate_state";
export interface SetBreakpointRequest {
    workspace_id?: string;
    workflow_id?: string;
    node_id?: string;
    file_path?: string;
    line_number?: number;
    condition_type?: DebuggerConditionType;
    threshold?: number;
    enabled?: boolean;
    label?: string;
}
export interface DebuggerBreakpointRecord {
    breakpoint_id: string;
    workspace_id: string;
    workflow_id: string;
    node_id: string | null;
    file_path: string;
    line_number: number | null;
    condition_type: DebuggerConditionType;
    threshold: number | null;
    enabled: boolean;
    label: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ListBreakpointsParams {
    workspace_id?: string;
    workflow_id?: string;
}
export interface DebuggerBreakpointListResponse {
    workspace_id: string;
    count: number;
    breakpoints: DebuggerBreakpointRecord[];
    [key: string]: unknown;
}
export interface DeleteBreakpointParams {
    workspace_id?: string;
}
export interface DeleteBreakpointResponse {
    deleted: boolean;
    breakpoint_id: string;
    workspace_id: string;
    [key: string]: unknown;
}
export interface DebuggerStepInput {
    node_id?: string;
    agent_id?: string;
    tool_name?: string;
    cost_usd?: number;
    hybrid_score?: number;
    requires_p10?: boolean;
    line_number?: number;
    variables?: Record<string, unknown>;
    [key: string]: unknown;
}
export interface StartDebugSessionRequest {
    workspace_id?: string;
    workflow_id?: string;
    steps?: DebuggerStepInput[];
    initial_state?: Record<string, unknown>;
}
export interface DebuggerSessionRecord {
    session_id: string;
    workspace_id: string;
    workflow_id: string;
    status: string;
    current_step_index: number;
    step_depth: number;
    total_steps: number;
    hit_breakpoint_id: string | null;
    hit_reason: string | null;
    active_step: Record<string, unknown>;
    active_frame: Record<string, unknown>;
    variables: Record<string, unknown>;
    call_stack: Array<Record<string, unknown>>;
    mutation_count: number;
    mutations: Array<Record<string, unknown>>;
    frame_sha256: string;
    updated_at: string;
    [key: string]: unknown;
}
export interface ListDebugSessionsParams {
    workspace_id?: string;
    limit?: number;
}
export interface DebuggerSessionListResponse {
    workspace_id: string;
    count: number;
    sessions: DebuggerSessionRecord[];
    [key: string]: unknown;
}
export interface StepDebugSessionRequest {
    workspace_id?: string;
    action?: DebuggerStepAction;
    state_patch?: Record<string, unknown>;
}
export interface GetDebuggerCodelensParams {
    workspace_id?: string;
    workflow_id?: string;
    file_path?: string;
    source_code?: string;
}
export interface DebuggerCodelensItem {
    symbol: string;
    file_path: string;
    line_start: number;
    line: number;
    model_checkpoint: string;
    p50_ms: number;
    p50_latency_ms: number;
    avg_cost_usd: number;
    provenance_4d: string;
    attached_breakpoints: number;
    [key: string]: unknown;
}
export interface DebuggerCodelensResponse {
    workspace_id: string;
    workflow_id: string;
    file_path: string;
    vscode_attach_uri: string;
    cursor_attach_uri: string;
    bridge: Record<string, unknown>;
    lenses: DebuggerCodelensItem[];
    [key: string]: unknown;
}
export declare class PlatformDebuggerClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    setBreakpoint(payload?: SetBreakpointRequest, options?: RequestOptions): Promise<DebuggerBreakpointRecord>;
    listBreakpoints(paramsOrWorkspaceId?: ListBreakpointsParams | string, options?: RequestOptions): Promise<DebuggerBreakpointListResponse>;
    deleteBreakpoint(breakpointId: string, paramsOrWorkspaceId?: DeleteBreakpointParams | string, options?: RequestOptions): Promise<DeleteBreakpointResponse>;
    startDebugSession(payload?: StartDebugSessionRequest, options?: RequestOptions): Promise<DebuggerSessionRecord>;
    listDebugSessions(paramsOrWorkspaceId?: ListDebugSessionsParams | string, options?: RequestOptions): Promise<DebuggerSessionListResponse>;
    stepDebugSession(sessionId: string, payloadOrAction?: StepDebugSessionRequest | DebuggerStepAction, options?: RequestOptions): Promise<DebuggerSessionRecord>;
    getDebuggerCodelens(paramsOrWorkspaceId?: GetDebuggerCodelensParams | string, options?: RequestOptions): Promise<DebuggerCodelensResponse>;
}
export { PlatformDebuggerClient as PlatformDebuggerDelegate };
//# sourceMappingURL=platformDebugger.d.ts.map