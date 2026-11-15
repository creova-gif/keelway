/**
 * Keelway Official TypeScript SDK — Phase 8 KFlow DAG Execution, KSpaces CRDT Sync & SBOM.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type KflowNodeKind = "trigger" | "agent" | "mcp_tool" | "p10_gate" | "transform" | (string & {});
export interface KflowNodeSpec {
    id: string;
    label?: string;
    agent_id?: string;
    kind?: KflowNodeKind;
    depends_on?: string[];
    requires_p10?: boolean;
    config?: Record<string, unknown>;
    [key: string]: unknown;
}
export interface ExecuteKflowDagRequest {
    workflow_id: string;
    nodes?: KflowNodeSpec[];
    trigger?: string;
    token_budget?: number;
    approved_node_ids?: string[];
    workspace_id?: string;
}
export interface KflowNodeResult {
    id: string;
    label?: string;
    agent_id?: string;
    depends_on?: string[];
    requires_p10?: boolean;
    wave?: number;
    status: string;
    tokens?: number;
    upstream_digests?: string[];
    output_digest?: string | null;
    error_detail?: string | null;
    [key: string]: unknown;
}
export interface KflowRunReceipt {
    run_id: string;
    workspace_id?: string;
    workflow_id: string;
    trigger?: string;
    status: string;
    held_node_id?: string | null;
    topological_order?: string[];
    waves?: string[][];
    nodes?: KflowNodeResult[];
    tokens_used?: number;
    token_budget?: number;
    receipt_sha256?: string;
    created_at?: string;
    [key: string]: unknown;
}
export interface ListKflowRunsParams {
    workspace_id?: string;
    workflow_id?: string;
    limit?: number;
}
export interface KflowRunListResponse {
    workspace_id?: string;
    count?: number;
    runs: KflowRunReceipt[];
    [key: string]: unknown;
}
export interface KspacesCrdtOperation {
    namespace?: string;
    key: string;
    value?: unknown;
    op?: "set" | "remove" | (string & {});
    lamport_ts?: number;
    [key: string]: unknown;
}
export interface KspacesCrdtEntry {
    namespace: string;
    key: string;
    value: unknown;
    lamport_ts: number;
    peer_id: string;
    tombstone: boolean;
    [key: string]: unknown;
}
export interface SyncKspacesCrdtRequest {
    peer_id: string;
    operations: KspacesCrdtOperation[];
    workspace_id?: string;
}
export interface KspacesStateResponse {
    workspace_id: string;
    vector_clock?: Record<string, number>;
    state_digest_sha256: string;
    active_keys_count: number;
    entries: KspacesCrdtEntry[];
    [key: string]: unknown;
}
export interface KspacesSyncResponse extends KspacesStateResponse {
    peer_id: string;
    applied_count: number;
}
export interface GetKspacesStateParams {
    workspace_id?: string;
    namespace?: string;
}
export interface GetPlatformSbomParams {
    workspace_id?: string;
}
export interface PlatformSbomComponent {
    name: string;
    version: string;
    component_type?: string;
    purl?: string;
    sha256?: string;
    supplier?: string;
    [key: string]: unknown;
}
export interface PlatformSbomResponse {
    workspace_id?: string;
    verified: boolean;
    verification_status?: string;
    serial_number?: string;
    bom_format: string;
    spec_version: string;
    component_count?: number;
    root_digest_sha256: string;
    provenance_signature: string;
    manifest?: {
        components?: PlatformSbomComponent[];
        [key: string]: unknown;
    };
    [key: string]: unknown;
}
export declare class PlatformKflowDelegate {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    executeKflowDag(req: ExecuteKflowDagRequest, options?: RequestOptions): Promise<KflowRunReceipt>;
    listKflowRuns(params?: ListKflowRunsParams | string, options?: RequestOptions): Promise<KflowRunListResponse>;
    syncKspacesCrdt(req: SyncKspacesCrdtRequest, options?: RequestOptions): Promise<KspacesSyncResponse>;
    getKspacesState(params?: GetKspacesStateParams | string, options?: RequestOptions): Promise<KspacesStateResponse>;
    getPlatformSbom(params?: GetPlatformSbomParams | string, options?: RequestOptions): Promise<PlatformSbomResponse>;
}
//# sourceMappingURL=platformKflow.d.ts.map