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

const DEFAULT_SHADOW_PROMPT = "Refactor retry loop with bounded exponential backoff in Python";
const DEFAULT_SHADOW_RESPONSE =
  "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))";

function assertExportFormat(fmt: DistillationExportFormat): DistillationExportFormat {
  switch (fmt) {
    case "sft_jsonl":
    case "dpo_preference":
      return fmt;
    default: {
      const _exhaustive: never = fmt;
      throw new Error(`Invalid export_format '${String(_exhaustive)}'.`);
    }
  }
}

function cleanNonEmpty(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return clean;
}

function assertUnitScore(val: number, fieldName: string): number {
  if (typeof val !== "number" || Number.isNaN(val) || val < 0 || val > 1) {
    throw new Error(`${fieldName} must be between 0.0 and 1.0.`);
  }
  return val;
}

function resolveDistillListCall(
  wsOrOpts: string | ListShadowPairsOptions | undefined,
  limitOrOpts: number | RequestOptions | undefined,
  options: RequestOptions | undefined,
): { query: Record<string, string>; options?: RequestOptions } {
  const isObj = typeof wsOrOpts === "object" && wsOrOpts !== null;
  const wsId = ((isObj ? wsOrOpts.workspace_id : wsOrOpts) ?? "default").trim() || "default";
  const limit = isObj ? (wsOrOpts.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
  const opts = isObj ? (limitOrOpts as RequestOptions | undefined) : typeof limitOrOpts === "object" ? limitOrOpts : options;
  if (!Number.isInteger(limit) || limit < 1) throw new Error("limit must be >= 1.");
  const query: Record<string, string> = { workspace_id: wsId, limit: String(limit) };
  if (isObj && wsOrOpts.task_tag !== undefined && wsOrOpts.task_tag.trim() !== "") {
    query.task_tag = wsOrOpts.task_tag.trim();
  }
  return { query, options: opts };
}

export class PlatformDistillClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public evaluateShadowPrompt(req: EvaluateShadowPromptRequest = {}, options?: RequestOptions): Promise<ShadowEvaluationRecord> {
    const frontierCost = req.frontier_cost_usd ?? 0.018;
    const frontierLatency = req.frontier_latency_ms ?? 840;
    const localLatency = req.local_latency_ms ?? 95;
    if (typeof frontierCost !== "number" || Number.isNaN(frontierCost) || frontierCost < 0) throw new Error("frontier_cost_usd must be >= 0.");
    if (!Number.isFinite(frontierLatency) || frontierLatency < 0) throw new Error("frontier_latency_ms must be >= 0.");
    if (!Number.isFinite(localLatency) || localLatency < 0) throw new Error("local_latency_ms must be >= 0.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      task_tag: cleanNonEmpty(req.task_tag ?? "code-patch", "task_tag"),
      prompt: cleanNonEmpty(req.prompt ?? DEFAULT_SHADOW_PROMPT, "prompt"),
      frontier_model: cleanNonEmpty(req.frontier_model ?? "claude-3-7-sonnet", "frontier_model"),
      local_model: cleanNonEmpty(req.local_model ?? "keelway-core:7b", "local_model"),
      frontier_response: cleanNonEmpty(req.frontier_response ?? DEFAULT_SHADOW_RESPONSE, "frontier_response"),
      local_response: cleanNonEmpty(req.local_response ?? DEFAULT_SHADOW_RESPONSE, "local_response"),
      frontier_cost_usd: frontierCost,
      frontier_latency_ms: frontierLatency,
      local_latency_ms: localLatency,
      similarity_threshold: assertUnitScore(req.similarity_threshold ?? 0.82, "similarity_threshold"),
      bypass_cache: Boolean(req.bypass_cache ?? false),
    };
    return this.requestJson("POST", "/v1/platform/distill/shadow/evaluate", { body, options });
  }

  public listShadowPairs(wsOrOpts?: string | ListShadowPairsOptions, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<ShadowPairListResponse> {
    return this.requestJson("GET", "/v1/platform/distill/shadow/pairs", resolveDistillListCall(wsOrOpts, limitOrOpts, options));
  }

  public getSemanticCacheStats(wsOrParams: string | GetSemanticCacheStatsParams = "default", options?: RequestOptions): Promise<SemanticCacheStatsResponse> {
    const wsId = ((typeof wsOrParams === "string" ? wsOrParams : wsOrParams.workspace_id) ?? "default").trim() || "default";
    return this.requestJson("GET", "/v1/platform/distill/cache/stats", { query: { workspace_id: wsId }, options });
  }

  public compileDistillationDataset(req: CompileDistillationDatasetRequest = {}, options?: RequestOptions): Promise<DistillationDatasetRecord> {
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      task_tag: (req.task_tag ?? "").trim(),
      export_format: assertExportFormat(req.export_format ?? "dpo_preference"),
      target_base_model: cleanNonEmpty(req.target_base_model ?? "keelway-core:7b", "target_base_model"),
      min_parity_score: assertUnitScore(req.min_parity_score ?? 0.0, "min_parity_score"),
    };
    return this.requestJson("POST", "/v1/platform/distill/datasets/compile", { body, options });
  }

  public listDistillationDatasets(wsOrParams?: string | ListDistillationDatasetsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<DistillationDatasetListResponse> {
    return this.requestJson("GET", "/v1/platform/distill/datasets", resolveDistillListCall(wsOrParams, limitOrOpts, options));
  }

  public evaluateDistillationPromotion(req: EvaluateDistillationPromotionRequest = {}, options?: RequestOptions): Promise<DistillationPromotionEvaluation> {
    const minPairs = req.min_pairs ?? 3;
    const monthlyVolume = req.monthly_request_volume ?? 50000;
    if (!Number.isInteger(minPairs) || minPairs < 1) throw new Error("min_pairs must be >= 1.");
    if (!Number.isInteger(monthlyVolume) || monthlyVolume < 1) throw new Error("monthly_request_volume must be >= 1.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      task_tag: cleanNonEmpty(req.task_tag ?? "code-patch", "task_tag"),
      target_local_model: cleanNonEmpty(req.target_local_model ?? "keelway-core:7b", "target_local_model"),
      min_pairs: minPairs,
      min_avg_parity: assertUnitScore(req.min_avg_parity ?? 0.85, "min_avg_parity"),
      monthly_request_volume: monthlyVolume,
    };
    return this.requestJson("POST", "/v1/platform/distill/promotion/evaluate", { body, options });
  }
}

export { PlatformDistillClient as PlatformDistillDelegate };
