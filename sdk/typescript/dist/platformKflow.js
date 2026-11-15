/**
 * Keelway Official TypeScript SDK — Phase 8 KFlow DAG Execution, KSpaces CRDT Sync & SBOM.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function kflowWsId(params) {
    return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}
export class PlatformKflowDelegate {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    executeKflowDag(req, options) {
        return this.requestJson("POST", "/v1/platform/automation/workflows/execute", {
            body: {
                workspace_id: req.workspace_id ?? "default",
                workflow_id: req.workflow_id,
                nodes: req.nodes ?? [],
                trigger: req.trigger ?? "manual",
                token_budget: req.token_budget ?? 25000,
                approved_node_ids: req.approved_node_ids ?? [],
            },
            options,
        });
    }
    listKflowRuns(params = {}, options) {
        const query = { workspace_id: kflowWsId(params) };
        if (typeof params !== "string") {
            if (params.workflow_id !== undefined)
                query.workflow_id = params.workflow_id;
            if (params.limit !== undefined)
                query.limit = String(params.limit);
        }
        return this.requestJson("GET", "/v1/platform/automation/runs", { query, options });
    }
    syncKspacesCrdt(req, options) {
        return this.requestJson("POST", "/v1/platform/kspaces/sync", {
            body: {
                workspace_id: req.workspace_id ?? "default",
                peer_id: req.peer_id,
                operations: req.operations,
            },
            options,
        });
    }
    getKspacesState(params = {}, options) {
        const query = { workspace_id: kflowWsId(params) };
        if (typeof params !== "string" && params.namespace !== undefined) {
            query.namespace = params.namespace;
        }
        return this.requestJson("GET", "/v1/platform/kspaces/state", { query, options });
    }
    getPlatformSbom(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/security/sbom", {
            query: { workspace_id: kflowWsId(params) },
            options,
        });
    }
}
//# sourceMappingURL=platformKflow.js.map