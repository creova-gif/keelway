/**
 * Keelway Official TypeScript SDK — Phase 19 Semantic Prompt Cache, Shadow Dual-Run Router
 * & QLoRA Distillation Flywheel (`client.platform`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type ShadowEvaluationVerdict = "CACHE_HIT" | "LOCAL_PARITY_READY" | "SHADOW_CAPTURED";
export type ShadowCacheMatchType = "exact_sha256" | "semantic_shingle" | "cache_miss";
export type DistillationExportFormat = "sft_jsonl" | "dpo_preference";
export type DistillationPromotionVerdict = "PROMOTE_TO_OPENCORE" | "NEEDS_MORE_PAIRS" | "HOLD_ON_FRONTIER";
export interface EvaluateShadowPromptRequest {
    workspace_id?: string;
    task_tag?: string;
    prompt?: string;
    frontier_model?: string;
    local_model?: string;
    frontier_response?: string;
    local_response?: string;
    frontier_cost_usd?: number;
    frontier_latency_ms?: number;
    local_latency_ms?: number;
    similarity_threshold?: number;
    bypass_cache?: boolean;
}
export interface ShadowEvaluationRecord {
    evaluation_id: string;
    pair_id: string | null;
    cache_entry_id: string;
    workspace_id: string;
    task_tag: string;
    verdict: ShadowEvaluationVerdict;
    match_type: ShadowCacheMatchType;
    similarity_score: number;
    parity_score: number;
    frontier_model: string;
    local_model: string;
    scrubbed_prompt: string;
    cached_response: string;
    cost_saved_usd: number;
    latency_saved_ms: number;
    dlp_redactions: number;
    event_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ShadowDistillPairRecord {
    pair_id: string;
    workspace_id: string;
    task_tag: string;
    scrubbed_prompt: string;
    scrubbed_frontier_response: string;
    scrubbed_local_response: string;
    frontier_model: string;
    local_model: string;
    parity_score: number;
    frontier_cost_usd: number;
    dlp_redactions: number;
    pair_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ListShadowPairsOptions {
    workspace_id?: string;
    task_tag?: string;
    limit?: number;
}
export type ListShadowPairsParams = ListShadowPairsOptions;
export interface ShadowPairListResponse {
    workspace_id: string;
    count: number;
    pairs: ShadowDistillPairRecord[];
    [key: string]: unknown;
}
export interface GetSemanticCacheStatsParams {
    workspace_id?: string;
}
export interface SemanticCacheStatsResponse {
    workspace_id: string;
    entry_count: number;
    total_hits: number;
    total_lookups: number;
    hit_rate: number;
    total_cost_saved_usd: number;
    total_latency_saved_ms: number;
    total_dlp_redactions: number;
    [key: string]: unknown;
}
export interface CompileDistillationDatasetRequest {
    workspace_id?: string;
    task_tag?: string;
    export_format?: DistillationExportFormat;
    target_base_model?: string;
    min_parity_score?: number;
}
export interface DistillationDatasetRecord {
    dataset_id: string;
    workspace_id: string;
    task_tag: string;
    export_format: DistillationExportFormat;
    target_base_model: string;
    record_count: number;
    avg_parity_score: number;
    lora_rank: number;
    lora_alpha: number;
    dlp_redactions: number;
    jsonl_preview: string;
    dataset_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ListDistillationDatasetsParams {
    workspace_id?: string;
    limit?: number;
}
export type ListDistillationDatasetsOptions = ListDistillationDatasetsParams;
export interface DistillationDatasetListResponse {
    workspace_id: string;
    count: number;
    datasets: DistillationDatasetRecord[];
    [key: string]: unknown;
}
export interface EvaluateDistillationPromotionRequest {
    workspace_id?: string;
    task_tag?: string;
    target_local_model?: string;
    min_pairs?: number;
    min_avg_parity?: number;
    monthly_request_volume?: number;
}
export interface DistillationPromotionEvaluation {
    evaluation_id: string;
    workspace_id: string;
    task_tag: string;
    target_local_model: string;
    verdict: DistillationPromotionVerdict;
    pair_count: number;
    min_pairs: number;
    avg_parity_score: number;
    min_avg_parity: number;
    avg_frontier_cost_usd: number;
    monthly_request_volume: number;
    projected_monthly_savings_usd: number;
    recommendation: string;
    gate_sha256: string;
    evaluated_at: string;
    [key: string]: unknown;
}
export declare class PlatformDistillClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    evaluateShadowPrompt(req?: EvaluateShadowPromptRequest, options?: RequestOptions): Promise<ShadowEvaluationRecord>;
    listShadowPairs(wsOrOpts?: string | ListShadowPairsOptions, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<ShadowPairListResponse>;
    getSemanticCacheStats(wsOrParams?: string | GetSemanticCacheStatsParams, options?: RequestOptions): Promise<SemanticCacheStatsResponse>;
    compileDistillationDataset(req?: CompileDistillationDatasetRequest, options?: RequestOptions): Promise<DistillationDatasetRecord>;
    listDistillationDatasets(wsOrParams?: string | ListDistillationDatasetsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<DistillationDatasetListResponse>;
    evaluateDistillationPromotion(req?: EvaluateDistillationPromotionRequest, options?: RequestOptions): Promise<DistillationPromotionEvaluation>;
}
export { PlatformDistillClient as PlatformDistillDelegate };
//# sourceMappingURL=platformDistill.d.ts.map