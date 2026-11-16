/**
 * Keelway Loopback Debugger Bridge Client for VS Code & Cursor Extension Host.
 * Authenticates via Bearer token and strips any browser Origin header to preserve zero-CSRF loopback posture.
 */
export type AttachScheme = "vscode" | "cursor";
export type DebugStepAction = "step_over" | "step_into" | "continue" | "mutate_state";
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
}
//# sourceMappingURL=bridgeClient.d.ts.map