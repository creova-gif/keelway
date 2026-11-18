/**
 * Keelway Official TypeScript SDK — Phase 15 Bounded Cyclic & Conditional KFlow Sub-Graphs,
 * Saga Compensation & Pre-Run Cost/Privacy Autopilot (`client.platform` / `client.platform.cyclic`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function assertPrivacyPolicy(policy) {
    switch (policy) {
        case "hybrid_balanced":
        case "airgap_strict":
        case "eu_residency":
            return policy;
        default: {
            const _exhaustive = policy;
            throw new Error(`Invalid privacy_policy '${String(_exhaustive)}'.`);
        }
    }
}
function encodePathSeg(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
function buildGraphBody(req) {
    const workflowId = (req.workflow_id ?? "WF-CYCLIC-01").trim();
    if (!workflowId)
        throw new Error("workflow_id must be non-empty.");
    const body = {
        workspace_id: req.workspace_id ?? "default",
        workflow_id: workflowId,
    };
    if (req.nodes !== undefined)
        body.nodes = req.nodes;
    if (req.loop_edges !== undefined)
        body.loop_edges = req.loop_edges;
    return body;
}
function buildListQuery(params) {
    const limit = params.limit ?? 25;
    if (!Number.isInteger(limit) || limit < 1)
        throw new Error("limit must be >= 1.");
    const query = {
        workspace_id: params.workspace_id ?? "default",
        limit: String(limit),
    };
    if (params.workflow_id !== undefined && params.workflow_id.trim() !== "") {
        query.workflow_id = params.workflow_id.trim();
    }
    return query;
}
export class PlatformCyclicClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    validateCyclicKflow(req = {}, options) {
        return this.requestJson("POST", "/v1/platform/kflow/cyclic/validate", { body: buildGraphBody(req), options });
    }
    executeCyclicKflow(req = {}, options) {
        const body = buildGraphBody(req);
        const threshold = req.critic_threshold ?? 0.85;
        if (threshold < 0 || threshold > 1)
            throw new Error("critic_threshold must be between 0.0 and 1.0.");
        if (req.max_iterations_override !== undefined) {
            if (!Number.isInteger(req.max_iterations_override) || req.max_iterations_override < 1 || req.max_iterations_override > 10) {
                throw new Error("max_iterations_override must be between 1 and 10.");
            }
            body.max_iterations_override = req.max_iterations_override;
        }
        if (req.fan_out_shards !== undefined) {
            if (!Number.isInteger(req.fan_out_shards) || req.fan_out_shards < 1 || req.fan_out_shards > 16) {
                throw new Error("fan_out_shards must be between 1 and 16.");
            }
            body.fan_out_shards = req.fan_out_shards;
        }
        body.critic_threshold = threshold;
        body.simulate_timeout = req.simulate_timeout ?? false;
        if (req.initial_state !== undefined)
            body.initial_state = req.initial_state;
        if (req.approved_node_ids !== undefined)
            body.approved_node_ids = req.approved_node_ids;
        return this.requestJson("POST", "/v1/platform/kflow/cyclic/execute", { body, options });
    }
    listCyclicKflowRuns(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/kflow/cyclic/runs", { query: buildListQuery(params), options });
    }
    getCyclicKflowRun(runId, workspaceId = "default", options) {
        const seg = encodePathSeg(runId, "run_id");
        const query = { workspace_id: workspaceId || "default" };
        return this.requestJson("GET", `/v1/platform/kflow/cyclic/runs/${seg}`, { query, options });
    }
    simulateKflowAutopilot(req = {}, options) {
        const body = buildGraphBody(req);
        const budgetCap = req.budget_cap_usd ?? 0.15;
        if (budgetCap < 0)
            throw new Error("budget_cap_usd must be >= 0.0.");
        const multiplier = req.expected_loop_multiplier ?? 2;
        if (!Number.isInteger(multiplier) || multiplier < 1)
            throw new Error("expected_loop_multiplier must be >= 1.");
        body.budget_cap_usd = budgetCap;
        body.privacy_policy = assertPrivacyPolicy(req.privacy_policy ?? "hybrid_balanced");
        body.expected_loop_multiplier = multiplier;
        return this.requestJson("POST", "/v1/platform/kflow/autopilot/simulate", { body, options });
    }
    listKflowAutopilotSimulations(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/kflow/autopilot/simulations", { query: buildListQuery(params), options });
    }
}
export { PlatformCyclicClient as PlatformCyclicDelegate };
//# sourceMappingURL=platformCyclic.js.map