/**
 * Keelway Official TypeScript SDK — Phase 12 Golden-Thread Bidirectional KFlow Studio,
 * Sandbox Blast-Radius Radar & Prompt Regression Gate (`client.platform` / `client.platform.studio`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function assertDirection(direction) {
    switch (direction) {
        case "code_to_graph":
        case "graph_to_code":
            return direction;
        default: {
            const exhaustive = direction;
            throw new Error(`Invalid direction '${String(exhaustive)}': must be 'code_to_graph' or 'graph_to_code'.`);
        }
    }
}
function assertLanguage(language) {
    switch (language) {
        case "python":
        case "typescript":
            return language;
        default: {
            const exhaustive = language;
            throw new Error(`Invalid language '${String(exhaustive)}': must be 'python' or 'typescript'.`);
        }
    }
}
function studioWsId(params) {
    return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}
export class PlatformStudioClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    syncKflowStudio(payload = {}, options) {
        const direction = assertDirection(payload.direction ?? "code_to_graph");
        const language = assertLanguage(payload.language ?? "python");
        const workflowId = (payload.workflow_id ?? "WF-STUDIO-01").trim();
        if (!workflowId) {
            throw new Error("workflow_id must be non-empty.");
        }
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            direction,
            language,
            workflow_id: workflowId,
        };
        if (payload.source_code !== undefined)
            body.source_code = payload.source_code;
        if (payload.nodes !== undefined)
            body.nodes = payload.nodes;
        if (payload.persist !== undefined)
            body.persist = payload.persist;
        return this.requestJson("POST", "/v1/platform/studio/kflow/sync", { body, options });
    }
    recordBlastRadius(payload = {}, options) {
        if (payload.egress_attempts !== undefined && payload.egress_attempts < 0) {
            throw new Error("egress_attempts must be >= 0.");
        }
        if (payload.p10_gates_triggered !== undefined && payload.p10_gates_triggered < 0) {
            throw new Error("p10_gates_triggered must be >= 0.");
        }
        const body = {
            workspace_id: payload.workspace_id ?? "default",
        };
        if (payload.trace_id !== undefined && payload.trace_id.trim() !== "") {
            body.trace_id = payload.trace_id.trim();
        }
        if (payload.workflow_id !== undefined && payload.workflow_id.trim() !== "") {
            body.workflow_id = payload.workflow_id.trim();
        }
        if (payload.fs_reads !== undefined)
            body.fs_reads = payload.fs_reads;
        if (payload.fs_writes !== undefined)
            body.fs_writes = payload.fs_writes;
        if (payload.blocked_paths !== undefined)
            body.blocked_paths = payload.blocked_paths;
        if (payload.egress_attempts !== undefined)
            body.egress_attempts = payload.egress_attempts;
        if (payload.blocked_egress_hosts !== undefined)
            body.blocked_egress_hosts = payload.blocked_egress_hosts;
        if (payload.p10_gates_triggered !== undefined)
            body.p10_gates_triggered = payload.p10_gates_triggered;
        if (payload.seatbelted !== undefined)
            body.seatbelted = payload.seatbelted;
        return this.requestJson("POST", "/v1/platform/studio/blast-radius/record", { body, options });
    }
    listBlastRadiusAudits(paramsOrWorkspaceId = {}, options) {
        const limit = typeof paramsOrWorkspaceId === "string"
            ? 25
            : (paramsOrWorkspaceId.limit ?? 25);
        if (limit < 1) {
            throw new Error("limit must be >= 1.");
        }
        const query = {
            workspace_id: studioWsId(paramsOrWorkspaceId),
            limit: String(limit),
        };
        if (typeof paramsOrWorkspaceId !== "string" && paramsOrWorkspaceId.trace_id !== undefined) {
            const cleanTid = paramsOrWorkspaceId.trace_id.trim();
            if (cleanTid)
                query.trace_id = cleanTid;
        }
        return this.requestJson("GET", "/v1/platform/studio/blast-radius", { query, options });
    }
    evaluatePromptGate(payload, options) {
        const cleanVer = (payload.candidate_prompt_version ?? "").trim();
        if (!cleanVer) {
            throw new Error("candidate_prompt_version must be non-empty.");
        }
        const cleanModel = (payload.candidate_model_id ?? "").trim();
        if (!cleanModel) {
            throw new Error("candidate_model_id must be non-empty.");
        }
        if (payload.min_pass_rate !== undefined &&
            (payload.min_pass_rate < 0 || payload.min_pass_rate > 1)) {
            throw new Error("min_pass_rate must be between 0.0 and 1.0.");
        }
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            candidate_prompt_version: cleanVer,
            candidate_model_id: cleanModel,
        };
        if (payload.candidate_prompt_text !== undefined) {
            body.candidate_prompt_text = payload.candidate_prompt_text;
        }
        if (payload.required_json_keys !== undefined) {
            body.required_json_keys = payload.required_json_keys;
        }
        if (payload.min_pass_rate !== undefined) {
            body.min_pass_rate = payload.min_pass_rate;
        }
        return this.requestJson("POST", "/v1/platform/studio/prompt-gate/evaluate", { body, options });
    }
    listPromptGateRuns(paramsOrWorkspaceId = {}, options) {
        const limit = typeof paramsOrWorkspaceId === "string"
            ? 20
            : (paramsOrWorkspaceId.limit ?? 20);
        if (limit < 1) {
            throw new Error("limit must be >= 1.");
        }
        const query = {
            workspace_id: studioWsId(paramsOrWorkspaceId),
            limit: String(limit),
        };
        return this.requestJson("GET", "/v1/platform/studio/prompt-gate/runs", { query, options });
    }
}
export { PlatformStudioClient as PlatformStudioDelegate };
//# sourceMappingURL=platformStudio.js.map