/**
 * Keelway Official TypeScript SDK — Phase 9 Enterprise Identity, SCIM 2.0,
 * Dual-Human P-10 Quorum, SIEM Audit Export & Observability Metrics.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export interface ConfigureOidcProviderRequest {
    workspace_id?: string;
    issuer_url: string;
    client_id: string;
    signing_secret?: string;
    group_role_mapping?: Record<string, string>;
    enabled?: boolean;
}
export interface OidcProviderConfigResponse {
    workspace_id: string;
    issuer_url: string;
    client_id: string;
    enabled: boolean;
    signing_secret_configured: boolean;
    signing_secret_fingerprint?: string | null;
    group_role_mapping: Record<string, string>;
    updated_at?: string;
    [key: string]: unknown;
}
export interface ListScimUsersParams {
    workspace_id?: string;
}
export interface ScimUserResource {
    schemas: string[];
    id: string;
    userName: string;
    displayName?: string;
    active: boolean;
    groups: string[];
    mapped_role: string;
    updated_at?: string;
    [key: string]: unknown;
}
export interface ScimUserListResponse {
    schemas: string[];
    workspace_id: string;
    totalResults: number;
    Resources: ScimUserResource[];
    [key: string]: unknown;
}
export interface ProvisionScimUserRequest {
    workspace_id?: string;
    userName: string;
    displayName?: string;
    groups?: string[];
    active?: boolean;
}
export interface ApproveP10QuorumRequest {
    workspace_id?: string;
    proposal_id: string;
    approver_id: string;
    initiator_id?: string;
    required_approvals?: number;
    reason?: string;
}
export interface P10QuorumApprovalEntry {
    approver_id: string;
    reason?: string;
    approved_at?: string;
    [key: string]: unknown;
}
export interface P10QuorumStatusResponse {
    workspace_id: string;
    proposal_id: string;
    initiator_id: string;
    required_approvals: number;
    approval_count: number;
    status: string;
    approvals: P10QuorumApprovalEntry[];
    quorum_receipt_sha256?: string | null;
    [key: string]: unknown;
}
export type SiemExportFormat = "ocsf" | "cef" | "jsonl" | (string & {});
export interface ExportSiemAuditParams {
    workspace_id?: string;
    format?: SiemExportFormat;
    limit?: number;
}
export interface SiemAuditExportResponse {
    workspace_id: string;
    format: SiemExportFormat;
    record_count: number;
    batch_sha256: string;
    exported_at: string;
    records: Array<Record<string, unknown> | string>;
    [key: string]: unknown;
}
export type ObservabilityMetricsFormat = "otlp_json" | "prometheus" | (string & {});
export interface GetObservabilityMetricsParams {
    workspace_id?: string;
    format?: ObservabilityMetricsFormat;
}
export interface ObservabilityMetricsResponse {
    workspace_id: string;
    format: ObservabilityMetricsFormat;
    generated_at: string;
    counters: Record<string, number>;
    prometheus_text?: string | null;
    otlp_resource_metrics?: Record<string, unknown> | Array<Record<string, unknown>> | null;
    [key: string]: unknown;
}
export declare class PlatformEnterpriseDelegate {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    configureOidcProvider(req: ConfigureOidcProviderRequest, options?: RequestOptions): Promise<OidcProviderConfigResponse>;
    listScimUsers(params?: ListScimUsersParams | string, options?: RequestOptions): Promise<ScimUserListResponse>;
    provisionScimUser(req: ProvisionScimUserRequest, options?: RequestOptions): Promise<ScimUserResource>;
    approveP10Quorum(req: ApproveP10QuorumRequest, options?: RequestOptions): Promise<P10QuorumStatusResponse>;
    exportSiemAudit(params?: ExportSiemAuditParams | string, options?: RequestOptions): Promise<SiemAuditExportResponse>;
    getObservabilityMetrics(params?: GetObservabilityMetricsParams | string, options?: RequestOptions): Promise<ObservabilityMetricsResponse>;
}
//# sourceMappingURL=platformEnterprise.d.ts.map