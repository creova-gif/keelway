/**
 * Keelway Official TypeScript SDK — Unified Platform Namespace (`client.platform`).
 *
 * Exposes all `/v1/platform/*` endpoints using `KeelwayClient`'s zero-dependency
 * Web Fetch, `AbortSignal` timeout, and `mapHttpError` infrastructure.
 */
import { PlatformRuntimeDelegate } from "./platform-runtime.js";
import { PlatformMcpEvalDelegate } from "./platformMcpEval.js";
import { PlatformKflowDelegate } from "./platformKflow.js";
import { PlatformEnterpriseDelegate } from "./platformEnterprise.js";
import { PlatformKbrainDelegate } from "./platformKbrain.js";
import { PlatformDevxDelegate } from "./platformDevx.js";
import { PlatformStudioClient } from "./platformStudio.js";
import { PlatformDebuggerClient } from "./platformDebugger.js";
import { PlatformCyclicClient } from "./platformCyclic.js";
import { PlatformHealingClient } from "./platformHealing.js";
import { PlatformSafetyMeshClient } from "./platformSafetyMesh.js";
import { PlatformHarnessClient } from "./platformHarness.js";
import { PlatformDistillClient } from "./platformDistill.js";
import { PlatformSupplyChainClient } from "./platformSupplyChain.js";
export class PlatformNamespace {
    requestJson;
    runtime;
    mcpEval;
    kflow;
    enterprise;
    kbrain;
    devx;
    studio;
    debugger;
    cyclic;
    healing;
    safetyMesh;
    harness;
    distill;
    supplyChain;
    constructor(requestJson, requestSse) {
        this.requestJson = requestJson;
        this.runtime = new PlatformRuntimeDelegate(requestJson, requestSse);
        this.mcpEval = new PlatformMcpEvalDelegate(requestJson);
        this.kflow = new PlatformKflowDelegate(requestJson);
        this.enterprise = new PlatformEnterpriseDelegate(requestJson);
        this.kbrain = new PlatformKbrainDelegate(requestJson);
        this.devx = new PlatformDevxDelegate(requestJson);
        this.studio = new PlatformStudioClient(requestJson);
        this.debugger = new PlatformDebuggerClient(requestJson);
        this.cyclic = new PlatformCyclicClient(requestJson);
        this.healing = new PlatformHealingClient(requestJson);
        this.safetyMesh = new PlatformSafetyMeshClient(requestJson);
        this.harness = new PlatformHarnessClient(requestJson);
        this.distill = new PlatformDistillClient(requestJson);
        this.supplyChain = new PlatformSupplyChainClient(requestJson);
    }
    overview(params = {}, options) {
        const workspaceId = typeof params === "string" ? params : (params.workspace_id ?? "default");
        return this.requestJson("GET", "/v1/platform/overview", { query: { workspace_id: workspaceId }, options });
    }
    listTiers(options) {
        return this.requestJson("GET", "/v1/platform/subscriptions/tiers", { options });
    }
    checkQuota(req, options) {
        return this.requestJson("POST", "/v1/platform/subscriptions/quota-check", {
            body: {
                org_id: req.org_id, tier: req.tier, tokens_requested: req.tokens_requested,
                current_rpm: req.current_rpm ?? 1, local_hardware: req.local_hardware ?? false,
            },
            options,
        });
    }
    validateByom(req, options) {
        const body = {
            provider: req.provider, credential_kind: req.credential_kind,
            api_key_preview: req.api_key_preview ?? "", model_id: req.model_id ?? "",
            commercial_use: req.commercial_use ?? true,
        };
        if (req.license_id !== undefined)
            body.license_id = req.license_id;
        return this.requestJson("POST", "/v1/platform/subscriptions/byom/validate", { body, options });
    }
    checkModelLicense(req, options) {
        return this.requestJson("POST", "/v1/platform/subscriptions/license-check", {
            body: {
                model_id: req.model_id, license_id: req.license_id, commercial_use: req.commercial_use ?? true,
                has_authorized_api_credential: req.has_authorized_api_credential ?? req.has_authorized_api_key ?? false,
                exceeds_700m_mau: req.exceeds_700m_mau ?? false,
            },
            options,
        });
    }
    listMarketplacePackages(params = {}, options) {
        const query = { workspace_id: params.workspace_id ?? "default" };
        if (params.kind !== undefined)
            query.kind = params.kind;
        if (params.query !== undefined)
            query.query = params.query;
        if (params.publisher_tier !== undefined)
            query.publisher_tier = params.publisher_tier;
        return this.requestJson("GET", "/v1/platform/marketplace/packages", { query, options });
    }
    scanMarketplacePackage(pkg, options) {
        return this.requestJson("POST", "/v1/platform/marketplace/scan", { body: { ...pkg }, options });
    }
    publishMarketplacePackage(pkg, options) {
        return this.requestJson("POST", "/v1/platform/marketplace/publish", { body: { ...pkg }, options });
    }
    installMarketplacePackage(req, options) {
        const body = { package_id: req.package_id, workspace_id: req.workspace_id ?? "default" };
        if (req.config !== undefined)
            body.config = req.config;
        return this.requestJson("POST", "/v1/platform/marketplace/install", { body, options });
    }
    purchaseMarketplacePackage(req, options) {
        const body = typeof req === "string"
            ? { package_id: req, buyer_tenant_id: "default" }
            : { package_id: req.package_id, buyer_tenant_id: req.buyer_tenant_id ?? "default" };
        if (typeof req !== "string") {
            if (req.workspace_id !== undefined)
                body.workspace_id = req.workspace_id;
            if (req.config !== undefined)
                body.config = req.config;
        }
        return this.requestJson("POST", "/v1/platform/marketplace/purchase", { body, options });
    }
    listMarketplaceSettlements(params = {}, options) {
        const tenantId = typeof params === "string" ? params : params.tenant_id;
        const query = tenantId !== undefined ? { tenant_id: tenantId } : undefined;
        return this.requestJson("GET", "/v1/platform/marketplace/settlements", { query, options });
    }
    listAgents(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/agents", { query: { workspace_id: params.workspace_id ?? "default" }, options });
    }
    dispatchTeam(req, options) {
        return this.requestJson("POST", "/v1/platform/agents/teams/dispatch", {
            body: {
                team_id: req.team_id, objective: req.objective ?? req.goal ?? "",
                workspace_id: req.workspace_id ?? "default", sensitive_mutation: req.sensitive_mutation ?? false,
            },
            options,
        });
    }
    async listIssues(params = {}, options) {
        const query = { workspace_id: params.workspace_id ?? "default" };
        if (params.status !== undefined)
            query.status = params.status;
        const res = await this.requestJson("GET", "/v1/platform/pm/issues", { query, options });
        if (params.status !== undefined && Array.isArray(res.issues)) {
            const filtered = res.issues.filter((i) => i.status === params.status);
            return { ...res, issues: filtered, total: filtered.length };
        }
        return res;
    }
    createIssue(req, options) {
        const body = {
            title: req.title, workspace_id: req.workspace_id ?? "default", priority: req.priority ?? "medium",
            status: req.status ?? "todo", assignee_agent: req.assignee_agent ?? "feature-coder", sprint_id: req.sprint_id ?? "SPR-01",
        };
        if (req.prd_id !== undefined)
            body.prd_id = req.prd_id;
        return this.requestJson("POST", "/v1/platform/pm/issues", { body, options });
    }
    listPrds(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/product/prds", { query: { workspace_id: params.workspace_id ?? "default" }, options });
    }
    createPrd(req, options) {
        const body = { title: req.title, summary: req.summary, workspace_id: req.workspace_id ?? "default" };
        if (req.acceptance_criteria !== undefined)
            body.acceptance_criteria = req.acceptance_criteria;
        return this.requestJson("POST", "/v1/platform/product/prds", { body, options });
    }
    listWorkflows(params = {}, options) {
        return this.requestJson("GET", "/v1/platform/automation/workflows", { query: { workspace_id: params.workspace_id ?? "default" }, options });
    }
    createWorkflow(req, options) {
        const body = { name: req.name, trigger: req.trigger ?? "manual", workspace_id: req.workspace_id ?? "default" };
        if (req.nodes !== undefined)
            body.nodes = req.nodes;
        return this.requestJson("POST", "/v1/platform/automation/workflows", { body, options });
    }
    compileBlueprint(req, options) {
        return this.requestJson("POST", "/v1/platform/nocode/blueprint", {
            body: {
                idea: req.idea, workspace_id: req.workspace_id ?? "default",
                experience_mode: req.experience_mode ?? "non_coder", target_stack: req.target_stack ?? "react-fastapi-sqlite",
            },
            options,
        });
    }
    listExtensions(params = {}, options) {
        const query = { workspace_id: params.workspace_id ?? "default" };
        if (params.extension_type !== undefined)
            query.extension_type = params.extension_type;
        return this.requestJson("GET", "/v1/platform/extensions", { query, options });
    }
    registerExtension(extension, options) {
        return this.requestJson("POST", "/v1/platform/extensions/register", { body: { ...extension }, options });
    }
    listDocs(params = {}, options) {
        return this.runtime.listDocs(params, options);
    }
    createDoc(req, options) {
        return this.runtime.createDoc(req, options);
    }
    updateDoc(docId, req, options) {
        return this.runtime.updateDoc(docId, req, options);
    }
    updateIssue(issueId, patch, options) {
        return this.runtime.updateIssue(issueId, patch, options);
    }
    listFeedback(params = {}, options) {
        return this.runtime.listFeedback(params, options);
    }
    createFeedback(req, options) {
        return this.runtime.createFeedback(req, options);
    }
    scanWorkspaceSecurity(req, options) {
        return this.runtime.scanWorkspaceSecurity(req, options);
    }
    listWorkspaces(options) {
        return this.runtime.listWorkspaces(options);
    }
    createWorkspace(req, options) {
        return this.runtime.createWorkspace(req, options);
    }
    listRbacMembers(params = {}, options) {
        return this.runtime.listRbacMembers(params, options);
    }
    upsertRbacMember(req, options) {
        return this.runtime.upsertRbacMember(req, options);
    }
    checkRbac(req, options) {
        return this.runtime.checkRbac(req, options);
    }
    listSecrets(params = {}, options) {
        return this.runtime.listSecrets(params, options);
    }
    putSecret(req, options) {
        return this.runtime.putSecret(req, options);
    }
    rotateSecret(name, req, options) {
        return this.runtime.rotateSecret(name, req, options);
    }
    deleteSecret(name, params = {}, options) {
        return this.runtime.deleteSecret(name, params, options);
    }
    listWebhooks(params = {}, options) {
        return this.runtime.listWebhooks(params, options);
    }
    createWebhook(req, options) {
        return this.runtime.createWebhook(req, options);
    }
    deleteWebhook(webhookId, params = {}, options) {
        return this.runtime.deleteWebhook(webhookId, params, options);
    }
    testWebhook(webhookId, req, options) {
        return this.runtime.testWebhook(webhookId, req, options);
    }
    verifyWebhook(req, options) {
        return this.runtime.verifyWebhook(req, options);
    }
    startExecutionRun(req, options) {
        return this.runtime.startExecutionRun(req, options);
    }
    resolveExecutionP10(runId, req, options) {
        return this.runtime.resolveExecutionP10(runId, req, options);
    }
    streamExecutionEvents(runId, options) {
        return this.runtime.streamExecutionEvents(runId, options);
    }
    simulatePricing(req, options) {
        return this.runtime.simulatePricing(req, options);
    }
    listMcpServers(params = {}, options) {
        return this.mcpEval.listMcpServers(params, options);
    }
    registerMcpServer(req, options) {
        return this.mcpEval.registerMcpServer(req, options);
    }
    deleteMcpServer(serverId, params = {}, options) {
        return this.mcpEval.deleteMcpServer(serverId, params, options);
    }
    listMcpTools(params = {}, options) {
        return this.mcpEval.listMcpTools(params, options);
    }
    callMcpTool(reqOrToolName, argumentsOrOptions, workspaceId, options) {
        return this.mcpEval.callMcpTool(reqOrToolName, argumentsOrOptions, workspaceId, options);
    }
    runGoldenEvals(req = {}, options) {
        return this.mcpEval.runGoldenEvals(req, options);
    }
    getLatestGoldenEvals(params = {}, options) {
        return this.mcpEval.getLatestGoldenEvals(params, options);
    }
    executeKflowDag(req, options) {
        return this.kflow.executeKflowDag(req, options);
    }
    listKflowRuns(params = {}, options) {
        return this.kflow.listKflowRuns(params, options);
    }
    syncKspacesCrdt(req, options) {
        return this.kflow.syncKspacesCrdt(req, options);
    }
    getKspacesState(params = {}, options) {
        return this.kflow.getKspacesState(params, options);
    }
    getPlatformSbom(params = {}, options) {
        return this.kflow.getPlatformSbom(params, options);
    }
    configureOidcProvider(req, options) {
        return this.enterprise.configureOidcProvider(req, options);
    }
    listScimUsers(params = {}, options) {
        return this.enterprise.listScimUsers(params, options);
    }
    provisionScimUser(req, options) {
        return this.enterprise.provisionScimUser(req, options);
    }
    approveP10Quorum(req, options) {
        return this.enterprise.approveP10Quorum(req, options);
    }
    exportSiemAudit(params = {}, options) {
        return this.enterprise.exportSiemAudit(params, options);
    }
    getObservabilityMetrics(params = {}, options) {
        return this.enterprise.getObservabilityMetrics(params, options);
    }
    recordKbrainFact(req, options) {
        return this.kbrain.recordKbrainFact(req, options);
    }
    searchKbrainFacts(params = {}, options) {
        return this.kbrain.searchKbrainFacts(params, options);
    }
    resolveKbrainFact(factId, req, options) {
        return this.kbrain.resolveKbrainFact(factId, req, options);
    }
    listKhubSkills(params = {}, options) {
        return this.kbrain.listKhubSkills(params, options);
    }
    verifyKhubMirror(req = {}, options) {
        return this.kbrain.verifyKhubMirror(req, options);
    }
    ingestOtelTraces(payload, options) {
        return this.devx.ingestOtelTraces(payload, options);
    }
    listFlightTapes(workspaceIdOrParams = "default", limitOrOptions, options) {
        if (typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null) {
            return this.devx.listFlightTapes(workspaceIdOrParams, limitOrOptions);
        }
        if (typeof limitOrOptions === "object") {
            return this.devx.listFlightTapes(workspaceIdOrParams, 20, limitOrOptions);
        }
        return this.devx.listFlightTapes(workspaceIdOrParams, limitOrOptions, options);
    }
    replayFlightTape(traceId, payload, options) {
        return this.devx.replayFlightTape(traceId, payload, options);
    }
    promoteTraceToEval(payload, options) {
        return this.devx.promoteTraceToEval(payload, options);
    }
    listEvalDatasetCases(workspaceIdOrParams = "default", options) {
        if (typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null) {
            return this.devx.listEvalDatasetCases(workspaceIdOrParams, options);
        }
        return this.devx.listEvalDatasetCases(workspaceIdOrParams, options);
    }
    migrateLanggraphSource(payload, options) {
        return this.devx.migrateLanggraphSource(payload, options);
    }
    syncKflowStudio(payload = {}, options) {
        return this.studio.syncKflowStudio(payload, options);
    }
    recordBlastRadius(payload = {}, options) {
        return this.studio.recordBlastRadius(payload, options);
    }
    listBlastRadiusAudits(paramsOrWorkspaceId = {}, options) {
        return this.studio.listBlastRadiusAudits(paramsOrWorkspaceId, options);
    }
    evaluatePromptGate(payload, options) {
        return this.studio.evaluatePromptGate(payload, options);
    }
    listPromptGateRuns(paramsOrWorkspaceId = {}, options) {
        return this.studio.listPromptGateRuns(paramsOrWorkspaceId, options);
    }
    setBreakpoint(payload = {}, options) {
        return this.debugger.setBreakpoint(payload, options);
    }
    listBreakpoints(paramsOrWorkspaceId = {}, options) {
        return this.debugger.listBreakpoints(paramsOrWorkspaceId, options);
    }
    deleteBreakpoint(breakpointId, paramsOrWorkspaceId = {}, options) {
        return this.debugger.deleteBreakpoint(breakpointId, paramsOrWorkspaceId, options);
    }
    startDebugSession(payload = {}, options) {
        return this.debugger.startDebugSession(payload, options);
    }
    listDebugSessions(paramsOrWorkspaceId = {}, options) {
        return this.debugger.listDebugSessions(paramsOrWorkspaceId, options);
    }
    stepDebugSession(sessionId, payloadOrAction = {}, options) {
        return this.debugger.stepDebugSession(sessionId, payloadOrAction, options);
    }
    getDebuggerCodelens(paramsOrWorkspaceId = {}, options) {
        return this.debugger.getDebuggerCodelens(paramsOrWorkspaceId, options);
    }
    validateCyclicKflow(req, options) {
        return this.cyclic.validateCyclicKflow(req, options);
    }
    executeCyclicKflow(req, options) {
        return this.cyclic.executeCyclicKflow(req, options);
    }
    listCyclicKflowRuns(params, options) {
        return this.cyclic.listCyclicKflowRuns(params, options);
    }
    getCyclicKflowRun(runId, workspaceId, options) {
        return this.cyclic.getCyclicKflowRun(runId, workspaceId, options);
    }
    simulateKflowAutopilot(req, options) {
        return this.cyclic.simulateKflowAutopilot(req, options);
    }
    listKflowAutopilotSimulations(params, options) {
        return this.cyclic.listKflowAutopilotSimulations(params, options);
    }
    normalizeContentBlocks(req, options) {
        return this.healing.normalizeContentBlocks(req, options);
    }
    enforceStructuredOutput(req, options) {
        return this.healing.enforceStructuredOutput(req, options);
    }
    listStructuredOutputRuns(params, options) {
        return this.healing.listStructuredOutputRuns(params, options);
    }
    diagnoseFailureRootCause(req, options) {
        return this.healing.diagnoseFailureRootCause(req, options);
    }
    applySelfHealingPatch(diagnosisId, req, options) {
        return this.healing.applySelfHealingPatch(diagnosisId, req, options);
    }
    listSelfHealingDiagnoses(params, options) {
        return this.healing.listSelfHealingDiagnoses(params, options);
    }
    verifyWorkflowSafety(req, options) {
        return this.safetyMesh.verifyWorkflowSafety(req, options);
    }
    listSafetyVerifications(workspaceIdOrParams, limitOrOptions, options) {
        if (typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null) {
            return this.safetyMesh.listSafetyVerifications(workspaceIdOrParams, limitOrOptions);
        }
        if (typeof limitOrOptions === "object" && limitOrOptions !== null) {
            return this.safetyMesh.listSafetyVerifications(workspaceIdOrParams, 25, limitOrOptions);
        }
        return this.safetyMesh.listSafetyVerifications(workspaceIdOrParams, limitOrOptions, options);
    }
    registerMeshNode(req, options) {
        return this.safetyMesh.registerMeshNode(req, options);
    }
    listMeshNodes(workspaceIdOrParams, options) {
        if (typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null) {
            return this.safetyMesh.listMeshNodes(workspaceIdOrParams, options);
        }
        return this.safetyMesh.listMeshNodes(workspaceIdOrParams, options);
    }
    dispatchMeshHandoff(req, options) {
        return this.safetyMesh.dispatchMeshHandoff(req, options);
    }
    listMeshHandoffs(workspaceIdOrParams, limitOrOptions, options) {
        if (typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null) {
            return this.safetyMesh.listMeshHandoffs(workspaceIdOrParams, limitOrOptions);
        }
        if (typeof limitOrOptions === "object" && limitOrOptions !== null) {
            return this.safetyMesh.listMeshHandoffs(workspaceIdOrParams, 25, limitOrOptions);
        }
        return this.safetyMesh.listMeshHandoffs(workspaceIdOrParams, limitOrOptions, options);
    }
    renderAgentHookConfig(req, options) {
        return this.harness.renderAgentHookConfig(req, options);
    }
    interceptAgentToolCall(req, options) {
        return this.harness.interceptAgentToolCall(req, options);
    }
    listHarnessTickets(wsOrOpts, limitOrOpts, options) {
        return this.harness.listHarnessTickets(wsOrOpts, limitOrOpts, options);
    }
    decideHarnessTicket(ticketId, req, options) {
        return this.harness.decideHarnessTicket(ticketId, req, options);
    }
    evaluateWorktreeCiGate(req, options) {
        return this.harness.evaluateWorktreeCiGate(req, options);
    }
    listWorktreeCiGateRuns(wsOrParams, limitOrOpts, options) {
        return this.harness.listWorktreeCiGateRuns(wsOrParams, limitOrOpts, options);
    }
    evaluateShadowPrompt(req, options) {
        return this.distill.evaluateShadowPrompt(req, options);
    }
    listShadowPairs(wsOrOpts, limitOrOpts, options) {
        return this.distill.listShadowPairs(wsOrOpts, limitOrOpts, options);
    }
    getSemanticCacheStats(wsOrParams, options) {
        return this.distill.getSemanticCacheStats(wsOrParams, options);
    }
    compileDistillationDataset(req, options) {
        return this.distill.compileDistillationDataset(req, options);
    }
    listDistillationDatasets(wsOrParams, limitOrOpts, options) {
        return this.distill.listDistillationDatasets(wsOrParams, limitOrOpts, options);
    }
    evaluateDistillationPromotion(req, options) {
        return this.distill.evaluateDistillationPromotion(req, options);
    }
    pinMcpLockfile(req, options) {
        return this.supplyChain.pinMcpLockfile(req, options);
    }
    listMcpLockfiles(wsOrParams, limitOrOpts, options) {
        return this.supplyChain.listMcpLockfiles(wsOrParams, limitOrOpts, options);
    }
    verifyMcpLockfile(req, options) {
        return this.supplyChain.verifyMcpLockfile(req, options);
    }
    listMcpLockVerifications(wsOrParams, limitOrOpts, options) {
        return this.supplyChain.listMcpLockVerifications(wsOrParams, limitOrOpts, options);
    }
    runConformanceBenchmark(req, options) {
        return this.supplyChain.runConformanceBenchmark(req, options);
    }
    listConformanceBenchmarks(wsOrParams, limitOrOpts, options) {
        return this.supplyChain.listConformanceBenchmarks(wsOrParams, limitOrOpts, options);
    }
}
export { PlatformNamespace as PlatformClient };
//# sourceMappingURL=platform.js.map