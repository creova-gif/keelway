/**
 * Keelway Official TypeScript SDK — Unified Platform Namespace (`client.platform`).
 *
 * Exposes all 20 `/v1/platform/*` endpoints using `KeelwayClient`'s zero-dependency
 * Web Fetch, `AbortSignal` timeout, and `mapHttpError` infrastructure.
 */

import type {
  CheckModelLicenseRequest,
  CheckModelLicenseResponse,
  CompileBlueprintRequest,
  CompiledBlueprintResponse,
  CreateIssueRequest,
  CreatePrdRequest,
  CreateWorkflowRequest,
  DispatchTeamRequest,
  ExtensionSpecInput,
  InstallMarketplacePackageRequest,
  InstallMarketplacePackageResponse,
  LifecycleAgentsResponse,
  ListExtensionsParams,
  ListIssuesParams,
  ListMarketplacePackagesParams,
  ListMarketplaceSettlementsParams,
  MarketplacePackageInput,
  MarketplacePackageListResponse,
  MarketplacePackageRecord,
  MarketplaceScanReport,
  MarketplaceSettlementRecord,
  MarketplaceSettlementSummaryResponse,
  PlatformExtensionListResponse,
  PlatformExtensionRecord,
  PlatformIssueListResponse,
  PlatformIssueRecord,
  PlatformOverviewParams,
  PlatformOverviewResponse,
  PlatformPrdListResponse,
  PlatformPrdRecord,
  PlatformWorkflowListResponse,
  PlatformWorkflowRecord,
  PurchaseMarketplacePackageRequest,
  QuotaCheckRequest,
  QuotaCheckResponse,
  SubscriptionTiersResponse,
  TeamRunResponse,
  ValidateByomRequest,
  ValidateByomResponse,
} from "./platform-types.js";
import type * as PT from "./platform-types.js";
import { PlatformRuntimeDelegate, type PlatformSseRequester } from "./platform-runtime.js";
import type { RequestOptions } from "./types.js";

export type PlatformJsonRequester = <T>(
  method: string,
  path: string,
  params?: {
    query?: Record<string, string>;
    body?: Record<string, unknown>;
    options?: RequestOptions;
  },
) => Promise<T>;

export class PlatformNamespace {
  private readonly requestJson: PlatformJsonRequester;
  private readonly runtime: PlatformRuntimeDelegate;

  constructor(requestJson: PlatformJsonRequester, requestSse?: PlatformSseRequester) {
    this.requestJson = requestJson;
    this.runtime = new PlatformRuntimeDelegate(requestJson, requestSse);
  }

  public overview(
    params: PlatformOverviewParams | string = {},
    options?: RequestOptions,
  ): Promise<PlatformOverviewResponse> {
    const workspaceId = typeof params === "string" ? params : (params.workspace_id ?? "default");
    return this.requestJson<PlatformOverviewResponse>("GET", "/v1/platform/overview", {
      query: { workspace_id: workspaceId },
      options,
    });
  }

  public listTiers(options?: RequestOptions): Promise<SubscriptionTiersResponse> {
    return this.requestJson<SubscriptionTiersResponse>(
      "GET",
      "/v1/platform/subscriptions/tiers",
      { options },
    );
  }

  public checkQuota(
    req: QuotaCheckRequest,
    options?: RequestOptions,
  ): Promise<QuotaCheckResponse> {
    return this.requestJson<QuotaCheckResponse>(
      "POST",
      "/v1/platform/subscriptions/quota-check",
      {
        body: {
          org_id: req.org_id,
          tier: req.tier,
          tokens_requested: req.tokens_requested,
          current_rpm: req.current_rpm ?? 1,
          local_hardware: req.local_hardware ?? false,
        },
        options,
      },
    );
  }

  public validateByom(
    req: ValidateByomRequest,
    options?: RequestOptions,
  ): Promise<ValidateByomResponse> {
    const body: Record<string, unknown> = {
      provider: req.provider,
      credential_kind: req.credential_kind,
      api_key_preview: req.api_key_preview ?? "",
      model_id: req.model_id ?? "",
      commercial_use: req.commercial_use ?? true,
    };
    if (req.license_id !== undefined) {
      body.license_id = req.license_id;
    }
    return this.requestJson<ValidateByomResponse>(
      "POST",
      "/v1/platform/subscriptions/byom/validate",
      { body, options },
    );
  }

  public checkModelLicense(
    req: CheckModelLicenseRequest,
    options?: RequestOptions,
  ): Promise<CheckModelLicenseResponse> {
    return this.requestJson<CheckModelLicenseResponse>(
      "POST",
      "/v1/platform/subscriptions/license-check",
      {
        body: {
          model_id: req.model_id,
          license_id: req.license_id,
          commercial_use: req.commercial_use ?? true,
          has_authorized_api_credential:
            req.has_authorized_api_credential ?? req.has_authorized_api_key ?? false,
          exceeds_700m_mau: req.exceeds_700m_mau ?? false,
        },
        options,
      },
    );
  }

  public listMarketplacePackages(
    params: ListMarketplacePackagesParams = {},
    options?: RequestOptions,
  ): Promise<MarketplacePackageListResponse> {
    const query: Record<string, string> = {
      workspace_id: params.workspace_id ?? "default",
    };
    if (params.kind !== undefined) query.kind = params.kind;
    if (params.query !== undefined) query.query = params.query;
    if (params.publisher_tier !== undefined) query.publisher_tier = params.publisher_tier;
    return this.requestJson<MarketplacePackageListResponse>(
      "GET",
      "/v1/platform/marketplace/packages",
      { query, options },
    );
  }

  public scanMarketplacePackage(
    pkg: MarketplacePackageInput,
    options?: RequestOptions,
  ): Promise<MarketplaceScanReport> {
    return this.requestJson<MarketplaceScanReport>("POST", "/v1/platform/marketplace/scan", {
      body: { ...pkg },
      options,
    });
  }

  public publishMarketplacePackage(
    pkg: MarketplacePackageInput,
    options?: RequestOptions,
  ): Promise<MarketplacePackageRecord> {
    return this.requestJson<MarketplacePackageRecord>(
      "POST",
      "/v1/platform/marketplace/publish",
      { body: { ...pkg }, options },
    );
  }

  public installMarketplacePackage(
    req: InstallMarketplacePackageRequest,
    options?: RequestOptions,
  ): Promise<InstallMarketplacePackageResponse> {
    const body: Record<string, unknown> = {
      package_id: req.package_id,
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.config !== undefined) {
      body.config = req.config;
    }
    return this.requestJson<InstallMarketplacePackageResponse>(
      "POST",
      "/v1/platform/marketplace/install",
      { body, options },
    );
  }

  public purchaseMarketplacePackage(
    req: PurchaseMarketplacePackageRequest | string,
    options?: RequestOptions,
  ): Promise<MarketplaceSettlementRecord> {
    const body: Record<string, unknown> =
      typeof req === "string"
        ? { package_id: req, buyer_tenant_id: "default" }
        : {
            package_id: req.package_id,
            buyer_tenant_id: req.buyer_tenant_id ?? "default",
          };
    if (typeof req !== "string") {
      if (req.workspace_id !== undefined) {
        body.workspace_id = req.workspace_id;
      }
      if (req.config !== undefined) {
        body.config = req.config;
      }
    }
    return this.requestJson<MarketplaceSettlementRecord>(
      "POST",
      "/v1/platform/marketplace/purchase",
      { body, options },
    );
  }

  public listMarketplaceSettlements(
    params: ListMarketplaceSettlementsParams | string = {},
    options?: RequestOptions,
  ): Promise<MarketplaceSettlementSummaryResponse> {
    const tenantId = typeof params === "string" ? params : params.tenant_id;
    const query: Record<string, string> | undefined =
      tenantId !== undefined ? { tenant_id: tenantId } : undefined;
    return this.requestJson<MarketplaceSettlementSummaryResponse>(
      "GET",
      "/v1/platform/marketplace/settlements",
      { query, options },
    );
  }

  public listAgents(
    params: { workspace_id?: string } = {},
    options?: RequestOptions,
  ): Promise<LifecycleAgentsResponse> {
    return this.requestJson<LifecycleAgentsResponse>("GET", "/v1/platform/agents", {
      query: { workspace_id: params.workspace_id ?? "default" },
      options,
    });
  }

  public dispatchTeam(
    req: DispatchTeamRequest,
    options?: RequestOptions,
  ): Promise<TeamRunResponse> {
    return this.requestJson<TeamRunResponse>("POST", "/v1/platform/agents/teams/dispatch", {
      body: {
        team_id: req.team_id,
        objective: req.objective ?? req.goal ?? "",
        workspace_id: req.workspace_id ?? "default",
        sensitive_mutation: req.sensitive_mutation ?? false,
      },
      options,
    });
  }

  public async listIssues(
    params: ListIssuesParams = {},
    options?: RequestOptions,
  ): Promise<PlatformIssueListResponse> {
    const query: Record<string, string> = {
      workspace_id: params.workspace_id ?? "default",
    };
    if (params.status !== undefined) {
      query.status = params.status;
    }
    const res = await this.requestJson<PlatformIssueListResponse>(
      "GET",
      "/v1/platform/pm/issues",
      { query, options },
    );
    if (params.status !== undefined && Array.isArray(res.issues)) {
      const filtered = res.issues.filter((i) => i.status === params.status);
      return { ...res, issues: filtered, total: filtered.length };
    }
    return res;
  }

  public createIssue(
    req: CreateIssueRequest,
    options?: RequestOptions,
  ): Promise<PlatformIssueRecord> {
    const body: Record<string, unknown> = {
      title: req.title,
      workspace_id: req.workspace_id ?? "default",
      priority: req.priority ?? "medium",
      status: req.status ?? "todo",
      assignee_agent: req.assignee_agent ?? "feature-coder",
      sprint_id: req.sprint_id ?? "SPR-01",
    };
    if (req.prd_id !== undefined) {
      body.prd_id = req.prd_id;
    }
    return this.requestJson<PlatformIssueRecord>("POST", "/v1/platform/pm/issues", {
      body,
      options,
    });
  }

  public listPrds(
    params: { workspace_id?: string } = {},
    options?: RequestOptions,
  ): Promise<PlatformPrdListResponse> {
    return this.requestJson<PlatformPrdListResponse>("GET", "/v1/platform/product/prds", {
      query: { workspace_id: params.workspace_id ?? "default" },
      options,
    });
  }

  public createPrd(
    req: CreatePrdRequest,
    options?: RequestOptions,
  ): Promise<PlatformPrdRecord> {
    const body: Record<string, unknown> = {
      title: req.title,
      summary: req.summary,
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.acceptance_criteria !== undefined) {
      body.acceptance_criteria = req.acceptance_criteria;
    }
    return this.requestJson<PlatformPrdRecord>("POST", "/v1/platform/product/prds", {
      body,
      options,
    });
  }

  public listWorkflows(
    params: { workspace_id?: string } = {},
    options?: RequestOptions,
  ): Promise<PlatformWorkflowListResponse> {
    return this.requestJson<PlatformWorkflowListResponse>(
      "GET",
      "/v1/platform/automation/workflows",
      {
        query: { workspace_id: params.workspace_id ?? "default" },
        options,
      },
    );
  }

  public createWorkflow(
    req: CreateWorkflowRequest,
    options?: RequestOptions,
  ): Promise<PlatformWorkflowRecord> {
    const body: Record<string, unknown> = {
      name: req.name,
      trigger: req.trigger ?? "manual",
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.nodes !== undefined) {
      body.nodes = req.nodes;
    }
    return this.requestJson<PlatformWorkflowRecord>(
      "POST",
      "/v1/platform/automation/workflows",
      { body, options },
    );
  }

  public compileBlueprint(
    req: CompileBlueprintRequest,
    options?: RequestOptions,
  ): Promise<CompiledBlueprintResponse> {
    return this.requestJson<CompiledBlueprintResponse>("POST", "/v1/platform/nocode/blueprint", {
      body: {
        idea: req.idea,
        workspace_id: req.workspace_id ?? "default",
        experience_mode: req.experience_mode ?? "non_coder",
        target_stack: req.target_stack ?? "react-fastapi-sqlite",
      },
      options,
    });
  }

  public listExtensions(
    params: ListExtensionsParams = {},
    options?: RequestOptions,
  ): Promise<PlatformExtensionListResponse> {
    const query: Record<string, string> = {
      workspace_id: params.workspace_id ?? "default",
    };
    if (params.extension_type !== undefined) {
      query.extension_type = params.extension_type;
    }
    return this.requestJson<PlatformExtensionListResponse>("GET", "/v1/platform/extensions", {
      query,
      options,
    });
  }

  public registerExtension(
    extension: ExtensionSpecInput,
    options?: RequestOptions,
  ): Promise<PlatformExtensionRecord> {
    return this.requestJson<PlatformExtensionRecord>(
      "POST",
      "/v1/platform/extensions/register",
      { body: { ...extension }, options },
    );
  }

  public listDocs(params: PT.ListDocsParams | string = {}, options?: RequestOptions): Promise<PT.PlatformDocListResponse> {
    return this.runtime.listDocs(params, options);
  }
  public createDoc(req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord> {
    return this.runtime.createDoc(req, options);
  }
  public updateDoc(docId: string, req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord> {
    return this.runtime.updateDoc(docId, req, options);
  }
  public updateIssue(issueId: string, patch: PT.UpdateIssueRequest, options?: RequestOptions): Promise<PlatformIssueRecord> {
    return this.runtime.updateIssue(issueId, patch, options);
  }
  public listFeedback(params: PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.PlatformFeedbackListResponse> {
    return this.runtime.listFeedback(params, options);
  }
  public createFeedback(req: PT.CreateFeedbackRequest, options?: RequestOptions): Promise<PT.PlatformFeedbackRecord> {
    return this.runtime.createFeedback(req, options);
  }
  public scanWorkspaceSecurity(req: PT.WorkspaceSecurityScanRequest, options?: RequestOptions): Promise<PT.WorkspaceSecurityScanReport> {
    return this.runtime.scanWorkspaceSecurity(req, options);
  }
  public listWorkspaces(options?: RequestOptions): Promise<PT.PlatformWorkspaceListResponse> {
    return this.runtime.listWorkspaces(options);
  }
  public createWorkspace(req: PT.CreateWorkspaceRequest, options?: RequestOptions): Promise<PT.PlatformWorkspaceRecord> {
    return this.runtime.createWorkspace(req, options);
  }
  public listRbacMembers(params: PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.RbacMemberListResponse> {
    return this.runtime.listRbacMembers(params, options);
  }
  public upsertRbacMember(req: PT.UpsertRbacMemberRequest, options?: RequestOptions): Promise<PT.RbacMemberRecord> {
    return this.runtime.upsertRbacMember(req, options);
  }
  public checkRbac(req: PT.CheckRbacRequest, options?: RequestOptions): Promise<PT.CheckRbacResponse> {
    return this.runtime.checkRbac(req, options);
  }
  public listSecrets(params: PT.ListSecretsParams | string = {}, options?: RequestOptions): Promise<PT.VaultSecretListResponse> {
    return this.runtime.listSecrets(params, options);
  }
  public putSecret(req: PT.PutSecretRequest, options?: RequestOptions): Promise<PT.VaultSecretMetadata> {
    return this.runtime.putSecret(req, options);
  }
  public rotateSecret(name: string, req: PT.RotateSecretRequest | string, options?: RequestOptions): Promise<PT.VaultSecretMetadata> {
    return this.runtime.rotateSecret(name, req, options);
  }
  public deleteSecret(name: string, params: PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.DeleteSecretResponse> {
    return this.runtime.deleteSecret(name, params, options);
  }
  public listWebhooks(params: PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.WebhookListResponse> {
    return this.runtime.listWebhooks(params, options);
  }
  public createWebhook(req: PT.CreateWebhookRequest, options?: RequestOptions): Promise<PT.WebhookRecord> {
    return this.runtime.createWebhook(req, options);
  }
  public deleteWebhook(webhookId: string, params: PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.DeleteWebhookResponse> {
    return this.runtime.deleteWebhook(webhookId, params, options);
  }
  public testWebhook(webhookId: string, req?: PT.TestWebhookRequest, options?: RequestOptions): Promise<PT.WebhookTestReceipt> {
    return this.runtime.testWebhook(webhookId, req, options);
  }
  public verifyWebhook(req: PT.VerifyWebhookRequest, options?: RequestOptions): Promise<PT.VerifyWebhookResponse> {
    return this.runtime.verifyWebhook(req, options);
  }
  public startExecutionRun(req: PT.StartExecutionRunRequest, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot> {
    return this.runtime.startExecutionRun(req, options);
  }
  public resolveExecutionP10(runId: string, req: PT.ResolveExecutionP10Request, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot> {
    return this.runtime.resolveExecutionP10(runId, req, options);
  }
  public streamExecutionEvents(
    runId: string,
    options?: PT.StreamExecutionEventsOptions,
  ): AsyncGenerator<Record<string, unknown>, void, unknown> {
    return this.runtime.streamExecutionEvents(runId, options);
  }
}
