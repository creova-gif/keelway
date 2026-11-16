/**
 * Keelway Official TypeScript SDK — Phase 11 OpenTelemetry GenAI Flight-Tape Time-Travel,
 * 1-Click Trace-to-Eval Promotion & Static AST LangGraph Migration.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function devxSeg(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
export class PlatformDevxDelegate {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    ingestOtelTraces(payload, options) {
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            workflow_name: payload.workflow_name ?? "agent-trace",
            source_framework: payload.source_framework ?? "opentelemetry_genai",
        };
        if (payload.spans !== undefined) {
            body.spans = payload.spans;
        }
        const resSpans = payload.resourceSpans ?? payload.resource_spans;
        if (resSpans !== undefined) {
            body.resourceSpans = resSpans;
            body.resource_spans = resSpans;
        }
        if (payload.trace_id !== undefined && payload.trace_id.trim() !== "") {
            body.trace_id = payload.trace_id.trim();
        }
        return this.requestJson("POST", "/v1/platform/traces/ingest", { body, options });
    }
    listFlightTapes(workspaceIdOrParams = "default", limitOrOptions, options) {
        const isObj = typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null;
        const workspaceId = isObj
            ? (workspaceIdOrParams.workspace_id ?? "default")
            : (workspaceIdOrParams || "default");
        const limit = isObj
            ? (workspaceIdOrParams.limit ?? 20)
            : typeof limitOrOptions === "number"
                ? limitOrOptions
                : 20;
        const resolvedOptions = isObj
            ? limitOrOptions
            : typeof limitOrOptions === "object"
                ? limitOrOptions
                : options;
        return this.requestJson("GET", "/v1/platform/traces", {
            query: { workspace_id: workspaceId, limit: String(limit) },
            options: resolvedOptions,
        });
    }
    replayFlightTape(traceId, payload = {}, options) {
        const fromStep = payload.from_step_index ?? 0;
        if (fromStep < 0)
            throw new Error("from_step_index must be >= 0.");
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            from_step_index: fromStep,
        };
        if (payload.override_prompt !== undefined)
            body.override_prompt = payload.override_prompt;
        if (payload.override_model !== undefined)
            body.override_model = payload.override_model;
        if (payload.override_state !== undefined)
            body.override_state = payload.override_state;
        return this.requestJson("POST", `/v1/platform/traces/${devxSeg(traceId, "traceId")}/replay`, { body, options });
    }
    promoteTraceToEval(payload, options) {
        const cleanTraceId = payload.trace_id.trim();
        if (!cleanTraceId)
            throw new Error("trace_id must be non-empty.");
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            trace_id: cleanTraceId,
        };
        if (payload.title !== undefined)
            body.title = payload.title;
        if (payload.expected_substrings !== undefined) {
            body.expected_substrings = payload.expected_substrings;
        }
        if (payload.forbidden_substrings !== undefined) {
            body.forbidden_substrings = payload.forbidden_substrings;
        }
        return this.requestJson("POST", "/v1/platform/eval/dataset/promote", { body, options });
    }
    listEvalDatasetCases(workspaceIdOrParams = "default", options) {
        const workspaceId = typeof workspaceIdOrParams === "string"
            ? (workspaceIdOrParams || "default")
            : (workspaceIdOrParams?.workspace_id ?? "default");
        return this.requestJson("GET", "/v1/platform/eval/dataset", {
            query: { workspace_id: workspaceId },
            options,
        });
    }
    migrateLanggraphSource(payload, options) {
        if (!payload.source_code || !payload.source_code.trim()) {
            throw new Error("source_code must be non-empty.");
        }
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            source_code: payload.source_code,
            source_language: payload.source_language ?? "python",
        };
        if (payload.workflow_name !== undefined) {
            body.workflow_name = payload.workflow_name;
        }
        return this.requestJson("POST", "/v1/platform/migrate/langgraph", { body, options });
    }
}
//# sourceMappingURL=platformDevx.js.map