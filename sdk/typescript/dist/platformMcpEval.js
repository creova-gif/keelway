/**
 * Keelway Official TypeScript SDK — Phase 7 MCP Control Plane & Golden Evaluation Suite.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function mcpSeg(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
function mcpWsId(params) {
    return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}
export class PlatformMcpEvalDelegate {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    listMcpServers(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/mcp/servers", { query: { workspace_id: mcpWsId(params) }, options });
    }
    registerMcpServer(req, options) {
        const body = {
            id: req.id,
            name: req.name,
            transport: req.transport,
            endpoint: req.endpoint,
            workspace_id: req.workspace_id ?? "default",
        };
        if (req.allowed_tools !== undefined)
            body.allowed_tools = req.allowed_tools;
        return this.requestJson("POST", "/v1/platform/mcp/servers", { body, options });
    }
    deleteMcpServer(serverId, params = {}, options) {
        return this.requestJson("DELETE", `/v1/platform/mcp/servers/${mcpSeg(serverId, "serverId")}`, {
            query: { workspace_id: mcpWsId(params) },
            options,
        });
    }
    listMcpTools(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/mcp/tools", { query: { workspace_id: mcpWsId(params) }, options });
    }
    callMcpTool(reqOrToolName, argumentsOrOptions, workspaceId, options) {
        if (typeof reqOrToolName === "string") {
            return this.requestJson("POST", "/v1/platform/mcp/call", {
                body: {
                    workspace_id: workspaceId ?? "default",
                    tool_name: reqOrToolName,
                    arguments: argumentsOrOptions ?? {},
                },
                options,
            });
        }
        return this.requestJson("POST", "/v1/platform/mcp/call", {
            body: {
                workspace_id: reqOrToolName.workspace_id ?? "default",
                tool_name: reqOrToolName.tool_name,
                arguments: reqOrToolName.arguments ?? {},
            },
            options: argumentsOrOptions,
        });
    }
    runGoldenEvals(req = {}, options) {
        const body = typeof req === "string"
            ? { workspace_id: "default", category: req || "all" }
            : { workspace_id: req.workspace_id ?? "default", category: req.category ?? "all" };
        return this.requestJson("POST", "/v1/platform/evals/golden", { body, options });
    }
    getLatestGoldenEvals(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/evals/latest", { query: { workspace_id: mcpWsId(params) }, options });
    }
}
//# sourceMappingURL=platformMcpEval.js.map