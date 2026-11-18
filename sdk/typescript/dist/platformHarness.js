/**
 * Keelway Official TypeScript SDK — Phase 18 Universal Coding-Agent Co-Harness
 * + Parallel Worktree CI Gate (`client.platform` / `client.platform.harness`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
function assertAgentHost(host) {
    switch (host) {
        case "claude_code":
        case "cursor":
        case "codex_cli":
            return host;
        default: {
            const _exhaustive = host;
            throw new Error(`Invalid agent_host '${String(_exhaustive)}'.`);
        }
    }
}
function assertHookMode(mode) {
    switch (mode) {
        case "enforce":
        case "audit_only":
            return mode;
        default: {
            const _exhaustive = mode;
            throw new Error(`Invalid mode '${String(_exhaustive)}'.`);
        }
    }
}
function assertTicketStatus(status) {
    switch (status) {
        case "PENDING":
        case "APPROVED":
        case "DENIED":
        case "CONSUMED":
            return status;
        default: {
            const _exhaustive = status;
            throw new Error(`Invalid status '${String(_exhaustive)}'.`);
        }
    }
}
function assertTicketDecision(decision) {
    switch (decision) {
        case "APPROVED":
        case "DENIED":
            return decision;
        default: {
            const _exhaustive = decision;
            throw new Error(`Invalid decision '${String(_exhaustive)}'.`);
        }
    }
}
function encodeSeg(value, fieldName) {
    const clean = (value ?? "").trim();
    if (!clean)
        throw new Error(`${fieldName} must be non-empty.`);
    return encodeURIComponent(clean);
}
function resolveTicketsListCall(wsOrOpts, limitOrOpts, options) {
    const isObj = typeof wsOrOpts === "object" && wsOrOpts !== null;
    const wsId = ((isObj ? wsOrOpts.workspace_id : wsOrOpts) ?? "default").trim() || "default";
    const limit = isObj ? (wsOrOpts.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
    const opts = isObj ? limitOrOpts : typeof limitOrOpts === "object" ? limitOrOpts : options;
    if (!Number.isInteger(limit) || limit < 1)
        throw new Error("limit must be >= 1.");
    const query = { workspace_id: wsId, limit: String(limit) };
    if (isObj && wsOrOpts.status !== undefined)
        query.status = assertTicketStatus(wsOrOpts.status);
    return { query, options: opts };
}
export class PlatformHarnessClient {
    requestJson;
    constructor(requestJson) {
        this.requestJson = requestJson;
    }
    renderAgentHookConfig(req = {}, options) {
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            agent_host: assertAgentHost(req.agent_host ?? "claude_code"),
            mode: assertHookMode(req.mode ?? "enforce"),
        };
        return this.requestJson("POST", "/v1/platform/harness/hooks/render", { body, options });
    }
    interceptAgentToolCall(req = {}, options) {
        const toolName = (req.tool_name ?? "Bash").trim();
        if (!toolName)
            throw new Error("tool_name must be non-empty.");
        const command = (req.command ?? "git push origin main").trim();
        if (!command)
            throw new Error("command must be non-empty.");
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            agent_host: assertAgentHost(req.agent_host ?? "claude_code"),
            tool_name: toolName,
            command,
        };
        if (req.ticket_id !== undefined && req.ticket_id !== null && req.ticket_id.trim() !== "")
            body.ticket_id = req.ticket_id.trim();
        return this.requestJson("POST", "/v1/platform/harness/intercept", { body, options });
    }
    listHarnessTickets(wsOrOpts, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/harness/tickets", resolveTicketsListCall(wsOrOpts, limitOrOpts, options));
    }
    decideHarnessTicket(ticketId, req, options) {
        const seg = encodeSeg(ticketId, "ticket_id");
        const reviewer = (req.reviewer ?? "lead-engineer").trim();
        if (!reviewer)
            throw new Error("reviewer must be non-empty.");
        const reason = (req.reason ?? "Verified safe workspace scope").trim();
        if (!reason)
            throw new Error("reason must be non-empty.");
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            decision: assertTicketDecision(req.decision),
            reviewer,
            reason,
        };
        return this.requestJson("POST", `/v1/platform/harness/tickets/${seg}/decide`, { body, options });
    }
    evaluateWorktreeCiGate(req = {}, options) {
        const workflowName = (req.workflow_name ?? "pr-worktree-arena").trim();
        if (!workflowName)
            throw new Error("workflow_name must be non-empty.");
        const diffSummary = (req.diff_summary ?? "Refactor retry backoff & add unit test in core/platform/").trim();
        if (!diffSummary)
            throw new Error("diff_summary must be non-empty.");
        const minScore = req.min_eval_score ?? 0.85;
        if (typeof minScore !== "number" || Number.isNaN(minScore) || minScore < 0 || minScore > 1)
            throw new Error("min_eval_score must be between 0.0 and 1.0.");
        const body = {
            workspace_id: (req.workspace_id ?? "default").trim() || "default",
            workflow_name: workflowName,
            diff_summary: diffSummary,
            min_eval_score: minScore,
        };
        if (req.candidates !== undefined)
            body.candidates = req.candidates;
        return this.requestJson("POST", "/v1/platform/harness/ci-gate/evaluate", { body, options });
    }
    listWorktreeCiGateRuns(wsOrParams, limitOrOpts, options) {
        return this.requestJson("GET", "/v1/platform/harness/ci-gate/runs", resolveTicketsListCall(wsOrParams, limitOrOpts, options));
    }
}
export { PlatformHarnessClient as PlatformHarnessDelegate };
//# sourceMappingURL=platformHarness.js.map