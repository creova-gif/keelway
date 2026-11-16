/**
 * Keelway Official TypeScript SDK — Phase 16 Typed Structured-Output & Content-Block Normalizer
 * + Autonomous Self-Healing Failure Root-Causer (`client.platform` / `client.platform.healing`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function assertProviderFormat(fmt) {
    switch (fmt) {
        case "deepseek_opencore":
        case "openai":
        case "anthropic":
        case "gemini":
            return fmt;
        default: {
            const _exhaustive = fmt;
            throw new Error(`Invalid provider_format '${String(_exhaustive)}'.`);
        }
    }
}
function encodePathSeg(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
function buildHealingListQuery(paramsOrWs) {
    const params = typeof paramsOrWs === "string" ? { workspace_id: paramsOrWs } : paramsOrWs;
    const limit = params.limit ?? 25;
    if (!Number.isInteger(limit) || limit < 1)
        throw new Error("limit must be >= 1.");
    return { workspace_id: params.workspace_id ?? "default", limit: String(limit) };
}
export class PlatformHealingClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    normalizeContentBlocks(req, options) {
        const modelId = (req.model_id ?? "keelway-core:7b").trim();
        if (!modelId)
            throw new Error("model_id must be non-empty.");
        const body = {
            workspace_id: req.workspace_id ?? "default",
            provider_format: assertProviderFormat(req.provider_format ?? "deepseek_opencore"),
            model_id: modelId,
            raw_payload: req.raw_payload,
        };
        return this.requestJson("POST", "/v1/platform/healing/content-blocks/normalize", { body, options });
    }
    enforceStructuredOutput(req, options) {
        const schemaName = (req.schema_name ?? "AgentDecisionContract").trim();
        if (!schemaName)
            throw new Error("schema_name must be non-empty.");
        const modelId = (req.model_id ?? "keelway-core:7b").trim();
        if (!modelId)
            throw new Error("model_id must be non-empty.");
        if (req.json_schema === null || typeof req.json_schema !== "object" || Array.isArray(req.json_schema)) {
            throw new Error("json_schema must be an object.");
        }
        const body = {
            workspace_id: req.workspace_id ?? "default",
            schema_name: schemaName,
            provider_format: assertProviderFormat(req.provider_format ?? "deepseek_opencore"),
            model_id: modelId,
            json_schema: req.json_schema,
            raw_output: req.raw_output,
            strict_mode: req.strict_mode ?? false,
            fail_closed: req.fail_closed ?? true,
        };
        return this.requestJson("POST", "/v1/platform/healing/structured/enforce", { body, options });
    }
    listStructuredOutputRuns(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/healing/structured/runs", {
            query: buildHealingListQuery(params),
            options,
        });
    }
    diagnoseFailureRootCause(req = {}, options) {
        const wfName = (req.workflow_name ?? "invoice-triage-agent").trim();
        if (!wfName)
            throw new Error("workflow_name must be non-empty.");
        const body = {
            workspace_id: req.workspace_id ?? "default",
            workflow_name: wfName,
        };
        if (req.trace_id !== undefined && req.trace_id !== null && req.trace_id.trim() !== "") {
            body.trace_id = req.trace_id.trim();
        }
        if (req.failed_step !== undefined && req.failed_step !== null) {
            body.failed_step = req.failed_step;
        }
        return this.requestJson("POST", "/v1/platform/healing/root-cause/diagnose", { body, options });
    }
    applySelfHealingPatch(diagnosisId, req = {}, options) {
        const seg = encodePathSeg(diagnosisId, "diagnosis_id");
        const body = {
            workspace_id: req.workspace_id ?? "default",
            promote_to_eval: req.promote_to_eval ?? true,
        };
        if (req.eval_title !== undefined && req.eval_title !== null && req.eval_title.trim() !== "") {
            body.eval_title = req.eval_title.trim();
        }
        return this.requestJson("POST", `/v1/platform/healing/root-cause/${seg}/apply`, { body, options });
    }
    listSelfHealingDiagnoses(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/healing/root-cause/diagnoses", {
            query: buildHealingListQuery(params),
            options,
        });
    }
}
export { PlatformHealingClient as PlatformHealingDelegate };
//# sourceMappingURL=platformHealing.js.map