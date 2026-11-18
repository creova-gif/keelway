/**
 * Keelway Loopback Debugger Bridge Client for VS Code & Cursor Extension Host.
 * Authenticates via Bearer token and strips any browser Origin header to preserve zero-CSRF loopback posture.
 */
export type AttachScheme = "vscode" | "cursor";
export type DebugStepAction = "step_over" | "step_into" | "continue" | "mutate_state";
export type HarnessTicketDecision = "APPROVED" | "DENIED";
export type BridgeDistillationPromotionVerdict = "PROMOTE_TO_OPENCORE" | "NEEDS_MORE_PAIRS" | "HOLD_ON_FRONTIER";
export type BridgeMcpLockSimulateMode = "clean" | "rug_pull" | "poisoning";
export type BridgeMcpLockVerificationVerdict = "LOCK_VERIFIED" | "DRIFT_RUG_PULL_BLOCKED" | "POISONING_BLOCKED";
export interface BridgeVerifyMcpLockfileOptions {
    workspaceId?: string;
    lockfileId?: string;
    simulateMode?: BridgeMcpLockSimulateMode;
}
export interface BridgeMcpLockVerificationRecord {
    verification_id: string;
    lockfile_id: string;
    workspace_id: string;
    verdict: BridgeMcpLockVerificationVerdict;
    expected_merkle_root_sha256: string;
    observed_merkle_root_sha256: string;
    drifted_tools: string[];
    poisoning_findings: string[];
    dlp_redactions: number;
    verification_sha256: string;
    verified_at: string;
    [key: string]: unknown;
}
export interface BridgeDistillationPromotionOptions {
    workspaceId?: string;
    taskTag?: string;
    targetLocalModel?: string;
    minPairs?: number;
    minAvgParity?: number;
    monthlyRequestVolume?: number;
}
export interface BridgeDistillationPromotionEvaluation {
    evaluation_id: string;
    workspace_id: string;
    task_tag: string;
    target_local_model: string;
    verdict: BridgeDistillationPromotionVerdict;
    pair_count: number;
    min_pairs: number;
    avg_parity_score: number;
    min_avg_parity: number;
    avg_frontier_cost_usd: number;
    monthly_request_volume: number;
    projected_monthly_savings_usd: number;
    recommendation: string;
    gate_sha256: string;
    evaluated_at: string;
    [key: string]: unknown;
}
export interface BridgeHarnessTicketRecord {
    ticket_id: string;
    workspace_id: string;
    agent_host: string;
    tool_name: string;
    scrubbed_command: string;
    command_sha256: string;
    status: "PENDING" | "APPROVED" | "DENIED" | "CONSUMED";
    reviewer?: string | null;
    decision_reason?: string | null;
    created_at?: string;
    decided_at?: string | null;
    consumed_at?: string | null;
    ticket_sha256?: string;
    [key: string]: unknown;
}
export interface AttachTarget {
    readonly scheme: AttachScheme;
    readonly port: number;
    readonly baseUrl: string;
    readonly workspaceId: string;
    readonly workflowId: string;
    readonly sessionId?: string;
}
export interface BridgeBreakpointRecord {
    breakpoint_id: string;
    workspace_id: string;
    workflow_id: string;
    node_id?: string | null;
    file_path?: string;
    line_number?: number | null;
    condition_type?: string;
    condition?: string | null;
    threshold?: number | null;
    enabled: boolean;
    label?: string;
    created_at?: string;
    [key: string]: unknown;
}
export interface BridgeDebugSession {
    session_id: string;
    workspace_id: string;
    workflow_id: string;
    status: string;
    current_step_index?: number;
    step_index?: number;
    step_depth?: number;
    total_steps?: number;
    hit_breakpoint_id?: string | null;
    hit_reason?: string | null;
    active_step?: {
        node_id?: string;
        agent_id?: string;
        tool_name?: string;
        line_number?: number;
        [key: string]: unknown;
    };
    current_node_id?: string | null;
    variables?: Record<string, unknown>;
    state?: Record<string, unknown>;
    call_stack?: Array<Record<string, unknown>>;
    mutation_count?: number;
    frame_sha256?: string;
    [key: string]: unknown;
}
export interface BridgeCodelensItem {
    symbol?: string;
    node_id?: string;
    file_path?: string;
    line_start?: number;
    model_checkpoint?: string;
    model_id?: string;
    p50_ms?: number;
    p50_latency_ms?: number;
    avg_cost_usd?: number;
    cost_usd?: number;
    provenance_4d?: string;
    zero_egress?: boolean;
    attached_breakpoints?: number;
    breakpoint_count?: number;
    [key: string]: unknown;
}
export interface BridgeClientOptions {
    baseUrl?: string;
    workspaceId?: string;
    workflowId?: string;
    apiToken?: string;
    getToken?: () => PromiseLike<string | undefined> | string | undefined;
    fetchImpl?: typeof fetch;
}
export declare class BridgeHttpError extends Error {
    readonly status: number;
    readonly detail: string;
    readonly payload?: unknown | undefined;
    constructor(status: number, detail: string, payload?: unknown | undefined);
}
export declare function parseAttachUri(uriString: string): AttachTarget;
export declare class KeelwayBridgeClient {
    private baseUrl;
    private workspaceId;
    private workflowId;
    private apiToken;
    private readonly getTokenFn;
    private readonly fetchFn;
    constructor(options?: BridgeClientOptions);
    getTarget(): {
        baseUrl: string;
        workspaceId: string;
        workflowId: string;
    };
    configureTarget(target: {
        baseUrl?: string;
        workspaceId?: string;
        workflowId?: string;
        apiToken?: string;
    }): void;
    private request;
    setBreakpoint(payload: {
        node_id?: string;
        workflow_id?: string;
        workspace_id?: string;
        condition_type?: string;
        threshold?: number;
        condition?: string;
        enabled?: boolean;
        file_path?: string;
        line_number?: number;
        label?: string;
    }): Promise<BridgeBreakpointRecord>;
    listBreakpoints(params?: {
        workspace_id?: string;
        workflow_id?: string;
    }): Promise<{
        workspace_id: string;
        count: number;
        breakpoints: BridgeBreakpointRecord[];
    }>;
    deleteBreakpoint(breakpointId: string, workspaceId?: string): Promise<{
        deleted: boolean;
        breakpoint_id: string;
        workspace_id: string;
    }>;
    startDebugSession(payload?: {
        workspace_id?: string;
        workflow_id?: string;
        steps?: Array<Record<string, unknown>>;
        initial_state?: Record<string, unknown>;
    }): Promise<BridgeDebugSession>;
    listDebugSessions(params?: {
        workspace_id?: string;
        limit?: number;
    }): Promise<{
        workspace_id: string;
        count: number;
        sessions: BridgeDebugSession[];
    }>;
    stepDebugSession(sessionId: string, payload: {
        action: DebugStepAction;
        workspace_id?: string;
        state_patch?: Record<string, unknown>;
        mutate_state?: Record<string, unknown>;
    }): Promise<BridgeDebugSession>;
    getCodelens(params?: {
        workspace_id?: string;
        workflow_id?: string;
        file_path?: string;
    }): Promise<{
        workspace_id: string;
        workflow_id?: string;
        vscode_attach_uri?: string;
        cursor_attach_uri?: string;
        lenses?: BridgeCodelensItem[];
        items?: BridgeCodelensItem[];
    }>;
    listPendingHarnessTickets(workspaceId?: string): Promise<{
        workspace_id: string;
        count: number;
        tickets: BridgeHarnessTicketRecord[];
    }>;
    decideHarnessTicket(ticketId: string, decision: "APPROVED" | "DENIED", workspaceId?: string): Promise<BridgeHarnessTicketRecord>;
    evaluateDistillationPromotion(opts?: BridgeDistillationPromotionOptions): Promise<BridgeDistillationPromotionEvaluation>;
    verifyMcpLockfile(opts?: BridgeVerifyMcpLockfileOptions): Promise<BridgeMcpLockVerificationRecord>;
}
//# sourceMappingURL=bridgeClient.d.ts.map