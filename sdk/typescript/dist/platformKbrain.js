/**
 * Keelway Official TypeScript SDK — Phase 10 KBrain Hybrid BM25/N-Gram Memory
 * & KHub Air-Gapped Skill Mirror Verification.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function kbrainSeg(value, fieldName) {
    const clean = value.trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
function kbrainWsId(params) {
    return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}
export class PlatformKbrainDelegate {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    recordKbrainFact(req, options) {
        const cleanKey = req.key.trim();
        if (!cleanKey)
            throw new Error("key must be non-empty.");
        const cleanStatement = req.statement.trim();
        if (!cleanStatement)
            throw new Error("statement must be non-empty.");
        return this.requestJson("POST", "/v1/platform/kbrain/facts", {
            body: {
                workspace_id: req.workspace_id ?? "default",
                key: cleanKey,
                statement: cleanStatement,
                scope: req.scope ?? "project",
                provenance_uri: req.provenance_uri ?? "workspace",
                tags: req.tags ?? [],
                auto_approve: req.auto_approve ?? true,
            },
            options,
        });
    }
    searchKbrainFacts(params = {}, options) {
        const isStr = typeof params === "string";
        const query = {
            workspace_id: isStr ? "default" : (params.workspace_id ?? "default"),
            query: isStr ? params : (params.query ?? ""),
            max_scope: isStr ? "org" : (params.max_scope ?? "org"),
            include_conflicts: String(isStr ? false : (params.include_conflicts ?? false)),
            limit: String(isStr ? 10 : (params.limit ?? 10)),
        };
        return this.requestJson("GET", "/v1/platform/kbrain/search", { query, options });
    }
    resolveKbrainFact(factId, req, options) {
        const resolution = (typeof req === "string" ? req : req.resolution).trim();
        if (!resolution)
            throw new Error("resolution must be non-empty.");
        return this.requestJson("POST", `/v1/platform/kbrain/facts/${kbrainSeg(factId, "factId")}/resolve`, {
            body: {
                workspace_id: typeof req === "string" ? "default" : (req.workspace_id ?? "default"),
                resolution,
            },
            options,
        });
    }
    listKhubSkills(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/khub/skills", {
            query: { workspace_id: kbrainWsId(params) },
            options,
        });
    }
    verifyKhubMirror(req = {}, options) {
        const body = Array.isArray(req)
            ? { workspace_id: "default", skill_ids: req }
            : { workspace_id: req.workspace_id ?? "default", skill_ids: req.skill_ids ?? [] };
        return this.requestJson("POST", "/v1/platform/khub/mirror/verify", { body, options });
    }
}
//# sourceMappingURL=platformKbrain.js.map