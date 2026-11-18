/**
 * Keelway Official TypeScript SDK — Distributed Cluster Namespace (`client.cluster`).
 *
 * Exposes all 10 `/v1/cluster/*` endpoints (GPU/NPU node discovery, registration,
 * drain/restore, VRAM & residency scheduling, shadow/canary/production lifecycle
 * promotion/rollback, and multi-tenant governance budget reservation) using
 * `KeelwayClient`'s zero-dependency Web Fetch infrastructure.
 */
export class ClusterNamespace {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    listNodes(params = {}, options) {
        const query = {
            include_drained: String(params.include_drained ?? true),
        };
        if (params.region !== undefined) {
            query.region = params.region;
        }
        if (params.runtime !== undefined) {
            query.runtime = params.runtime;
        }
        return this.requestJson("GET", "/v1/cluster/nodes", {
            query,
            options,
        });
    }
    registerNode(payload, options) {
        return this.requestJson("POST", "/v1/cluster/nodes/register", {
            body: { ...payload },
            options,
        });
    }
    drainNode(nodeId, options) {
        return this.requestJson("POST", `/v1/cluster/nodes/${encodeURIComponent(nodeId)}/drain`, { options });
    }
    restoreNode(nodeId, options) {
        return this.requestJson("POST", `/v1/cluster/nodes/${encodeURIComponent(nodeId)}/restore`, { options });
    }
    schedule(payload, options) {
        return this.requestJson("POST", "/v1/cluster/schedule", {
            body: { ...payload },
            options,
        });
    }
    listLifecycle(params = {}, options) {
        const query = params.stage !== undefined ? { stage: params.stage } : undefined;
        return this.requestJson("GET", "/v1/cluster/lifecycle", {
            query,
            options,
        });
    }
    promoteModel(payload, options) {
        return this.requestJson("POST", "/v1/cluster/lifecycle/promote", {
            body: { ...payload },
            options,
        });
    }
    rollbackModel(payload, options) {
        return this.requestJson("POST", "/v1/cluster/lifecycle/rollback", {
            body: { ...payload },
            options,
        });
    }
    governanceAdapterStatus(options) {
        return this.requestJson("GET", "/v1/cluster/governance-adapter/status", { options });
    }
    reserveBudget(payload, options) {
        return this.requestJson("POST", "/v1/cluster/governance-adapter/reserve-budget", {
            body: { ...payload },
            options,
        });
    }
}
//# sourceMappingURL=cluster.js.map