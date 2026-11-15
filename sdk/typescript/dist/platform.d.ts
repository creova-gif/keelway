/**
 * Keelway Official TypeScript SDK — Unified Platform Namespace (`client.platform`).
 *
 * Exposes all 20 `/v1/platform/*` endpoints using `KeelwayClient`'s zero-dependency
 * Web Fetch, `AbortSignal` timeout, and `mapHttpError` infrastructure.
 */
import type { CheckModelLicenseRequest, CheckModelLicenseResponse, CompileBlueprintRequest, CompiledBlueprintResponse, CreateIssueRequest, CreatePrdRequest, CreateWorkflowRequest, DispatchTeamRequest, ExtensionSpecInput, InstallMarketplacePackageRequest, InstallMarketplacePackageResponse, LifecycleAgentsResponse, ListExtensionsParams, ListIssuesParams, ListMarketplacePackagesParams, ListMarketplaceSettlementsParams, MarketplacePackageInput, MarketplacePackageListResponse, MarketplacePackageRecord, MarketplaceScanReport, MarketplaceSettlementRecord, MarketplaceSettlementSummaryResponse, PlatformExtensionListResponse, PlatformExtensionRecord, PlatformIssueListResponse, PlatformIssueRecord, PlatformOverviewParams, PlatformOverviewResponse, PlatformPrdListResponse, PlatformPrdRecord, PlatformWorkflowListResponse, PlatformWorkflowRecord, PurchaseMarketplacePackageRequest, QuotaCheckRequest, QuotaCheckResponse, SubscriptionTiersResponse, TeamRunResponse, ValidateByomRequest, ValidateByomResponse } from "./platform-types.js";
import type * as PT from "./platform-types.js";
import { type PlatformSseRequester } from "./platform-runtime.js";
import { type CallMcpToolRequest, type CallMcpToolResponse, type DeleteMcpServerResponse, type GoldenEvalReport, type LatestGoldenEvalsResponse, type ListMcpServersParams, type ListMcpToolsParams, type McpServerListResponse, type McpServerRecord, type McpToolListResponse, type RegisterMcpServerRequest, type RunGoldenEvalsRequest } from "./platformMcpEval.js";
import { type ExecuteKflowDagRequest, type GetKspacesStateParams, type GetPlatformSbomParams, type KflowRunListResponse, type KflowRunReceipt, type KspacesStateResponse, type KspacesSyncResponse, type ListKflowRunsParams, type PlatformSbomResponse, type SyncKspacesCrdtRequest } from "./platformKflow.js";
import { type ApproveP10QuorumRequest, type ConfigureOidcProviderRequest, type ExportSiemAuditParams, type GetObservabilityMetricsParams, type ListScimUsersParams, type ObservabilityMetricsResponse, type OidcProviderConfigResponse, type P10QuorumStatusResponse, type ProvisionScimUserRequest, type ScimUserListResponse, type ScimUserResource, type SiemAuditExportResponse } from "./platformEnterprise.js";
import { type KbrainFactRecord, type KbrainFactResolution, type KhubSkillListResponse, type ListKhubSkillsParams, type RecordKbrainFactRequest, type ResolveKbrainFactRequest, type SearchKbrainFactsParams, type SearchKbrainFactsResponse, type VerifyKhubMirrorRequest, type VerifyKhubMirrorResponse } from "./platformKbrain.js";
import type { RequestOptions } from "./types.js";
export type PlatformJsonRequester = <T>(method: string, path: string, params?: {
    query?: Record<string, string>;
    body?: Record<string, unknown>;
    options?: RequestOptions;
}) => Promise<T>;
export declare class PlatformNamespace {
    private readonly requestJson;
    private readonly runtime;
    private readonly mcpEval;
    private readonly kflow;
    private readonly enterprise;
    private readonly kbrain;
    constructor(requestJson: PlatformJsonRequester, requestSse?: PlatformSseRequester);
    overview(params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PlatformOverviewResponse>;
    listTiers(options?: RequestOptions): Promise<SubscriptionTiersResponse>;
    checkQuota(req: QuotaCheckRequest, options?: RequestOptions): Promise<QuotaCheckResponse>;
    validateByom(req: ValidateByomRequest, options?: RequestOptions): Promise<ValidateByomResponse>;
    checkModelLicense(req: CheckModelLicenseRequest, options?: RequestOptions): Promise<CheckModelLicenseResponse>;
    listMarketplacePackages(params?: ListMarketplacePackagesParams, options?: RequestOptions): Promise<MarketplacePackageListResponse>;
    scanMarketplacePackage(pkg: MarketplacePackageInput, options?: RequestOptions): Promise<MarketplaceScanReport>;
    publishMarketplacePackage(pkg: MarketplacePackageInput, options?: RequestOptions): Promise<MarketplacePackageRecord>;
    installMarketplacePackage(req: InstallMarketplacePackageRequest, options?: RequestOptions): Promise<InstallMarketplacePackageResponse>;
    purchaseMarketplacePackage(req: PurchaseMarketplacePackageRequest | string, options?: RequestOptions): Promise<MarketplaceSettlementRecord>;
    listMarketplaceSettlements(params?: ListMarketplaceSettlementsParams | string, options?: RequestOptions): Promise<MarketplaceSettlementSummaryResponse>;
    listAgents(params?: {
        workspace_id?: string;
    }, options?: RequestOptions): Promise<LifecycleAgentsResponse>;
    dispatchTeam(req: DispatchTeamRequest, options?: RequestOptions): Promise<TeamRunResponse>;
    listIssues(params?: ListIssuesParams, options?: RequestOptions): Promise<PlatformIssueListResponse>;
    createIssue(req: CreateIssueRequest, options?: RequestOptions): Promise<PlatformIssueRecord>;
    listPrds(params?: {
        workspace_id?: string;
    }, options?: RequestOptions): Promise<PlatformPrdListResponse>;
    createPrd(req: CreatePrdRequest, options?: RequestOptions): Promise<PlatformPrdRecord>;
    listWorkflows(params?: {
        workspace_id?: string;
    }, options?: RequestOptions): Promise<PlatformWorkflowListResponse>;
    createWorkflow(req: CreateWorkflowRequest, options?: RequestOptions): Promise<PlatformWorkflowRecord>;
    compileBlueprint(req: CompileBlueprintRequest, options?: RequestOptions): Promise<CompiledBlueprintResponse>;
    listExtensions(params?: ListExtensionsParams, options?: RequestOptions): Promise<PlatformExtensionListResponse>;
    registerExtension(extension: ExtensionSpecInput, options?: RequestOptions): Promise<PlatformExtensionRecord>;
    listDocs(params?: PT.ListDocsParams | string, options?: RequestOptions): Promise<PT.PlatformDocListResponse>;
    createDoc(req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord>;
    updateDoc(docId: string, req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord>;
    updateIssue(issueId: string, patch: PT.UpdateIssueRequest, options?: RequestOptions): Promise<PlatformIssueRecord>;
    listFeedback(params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.PlatformFeedbackListResponse>;
    createFeedback(req: PT.CreateFeedbackRequest, options?: RequestOptions): Promise<PT.PlatformFeedbackRecord>;
    scanWorkspaceSecurity(req: PT.WorkspaceSecurityScanRequest, options?: RequestOptions): Promise<PT.WorkspaceSecurityScanReport>;
    listWorkspaces(options?: RequestOptions): Promise<PT.PlatformWorkspaceListResponse>;
    createWorkspace(req: PT.CreateWorkspaceRequest, options?: RequestOptions): Promise<PT.PlatformWorkspaceRecord>;
    listRbacMembers(params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.RbacMemberListResponse>;
    upsertRbacMember(req: PT.UpsertRbacMemberRequest, options?: RequestOptions): Promise<PT.RbacMemberRecord>;
    checkRbac(req: PT.CheckRbacRequest, options?: RequestOptions): Promise<PT.CheckRbacResponse>;
    listSecrets(params?: PT.ListSecretsParams | string, options?: RequestOptions): Promise<PT.VaultSecretListResponse>;
    putSecret(req: PT.PutSecretRequest, options?: RequestOptions): Promise<PT.VaultSecretMetadata>;
    rotateSecret(name: string, req: PT.RotateSecretRequest | string, options?: RequestOptions): Promise<PT.VaultSecretMetadata>;
    deleteSecret(name: string, params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.DeleteSecretResponse>;
    listWebhooks(params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.WebhookListResponse>;
    createWebhook(req: PT.CreateWebhookRequest, options?: RequestOptions): Promise<PT.WebhookRecord>;
    deleteWebhook(webhookId: string, params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.DeleteWebhookResponse>;
    testWebhook(webhookId: string, req?: PT.TestWebhookRequest, options?: RequestOptions): Promise<PT.WebhookTestReceipt>;
    verifyWebhook(req: PT.VerifyWebhookRequest, options?: RequestOptions): Promise<PT.VerifyWebhookResponse>;
    startExecutionRun(req: PT.StartExecutionRunRequest, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot>;
    resolveExecutionP10(runId: string, req: PT.ResolveExecutionP10Request, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot>;
    streamExecutionEvents(runId: string, options?: PT.StreamExecutionEventsOptions): AsyncGenerator<Record<string, unknown>, void, unknown>;
    simulatePricing(req?: PT.PricingSimulationRequest, options?: RequestOptions): Promise<Record<string, unknown>>;
    listMcpServers(params?: ListMcpServersParams | string, options?: RequestOptions): Promise<McpServerListResponse>;
    registerMcpServer(req: RegisterMcpServerRequest, options?: RequestOptions): Promise<McpServerRecord>;
    deleteMcpServer(serverId: string, params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<DeleteMcpServerResponse>;
    listMcpTools(params?: ListMcpToolsParams | string, options?: RequestOptions): Promise<McpToolListResponse>;
    callMcpTool(req: CallMcpToolRequest, options?: RequestOptions): Promise<CallMcpToolResponse>;
    callMcpTool(toolName: string, args?: Record<string, unknown>, workspaceId?: string, options?: RequestOptions): Promise<CallMcpToolResponse>;
    runGoldenEvals(req?: RunGoldenEvalsRequest | string, options?: RequestOptions): Promise<GoldenEvalReport>;
    getLatestGoldenEvals(params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<LatestGoldenEvalsResponse>;
    executeKflowDag(req: ExecuteKflowDagRequest, options?: RequestOptions): Promise<KflowRunReceipt>;
    listKflowRuns(params?: ListKflowRunsParams | string, options?: RequestOptions): Promise<KflowRunListResponse>;
    syncKspacesCrdt(req: SyncKspacesCrdtRequest, options?: RequestOptions): Promise<KspacesSyncResponse>;
    getKspacesState(params?: GetKspacesStateParams | string, options?: RequestOptions): Promise<KspacesStateResponse>;
    getPlatformSbom(params?: GetPlatformSbomParams | string, options?: RequestOptions): Promise<PlatformSbomResponse>;
    configureOidcProvider(req: ConfigureOidcProviderRequest, options?: RequestOptions): Promise<OidcProviderConfigResponse>;
    listScimUsers(params?: ListScimUsersParams | string, options?: RequestOptions): Promise<ScimUserListResponse>;
    provisionScimUser(req: ProvisionScimUserRequest, options?: RequestOptions): Promise<ScimUserResource>;
    approveP10Quorum(req: ApproveP10QuorumRequest, options?: RequestOptions): Promise<P10QuorumStatusResponse>;
    exportSiemAudit(params?: ExportSiemAuditParams | string, options?: RequestOptions): Promise<SiemAuditExportResponse>;
    getObservabilityMetrics(params?: GetObservabilityMetricsParams | string, options?: RequestOptions): Promise<ObservabilityMetricsResponse>;
    recordKbrainFact(req: RecordKbrainFactRequest, options?: RequestOptions): Promise<KbrainFactRecord>;
    searchKbrainFacts(params?: SearchKbrainFactsParams | string, options?: RequestOptions): Promise<SearchKbrainFactsResponse>;
    resolveKbrainFact(factId: string, req: ResolveKbrainFactRequest | KbrainFactResolution, options?: RequestOptions): Promise<KbrainFactRecord>;
    listKhubSkills(params?: ListKhubSkillsParams | string, options?: RequestOptions): Promise<KhubSkillListResponse>;
    verifyKhubMirror(req?: VerifyKhubMirrorRequest | string[], options?: RequestOptions): Promise<VerifyKhubMirrorResponse>;
}
//# sourceMappingURL=platform.d.ts.map