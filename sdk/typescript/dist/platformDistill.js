/**
 * Keelway Official TypeScript SDK — Phase 19 Semantic Prompt Cache, Shadow Dual-Run Router
 * & QLoRA Distillation Flywheel (`client.platform`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
const DEFAULT_SHADOW_PROMPT = "Refactor retry loop with bounded exponential backoff in Python";
const DEFAULT_SHADOW_RESPONSE = "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))";
function assertExportFormat(fmt) {
    switch (fmt) {
        case "sft_jsonl":
        case "dpo_preference":
            return fmt;
        default: {
            const _exhaustive = fmt;
            throw new Error(`Invalid export_format '${String(_exhaustive)}'.`);
        }
    }
}
function cleanNonEmpty(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return clean;
}
function assertUnitScore(val, fieldName) {
    if (typeof val !== "number" || Number.isNaN(val) || val < 0 || val > 1) {
        throw new Error(`${fieldName} must be between 0.0 and 1.0.`);
    }
    return val;
}
function resolveDistillListCall(wsOrOpts, limitOrOpts, options) {
    const isObj = typeof wsOrOpts === "object" && wsOrOpts !== null;
    const wsId = ((isObj ? wsOrOpts.workspace_id : wsOrOpts) ?? "default").trim() || "default";
    const limit = isObj ? (wsOrOpts.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
    const opts = isObj ? limitOrOpts : typeof limitOrOpts === "object" ? limitOrOpts : options;
    if (!Number.isInteger(limit) || limit < 1)
        throw new Error("limit must be >= 1.");
    const query = { workspace_id: wsId, limit: String(limit) };
    if (isObj && wsOrOpts.task_tag !== undefined && wsOrOpts.task_tag.trim() !== "") {
        query.task_tag = wsOrOpts.task_tag.trim();
    }
    return { query, options: opts };
}
export class PlatformDistillClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    evaluateShadowPrompt(req = {}, options) {
        const frontierCost = req.frontier_cost_usd ?? 0.018;
        const frontierLatency = req.frontier_latency_ms ?? 840;
        const localLatency = req.local_latency_ms ?? 95;
        if (typeof frontierCost !== "number" || Number.isNaN(frontierCost) || frontierCost < 0)
            throw new Error("frontier_cost_usd must be >= 0.");
        if (!Number.isFinite(frontierLatency) || frontierLatency < 0)
            throw new Error("frontier_latency_ms must be >= 0.");
        if (!Number.isFinite(localLatency) || localLatency < 0)
            throw new Error("local_latency_ms must be >= 0.");
        const body = {
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
    listShadowPairs(wsOrOpts, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/distill/shadow/pairs", resolveDistillListCall(wsOrOpts, limitOrOpts, options));
    }
    getSemanticCacheStats(wsOrParams = "default", options) {
        const wsId = ((typeof wsOrParams === "string" ? wsOrParams : wsOrParams.workspace_id) ?? "default").trim() || "default";
        return this.requestJson("GET", "/v1/platform/distill/cache/stats", { query: { workspace_id: wsId }, options });
    }
    compileDistillationDataset(req = {}, options) {
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            task_tag: (req.task_tag ?? "").trim(),
            export_format: assertExportFormat(req.export_format ?? "dpo_preference"),
            target_base_model: cleanNonEmpty(req.target_base_model ?? "keelway-core:7b", "target_base_model"),
            min_parity_score: assertUnitScore(req.min_parity_score ?? 0.0, "min_parity_score"),
        };
        return this.requestJson("POST", "/v1/platform/distill/datasets/compile", { body, options });
    }
    listDistillationDatasets(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/distill/datasets", resolveDistillListCall(wsOrParams, limitOrOpts, options));
    }
    evaluateDistillationPromotion(req = {}, options) {
        const minPairs = req.min_pairs ?? 3;
        const monthlyVolume = req.monthly_request_volume ?? 50000;
        if (!Number.isInteger(minPairs) || minPairs < 1)
            throw new Error("min_pairs must be >= 1.");
        if (!Number.isInteger(monthlyVolume) || monthlyVolume < 1)
            throw new Error("monthly_request_volume must be >= 1.");
        const body = {
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
//# sourceMappingURL=platformDistill.js.map