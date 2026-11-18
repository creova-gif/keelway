/**
 * Keelway Client SDK — Zero-Dependency TypeScript Interface for Keelway Unified AI Platform.
 *
 * Uses native Web Fetch, ReadableStream, TextDecoder, and AbortSignal so a single
 * build runs identically across Node 20+, Bun, Deno, Cloudflare Workers, and browsers.
 */
import { ClusterNamespace } from "./cluster.js";
import { PlatformNamespace } from "./platform.js";
import type { AdaptRecipeRequest, ChatCompletionCreateRequest, ChatCompletionResponse, ChatCompletionStreamRequest, ChatStreamChunk, CompileModelfileRequest, CompileModelfileResponse, GovernanceAuditResponse, GovernanceDecisionResponse, GovernanceEvaluateRequest, IssuedKeyResponse, IssueKeyRequest, KeelwayClientOptions, LoadOpenCoreModelRequest, ModelListResponse, ModelsListParams, OpenCoreAdaptersResponse, OpenCoreStatusResponse, OpenCoreWeightManifest, RequestOptions, ResponseCreateRequest, ResponseObject, ResponseStreamEvent, ResponseStreamRequest, RoutingDecisionsResponse, RoutingExplainRequest, RoutingExplainResponse, SwarmEvaluateRequest, SwarmEvaluateResponse, TenantPolicy, TenantPolicyUpsertRequest, UsageSummary } from "./types.js";
/**
 * Official Keelway Platform Client (`@keelway/sdk` v1.0.0).
 */
export declare class KeelwayClient {
    readonly baseUrl: string;
    readonly timeoutMs: number;
    private readonly apiKey?;
    private readonly fetchImpl;
    private readonly defaultHeaders;
    readonly models: {
        list: (params?: ModelsListParams, options?: RequestOptions) => Promise<ModelListResponse>;
    };
    readonly usage: {
        get: (options?: RequestOptions) => Promise<UsageSummary>;
    };
    readonly chat: {
        completions: {
            create: (request: ChatCompletionCreateRequest, options?: RequestOptions) => Promise<ChatCompletionResponse>;
            stream: (request: ChatCompletionStreamRequest, options?: RequestOptions) => AsyncGenerator<ChatStreamChunk, void, unknown>;
        };
    };
    readonly responses: {
        create: (request: ResponseCreateRequest, options?: RequestOptions) => Promise<ResponseObject>;
        get: (responseId: string, options?: RequestOptions) => Promise<ResponseObject>;
        stream: (request: ResponseStreamRequest, options?: RequestOptions) => AsyncGenerator<ResponseStreamEvent, void, unknown>;
    };
    readonly routing: {
        explain: (request: RoutingExplainRequest, options?: RequestOptions) => Promise<RoutingExplainResponse>;
        decisions: (params?: {
            limit?: number;
        }, options?: RequestOptions) => Promise<RoutingDecisionsResponse>;
    };
    readonly opencore: {
        status: (options?: RequestOptions) => Promise<OpenCoreStatusResponse>;
        weights: (options?: RequestOptions) => Promise<OpenCoreWeightManifest[]>;
        compileModelfile: (req: CompileModelfileRequest, options?: RequestOptions) => Promise<CompileModelfileResponse>;
        adapters: (params?: {
            base_model_id?: string;
        }, options?: RequestOptions) => Promise<OpenCoreAdaptersResponse>;
        loadModel: (req: LoadOpenCoreModelRequest, options?: RequestOptions) => Promise<Record<string, unknown>>;
        unloadModel: (modelId: string, options?: RequestOptions) => Promise<Record<string, unknown>>;
        adaptRecipe: (req: AdaptRecipeRequest, options?: RequestOptions) => Promise<Record<string, unknown>>;
    };
    readonly governance: {
        upsertPolicy: (policy: TenantPolicyUpsertRequest, options?: RequestOptions) => Promise<TenantPolicy>;
        getPolicy: (tenantId: string, options?: RequestOptions) => Promise<TenantPolicy>;
        listPolicies: (options?: RequestOptions) => Promise<TenantPolicy[]>;
        issueKey: (req: IssueKeyRequest, options?: RequestOptions) => Promise<IssuedKeyResponse>;
        verifyAudit: (params?: {
            tenant_id?: string;
            limit?: number;
        }, options?: RequestOptions) => Promise<GovernanceAuditResponse>;
        evaluate: (req: GovernanceEvaluateRequest, options?: RequestOptions) => Promise<GovernanceDecisionResponse>;
    };
    readonly swarm: {
        evaluate: (req: SwarmEvaluateRequest, options?: RequestOptions) => Promise<SwarmEvaluateResponse>;
    };
    readonly platform: PlatformNamespace;
    readonly cluster: ClusterNamespace;
    constructor(options?: KeelwayClientOptions);
    /**
     * Probe Keelway daemon health (`/health`).
     */
    health(options?: RequestOptions): Promise<Record<string, unknown>>;
    private buildUrl;
    private buildHeaders;
    private mapTransportException;
    private requestJson;
    private requestSseFrames;
    private streamChatCompletions;
    private streamResponses;
}
//# sourceMappingURL=client.d.ts.map