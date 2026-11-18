/**
 * Keelway Official TypeScript SDK — Phase 14 Live Step-Through Debugger,
 * Conditional Gutter Breakpoints, DLP-Guarded State Mutation & 4D Routing CodeLens
 * (`client.platform` / `client.platform.debugger`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function assertConditionType(cond) {
    switch (cond) {
        case "always":
        case "cost_usd_gt":
        case "hybrid_score_lt":
        case "before_shell_tool":
        case "before_p10_gate":
        case "line_match":
            return cond;
        default: {
            const _exhaustive = cond;
            throw new Error(`Invalid condition_type '${String(_exhaustive)}'.`);
        }
    }
}
function assertStepAction(action) {
    switch (action) {
        case "step_over":
        case "step_into":
        case "continue":
        case "mutate_state":
            return action;
        default: {
            const _exhaustive = action;
            throw new Error(`Invalid debugger action '${String(_exhaustive)}'.`);
        }
    }
}
function debuggerWsId(params) {
    return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}
function encodePathSeg(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
export class PlatformDebuggerClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    setBreakpoint(payload = {}, options) {
        const workflowId = (payload.workflow_id ?? "WF-STUDIO-01").trim();
        if (!workflowId)
            throw new Error("workflow_id must be non-empty.");
        const conditionType = assertConditionType(payload.condition_type ?? "always");
        if (payload.line_number !== undefined && (!Number.isInteger(payload.line_number) || payload.line_number < 1)) {
            throw new Error("line_number must be >= 1.");
        }
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            workflow_id: workflowId,
            file_path: (payload.file_path ?? "workflows/refund_agent.py").trim() || "workflows/refund_agent.py",
            condition_type: conditionType,
            enabled: payload.enabled ?? true,
        };
        if (payload.node_id !== undefined && payload.node_id.trim() !== "")
            body.node_id = payload.node_id.trim();
        if (payload.line_number !== undefined)
            body.line_number = payload.line_number;
        if (payload.threshold !== undefined)
            body.threshold = payload.threshold;
        if (payload.label !== undefined && payload.label.trim() !== "")
            body.label = payload.label.trim();
        return this.requestJson("POST", "/v1/platform/debugger/breakpoints", { body, options });
    }
    listBreakpoints(paramsOrWorkspaceId = {}, options) {
        const query = { workspace_id: debuggerWsId(paramsOrWorkspaceId) };
        if (typeof paramsOrWorkspaceId !== "string" && paramsOrWorkspaceId.workflow_id !== undefined) {
            const wf = paramsOrWorkspaceId.workflow_id.trim();
            if (wf)
                query.workflow_id = wf;
        }
        return this.requestJson("GET", "/v1/platform/debugger/breakpoints", { query, options });
    }
    deleteBreakpoint(breakpointId, paramsOrWorkspaceId = {}, options) {
        const seg = encodePathSeg(breakpointId, "breakpoint_id");
        const query = { workspace_id: debuggerWsId(paramsOrWorkspaceId) };
        return this.requestJson("DELETE", `/v1/platform/debugger/breakpoints/${seg}`, { query, options });
    }
    startDebugSession(payload = {}, options) {
        const workflowId = (payload.workflow_id ?? "WF-STUDIO-01").trim();
        if (!workflowId)
            throw new Error("workflow_id must be non-empty.");
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            workflow_id: workflowId,
        };
        if (payload.steps !== undefined)
            body.steps = payload.steps;
        if (payload.initial_state !== undefined)
            body.initial_state = payload.initial_state;
        return this.requestJson("POST", "/v1/platform/debugger/sessions", { body, options });
    }
    listDebugSessions(paramsOrWorkspaceId = {}, options) {
        const limit = typeof paramsOrWorkspaceId === "string" ? 20 : (paramsOrWorkspaceId.limit ?? 20);
        if (limit < 1)
            throw new Error("limit must be >= 1.");
        const query = {
            workspace_id: debuggerWsId(paramsOrWorkspaceId),
            limit: String(limit),
        };
        return this.requestJson("GET", "/v1/platform/debugger/sessions", { query, options });
    }
    stepDebugSession(sessionId, payloadOrAction = {}, options) {
        const seg = encodePathSeg(sessionId, "session_id");
        const payload = typeof payloadOrAction === "string" ? { action: payloadOrAction } : payloadOrAction;
        const action = assertStepAction(payload.action ?? "step_over");
        const body = {
            workspace_id: payload.workspace_id ?? "default",
            action,
        };
        if (payload.state_patch !== undefined)
            body.state_patch = payload.state_patch;
        return this.requestJson("POST", `/v1/platform/debugger/sessions/${seg}/step`, { body, options });
    }
    getDebuggerCodelens(paramsOrWorkspaceId = {}, options) {
        const query = { workspace_id: debuggerWsId(paramsOrWorkspaceId) };
        if (typeof paramsOrWorkspaceId !== "string") {
            if (paramsOrWorkspaceId.workflow_id !== undefined && paramsOrWorkspaceId.workflow_id.trim() !== "") {
                query.workflow_id = paramsOrWorkspaceId.workflow_id.trim();
            }
            if (paramsOrWorkspaceId.file_path !== undefined && paramsOrWorkspaceId.file_path.trim() !== "") {
                query.file_path = paramsOrWorkspaceId.file_path.trim();
            }
            if (paramsOrWorkspaceId.source_code !== undefined) {
                query.source_code = paramsOrWorkspaceId.source_code;
            }
        }
        return this.requestJson("GET", "/v1/platform/debugger/codelens", { query, options });
    }
}
export { PlatformDebuggerClient as PlatformDebuggerDelegate };
//# sourceMappingURL=platformDebugger.js.map