import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type WorkspaceRbacRole = RbacRoleId;
export type CyclicRunStatus = "CONVERGED" | "COMPENSATED" | "HELD_P10";
export type CyclicLoopCondition = "critic_score_lt" | "retry_on_error" | "until_converged";
export type AutopilotPrivacyPolicy = "hybrid_balanced" | "airgap_strict" | "eu_residency";

export interface CyclicNodeSpec { id: string; agent_id: string; model: string; depends_on: string[]; fan_out_items: number; timeout_ms: number; compensation_handler: string; base_cost_usd: number; ttft_ms: number; requires_p10: boolean; }
export interface CyclicLoopEdgeSpec { from_node: string; to_node: string; condition: CyclicLoopCondition; threshold: number; max_iterations: number; }
export interface CyclicValidationResult { workspace_id: string; workflow_id: string; valid: boolean; node_count: number; loop_edge_count: number; max_worst_case_steps: number; topological_spine: string[]; compensation_handlers: string[]; spec_sha256: string; }
export interface CyclicIterationTraceItem { iteration: number; node_id: string; agent_id: string; model?: string; critic_score: number; shard_count: number; status: string; cost_usd: number; latency_ms: number; }
export interface CyclicCompensationItem { node_id: string; handler: string; reason: string; status: string; }
export interface CyclicKflowRunRecord {
  run_id: string; workspace_id: string; workflow_id: string; status: CyclicRunStatus; iterations_executed: number; max_iterations: number;
  converged: boolean; final_critic_score: number; critic_threshold: number; fan_out_shards: number; total_cost_usd: number; total_latency_ms: number;
  iteration_trace: CyclicIterationTraceItem[]; compensation_log: CyclicCompensationItem[]; held_node_id: string | null; run_sha256: string; created_at: string;
}
export interface AutopilotNodePlanItem { node_id: string; original_model: string; selected_model: string; rewritten: boolean; reason: string; p50_cost_usd: number; p95_cost_usd: number; data_boundary: string; }
export interface AutopilotSimulationRecord {
  simulation_id: string; workspace_id: string; workflow_id: string; privacy_policy: AutopilotPrivacyPolicy; budget_cap_usd: number;
  baseline_p50_usd: number; baseline_p95_usd: number; optimized_p50_usd: number; optimized_p95_usd: number; savings_pct: number;
  baseline_ttft_ms: number; optimized_ttft_ms: number; privacy_compliant: boolean; violations_resolved: number;
  node_plan: AutopilotNodePlanItem[]; simulation_sha256: string; created_at: string;
}
export interface ValidateCyclicKflowRequest { workspace_id?: string; workflow_id?: string; nodes?: CyclicNodeSpec[]; loop_edges?: CyclicLoopEdgeSpec[]; }
export interface ExecuteCyclicKflowRequest { workspace_id?: string; workflow_id?: string; nodes?: CyclicNodeSpec[]; loop_edges?: CyclicLoopEdgeSpec[]; max_iterations_override?: number; critic_threshold?: number; fan_out_shards?: number; simulate_timeout?: boolean; initial_state?: Record<string, unknown>; approved_node_ids?: string[]; }
export interface SimulateKflowAutopilotRequest { workspace_id?: string; workflow_id?: string; nodes?: CyclicNodeSpec[]; loop_edges?: CyclicLoopEdgeSpec[]; budget_cap_usd?: number; privacy_policy?: AutopilotPrivacyPolicy; expected_loop_multiplier?: number; }

export class PlatformCyclicHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) { super(message); this.name = "PlatformCyclicHttpError"; this.status = status; }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const DLP_SECRET_RE = /sk-[A-Za-z0-9_-]{12,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{16,}|BEGIN [A-Z ]*PRIVATE KEY/;
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
export const canRbacRunCyclicKflow = (role: WorkspaceRbacRole): boolean => role !== "viewer";
const computeCyclicSha256 = (seed: string): string => [1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`cyc:${i}:${seed}`)).join("");
const isOpenCoreModel = (m: string): boolean => /^(keelway-|qwen|llama)/i.test(m.trim());
const skipTestFetch = (): boolean =>
  import.meta.env.MODE === "test" &&
  (typeof globalThis.fetch !== "function" || (!("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN));

export const DEFAULT_CYCLIC_NODES: ReadonlyArray<CyclicNodeSpec> = [
  { id: "draft_patch", agent_id: "code-synthesizer", model: "claude-3-7-sonnet", depends_on: [], fan_out_items: 3, timeout_ms: 4000, compensation_handler: "revert_worktree", base_cost_usd: 0.045, ttft_ms: 340, requires_p10: false },
  { id: "critic_verify", agent_id: "critic-verifier", model: "gpt-4.1", depends_on: ["draft_patch"], fan_out_items: 1, timeout_ms: 3000, compensation_handler: "discard_candidate", base_cost_usd: 0.035, ttft_ms: 290, requires_p10: false },
  { id: "publish_release", agent_id: "release-guard", model: "keelway-core:7b", depends_on: ["critic_verify"], fan_out_items: 1, timeout_ms: 2500, compensation_handler: "rollback_tag", base_cost_usd: 0, ttft_ms: 135, requires_p10: false },
];

export const DEFAULT_CYCLIC_LOOP_EDGES: ReadonlyArray<CyclicLoopEdgeSpec> = [
  { from_node: "critic_verify", to_node: "draft_patch", condition: "critic_score_lt", threshold: 0.85, max_iterations: 3 },
];

const runsByWs = new Map<string, CyclicKflowRunRecord[]>();
const simsByWs = new Map<string, AutopilotSimulationRecord[]>();
let fallbackSeq = 0;
export function resetCyclicFallbackStore(): void { runsByWs.clear(); simsByWs.clear(); fallbackSeq = 0; }

async function apiRequest(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: WorkspaceRbacRole): Promise<{ ok: boolean; status: number; data: unknown }> {
  if (!path.startsWith("/v1/platform/kflow")) throw new Error(`Security violation: /v1/platform/kflow/* required, got ${path}`);
  const search = new URLSearchParams();
  if (query) for (const [k, v] of Object.entries(query)) if (v !== undefined) search.set(k, v);
  const token = getStudioToken();
  if (token) search.set("token", token);
  const url = search.toString() ? `${path}?${search.toString()}` : path;
  if (skipTestFetch()) return { ok: false, status: 0, data: null };
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (role) headers.set("X-Keelway-Role", role);
  if (token) { headers.set("Authorization", `Bearer ${token}`); headers.set("X-Studio-Token", token); headers.set("X-Keelway-Token", token); }
  let res: Response;
  try { res = await fetch(url, { ...init, credentials: "same-origin", headers }); } catch { return { ok: false, status: 0, data: null }; }
  const text = await res.text().catch(() => "");
  let data: unknown = null;
  if (text) { try { data = JSON.parse(text) as unknown; } catch { data = null; } }
  if (!res.ok && res.status >= 400) {
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string" ? String(data.detail ?? data.error ?? data.message) : `Cyclic KFlow request failed with HTTP ${res.status}.`;
    throw new PlatformCyclicHttpError(res.status, detail);
  }
  return { ok: res.ok, status: res.status, data };
}

function assertRunRbac(role: WorkspaceRbacRole): void {
  if (!canRbacRunCyclicKflow(role)) throw new PlatformCyclicHttpError(403, "RBAC Denied (viewer): Viewer role cannot execute cyclic KFlow runs or autopilot simulations.");
}

function validateBoundsOrThrow(nodes: ReadonlyArray<CyclicNodeSpec>, edges: ReadonlyArray<CyclicLoopEdgeSpec>, maxIterOverride?: number, shards?: number, threshold?: number, initialState?: Record<string, unknown>): void {
  if (initialState && DLP_SECRET_RE.test(JSON.stringify(initialState))) throw new PlatformCyclicHttpError(422, "DLP policy violation: raw secret token detected in initial_state; execution rejected before SQLite persistence.");
  if (maxIterOverride !== undefined && (!Number.isFinite(maxIterOverride) || maxIterOverride < 1 || maxIterOverride > 10)) throw new PlatformCyclicHttpError(422, "max_iterations_override must be between 1 and 10.");
  if (shards !== undefined && (!Number.isFinite(shards) || shards < 1 || shards > 16)) throw new PlatformCyclicHttpError(422, "fan_out_shards must be between 1 and 16.");
  if (threshold !== undefined && (!Number.isFinite(threshold) || threshold < 0 || threshold > 1)) throw new PlatformCyclicHttpError(422, "critic_threshold must be between 0.0 and 1.0.");
  for (const n of nodes) if (!Number.isFinite(n.fan_out_items) || n.fan_out_items < 1 || n.fan_out_items > 16) throw new PlatformCyclicHttpError(422, `Node '${n.id}' fan_out_items must be between 1 and 16.`);
  for (const e of edges) {
    if (!Number.isFinite(e.max_iterations) || e.max_iterations < 1 || e.max_iterations > 10) throw new PlatformCyclicHttpError(422, "loop_edge max_iterations must be between 1 and 10.");
    if (!Number.isFinite(e.threshold) || e.threshold < 0 || e.threshold > 1) throw new PlatformCyclicHttpError(422, "loop_edge threshold must be between 0.0 and 1.0.");
  }
}

function resolvePolicyRewriteReason(policy: AutopilotPrivacyPolicy): string | null {
  switch (policy) {
    case "airgap_strict": return "airgap_strict: zero-egress OpenCore enforcement";
    case "eu_residency": return "eu_residency: sovereign local checkpoint";
    case "hybrid_balanced": return null;
    default: { const _exhaustive: never = policy; return _exhaustive; }
  }
}

export async function validateCyclicKflow(req: ValidateCyclicKflowRequest = {}, role: WorkspaceRbacRole = "owner"): Promise<CyclicValidationResult> {
  const ws = req.workspace_id ?? "default";
  const wf = req.workflow_id ?? "WF-CYCLIC-01";
  const res = await apiRequest("/v1/platform/kflow/cyclic/validate", { method: "POST", body: JSON.stringify({ ...req, workspace_id: ws, workflow_id: wf }) }, undefined, role);
  if (res.ok && isRecord(res.data) && typeof res.data.spec_sha256 === "string") return res.data as unknown as CyclicValidationResult;
  const nodes = req.nodes ?? DEFAULT_CYCLIC_NODES.map((n) => ({ ...n, depends_on: [...n.depends_on] }));
  const edges = req.loop_edges ?? DEFAULT_CYCLIC_LOOP_EDGES.map((e) => ({ ...e }));
  validateBoundsOrThrow(nodes, edges);
  const loopMax = edges[0]?.max_iterations ?? 1;
  return {
    workspace_id: ws, workflow_id: wf, valid: true, node_count: nodes.length, loop_edge_count: edges.length,
    max_worst_case_steps: Math.max(nodes.length, (nodes.length - 1) * loopMax + 1),
    topological_spine: nodes.map((n) => n.id), compensation_handlers: nodes.map((n) => n.compensation_handler),
    spec_sha256: computeCyclicSha256(`val:${ws}:${wf}:${JSON.stringify(nodes)}:${JSON.stringify(edges)}`),
  };
}

export async function executeCyclicKflow(req: ExecuteCyclicKflowRequest = {}, role: WorkspaceRbacRole = "owner"): Promise<CyclicKflowRunRecord> {
  const ws = req.workspace_id ?? "default";
  const wf = req.workflow_id ?? "WF-CYCLIC-01";
  const res = await apiRequest("/v1/platform/kflow/cyclic/execute", { method: "POST", body: JSON.stringify({ ...req, workspace_id: ws, workflow_id: wf }) }, undefined, role);
  if (res.ok && isRecord(res.data) && typeof res.data.run_id === "string") return res.data as unknown as CyclicKflowRunRecord;
  assertRunRbac(role);
  const nodes = req.nodes ?? DEFAULT_CYCLIC_NODES.map((n) => ({ ...n, depends_on: [...n.depends_on] }));
  const edges = req.loop_edges ?? DEFAULT_CYCLIC_LOOP_EDGES.map((e) => ({ ...e }));
  validateBoundsOrThrow(nodes, edges, req.max_iterations_override, req.fan_out_shards, req.critic_threshold, req.initial_state);
  const maxIter = req.max_iterations_override ?? edges[0]?.max_iterations ?? 3;
  const thr = req.critic_threshold ?? edges[0]?.threshold ?? 0.85;
  const shards = req.fan_out_shards ?? Math.max(...nodes.map((n) => n.fan_out_items));
  const approved = new Set(req.approved_node_ids ?? []);
  const unapprovedP10 = nodes.find((n) => n.requires_p10 && !approved.has(n.id));
  const trace: CyclicIterationTraceItem[] = [];
  let compLog: CyclicCompensationItem[] = [];
  let status: CyclicRunStatus = "CONVERGED";
  let converged = false;
  let finalScore = 0;
  let iterExec = 0;
  if (unapprovedP10) {
    status = "HELD_P10";
  } else if (req.simulate_timeout) {
    iterExec = 1;
    const visited = nodes.slice(0, Math.min(nodes.length, 2));
    visited.forEach((n, idx) => {
      const last = idx === visited.length - 1;
      trace.push({ iteration: 1, node_id: n.id, agent_id: n.agent_id, model: n.model, critic_score: 0, shard_count: n.fan_out_items > 1 ? shards : n.fan_out_items, status: last ? "TIMED_OUT" : "COMPLETED", cost_usd: isOpenCoreModel(n.model) ? 0 : n.base_cost_usd, latency_ms: last ? n.timeout_ms : n.ttft_ms });
    });
    compLog = [...visited].reverse().map((n) => ({ node_id: n.id, handler: n.compensation_handler, reason: "timeout_exceeded", status: "ROLLED_BACK" }));
    status = "COMPENSATED";
  } else {
    const loopNodes = nodes.slice(0, Math.max(1, nodes.length - 1));
    const postNodes = nodes.slice(Math.max(1, nodes.length - 1));
    for (let i = 1; i <= maxIter; i += 1) {
      iterExec = i;
      finalScore = Number(Math.min(0.96, 0.58 + 0.16 * i).toFixed(4));
      for (const n of loopNodes) {
        const sh = n.fan_out_items > 1 || n.id === loopNodes[0]?.id ? shards : n.fan_out_items;
        const unitCost = isOpenCoreModel(n.model) ? 0 : n.base_cost_usd;
        trace.push({ iteration: i, node_id: n.id, agent_id: n.agent_id, model: n.model, critic_score: finalScore, shard_count: sh, status: "COMPLETED", cost_usd: Number(((unitCost * sh) / Math.max(1, n.fan_out_items)).toFixed(6)), latency_ms: n.ttft_ms + Math.max(0, sh - 1) * 20 });
      }
      if (edges.length === 0 || finalScore >= thr) { converged = true; break; }
    }
    if (converged) {
      for (const n of postNodes) trace.push({ iteration: iterExec, node_id: n.id, agent_id: n.agent_id, model: n.model, critic_score: finalScore, shard_count: n.fan_out_items, status: "COMPLETED", cost_usd: isOpenCoreModel(n.model) ? 0 : n.base_cost_usd, latency_ms: n.ttft_ms });
      status = "CONVERGED";
    } else {
      compLog = [...loopNodes].reverse().map((n) => ({ node_id: n.id, handler: n.compensation_handler, reason: "max_iterations_exhausted", status: "ROLLED_BACK" }));
      status = "COMPENSATED";
    }
  }
  fallbackSeq += 1;
  const runId = `cyc-${computeLocalFingerprintHex(`${ws}:${wf}:${fallbackSeq}`).slice(0, 12)}`;
  const record: CyclicKflowRunRecord = {
    run_id: runId, workspace_id: ws, workflow_id: wf, status, iterations_executed: iterExec, max_iterations: maxIter,
    converged, final_critic_score: finalScore, critic_threshold: thr, fan_out_shards: shards,
    total_cost_usd: Number(trace.reduce((s, t) => s + t.cost_usd, 0).toFixed(6)),
    total_latency_ms: trace.reduce((s, t) => s + t.latency_ms, 0),
    iteration_trace: trace, compensation_log: compLog, held_node_id: unapprovedP10?.id ?? null,
    run_sha256: computeCyclicSha256(`${runId}:${status}:${iterExec}:${finalScore}:${JSON.stringify(trace)}:${JSON.stringify(compLog)}`),
    created_at: new Date().toISOString(),
  };
  runsByWs.set(ws, [record, ...(runsByWs.get(ws) ?? [])]);
  return record;
}

export async function listCyclicKflowRuns(workspaceId = "default", workflowId?: string, role: WorkspaceRbacRole = "owner"): Promise<CyclicKflowRunRecord[]> {
  const res = await apiRequest("/v1/platform/kflow/cyclic/runs", { method: "GET" }, { workspace_id: workspaceId, workflow_id: workflowId }, role);
  const list = Array.isArray(res.data) ? res.data : isRecord(res.data) && Array.isArray(res.data.runs) ? res.data.runs : null;
  if (res.ok && list) return list as CyclicKflowRunRecord[];
  const stored = runsByWs.get(workspaceId) ?? [];
  return workflowId ? stored.filter((r) => r.workflow_id === workflowId) : [...stored];
}

export async function simulateKflowAutopilot(req: SimulateKflowAutopilotRequest = {}, role: WorkspaceRbacRole = "owner"): Promise<AutopilotSimulationRecord> {
  const ws = req.workspace_id ?? "default";
  const wf = req.workflow_id ?? "WF-CYCLIC-01";
  const policy: AutopilotPrivacyPolicy = req.privacy_policy ?? "hybrid_balanced";
  const cap = req.budget_cap_usd ?? 0.15;
  const res = await apiRequest("/v1/platform/kflow/autopilot/simulate", { method: "POST", body: JSON.stringify({ ...req, workspace_id: ws, workflow_id: wf, privacy_policy: policy, budget_cap_usd: cap }) }, undefined, role);
  if (res.ok && isRecord(res.data) && typeof res.data.simulation_id === "string") return res.data as unknown as AutopilotSimulationRecord;
  assertRunRbac(role);
  if (!Number.isFinite(cap) || cap < 0) throw new PlatformCyclicHttpError(422, "budget_cap_usd must be >= 0.0.");
  const nodes = req.nodes ?? DEFAULT_CYCLIC_NODES.map((n) => ({ ...n, depends_on: [...n.depends_on] }));
  const edges = req.loop_edges ?? DEFAULT_CYCLIC_LOOP_EDGES.map((e) => ({ ...e }));
  validateBoundsOrThrow(nodes, edges);
  const mult = Math.max(2, req.expected_loop_multiplier ?? 2);
  const policyReason = resolvePolicyRewriteReason(policy);
  const drafts = nodes.map((n) => {
    const local = isOpenCoreModel(n.model);
    const rewritten = !local && policyReason !== null;
    const target = /(code|synth|patch|draft)/i.test(`${n.id} ${n.agent_id}`) ? "qwen2.5-coder:7b" : "keelway-core:7b";
    return { node: n, local, origCost: local ? 0 : n.base_cost_usd, rewritten, selected: rewritten ? target : n.model, reason: rewritten ? policyReason : "retained: within policy and P95 budget envelope" };
  });
  let violations = drafts.filter((d) => d.rewritten).length;
  const calcP95 = () => Number(drafts.reduce((s, d) => s + (d.rewritten ? 0 : d.origCost) * mult, 0).toFixed(6));
  for (const cand of [...drafts].filter((d) => !d.local && !d.rewritten).sort((a, b) => b.origCost - a.origCost)) {
    if (calcP95() <= cap) break;
    cand.rewritten = true;
    cand.selected = /(code|synth|patch|draft)/i.test(`${cand.node.id} ${cand.node.agent_id}`) ? "qwen2.5-coder:7b" : "keelway-core:7b";
    cand.reason = "budget_cap_usd: P95 spend autopilot fallback";
    violations += 1;
  }
  const baseP50 = Number(drafts.reduce((s, d) => s + d.origCost, 0).toFixed(6));
  const baseP95 = Number((baseP50 * mult).toFixed(6));
  const baseTtft = drafts.reduce((s, d) => s + d.node.ttft_ms, 0);
  const nodePlan: AutopilotNodePlanItem[] = drafts.map((d) => ({
    node_id: d.node.id, original_model: d.node.model, selected_model: d.selected, rewritten: d.rewritten, reason: d.reason,
    p50_cost_usd: d.rewritten ? 0 : d.origCost, p95_cost_usd: d.rewritten ? 0 : Number((d.origCost * mult).toFixed(6)),
    data_boundary: d.local || d.rewritten ? "local_metal_zero_egress" : "frontier_cloud",
  }));
  const optP50 = Number(nodePlan.reduce((s, p) => s + p.p50_cost_usd, 0).toFixed(6));
  const optP95 = Number(nodePlan.reduce((s, p) => s + p.p95_cost_usd, 0).toFixed(6));
  fallbackSeq += 1;
  const simId = `apsim-${computeLocalFingerprintHex(`${ws}:${wf}:${policy}:${fallbackSeq}`).slice(0, 12)}`;
  const sim: AutopilotSimulationRecord = {
    simulation_id: simId, workspace_id: ws, workflow_id: wf, privacy_policy: policy, budget_cap_usd: cap,
    baseline_p50_usd: baseP50, baseline_p95_usd: baseP95, optimized_p50_usd: optP50, optimized_p95_usd: optP95,
    savings_pct: baseP95 > 0 ? Number((((baseP95 - optP95) / baseP95) * 100).toFixed(2)) : 0,
    baseline_ttft_ms: baseTtft, optimized_ttft_ms: drafts.reduce((s, d) => s + (d.rewritten ? 135 : d.node.ttft_ms), 0),
    privacy_compliant: true, violations_resolved: violations, node_plan: nodePlan,
    simulation_sha256: computeCyclicSha256(`${simId}:${policy}:${cap}:${optP95}:${JSON.stringify(nodePlan)}`),
    created_at: new Date().toISOString(),
  };
  simsByWs.set(ws, [sim, ...(simsByWs.get(ws) ?? [])]);
  return sim;
}

export async function listKflowAutopilotSimulations(workspaceId = "default", workflowId?: string, role: WorkspaceRbacRole = "owner"): Promise<AutopilotSimulationRecord[]> {
  const res = await apiRequest("/v1/platform/kflow/autopilot/simulations", { method: "GET" }, { workspace_id: workspaceId, workflow_id: workflowId }, role);
  const list = Array.isArray(res.data) ? res.data : isRecord(res.data) && Array.isArray(res.data.simulations) ? res.data.simulations : null;
  if (res.ok && list) return list as AutopilotSimulationRecord[];
  const stored = simsByWs.get(workspaceId) ?? [];
  return workflowId ? stored.filter((s) => s.workflow_id === workflowId) : [...stored];
}
