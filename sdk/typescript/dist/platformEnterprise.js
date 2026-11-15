/**
 * Keelway Official TypeScript SDK — Phase 9 Enterprise Identity, SCIM 2.0,
 * Dual-Human P-10 Quorum, SIEM Audit Export & Observability Metrics.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function enterpriseWsId(params) {
    return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}
export class PlatformEnterpriseDelegate {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    configureOidcProvider(req, options) {
        return this.requestJson("PUT", "/v1/platform/enterprise/oidc", {
            body: {
                workspace_id: req.workspace_id ?? "default",
                issuer_url: req.issuer_url,
                client_id: req.client_id,
                signing_secret: req.signing_secret ?? "",
                group_role_mapping: req.group_role_mapping ?? {},
                enabled: req.enabled ?? true,
            },
            options,
        });
    }
    listScimUsers(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/enterprise/scim/v2/Users", {
            query: { workspace_id: enterpriseWsId(params) },
            options,
        });
    }
    provisionScimUser(req, options) {
        return this.requestJson("POST", "/v1/platform/enterprise/scim/v2/Users", {
            body: {
                workspace_id: req.workspace_id ?? "default",
                userName: req.userName,
                displayName: req.displayName ?? "",
                groups: req.groups ?? [],
                active: req.active ?? true,
            },
            options,
        });
    }
    approveP10Quorum(req, options) {
        return this.requestJson("POST", "/v1/platform/enterprise/p10-quorum/approve", {
            body: {
                workspace_id: req.workspace_id ?? "default",
                proposal_id: req.proposal_id,
                approver_id: req.approver_id,
                initiator_id: req.initiator_id ?? "",
                required_approvals: req.required_approvals ?? 2,
                reason: req.reason ?? "",
            },
            options,
        });
    }
    exportSiemAudit(params = {}, options) {
        const query = {
            workspace_id: enterpriseWsId(params),
            format: typeof params === "string" ? "ocsf" : (params.format ?? "ocsf"),
            limit: String(typeof params === "string" ? 100 : (params.limit ?? 100)),
        };
        return this.requestJson("GET", "/v1/platform/enterprise/siem/export", { query, options });
    }
    getObservabilityMetrics(params = {}, options) {
        const query = {
            workspace_id: enterpriseWsId(params),
            format: typeof params === "string" ? "otlp_json" : (params.format ?? "otlp_json"),
        };
        return this.requestJson("GET", "/v1/platform/observability/metrics", { query, options });
    }
}
//# sourceMappingURL=platformEnterprise.js.map