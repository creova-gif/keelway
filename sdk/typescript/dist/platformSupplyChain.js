/**
 * Keelway Official TypeScript SDK — Phase 20 Cryptographic MCP & Skill Lockfile,
 * Tool-Poisoning / Rug-Pull Firewall & Conformance Benchmark (`client.platform`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
const DEFAULT_TOOL_SCHEMA_JSON = '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}';
function assertSimulateMode(mode) {
    switch (mode) {
        case "clean":
        case "rug_pull":
        case "poisoning":
            return mode;
        default: {
            const _exhaustive = mode;
            throw new Error(`Invalid simulate_mode '${String(_exhaustive)}'.`);
        }
    }
}
function assertTargetKind(kind) {
    switch (kind) {
        case "mcp_server":
        case "skill_package":
        case "opencore_model":
            return kind;
        default: {
            const _exhaustive = kind;
            throw new Error(`Invalid target_kind '${String(_exhaustive)}'.`);
        }
    }
}
function cleanNonEmpty(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return clean;
}
function normalizeTools(tools, fieldName) {
    if (!Array.isArray(tools))
        throw new Error(`${fieldName} must be an array.`);
    return tools.map((item) => {
        if (typeof item.description !== "string" || item.description.length === 0) {
            throw new Error(`${fieldName}[].description must be non-empty.`);
        }
        return {
            server_id: cleanNonEmpty(item.server_id, `${fieldName}[].server_id`),
            tool_name: cleanNonEmpty(item.tool_name, `${fieldName}[].tool_name`),
            version: (item.version ?? "1.0.0").trim() || "1.0.0",
            description: item.description,
            input_schema_json: item.input_schema_json && item.input_schema_json.length > 0 ? item.input_schema_json : DEFAULT_TOOL_SCHEMA_JSON,
        };
    });
}
function resolveSupplyChainListCall(wsOrParams, limitOrOpts, options) {
    const isObj = typeof wsOrParams === "object" && wsOrParams !== null;
    const wsId = ((isObj ? wsOrParams.workspace_id : wsOrParams) ?? "default").trim() || "default";
    const limit = isObj ? (wsOrParams.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
    const opts = isObj ? limitOrOpts : typeof limitOrOpts === "object" ? limitOrOpts : options;
    if (!Number.isInteger(limit) || limit < 1)
        throw new Error("limit must be >= 1.");
    return { query: { workspace_id: wsId, limit: String(limit) }, options: opts };
}
export class PlatformSupplyChainClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    pinMcpLockfile(req = {}, options) {
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            lockfile_name: cleanNonEmpty(req.lockfile_name ?? "keelway.lock.json", "lockfile_name"),
        };
        if (req.tools !== undefined)
            body.tools = normalizeTools(req.tools, "tools");
        return this.requestJson("POST", "/v1/platform/supply-chain/lock/pin", { body, options });
    }
    listMcpLockfiles(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/supply-chain/lock/snapshots", resolveSupplyChainListCall(wsOrParams, limitOrOpts, options));
    }
    verifyMcpLockfile(req = {}, options) {
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            simulate_mode: assertSimulateMode(req.simulate_mode ?? "clean"),
        };
        if (req.lockfile_id !== undefined && req.lockfile_id !== null && req.lockfile_id.trim() !== "") {
            body.lockfile_id = req.lockfile_id.trim();
        }
        if (req.live_tools !== undefined)
            body.live_tools = normalizeTools(req.live_tools, "live_tools");
        return this.requestJson("POST", "/v1/platform/supply-chain/lock/verify", { body, options });
    }
    listMcpLockVerifications(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/supply-chain/lock/verifications", resolveSupplyChainListCall(wsOrParams, limitOrOpts, options));
    }
    runConformanceBenchmark(req = {}, options) {
        const budget = req.latency_budget_ms ?? 250;
        const minScore = req.min_conformance_score ?? 0.9;
        if (!Number.isInteger(budget) || budget < 1)
            throw new Error("latency_budget_ms must be >= 1.");
        if (typeof minScore !== "number" || Number.isNaN(minScore) || minScore < 0 || minScore > 1) {
            throw new Error("min_conformance_score must be between 0.0 and 1.0.");
        }
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            target_id: cleanNonEmpty(req.target_id ?? "mcp-git-local", "target_id"),
            target_kind: assertTargetKind(req.target_kind ?? "mcp_server"),
            model_id: cleanNonEmpty(req.model_id ?? "keelway-core:7b", "model_id"),
            latency_budget_ms: budget,
            min_conformance_score: minScore,
        };
        if (req.scenarios !== undefined)
            body.scenarios = req.scenarios.map((s) => ({ ...s }));
        return this.requestJson("POST", "/v1/platform/supply-chain/bench/run", { body, options });
    }
    listConformanceBenchmarks(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/supply-chain/bench/runs", resolveSupplyChainListCall(wsOrParams, limitOrOpts, options));
    }
}
export { PlatformSupplyChainClient as PlatformSupplyChainDelegate };
//# sourceMappingURL=platformSupplyChain.js.map