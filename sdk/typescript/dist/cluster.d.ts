/**
 * Keelway Official TypeScript SDK — Distributed Cluster Namespace (`client.cluster`).
 *
 * Exposes all 10 `/v1/cluster/*` endpoints (GPU/NPU node discovery, registration,
 * drain/restore, VRAM & residency scheduling, shadow/canary/production lifecycle
 * promotion/rollback, and multi-tenant governance budget reservation) using
 * `KeelwayClient`'s zero-dependency Web Fetch infrastructure.
 */
import type { RequestOptions } from "./types.js";
export type ClusterJsonRequester = <T>(method: string, path: string, params?: {
    query?: Record<string, string>;
    body?: Record<string, unknown>;
    options?: RequestOptions;
}) => Promise<T>;
export interface ClusterListNodesParams {
    region?: string;
    runtime?: string;
    include_drained?: boolean;
}
export interface ClusterNodeRecord {
    node_id: string;
    region?: string;
    runtime?: string;
    accelerator?: string;
    total_vram_gb?: number;
    free_vram_gb?: number;
    status?: string;
    [key: string]: unknown;
}
export interface ClusterNodeListResponse {
    nodes: ClusterNodeRecord[];
    count?: number;
    total?: number;
    [key: string]: unknown;
}
export type RegisterClusterNodeRequest = Record<string, unknown>;
export type ClusterScheduleRequest = Record<string, unknown>;
export interface ClusterScheduleResponse {
    scheduled?: boolean;
    selected_node_id?: string | null;
    node_id?: string | null;
    model_id?: string;
    region?: string;
    reason?: string;
    [key: string]: unknown;
}
export interface ClusterLifecycleResponse {
    entries?: Record<string, unknown>[];
    models?: Record<string, unknown>[];
    deployments?: Record<string, unknown>[];
    total?: number;
    [key: string]: unknown;
}
export type PromoteClusterModelRequest = Record<string, unknown>;
export type RollbackClusterModelRequest = Record<string, unknown>;
export interface ClusterGovernanceAdapterStatusResponse {
    status?: string;
    active?: boolean;
    [key: string]: unknown;
}
export type ReserveClusterBudgetRequest = Record<string, unknown>;
export interface ReserveClusterBudgetResponse {
    allowed?: boolean;
    reserved?: boolean;
    reservation_id?: string;
    [key: string]: unknown;
}
export declare class ClusterNamespace {
    private readonly requestJson;
    constructor(requestJson: ClusterJsonRequester);
    listNodes(params?: ClusterListNodesParams, options?: RequestOptions): Promise<ClusterNodeListResponse>;
    registerNode(payload: RegisterClusterNodeRequest, options?: RequestOptions): Promise<ClusterNodeRecord>;
    drainNode(nodeId: string, options?: RequestOptions): Promise<ClusterNodeRecord>;
    restoreNode(nodeId: string, options?: RequestOptions): Promise<ClusterNodeRecord>;
    schedule(payload: ClusterScheduleRequest, options?: RequestOptions): Promise<ClusterScheduleResponse>;
    listLifecycle(params?: {
        stage?: string;
    }, options?: RequestOptions): Promise<ClusterLifecycleResponse>;
    promoteModel(payload: PromoteClusterModelRequest, options?: RequestOptions): Promise<Record<string, unknown>>;
    rollbackModel(payload: RollbackClusterModelRequest, options?: RequestOptions): Promise<Record<string, unknown>>;
    governanceAdapterStatus(options?: RequestOptions): Promise<ClusterGovernanceAdapterStatusResponse>;
    reserveBudget(payload: ReserveClusterBudgetRequest, options?: RequestOptions): Promise<ReserveClusterBudgetResponse>;
}
//# sourceMappingURL=cluster.d.ts.map