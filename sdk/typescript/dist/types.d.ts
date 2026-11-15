/**
 * Keelway Official TypeScript SDK — Request, Response, and Domain Types.
 *
 * Zero runtime dependencies; compatible with Node 20+, Bun, Deno,
 * Cloudflare Workers, and modern browsers.
 */
export type FetchLike = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
export interface KeelwayClientOptions {
    /** Base URL of the Keelway daemon or enterprise gateway. Defaults to `"http://127.0.0.1:7420"`. */
    baseUrl?: string;
    /** Scoped `kw_live_*` API key or session bearer token. Sent exclusively in `Authorization: Bearer <key>`. */
    apiKey?: string;
    /** Alias for `apiKey` (Python SDK parity). */
    token?: string;
    /** Per-request timeout in milliseconds before aborting. Defaults to `30000` (30s). */
    timeoutMs?: number;
    /** Custom `fetch` implementation for testing, custom TLS agents, or edge runtimes. */
    fetchImpl?: FetchLike;
    /** Additional static headers merged into every request. */
    defaultHeaders?: Record<string, string>;
}
export interface RequestOptions {
    /** Optional caller-controlled `AbortSignal` combined with client `timeoutMs`. */
    signal?: AbortSignal;
    /** Per-request timeout override in milliseconds. */
    timeoutMs?: number;
    /** Additional per-request headers. */
    headers?: Record<string, string>;
}
export type ModelCategory = "open_weight" | "closed_proprietary" | (string & {});
export type PrivacyLevel = "standard" | "private" | "air_gap" | (string & {});
export type ChatRole = "system" | "developer" | "user" | "assistant" | "tool";
export interface ChatMessage {
    role: ChatRole;
    content: string;
}
export interface ResponseFormat {
    type: "text" | "json_object" | "json_schema" | (string & {});
    json_schema?: Record<string, unknown>;
}
export interface ModelsListParams {
    category?: ModelCategory;
    provider?: string;
    capability?: string;
}
export interface ModelDescriptor {
    id: string;
    object?: string;
    category: ModelCategory;
    provider?: string;
    owned_by?: string;
    deployment?: string;
    deployment_type?: string;
    license?: string;
    context_window?: number;
    capabilities?: string[];
    input_cost_per_1m_usd?: number;
    output_cost_per_1m_usd?: number;
    [key: string]: unknown;
}
export interface ModelListResponse {
    object: "list" | string;
    data: ModelDescriptor[];
    [key: string]: unknown;
}
export interface UsageSummary {
    currency?: string;
    total_cost_usd: number;
    billed_cloud_expenditure_usd?: number;
    quantified_local_savings_usd?: number;
    sovereign_efficiency_index?: number;
    local_inference_ratio?: number;
    entries_recorded?: number;
    [key: string]: unknown;
}
export interface ChatCompletionBaseRequest {
    /** Prompt shorthand string or array of structured chat messages. */
    messages: string | ChatMessage[];
    model?: string;
    temperature?: number;
    max_tokens?: number;
    response_format?: ResponseFormat;
    privacy_level?: PrivacyLevel;
    required_capabilities?: string[];
    max_cost_usd?: number;
}
export interface ChatCompletionCreateRequest extends ChatCompletionBaseRequest {
    stream?: false;
}
export interface ChatCompletionStreamRequest extends ChatCompletionBaseRequest {
    stream?: true;
}
export interface ChatCompletionChoice {
    index: number;
    message: {
        role: ChatRole;
        content: string;
    };
    finish_reason?: string | null;
}
export interface TokenUsage {
    prompt_tokens?: number;
    completion_tokens?: number;
    input_tokens?: number;
    output_tokens?: number;
    total_tokens: number;
}
export interface ChatCompletionResponse {
    id: string;
    object: "chat.completion" | string;
    created?: number;
    model: string;
    choices: ChatCompletionChoice[];
    usage?: TokenUsage;
    keelway_metadata?: Record<string, unknown>;
    [key: string]: unknown;
}
export interface ChatStreamDelta {
    role?: ChatRole;
    content?: string;
    [key: string]: unknown;
}
export interface ChatStreamChoice {
    index: number;
    delta: ChatStreamDelta;
    finish_reason?: string | null;
}
export interface ChatStreamChunk {
    id: string;
    object?: "chat.completion.chunk" | string;
    created?: number;
    model?: string;
    choices: ChatStreamChoice[];
    usage?: TokenUsage;
    [key: string]: unknown;
}
export interface ResponseInputContentBlock {
    type?: string;
    text: string;
    annotations?: unknown[];
}
export interface ResponseInputItem {
    role?: ChatRole;
    content: string | ResponseInputContentBlock[];
}
export interface ResponseCreateBaseRequest {
    input: string | ResponseInputItem[];
    model?: string;
    instructions?: string;
    previous_response_id?: string;
    temperature?: number;
    max_output_tokens?: number;
    text?: {
        format?: ResponseFormat;
        [key: string]: unknown;
    };
    store?: boolean;
    privacy_level?: PrivacyLevel;
    required_capabilities?: string[];
    max_cost_usd?: number;
    speculative?: boolean;
    draft_model?: string;
}
export interface ResponseCreateRequest extends ResponseCreateBaseRequest {
    stream?: false;
}
export interface ResponseStreamRequest extends ResponseCreateBaseRequest {
    stream?: true;
}
export interface ResponseOutputItem {
    id: string;
    type: "message" | string;
    status: string;
    role: ChatRole;
    content: ResponseInputContentBlock[];
}
export interface ResponseObject {
    id: string;
    object: "response" | string;
    created_at?: number;
    status?: string;
    model: string;
    previous_response_id?: string | null;
    output?: ResponseOutputItem[];
    output_text: string;
    usage?: TokenUsage;
    keelway_metadata?: Record<string, unknown>;
    [key: string]: unknown;
}
export interface ResponseStreamEvent {
    type: "response.created" | "response.output_text.delta" | "response.completed" | "error" | (string & {});
    event?: string;
    response_id?: string;
    item_id?: string;
    output_index?: number;
    content_index?: number;
    delta?: string;
    response?: ResponseObject;
    error?: {
        message: string;
        [key: string]: unknown;
    };
    [key: string]: unknown;
}
export interface GovernanceProvenance4D {
    license?: string;
    model_license?: string;
    weight_category?: ModelCategory;
    hosting?: string;
    hosting_location?: string;
    operator?: string;
    inference_operator?: string;
    data_boundary?: string;
    data_residency_boundary?: string;
    open_weight_implies_local?: boolean;
    residency_note?: string;
    [key: string]: unknown;
}
export interface RoutingExplainRequest {
    messages?: string | ChatMessage[];
    prompt?: string;
    model?: string;
    max_tokens?: number;
    privacy_level?: PrivacyLevel;
    required_capabilities?: string[];
    max_cost_usd?: number;
    preferred_provider?: string;
    category_preference?: ModelCategory;
    endpoint_url?: string;
}
export interface RoutingExplainResponse {
    decision_id?: string;
    timestamp?: number;
    requested_model?: string | null;
    selected_model?: string | null;
    selected_provider?: string | null;
    fallback_chain: string[];
    reason?: string;
    routing_reason?: string;
    governance_provenance?: GovernanceProvenance4D;
    provenance?: GovernanceProvenance4D;
    estimated_cost_usd?: number;
    privacy_level?: PrivacyLevel;
    privacy_compliant?: boolean;
    [key: string]: unknown;
}
export interface RoutingDecisionsResponse {
    object: "list" | string;
    count: number;
    decisions: RoutingExplainResponse[];
}
export interface OpenCoreStatusResponse {
    status: string;
    hardware: Record<string, unknown>;
    telemetry: Record<string, unknown>;
    [key: string]: unknown;
}
export interface OpenCoreWeightManifest {
    model_id: string;
    quantization: string;
    is_cached: boolean;
    local_path?: string;
    [key: string]: unknown;
}
export interface CompileModelfileRequest {
    model_id?: string;
    base_source?: string;
    quantization?: string;
    adapter_id?: string;
    temperature?: number;
    top_p?: number;
    num_ctx?: number;
    modelfile_path?: string;
}
export interface CompileModelfileResponse {
    model_id: string;
    modelfile: string;
    cli_command?: string;
    spec?: Record<string, unknown>;
    sha256?: string;
    [key: string]: unknown;
}
export interface LoRAAdapterDescriptor {
    adapter_id: string;
    name: string;
    base_model_id: string;
    task?: string;
    languages?: string[];
    adapter_path?: string;
    sha256_checksum?: string;
    lora_r?: number;
    lora_alpha?: number;
    attached_models?: string[];
    is_attached?: boolean;
    [key: string]: unknown;
}
export interface OpenCoreAdaptersResponse {
    adapters: LoRAAdapterDescriptor[];
    attached_by_model: Record<string, string>;
}
export interface LoadOpenCoreModelRequest {
    model_id: string;
    quantization?: string;
    backend?: string;
    base_model_override?: string;
}
export interface AdaptRecipeRequest {
    base_model_id?: string;
    task?: string;
    target_languages?: string[];
}
export type DataResidencyZone = "global" | "zero_egress" | "eu_sovereign" | "africa_sovereign" | "us_sovereign" | (string & {});
export interface TenantPolicy {
    tenant_id: string;
    name: string;
    allowed_categories?: string[];
    allowed_providers?: string[];
    residency_zone?: DataResidencyZone;
    daily_spend_limit_usd?: number;
    monthly_spend_limit_usd?: number;
    fallback_to_opencore_on_budget_exceeded?: boolean;
    requests_per_minute?: number;
    tokens_per_minute?: number;
    log_redacted_prompts?: boolean;
    retention_days?: number;
    [key: string]: unknown;
}
export type TenantPolicyUpsertRequest = TenantPolicy;
export interface IssueKeyRequest {
    tenant_id: string;
    name: string;
    scopes?: string[];
    expires_at?: string;
}
export interface IssuedKeyResponse {
    key_id?: string;
    key_prefix?: string;
    tenant_id: string;
    name: string;
    scopes: string[];
    api_key: string;
    created_at?: string;
    expires_at?: string | null;
    revoked?: boolean;
    [key: string]: unknown;
}
export interface GovernanceEvaluateRequest {
    tenant_id: string;
    requested_model?: string;
    model?: string;
    provider?: string;
    category?: string;
    estimated_cost_usd?: number;
    estimated_tokens?: number;
    prompt_preview?: string;
    forbid_open_weight?: boolean;
    [key: string]: unknown;
}
export interface GovernanceDecisionResponse {
    allowed: boolean;
    action?: string;
    decision?: string;
    effective_model?: string | null;
    effective_provider?: string | null;
    reason?: string;
    status_code?: number;
    retry_after_seconds?: number;
    [key: string]: unknown;
}
export interface GovernanceAuditEntry {
    seq: number;
    timestamp?: string;
    tenant_id: string;
    action: string;
    outcome?: string;
    reason?: string;
    prompt_excerpt?: string | null;
    prev_hash?: string;
    entry_hash: string;
    [key: string]: unknown;
}
export interface GovernanceAuditResponse {
    entries: GovernanceAuditEntry[];
    total?: number;
    chain_valid: boolean;
    broken_at_seq?: number | null;
    [key: string]: unknown;
}
export interface SwarmEntitySpec {
    name: string;
    type: string;
    summary: string;
    tier?: "influencer" | "citizen" | (string & {});
    [key: string]: unknown;
}
export interface SwarmEvaluateRequest {
    seed_text?: string;
    simulation_goal?: string;
    entities_spec?: SwarmEntitySpec[];
    rounds?: number;
    injected_event?: string;
    mode?: "mock" | "live";
    frontier_model?: string;
    opencore_model?: string;
    draft_model?: string;
}
export interface SwarmEvaluateResponse {
    mode?: string;
    graph_id: string;
    ontology?: Record<string, unknown>;
    profiles?: Record<string, unknown>[];
    episodes?: Record<string, unknown>[];
    speculative_report?: string;
    speculative_acceptance_rate?: number;
    security_checks?: Record<string, unknown>;
    savings_pct?: number;
    open_weight_calls?: number;
    closed_cloud_calls?: number;
    telemetry?: {
        total_calls: number;
        open_weight_calls: number;
        closed_cloud_calls: number;
        total_cost_usd: number;
        estimated_all_cloud_cost_usd: number;
        savings_pct: number;
        elapsed_ms: number;
        [key: string]: unknown;
    };
    [key: string]: unknown;
}
export type * from "./platformMcpEval.js";
export type * from "./platformKflow.js";
export type * from "./platformEnterprise.js";
export type * from "./platformKbrain.js";
//# sourceMappingURL=types.d.ts.map