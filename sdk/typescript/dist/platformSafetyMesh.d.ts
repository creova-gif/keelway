/**
 * Keelway Official TypeScript SDK — Phase 17 Formal Safety State-Machine Verifier
 * + Federated Edge-to-Cluster Agent Mesh (`client.platform` / `client.platform.safetyMesh`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type SafetyToolKind = "read_only" | "write" | "destructive_shell" | "external_transfer" | "cloud_egress";
export type SafetyDataClassification = "public" | "internal" | "restricted_pii";
export type SafetyVerificationStatus = "VERIFIED_SAFE" | "VIOLATION_FOUND";
export type MeshTier = "edge_local" | "cluster_burst";
export type MeshHardwareHal = "apple_metal_secure_enclave" | "nvidia_h100_cc" | "linux_tpm2";
export type MeshNodeStatus = "ONLINE" | "DRAINING";
export type MeshHandoffStatus = "ATTESTED_COMPLETE" | "PINNED_EDGE_ONLY";
export interface SafetyWorkflowNodeInput {
    node_id: string;
    role?: string;
    tool_kind?: SafetyToolKind;
    requires_p10?: boolean;
    max_iterations?: number;
    data_classification?: SafetyDataClassification;
    [key: string]: unknown;
}
export interface SafetyWorkflowEdgeInput {
    from_node: string;
    to_node: string;
    condition?: string;
    [key: string]: unknown;
}
export interface VerifyWorkflowSafetyRequest {
    workspace_id?: string;
    workflow_id?: string;
    workflow_name?: string;
    nodes?: SafetyWorkflowNodeInput[];
    edges?: SafetyWorkflowEdgeInput[];
    airgap_mode?: boolean;
    inject_p10_guards?: boolean;
}
export interface SafetyInvariantCheck {
    invariant_id: string;
    passed: boolean;
    description: string;
    [key: string]: unknown;
}
export interface SafetyViolation {
    invariant_id: string;
    severity: string;
    offending_node: string;
    counterexample_path: string[];
    remediation: string;
    [key: string]: unknown;
}
export interface SafetyVerificationRecord {
    verification_id: string;
    workspace_id: string;
    workflow_id: string;
    workflow_name: string;
    status: SafetyVerificationStatus;
    states_explored: number;
    invariants_checked: SafetyInvariantCheck[];
    violations: SafetyViolation[];
    p10_guards_injected: string[];
    dlp_redactions: number;
    proof_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ListSafetyVerificationsParams {
    workspace_id?: string;
    limit?: number;
}
export interface SafetyVerificationListResponse {
    workspace_id: string;
    count: number;
    verifications: SafetyVerificationRecord[];
    [key: string]: unknown;
}
export interface RegisterMeshNodeRequest {
    workspace_id?: string;
    node_id?: string;
    name: string;
    tier?: MeshTier;
    hardware_hal?: MeshHardwareHal;
    region?: string;
    vram_gb?: number;
    status?: MeshNodeStatus;
}
export interface MeshNodeRecord {
    node_id: string;
    workspace_id: string;
    name: string;
    tier: MeshTier;
    hardware_hal: MeshHardwareHal;
    region: string;
    vram_gb: number;
    status: string;
    attestation_sha256: string;
    registered_at: string;
    [key: string]: unknown;
}
export interface ListMeshNodesParams {
    workspace_id?: string;
}
export interface MeshNodeListResponse {
    workspace_id: string;
    count: number;
    nodes: MeshNodeRecord[];
    [key: string]: unknown;
}
export interface DispatchMeshHandoffRequest {
    workspace_id?: string;
    workflow_name?: string;
    task_summary?: string;
    data_classification?: SafetyDataClassification;
    allow_sanitized_burst?: boolean;
    force_raw_cloud_burst?: boolean;
}
export interface MeshStageExecution {
    stage_name: string;
    target_tier: MeshTier;
    node_id: string;
    model_id: string;
    hardware_hal: string;
    zero_raw_pii_egress: boolean;
    cost_usd: number;
    [key: string]: unknown;
}
export interface MeshHandoffRecord {
    handoff_id: string;
    workspace_id: string;
    workflow_name: string;
    data_classification: string;
    status: MeshHandoffStatus;
    edge_node_id: string;
    burst_node_id: string | null;
    stages: MeshStageExecution[];
    total_cost_usd: number;
    dlp_redactions: number;
    attestation_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export type ListMeshHandoffsParams = ListSafetyVerificationsParams;
export interface MeshHandoffListResponse {
    workspace_id: string;
    count: number;
    handoffs: MeshHandoffRecord[];
    [key: string]: unknown;
}
export declare class PlatformSafetyMeshClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    verifyWorkflowSafety(req?: VerifyWorkflowSafetyRequest, options?: RequestOptions): Promise<SafetyVerificationRecord>;
    listSafetyVerifications(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<SafetyVerificationListResponse>;
    listSafetyVerifications(params?: ListSafetyVerificationsParams, options?: RequestOptions): Promise<SafetyVerificationListResponse>;
    registerMeshNode(req: RegisterMeshNodeRequest, options?: RequestOptions): Promise<MeshNodeRecord>;
    listMeshNodes(workspaceId?: string, options?: RequestOptions): Promise<MeshNodeListResponse>;
    listMeshNodes(params?: ListMeshNodesParams, options?: RequestOptions): Promise<MeshNodeListResponse>;
    dispatchMeshHandoff(req?: DispatchMeshHandoffRequest, options?: RequestOptions): Promise<MeshHandoffRecord>;
    listMeshHandoffs(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<MeshHandoffListResponse>;
    listMeshHandoffs(params?: ListMeshHandoffsParams, options?: RequestOptions): Promise<MeshHandoffListResponse>;
}
export { PlatformSafetyMeshClient as PlatformSafetyMeshDelegate };
//# sourceMappingURL=platformSafetyMesh.d.ts.map