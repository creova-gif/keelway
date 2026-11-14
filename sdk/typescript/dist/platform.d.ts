/**
 * Keelway Official TypeScript SDK — Unified Platform Namespace (`client.platform`).
 *
 * Exposes all 20 `/v1/platform/*` endpoints using `KeelwayClient`'s zero-dependency
 * Web Fetch, `AbortSignal` timeout, and `mapHttpError` infrastructure.
 */
import type { CheckModelLicenseRequest, CheckModelLicenseResponse, CompileBlueprintRequest, CompiledBlueprintResponse, CreateIssueRequest, CreatePrdRequest, CreateWorkflowRequest, DispatchTeamRequest, ExtensionSpecInput, InstallMarketplacePackageRequest, InstallMarketplacePackageResponse, LifecycleAgentsResponse, ListExtensionsParams, ListIssuesParams, ListMarketplacePackagesParams, MarketplacePackageInput, MarketplacePackageListResponse, MarketplacePackageRecord, MarketplaceScanReport, PlatformExtensionListResponse, PlatformExtensionRecord, PlatformIssueListResponse, PlatformIssueRecord, PlatformOverviewParams, PlatformOverviewResponse, PlatformPrdListResponse, PlatformPrdRecord, PlatformWorkflowListResponse, PlatformWorkflowRecord, QuotaCheckRequest, QuotaCheckResponse, SubscriptionTiersResponse, TeamRunResponse, ValidateByomRequest, ValidateByomResponse } from "./platform-types.js";
import type { RequestOptions } from "./types.js";
export type PlatformJsonRequester = <T>(method: string, path: string, params?: {
    query?: Record<string, string>;
    body?: Record<string, unknown>;
    options?: RequestOptions;
}) => Promise<T>;
export declare class PlatformNamespace {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    overview(params?: PlatformOverviewParams | string, options?: RequestOptions): Promise<PlatformOverviewResponse>;
    listTiers(options?: RequestOptions): Promise<SubscriptionTiersResponse>;
    checkQuota(req: QuotaCheckRequest, options?: RequestOptions): Promise<QuotaCheckResponse>;
    validateByom(req: ValidateByomRequest, options?: RequestOptions): Promise<ValidateByomResponse>;
    checkModelLicense(req: CheckModelLicenseRequest, options?: RequestOptions): Promise<CheckModelLicenseResponse>;
    listMarketplacePackages(params?: ListMarketplacePackagesParams, options?: RequestOptions): Promise<MarketplacePackageListResponse>;
    scanMarketplacePackage(pkg: MarketplacePackageInput, options?: RequestOptions): Promise<MarketplaceScanReport>;
    publishMarketplacePackage(pkg: MarketplacePackageInput, options?: RequestOptions): Promise<MarketplacePackageRecord>;
    installMarketplacePackage(req: InstallMarketplacePackageRequest, options?: RequestOptions): Promise<InstallMarketplacePackageResponse>;
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
}
//# sourceMappingURL=platform.d.ts.map