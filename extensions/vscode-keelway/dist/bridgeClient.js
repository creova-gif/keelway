/**
 * Keelway Loopback Debugger Bridge Client for VS Code & Cursor Extension Host.
 * Authenticates via Bearer token and strips any browser Origin header to preserve zero-CSRF loopback posture.
 */
export class BridgeHttpError extends Error {
    status;
    detail;
    payload;
    constructor(status, detail, payload) {
        super(`Keelway bridge HTTP ${status}: ${detail}`);
        this.status = status;
        this.detail = detail;
        this.payload = payload;
        this.name = "BridgeHttpError";
    }
}
export function parseAttachUri(uriString) {
    let parsed;
    try {
        parsed = new URL(uriString.trim());
    }
    catch {
        throw new Error(`Invalid Keelway attach URI: ${uriString}`);
    }
    const rawScheme = parsed.protocol.replace(/:$/, "").toLowerCase();
    if (rawScheme !== "vscode" && rawScheme !== "cursor") {
        throw new Error(`Unsupported URI scheme '${rawScheme}': expected 'vscode' or 'cursor'.`);
    }
    const authority = parsed.host.toLowerCase();
    if (authority && authority !== "keelway.vscode-keelway")
        throw new Error(`Unexpected extension authority '${authority}'.`);
    if (parsed.pathname !== "/attach")
        throw new Error(`Unsupported attach path '${parsed.pathname}': expected '/attach'.`);
    const rawPort = parsed.searchParams.get("port") ?? "7420";
    const port = Number(rawPort);
    if (!Number.isInteger(port) || port < 1 || port > 65535)
        throw new Error(`Invalid loopback port '${rawPort}'.`);
    const workspaceId = (parsed.searchParams.get("workspace") ?? parsed.searchParams.get("workspace_id") ?? "default").trim() || "default";
    const workflowId = (parsed.searchParams.get("workflow") ?? parsed.searchParams.get("workflow_id") ?? "WF-STUDIO-01").trim() || "WF-STUDIO-01";
    const sessionParam = (parsed.searchParams.get("session") ?? parsed.searchParams.get("session_id") ?? "").trim();
    return { scheme: rawScheme, port, baseUrl: `http://127.0.0.1:${port}`, workspaceId, workflowId, ...(sessionParam ? { sessionId: sessionParam } : {}) };
}
function encodeSeg(value, label) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${label} must be non-empty.`);
    return encodeURIComponent(clean);
}
export class KeelwayBridgeClient {
    baseUrl;
    workspaceId;
    workflowId;
    apiToken;
    getTokenFn;
    fetchFn;
    constructor(options = {}) {
        this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:7420").replace(/\/+$/, "");
        this.workspaceId = options.workspaceId ?? "default";
        this.workflowId = options.workflowId ?? "WF-STUDIO-01";
        this.apiToken = options.apiToken;
        this.getTokenFn = options.getToken;
        this.fetchFn = options.fetchImpl ?? globalThis.fetch;
    }
    getTarget() {
        return { baseUrl: this.baseUrl, workspaceId: this.workspaceId, workflowId: this.workflowId };
    }
    configureTarget(target) {
        if (target.baseUrl)
            this.baseUrl = target.baseUrl.replace(/\/+$/, "");
        if (target.workspaceId)
            this.workspaceId = target.workspaceId;
        if (target.workflowId)
            this.workflowId = target.workflowId;
        if (target.apiToken !== undefined)
            this.apiToken = target.apiToken;
    }
    async request(method, path, opts) {
        const url = new URL(`${this.baseUrl}${path}`);
        for (const [k, v] of Object.entries(opts?.query ?? {})) {
            if (v !== undefined && v !== "")
                url.searchParams.set(k, v);
        }
        const headers = { Accept: "application/json" };
        for (const [hk, hv] of Object.entries(opts?.extraHeaders ?? {})) {
            if (hk.toLowerCase() !== "origin")
                headers[hk] = hv;
        }
        const resolvedToken = this.apiToken ?? (this.getTokenFn ? await this.getTokenFn() : undefined);
        if (resolvedToken && resolvedToken.trim())
            headers.Authorization = `Bearer ${resolvedToken.trim()}`;
        if (opts?.body !== undefined)
            headers["Content-Type"] = "application/json";
        delete headers.Origin;
        delete headers.origin;
        const response = await this.fetchFn(url.toString(), { method, headers, body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined });
        const text = await response.text();
        const parsed = text ? JSON.parse(text) : {};
        if (!response.ok) {
            const detail = typeof parsed === "object" && parsed !== null && "detail" in parsed ? String(parsed.detail) : response.statusText || `HTTP ${response.status}`;
            throw new BridgeHttpError(response.status, detail, parsed);
        }
        return parsed;
    }
    setBreakpoint(payload) {
        const body = { workspace_id: payload.workspace_id ?? this.workspaceId, workflow_id: payload.workflow_id ?? this.workflowId, condition_type: payload.condition_type ?? "always", enabled: payload.enabled ?? true };
        if (payload.node_id !== undefined)
            body.node_id = payload.node_id.trim();
        if (payload.threshold !== undefined)
            body.threshold = payload.threshold;
        if (payload.condition !== undefined)
            body.condition = payload.condition;
        if (payload.file_path !== undefined)
            body.file_path = payload.file_path;
        if (payload.line_number !== undefined)
            body.line_number = payload.line_number;
        if (payload.label !== undefined)
            body.label = payload.label;
        return this.request("POST", "/v1/platform/debugger/breakpoints", { body });
    }
    listBreakpoints(params = {}) {
        return this.request("GET", "/v1/platform/debugger/breakpoints", { query: { workspace_id: params.workspace_id ?? this.workspaceId, workflow_id: params.workflow_id } });
    }
    deleteBreakpoint(breakpointId, workspaceId) {
        return this.request("DELETE", `/v1/platform/debugger/breakpoints/${encodeSeg(breakpointId, "breakpoint_id")}`, { query: { workspace_id: workspaceId ?? this.workspaceId } });
    }
    startDebugSession(payload = {}) {
        const body = { workspace_id: payload.workspace_id ?? this.workspaceId, workflow_id: payload.workflow_id ?? this.workflowId };
        if (payload.steps !== undefined)
            body.steps = payload.steps;
        if (payload.initial_state !== undefined)
            body.initial_state = payload.initial_state;
        return this.request("POST", "/v1/platform/debugger/sessions", { body });
    }
    listDebugSessions(params = {}) {
        return this.request("GET", "/v1/platform/debugger/sessions", { query: { workspace_id: params.workspace_id ?? this.workspaceId, limit: String(params.limit ?? 20) } });
    }
    stepDebugSession(sessionId, payload) {
        const body = { workspace_id: payload.workspace_id ?? this.workspaceId, action: payload.action };
        const patch = payload.state_patch ?? payload.mutate_state;
        if (patch !== undefined)
            body.state_patch = patch;
        return this.request("POST", `/v1/platform/debugger/sessions/${encodeSeg(sessionId, "session_id")}/step`, { body });
    }
    getCodelens(params = {}) {
        return this.request("GET", "/v1/platform/debugger/codelens", { query: { workspace_id: params.workspace_id ?? this.workspaceId, workflow_id: params.workflow_id, file_path: params.file_path } });
    }
}
//# sourceMappingURL=bridgeClient.js.map