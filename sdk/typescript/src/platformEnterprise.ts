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

function enterpriseWsId(params?: { workspace_id?: string } | string): string {
  return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}

export class PlatformEnterpriseDelegate {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public configureOidcProvider(
    req: ConfigureOidcProviderRequest,
    options?: RequestOptions,
  ): Promise<OidcProviderConfigResponse> {
    return this.requestJson("PUT", "/v1/platform/enterprise/oidc", {
      body: {
        workspace_id: req.workspace_id ?? "default",
        issuer_url: req.issuer_url,
        client_id: req.client_id,
        signing_secret: req.signing_secret ?? "",
        group_role_mapping: req.group_role_mapping ?? {},
        enabled: req.enabled ?? true,
      },
      options,
    });
  }

  public listScimUsers(
    params: ListScimUsersParams | string = {},
    options?: RequestOptions,
  ): Promise<ScimUserListResponse> {
    return this.requestJson("GET", "/v1/platform/enterprise/scim/v2/Users", {
      query: { workspace_id: enterpriseWsId(params) },
      options,
    });
  }

  public provisionScimUser(
    req: ProvisionScimUserRequest,
    options?: RequestOptions,
  ): Promise<ScimUserResource> {
    return this.requestJson("POST", "/v1/platform/enterprise/scim/v2/Users", {
      body: {
        workspace_id: req.workspace_id ?? "default",
        userName: req.userName,
        displayName: req.displayName ?? "",
        groups: req.groups ?? [],
        active: req.active ?? true,
      },
      options,
    });
  }

  public approveP10Quorum(
    req: ApproveP10QuorumRequest,
    options?: RequestOptions,
  ): Promise<P10QuorumStatusResponse> {
    return this.requestJson("POST", "/v1/platform/enterprise/p10-quorum/approve", {
      body: {
        workspace_id: req.workspace_id ?? "default",
        proposal_id: req.proposal_id,
        approver_id: req.approver_id,
        initiator_id: req.initiator_id ?? "",
        required_approvals: req.required_approvals ?? 2,
        reason: req.reason ?? "",
      },
      options,
    });
  }

  public exportSiemAudit(
    params: ExportSiemAuditParams | string = {},
    options?: RequestOptions,
  ): Promise<SiemAuditExportResponse> {
    const query: Record<string, string> = {
      workspace_id: enterpriseWsId(params),
      format: typeof params === "string" ? "ocsf" : (params.format ?? "ocsf"),
      limit: String(typeof params === "string" ? 100 : (params.limit ?? 100)),
    };
    return this.requestJson("GET", "/v1/platform/enterprise/siem/export", { query, options });
  }

  public getObservabilityMetrics(
    params: GetObservabilityMetricsParams | string = {},
    options?: RequestOptions,
  ): Promise<ObservabilityMetricsResponse> {
    const query: Record<string, string> = {
      workspace_id: enterpriseWsId(params),
      format: typeof params === "string" ? "otlp_json" : (params.format ?? "otlp_json"),
    };
    return this.requestJson("GET", "/v1/platform/observability/metrics", { query, options });
  }
}
