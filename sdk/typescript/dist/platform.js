/**
 * Keelway Official TypeScript SDK — Unified Platform Namespace (`client.platform`).
 *
 * Exposes all 20 `/v1/platform/*` endpoints using `KeelwayClient`'s zero-dependency
 * Web Fetch, `AbortSignal` timeout, and `mapHttpError` infrastructure.
 */
export class PlatformNamespace {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    overview(params = {}, options) {
        const workspaceId = typeof params === "string" ? params : (params.workspace_id ?? "default");
        return this.requestJson("GET", "/v1/platform/overview", {
            query: { workspace_id: workspaceId },
            options,
        });
    }
    listTiers(options) {
        return this.requestJson("GET", "/v1/platform/subscriptions/tiers", { options });
    }
    checkQuota(req, options) {
        return this.requestJson("POST", "/v1/platform/subscriptions/quota-check", {
            body: {
                org_id: req.org_id,
                tier: req.tier,
                tokens_requested: req.tokens_requested,
                current_rpm: req.current_rpm ?? 1,
                local_hardware: req.local_hardware ?? false,
            },
            options,
        });
    }
    validateByom(req, options) {
        const body = {
            provider: req.provider,
            credential_kind: req.credential_kind,
            api_key_preview: req.api_key_preview ?? "",
            model_id: req.model_id ?? "",
            commercial_use: req.commercial_use ?? true,
        };
        if (req.license_id !== undefined) {
            body.license_id = req.license_id;
        }
        return this.requestJson("POST", "/v1/platform/subscriptions/byom/validate", { body, options });
    }
    checkModelLicense(req, options) {
        return this.requestJson("POST", "/v1/platform/subscriptions/license-check", {
            body: {
                model_id: req.model_id,
                license_id: req.license_id,
                commercial_use: req.commercial_use ?? true,
                has_authorized_api_credential: req.has_authorized_api_credential ?? req.has_authorized_api_key ?? false,
                exceeds_700m_mau: req.exceeds_700m_mau ?? false,
            },
            options,
        });
    }
    listMarketplacePackages(params = {}, options) {
        const query = {
            workspace_id: params.workspace_id ?? "default",
        };
        if (params.kind !== undefined)
            query.kind = params.kind;
        if (params.query !== undefined)
            query.query = params.query;
        if (params.publisher_tier !== undefined)
            query.publisher_tier = params.publisher_tier;
        return this.requestJson("GET", "/v1/platform/marketplace/packages", { query, options });
    }
    scanMarketplacePackage(pkg, options) {
        return this.requestJson("POST", "/v1/platform/marketplace/scan", {
            body: { ...pkg },
            options,
        });
    }
    publishMarketplacePackage(pkg, options) {
        return this.requestJson("POST", "/v1/platform/marketplace/publish", { body: { ...pkg }, options });
    }
    installMarketplacePackage(req, options) {
        const body = {
            package_id: req.package_id,
            workspace_id: req.workspace_id ?? "default",
        };
        if (req.config !== undefined) {
            body.config = req.config;
        }
        return this.requestJson("POST", "/v1/platform/marketplace/install", { body, options });
    }
    listAgents(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/agents", {
            query: { workspace_id: params.workspace_id ?? "default" },
            options,
        });
    }
    dispatchTeam(req, options) {
        return this.requestJson("POST", "/v1/platform/agents/teams/dispatch", {
            body: {
                team_id: req.team_id,
                objective: req.objective ?? req.goal ?? "",
                workspace_id: req.workspace_id ?? "default",
                sensitive_mutation: req.sensitive_mutation ?? false,
            },
            options,
        });
    }
    async listIssues(params = {}, options) {
        const query = {
            workspace_id: params.workspace_id ?? "default",
        };
        if (params.status !== undefined) {
            query.status = params.status;
        }
        const res = await this.requestJson("GET", "/v1/platform/pm/issues", { query, options });
        if (params.status !== undefined && Array.isArray(res.issues)) {
            const filtered = res.issues.filter((i) => i.status === params.status);
            return { ...res, issues: filtered, total: filtered.length };
        }
        return res;
    }
    createIssue(req, options) {
        const body = {
            title: req.title,
            workspace_id: req.workspace_id ?? "default",
            priority: req.priority ?? "medium",
            status: req.status ?? "todo",
            assignee_agent: req.assignee_agent ?? "feature-coder",
            sprint_id: req.sprint_id ?? "SPR-01",
        };
        if (req.prd_id !== undefined) {
            body.prd_id = req.prd_id;
        }
        return this.requestJson("POST", "/v1/platform/pm/issues", {
            body,
            options,
        });
    }
    listPrds(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/product/prds", {
            query: { workspace_id: params.workspace_id ?? "default" },
            options,
        });
    }
    createPrd(req, options) {
        const body = {
            title: req.title,
            summary: req.summary,
            workspace_id: req.workspace_id ?? "default",
        };
        if (req.acceptance_criteria !== undefined) {
            body.acceptance_criteria = req.acceptance_criteria;
        }
        return this.requestJson("POST", "/v1/platform/product/prds", {
            body,
            options,
        });
    }
    listWorkflows(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/automation/workflows", {
            query: { workspace_id: params.workspace_id ?? "default" },
            options,
        });
    }
    createWorkflow(req, options) {
        const body = {
            name: req.name,
            trigger: req.trigger ?? "manual",
            workspace_id: req.workspace_id ?? "default",
        };
        if (req.nodes !== undefined) {
            body.nodes = req.nodes;
        }
        return this.requestJson("POST", "/v1/platform/automation/workflows", { body, options });
    }
    compileBlueprint(req, options) {
        return this.requestJson("POST", "/v1/platform/nocode/blueprint", {
            body: {
                idea: req.idea,
                workspace_id: req.workspace_id ?? "default",
                experience_mode: req.experience_mode ?? "non_coder",
                target_stack: req.target_stack ?? "react-fastapi-sqlite",
            },
            options,
        });
    }
    listExtensions(params = {}, options) {
        const query = {
            workspace_id: params.workspace_id ?? "default",
        };
        if (params.extension_type !== undefined) {
            query.extension_type = params.extension_type;
        }
        return this.requestJson("GET", "/v1/platform/extensions", {
            query,
            options,
        });
    }
    registerExtension(extension, options) {
        return this.requestJson("POST", "/v1/platform/extensions/register", { body: { ...extension }, options });
    }
}
//# sourceMappingURL=platform.js.map