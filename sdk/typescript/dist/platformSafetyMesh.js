/**
 * Keelway Official TypeScript SDK — Phase 17 Formal Safety State-Machine Verifier
 * + Federated Edge-to-Cluster Agent Mesh (`client.platform` / `client.platform.safetyMesh`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function assertMeshTier(tier) {
    switch (tier) {
        case "edge_local":
        case "cluster_burst":
            return tier;
        default: {
            const _exhaustive = tier;
            throw new Error(`Invalid tier '${String(_exhaustive)}'.`);
        }
    }
}
function assertHardwareHal(hal) {
    switch (hal) {
        case "apple_metal_secure_enclave":
        case "nvidia_h100_cc":
        case "linux_tpm2":
            return hal;
        default: {
            const _exhaustive = hal;
            throw new Error(`Invalid hardware_hal '${String(_exhaustive)}'.`);
        }
    }
}
function assertNodeStatus(status) {
    switch (status) {
        case "ONLINE":
        case "DRAINING":
            return status;
        default: {
            const _exhaustive = status;
            throw new Error(`Invalid status '${String(_exhaustive)}'.`);
        }
    }
}
function assertDataClassification(cls) {
    switch (cls) {
        case "public":
        case "internal":
        case "restricted_pii":
            return cls;
        default: {
            const _exhaustive = cls;
            throw new Error(`Invalid data_classification '${String(_exhaustive)}'.`);
        }
    }
}
function resolveListCall(wsOrParams, limitOrOpts, options) {
    const isObj = typeof wsOrParams === "object" && wsOrParams !== null;
    const wsId = ((isObj ? wsOrParams.workspace_id : wsOrParams) ?? "default").trim() || "default";
    const limit = isObj ? (wsOrParams.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
    const opts = isObj ? limitOrOpts : typeof limitOrOpts === "object" ? limitOrOpts : options;
    if (!Number.isInteger(limit) || limit < 1)
        throw new Error("limit must be >= 1.");
    return { query: { workspace_id: wsId, limit: String(limit) }, options: opts };
}
export class PlatformSafetyMeshClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    verifyWorkflowSafety(req = {}, options) {
        const workflowId = (req.workflow_id ?? "WF-TREASURY-01").trim();
        if (!workflowId)
            throw new Error("workflow_id must be non-empty.");
        const workflowName = (req.workflow_name ?? "treasury-wire-approver").trim();
        if (!workflowName)
            throw new Error("workflow_name must be non-empty.");
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            workflow_id: workflowId,
            workflow_name: workflowName,
            airgap_mode: req.airgap_mode ?? false,
            inject_p10_guards: req.inject_p10_guards ?? false,
        };
        if (req.nodes !== undefined)
            body.nodes = req.nodes;
        if (req.edges !== undefined)
            body.edges = req.edges;
        return this.requestJson("POST", "/v1/platform/safety/verify", { body, options });
    }
    listSafetyVerifications(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/safety/verifications", resolveListCall(wsOrParams, limitOrOpts, options));
    }
    registerMeshNode(req, options) {
        const name = (req.name ?? "").trim();
        if (!name)
            throw new Error("name must be non-empty.");
        const region = (req.region ?? "local-loopback").trim();
        if (!region)
            throw new Error("region must be non-empty.");
        const vramGb = req.vram_gb ?? 32;
        if (!Number.isInteger(vramGb) || vramGb < 1)
            throw new Error("vram_gb must be >= 1.");
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            name,
            tier: assertMeshTier(req.tier ?? "edge_local"),
            hardware_hal: assertHardwareHal(req.hardware_hal ?? "apple_metal_secure_enclave"),
            region,
            vram_gb: vramGb,
            status: assertNodeStatus(req.status ?? "ONLINE"),
        };
        if (req.node_id !== undefined && req.node_id.trim() !== "")
            body.node_id = req.node_id.trim();
        return this.requestJson("POST", "/v1/platform/mesh/nodes", { body, options });
    }
    listMeshNodes(wsOrParams = "default", options) {
        const wsId = typeof wsOrParams === "object" && wsOrParams !== null ? (wsOrParams.workspace_id ?? "default").trim() || "default" : wsOrParams.trim() || "default";
        return this.requestJson("GET", "/v1/platform/mesh/nodes", { query: { workspace_id: wsId }, options });
    }
    dispatchMeshHandoff(req = {}, options) {
        const workflowName = (req.workflow_name ?? "clinical-synthesis-pipeline").trim();
        if (!workflowName)
            throw new Error("workflow_name must be non-empty.");
        const taskSummary = (req.task_summary ?? "Ingest patient intake & synthesize anonymized cohort summary").trim();
        if (!taskSummary)
            throw new Error("task_summary must be non-empty.");
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            workflow_name: workflowName,
            task_summary: taskSummary,
            data_classification: assertDataClassification(req.data_classification ?? "restricted_pii"),
            allow_sanitized_burst: req.allow_sanitized_burst ?? true,
            force_raw_cloud_burst: req.force_raw_cloud_burst ?? false,
        };
        return this.requestJson("POST", "/v1/platform/mesh/dispatch", { body, options });
    }
    listMeshHandoffs(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/mesh/handoffs", resolveListCall(wsOrParams, limitOrOpts, options));
    }
}
export { PlatformSafetyMeshClient as PlatformSafetyMeshDelegate };
//# sourceMappingURL=platformSafetyMesh.js.map