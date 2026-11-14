import { getStudioToken } from "@/lib/api";
import type {
  AutomationWorkflowItem, ExperienceMode, MarketplaceCategoryId, MarketplacePackageItem,
  PmIssueItem, PmIssuePriority, PmIssueStatus, ProductPrdItem,
} from "@/lib/platformData";

export type EnterpriseRetentionMode = "ephemeral_0d" | "standard_30d" | "regulated_365d" | "worm_7y";

export interface PlatformHydrationSnapshot {
  hydrated: boolean; packages: MarketplacePackageItem[]; installedPackageIds: string[];
  issues: PmIssueItem[]; prds: ProductPrdItem[]; workflows: AutomationWorkflowItem[];
  retentionMode?: EnterpriseRetentionMode;
}

export interface MarketplacePublishPayload {
  id: string; name: string; kind: MarketplaceCategoryId; version?: string; publisher?: string;
  publisher_tier?: "first_party" | "verified_third_party" | "enterprise_partner";
  pricing_model?: string; price_usd?: number; description: string;
  permissions: {
    read_paths: string[]; write_paths: string[];
    network: "none" | "scoped" | "full"; requires_p10_approval: boolean;
  };
}

export interface ClusterNodeItem {
  nodeId: string; runtime: "ollama_metal" | "vllm" | "ray_serve"; runtimeLabel: string;
  region: "airgap_local" | "us" | "eu" | "africa"; gpuModel: string;
  totalVramGb: number; freeVramGb: number;
  status: "healthy" | "drained" | "unhealthy"; loadedModels: string[];
}

export interface ModelCanaryItem {
  modelId: string; stage: "stable" | "canary" | "deprecated" | "retired" | "shadow"; trafficWeightPct: number;
}

export interface MarketplaceSettlementSummary {
  count: number; grossUsd: number; creatorPayoutUsd: number; platformFeeUsd: number; verifiedSplitLabel: string;
}

export interface ClusterAndSettlementSnapshot {
  nodes: ClusterNodeItem[]; canaries: ModelCanaryItem[]; settlement: MarketplaceSettlementSummary | null;
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const VALID_CATEGORIES = new Set<MarketplaceCategoryId>([
  "ai_agent", "multi_agent_system", "agent_skill", "plugin_extension",
  "automation_template", "dev_tool", "industry_enterprise_solution",
]);
const VALID_RETENTION = new Set<EnterpriseRetentionMode>([
  "ephemeral_0d", "standard_30d", "regulated_365d", "worm_7y",
]);

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function shouldSkipUnmockedTestFetch(): boolean {
  if (import.meta.env.MODE !== "test") return false;
  if (typeof globalThis.fetch !== "function") return true;
  const hasMockProp = "mock" in (globalThis.fetch as unknown as Record<string, unknown>);
  return !hasMockProp && globalThis.fetch === INITIAL_FETCH_FN;
}

function buildPlatformUrl(path: string, query?: Record<string, string | undefined>): string {
  if (!path.startsWith("/v1/platform/") && !path.startsWith("/v1/cluster/")) {
    throw new Error(`Security violation: platformApi allows only /v1/platform/* or /v1/cluster/* paths, got ${path}`);
  }
  const search = new URLSearchParams();
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v) search.set(k, v);
    }
  }
  const token = getStudioToken();
  if (token) search.set("token", token);
  const qs = search.toString();
  return qs ? `${path}?${qs}` : path;
}

async function requestPlatformJson(
  path: string,
  init: RequestInit,
  query?: Record<string, string | undefined>,
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const url = buildPlatformUrl(path, query);
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null };
  try {
    const headers = new Headers(init.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const token = getStudioToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
      headers.set("X-Studio-Token", token);
      headers.set("X-Keelway-Token", token);
    }
    const res = await fetch(url, { ...init, credentials: "same-origin", headers });
    if (!res.ok) return { ok: false, status: res.status, data: null };
    return { ok: true, status: res.status, data: await res.json() };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

function decodeServerPackage(raw: unknown): MarketplacePackageItem | null {
  if (!isRecord(raw) || typeof raw.id !== "string" || typeof raw.name !== "string") return null;
  const rawKind = String(raw.category ?? raw.kind ?? "agent_skill") as MarketplaceCategoryId;
  const category: MarketplaceCategoryId = VALID_CATEGORIES.has(rawKind) ? rawKind : "agent_skill";
  const tierRaw = String(raw.publisherTier ?? raw.publisher_tier ?? "verified_third_party");
  const publisherTier: MarketplacePackageItem["publisherTier"] =
    tierRaw === "first_party" || tierRaw === "enterprise_partner" ? tierRaw : "verified_third_party";
  const priceUsd = typeof raw.price_usd === "number" ? raw.price_usd : 0;
  const priceLabel = typeof raw.priceLabel === "string"
    ? raw.priceLabel
    : raw.pricing_model === "enterprise" ? "Enterprise" : priceUsd <= 0 ? "Included" : `$${priceUsd} / mo`;
  const revenueSplitLabel = typeof raw.revenueSplitLabel === "string"
    ? raw.revenueSplitLabel
    : publisherTier === "first_party"
      ? "100% First-Party · $0 Fee"
      : publisherTier === "enterprise_partner" ? "80% Partner / 20% Platform" : "85% Creator / 15% Platform";
  const rawSha = typeof raw.manifestSha256 === "string" ? raw.manifestSha256 : String(raw.manifest_sha256 ?? "");
  return {
    id: raw.id,
    name: raw.name,
    category,
    publisher: typeof raw.publisher === "string" ? raw.publisher : "Workspace Creator",
    publisherTier,
    revenueSplitLabel,
    priceLabel,
    summary: typeof raw.summary === "string" ? raw.summary : String(raw.description ?? ""),
    manifestSha256: rawSha.startsWith("sha256:") ? rawSha : `sha256:${(rawSha || "verified").slice(0, 12)}`,
    securityVerified: raw.securityVerified !== false && raw.security_verified !== false,
  };
}

function decodeServerIssue(raw: unknown): PmIssueItem | null {
  if (!isRecord(raw) || typeof raw.id !== "string" || typeof raw.title !== "string") return null;
  const st = String(raw.status ?? "todo");
  const status: PmIssueStatus = st === "backlog" || st === "in_progress" || st === "in_review" || st === "done" ? st : "todo";
  const pr = String(raw.priority ?? "medium");
  const priority: PmIssuePriority = pr === "urgent" || pr === "high" || pr === "low" ? pr : "medium";
  return {
    id: raw.id, title: raw.title, status, priority,
    sprint: typeof raw.sprint === "string" ? raw.sprint : String(raw.sprint_id ?? "Sprint 14 · Sovereign Platform"),
    milestone: typeof raw.milestone === "string" ? raw.milestone : "v1.1 Unified GA",
    dependencies: Array.isArray(raw.dependencies) ? raw.dependencies.filter((d): d is string => typeof d === "string") : [],
    assignedAgentId: typeof raw.assignedAgentId === "string" ? raw.assignedAgentId : typeof raw.assignee_agent === "string" ? raw.assignee_agent : undefined,
    linkedPrdId: typeof raw.linkedPrdId === "string" ? raw.linkedPrdId : typeof raw.prd_id === "string" ? raw.prd_id : undefined,
  };
}

function decodeServerPrd(raw: unknown): ProductPrdItem | null {
  if (!isRecord(raw) || typeof raw.id !== "string" || typeof raw.title !== "string") return null;
  const rawCriteria = Array.isArray(raw.acceptanceCriteria) ? raw.acceptanceCriteria : Array.isArray(raw.acceptance_criteria) ? raw.acceptance_criteria : [];
  return {
    id: raw.id,
    title: raw.title,
    problemStatement: typeof raw.problemStatement === "string" ? raw.problemStatement : String(raw.summary ?? ""),
    riceScore: typeof raw.riceScore === "number" ? raw.riceScore : 90,
    releaseStage: raw.status === "approved" ? "in_delivery" : "discovery",
    linkedIssueIds: Array.isArray(raw.linkedIssueIds) ? raw.linkedIssueIds.filter((i): i is string => typeof i === "string") : [],
    acceptanceCriteria: rawCriteria.map((ac, i) =>
      isRecord(ac) && typeof ac.text === "string"
        ? { id: String(ac.id ?? `${raw.id}-ac-${i}`), text: ac.text, met: Boolean(ac.met) }
        : { id: `${raw.id}-ac-${i}`, text: String(ac), met: true },
    ),
  };
}

function decodeServerWorkflow(raw: unknown): AutomationWorkflowItem | null {
  if (!isRecord(raw) || typeof raw.id !== "string" || typeof raw.name !== "string") return null;
  const trig = String(raw.triggerSpec ?? raw.trigger ?? "manual");
  const triggerKind: AutomationWorkflowItem["triggerKind"] =
    trig.includes("cron") || trig.includes("*") ? "cron" : trig.includes("webhook") ? "webhook" : "event";
  return {
    id: raw.id,
    name: raw.name,
    triggerKind,
    triggerSpec: trig,
    lastRunStatus: raw.status === "failed" ? "failed" : "ready",
    tokenBudget: typeof raw.tokenBudget === "number" ? raw.tokenBudget : 25_000,
    nodes: (Array.isArray(raw.nodes) ? raw.nodes : []).filter(isRecord).map((n, i) => ({
      id: String(n.id ?? `n-${i}`),
      label: String(n.label ?? "Step"),
      agentId: String(n.agentId ?? n.agent ?? "workflow-automator"),
      dependsOn: Array.isArray(n.dependsOn) ? n.dependsOn.filter((d): d is string => typeof d === "string") : [],
      status: n.status === "failed" ? "failed" : "passed",
    })),
  };
}

export async function fetchPlatformHydration(workspaceId = "default"): Promise<PlatformHydrationSnapshot> {
  const q = { workspace_id: workspaceId };
  const [overviewRes, mpRes, issuesRes, prdsRes, wfRes] = await Promise.all([
    requestPlatformJson("/v1/platform/overview", { method: "GET" }, q),
    requestPlatformJson("/v1/platform/marketplace/packages", { method: "GET" }, q),
    requestPlatformJson("/v1/platform/pm/issues", { method: "GET" }, q),
    requestPlatformJson("/v1/platform/product/prds", { method: "GET" }, q),
    requestPlatformJson("/v1/platform/automation/workflows", { method: "GET" }, q),
  ]);
  if (!(overviewRes.ok || mpRes.ok || issuesRes.ok || prdsRes.ok || wfRes.ok)) {
    return { hydrated: false, packages: [], installedPackageIds: [], issues: [], prds: [], workflows: [] };
  }
  const ov = isRecord(overviewRes.data) ? overviewRes.data : {};
  const mp = isRecord(mpRes.data) ? mpRes.data : {};
  const rawInstalled = [
    ...(Array.isArray(mp.installed) ? mp.installed : []),
    ...(Array.isArray(ov.installed_packages) ? ov.installed_packages : []),
  ];
  const installedPackageIds = Array.from(
    new Set(
      rawInstalled
        .map((it) => (typeof it === "string" ? it : isRecord(it) ? String(it.package_id ?? it.id ?? "") : ""))
        .filter(Boolean),
    ),
  );
  const rawIssues = isRecord(issuesRes.data) && Array.isArray(issuesRes.data.issues) ? issuesRes.data.issues : Array.isArray(ov.issues) ? ov.issues : [];
  const rawPrds = isRecord(prdsRes.data) && Array.isArray(prdsRes.data.prds) ? prdsRes.data.prds : Array.isArray(ov.prds) ? ov.prds : [];
  const rawWfs = isRecord(wfRes.data) && Array.isArray(wfRes.data.workflows) ? wfRes.data.workflows : Array.isArray(ov.workflows) ? ov.workflows : [];
  const ent = isRecord(ov.enterprise) ? ov.enterprise : {};
  const retCandidate = String(ov.retention_mode ?? ent.retention_mode ?? "") as EnterpriseRetentionMode;
  return {
    hydrated: true,
    packages: (Array.isArray(mp.packages) ? mp.packages : []).map(decodeServerPackage).filter((p): p is MarketplacePackageItem => p !== null),
    installedPackageIds,
    issues: rawIssues.map(decodeServerIssue).filter((i): i is PmIssueItem => i !== null),
    prds: rawPrds.map(decodeServerPrd).filter((p): p is ProductPrdItem => p !== null),
    workflows: rawWfs.map(decodeServerWorkflow).filter((w): w is AutomationWorkflowItem => w !== null),
    retentionMode: VALID_RETENTION.has(retCandidate) ? retCandidate : undefined,
  };
}

export async function postPlatformIssue(payload: {
  title: string; priority: PmIssuePriority; assignedAgentId?: string;
  workspaceId?: string; status?: PmIssueStatus; prdId?: string; sprintId?: string;
}): Promise<{ ok: boolean; data: unknown }> {
  const res = await requestPlatformJson("/v1/platform/pm/issues", {
    method: "POST",
    body: JSON.stringify({
      title: payload.title,
      workspace_id: payload.workspaceId ?? "default",
      priority: payload.priority,
      status: payload.status ?? "todo",
      assignee_agent: payload.assignedAgentId ?? "feature-coder",
      ...(payload.prdId ? { prd_id: payload.prdId } : {}),
      sprint_id: payload.sprintId ?? "SPR-01",
    }),
  });
  return { ok: res.ok, data: res.data };
}

export async function postMarketplaceInstall(packageId: string, workspaceId = "default"): Promise<{ ok: boolean }> {
  const res = await requestPlatformJson("/v1/platform/marketplace/install", {
    method: "POST", body: JSON.stringify({ package_id: packageId, workspace_id: workspaceId }),
  });
  return { ok: res.ok };
}

export async function postMarketplaceUninstall(packageId: string, workspaceId = "default"): Promise<{ ok: boolean }> {
  const res = await requestPlatformJson("/v1/platform/marketplace/uninstall", {
    method: "POST", body: JSON.stringify({ package_id: packageId, workspace_id: workspaceId }),
  });
  return { ok: res.ok };
}

export async function postMarketplacePublish(payload: MarketplacePublishPayload): Promise<{ ok: boolean; data: unknown }> {
  const res = await requestPlatformJson("/v1/platform/marketplace/publish", {
    method: "POST", body: JSON.stringify(payload),
  });
  return { ok: res.ok, data: res.data };
}

export async function postTeamDispatch(
  teamId: string, goal: string, sensitiveMutation = true, workspaceId = "default",
): Promise<{ ok: boolean; data: unknown }> {
  const res = await requestPlatformJson("/v1/platform/agents/teams/dispatch", {
    method: "POST",
    body: JSON.stringify({ team_id: teamId, objective: goal, workspace_id: workspaceId, sensitive_mutation: sensitiveMutation }),
  });
  return { ok: res.ok, data: res.data };
}

export async function postNoCodeBlueprint(
  idea: string, experienceMode: ExperienceMode, targetStack = "fastapi_react_sqlite", workspaceId = "default",
): Promise<{ ok: boolean; data: unknown }> {
  const res = await requestPlatformJson("/v1/platform/nocode/blueprint", {
    method: "POST",
    body: JSON.stringify({ idea, workspace_id: workspaceId, experience_mode: experienceMode, target_stack: targetStack }),
  });
  return { ok: res.ok, data: res.data };
}

function decodeClusterNode(raw: unknown): ClusterNodeItem | null {
  if (!isRecord(raw) || typeof (raw.node_id ?? raw.nodeId) !== "string") return null;
  const rtRaw = String(raw.runtime ?? "vllm");
  const runtime: ClusterNodeItem["runtime"] = rtRaw === "ollama_metal" || rtRaw === "ray_serve" ? rtRaw : "vllm";
  const runtimeLabel = runtime === "ollama_metal" ? "Apple Metal" : runtime === "ray_serve" ? "Ray Serve" : "vLLM";
  const regRaw = String(raw.region ?? "us");
  const region: ClusterNodeItem["region"] = regRaw === "airgap_local" || regRaw === "eu" || regRaw === "africa" ? regRaw : "us";
  const totalVramGb = typeof raw.total_vram_gb === "number" ? raw.total_vram_gb : typeof raw.totalVramGb === "number" ? raw.totalVramGb : 32;
  const freeVramGb = typeof raw.free_vram_gb === "number" ? raw.free_vram_gb : typeof raw.freeVramGb === "number" ? raw.freeVramGb : totalVramGb;
  const stRaw = String(raw.status ?? "healthy");
  return {
    nodeId: String(raw.node_id ?? raw.nodeId), runtime, runtimeLabel, region,
    gpuModel: String(raw.gpu_model ?? raw.gpuModel ?? runtimeLabel), totalVramGb, freeVramGb,
    status: stRaw === "drained" || stRaw === "unhealthy" ? stRaw : "healthy",
    loadedModels: Array.isArray(raw.loaded_models ?? raw.loadedModels) ? ((raw.loaded_models ?? raw.loadedModels) as unknown[]).map(String) : [],
  };
}

export async function fetchClusterAndSettlementSnapshot(): Promise<ClusterAndSettlementSnapshot | null> {
  const [nodesRes, lcRes, setRes] = await Promise.all([
    requestPlatformJson("/v1/cluster/nodes", { method: "GET" }),
    requestPlatformJson("/v1/cluster/lifecycle", { method: "GET" }),
    requestPlatformJson("/v1/platform/marketplace/settlements", { method: "GET" }),
  ]);
  if (!(nodesRes.ok || lcRes.ok || setRes.ok)) return null;
  const rawNodes = Array.isArray(nodesRes.data) ? nodesRes.data : isRecord(nodesRes.data) && Array.isArray(nodesRes.data.nodes) ? nodesRes.data.nodes : [];
  const lcObj = isRecord(lcRes.data) ? lcRes.data : {};
  const rawLc = Array.isArray(lcRes.data) ? lcRes.data : Array.isArray(lcObj.entries) ? lcObj.entries : Array.isArray(lcObj.models) ? lcObj.models : Array.isArray(lcObj.canaries) ? lcObj.canaries : [];
  const canaries: ModelCanaryItem[] = rawLc.filter(isRecord).map((m) => ({
    modelId: String(m.model_id ?? m.modelId ?? m.id ?? "keelway-core:7b"),
    stage: m.stage === "canary" || m.stage === "deprecated" || m.stage === "retired" || m.stage === "shadow" ? m.stage : "stable",
    trafficWeightPct: Number(m.traffic_weight_pct ?? m.trafficWeightPct ?? m.canary_weight_pct ?? m.weight_pct ?? 100),
  }));
  const stRoot = isRecord(setRes.data) ? setRes.data : {};
  const stTotals = isRecord(stRoot.totals) ? stRoot.totals : stRoot;
  const hasSettlement = isRecord(stRoot.totals) || typeof stTotals.gross_usd === "number" || typeof stTotals.grossUsd === "number";
  return {
    nodes: rawNodes.map(decodeClusterNode).filter((n): n is ClusterNodeItem => n !== null),
    canaries,
    settlement: hasSettlement ? {
      count: Number(stTotals.count ?? 0), grossUsd: Number(stTotals.gross_usd ?? stTotals.grossUsd ?? 0),
      creatorPayoutUsd: Number(stTotals.creator_payout_usd ?? stTotals.creatorPayoutUsd ?? 0),
      platformFeeUsd: Number(stTotals.platform_fee_usd ?? stTotals.platformFeeUsd ?? 0),
      verifiedSplitLabel: "85% Creator / 15% Platform",
    } : null,
  };
}

export async function postClusterNodeAction(nodeId: string, action: "drain" | "restore"): Promise<{ ok: boolean; data: unknown }> {
  const res = await requestPlatformJson(`/v1/cluster/nodes/${encodeURIComponent(nodeId)}/${action}`, {
    method: "POST", body: JSON.stringify({ node_id: nodeId, action }),
  });
  return { ok: res.ok, data: res.data };
}
