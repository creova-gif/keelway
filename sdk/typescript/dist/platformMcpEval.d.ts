/**
 * Keelway Official TypeScript SDK — Phase 7 MCP Control Plane & Golden Evaluation Suite.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type McpTransport = "sse" | "stdio" | "builtin" | (string & {});
export type GoldenEvalCategory = "all" | "workspace_ast" | "governance_p10" | "security_redteam" | "routing_pricing" | (string & {});
export interface ListMcpServersParams {
    workspace_id?: string;
}
export interface ListMcpToolsParams {
    workspace_id?: string;
}
export interface RegisterMcpServerRequest {
    id: string;
    name: string;
    transport: McpTransport;
    endpoint: string;
    workspace_id?: string;
    allowed_tools?: string[];
}
export interface McpServerRecord {
    id: string;
    name: string;
    transport: McpTransport;
    endpoint?: string;
    workspace_id?: string;
    builtin?: boolean;
    status?: string;
    tools_count?: number;
    allowed_tools?: string[];
    protocol_version?: string;
    created_at?: string;
    [key: string]: unknown;
}
export interface McpServerListResponse {
    workspace_id?: string;
    protocol_version?: string;
    count?: number;
    total?: number;
    servers: McpServerRecord[];
    [key: string]: unknown;
}
export interface DeleteMcpServerResponse {
    deleted: boolean;
    id?: string;
    server_id?: string;
    workspace_id?: string;
    [key: string]: unknown;
}
export interface McpToolDescriptor {
    name: string;
    server_id?: string;
    description?: string;
    inputSchema?: Record<string, unknown>;
    input_schema?: Record<string, unknown>;
    mutating?: boolean;
    builtin?: boolean;
    [key: string]: unknown;
}
export interface McpToolListResponse {
    workspace_id?: string;
    protocol_version?: string;
    count?: number;
    total?: number;
    tools: McpToolDescriptor[];
    [key: string]: unknown;
}
export interface CallMcpToolRequest {
    tool_name: string;
    arguments?: Record<string, unknown>;
    workspace_id?: string;
}
export interface CallMcpToolResponse {
    ok: boolean;
    workspace_id?: string;
    tool_name: string;
    protocol_version?: string;
    redacted?: boolean;
    duration_ms?: number;
    result?: unknown;
    receipt_sha256?: string;
    [key: string]: unknown;
}
export interface RunGoldenEvalsRequest {
    category?: GoldenEvalCategory;
    workspace_id?: string;
}
export interface GoldenEvalCaseResult {
    id: string;
    category: string;
    title?: string;
    passed: boolean;
    duration_ms?: number;
    evidence?: string;
    [key: string]: unknown;
}
export interface GoldenEvalReport {
    eval_run_id: string;
    workspace_id?: string;
    category: string;
    total_cases: number;
    passed_cases: number;
    failed_cases: number;
    pass_rate: number;
    duration_ms?: number;
    categories?: Record<string, {
        total: number;
        passed: number;
        failed: number;
        pass_rate: number;
    }>;
    cases?: GoldenEvalCaseResult[];
    receipt_sha256?: string;
    created_at?: string;
    [key: string]: unknown;
}
export interface LatestGoldenEvalsResponse {
    workspace_id: string;
    has_run: boolean;
    latest: GoldenEvalReport | null;
    [key: string]: unknown;
}
export declare class PlatformMcpEvalDelegate {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    listMcpServers(params?: ListMcpServersParams | string, options?: RequestOptions): Promise<McpServerListResponse>;
    registerMcpServer(req: RegisterMcpServerRequest, options?: RequestOptions): Promise<McpServerRecord>;
    deleteMcpServer(serverId: string, params?: {
        workspace_id?: string;
    } | string, options?: RequestOptions): Promise<DeleteMcpServerResponse>;
    listMcpTools(params?: ListMcpToolsParams | string, options?: RequestOptions): Promise<McpToolListResponse>;
    callMcpTool(reqOrToolName: CallMcpToolRequest | string, argumentsOrOptions?: Record<string, unknown> | RequestOptions, workspaceId?: string, options?: RequestOptions): Promise<CallMcpToolResponse>;
    runGoldenEvals(req?: RunGoldenEvalsRequest | string, options?: RequestOptions): Promise<GoldenEvalReport>;
    getLatestGoldenEvals(params?: {
        workspace_id?: string;
    } | string, options?: RequestOptions): Promise<LatestGoldenEvalsResponse>;
}
//# sourceMappingURL=platformMcpEval.d.ts.map