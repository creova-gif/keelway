import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type WorkspaceRbacRole = RbacRoleId;
export type DebuggerConditionType = "always" | "cost_usd_gt" | "hybrid_score_lt" | "before_shell_tool" | "before_p10_gate" | "line_match";
export type DebuggerStepAction = "step_over" | "step_into" | "continue" | "mutate_state";
export type DebuggerSessionStatus = "READY" | "PAUSED" | "COMPLETED";

export interface DebuggerBreakpoint {
  breakpoint_id: string; workspace_id: string; condition_type: DebuggerConditionType;
  threshold: number; line_pattern?: string; label: string; enabled: boolean; created_at: string;
}
export interface DebuggerStepFrame {
  step_index: number; node_id: string; agent_id: string; tool_name: string;
  cost_usd: number; hybrid_score: number; requires_p10: boolean; source_line: string;
}
export interface DebuggerCallStackEntry { frame_index: number; node_id: string; agent_id: string; tool_name: string; depth: number; }
export interface DebuggerSession {
  session_id: string; workspace_id: string; workflow_id: string; status: DebuggerSessionStatus;
  current_step_index: number; total_steps: number; step_depth: number; hit_reason: string | null;
  active_frame: DebuggerStepFrame; call_stack: DebuggerCallStackEntry[];
  variables: Record<string, unknown>; mutation_count: number; frame_sha256: string; steps: DebuggerStepFrame[];
}
export interface DebuggerCodeLensItem {
  symbol: string; file_path: string; line: number; model_checkpoint: string;
  p50_latency_ms: number; avg_cost_usd: number; provenance_4d: string; cursor_attach_uri: string; vscode_attach_uri: string;
}
export interface DebuggerCodeLensResponse { workspace_id: string; lenses: DebuggerCodeLensItem[]; cursor_attach_uri: string; vscode_attach_uri: string; }
export interface SetDebuggerBreakpointRequest { workspace_id?: string; condition_type: DebuggerConditionType; threshold?: number; line_pattern?: string; label?: string; enabled?: boolean; }
export interface StartDebuggerSessionRequest { workspace_id?: string; workflow_id?: string; initial_variables?: Record<string, unknown>; }
export interface StepDebuggerSessionRequest { workspace_id?: string; action: DebuggerStepAction; state_patch?: Record<string, unknown>; }

export class PlatformDebuggerHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) { super(message); this.name = "PlatformDebuggerHttpError"; this.status = status; }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const DLP_STATE_PATCH_RE = /sk-[A-Za-z0-9_-]{12,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{16,}|BEGIN [A-Z ]*PRIVATE KEY/;
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
export const canRbacMutateDebugger = (role: WorkspaceRbacRole): boolean => role !== "viewer";
const computeFrameSha256 = (seed: string): string => [1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`dbg:${i}:${seed}`)).join("");
const skipTestFetch = (): boolean => import.meta.env.MODE === "test" && (typeof globalThis.fetch !== "function" || (!("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN));

async function apiRequest(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: WorkspaceRbacRole): Promise<{ ok: boolean; status: number; data: unknown }> {
  if (!path.startsWith("/v1/platform/debugger")) throw new Error(`Security violation: /v1/platform/debugger/* required, got ${path}`);
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
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string" ? String(data.detail ?? data.error ?? data.message) : `Debugger request failed with HTTP ${res.status}.`;
    throw new PlatformDebuggerHttpError(res.status, detail);
  }
  return { ok: res.ok, status: res.status, data };
}

const DEFAULT_STEPS: ReadonlyArray<DebuggerStepFrame> = [
  { step_index: 0, node_id: "triage_claim", agent_id: "issue-triager", tool_name: "read_claim", cost_usd: 0.04, hybrid_score: 0.94, requires_p10: false, source_line: "core/claims/workflow.py:18" },
  { step_index: 1, node_id: "verify_ledger", agent_id: "finops-auditor", tool_name: "shell_exec", cost_usd: 0.31, hybrid_score: 0.72, requires_p10: false, source_line: "core/billing/ledger.py:42" },
  { step_index: 2, node_id: "approve_payout", agent_id: "security-auditor", tool_name: "p10_settlement", cost_usd: 0.09, hybrid_score: 0.91, requires_p10: true, source_line: "core/security/p10_gate.py:67" },
];

const breakpointsByWs = new Map<string, DebuggerBreakpoint[]>();
const sessionsByWs = new Map<string, DebuggerSession[]>();
let fallbackSeq = 0;
export function resetDebuggerFallbackStore(): void { breakpointsByWs.clear(); sessionsByWs.clear(); fallbackSeq = 0; }

export function formatBreakpointLabel(cond: DebuggerConditionType, threshold: number, pattern?: string): string {
  switch (cond) {
    case "always": return "Pause on every step";
    case "cost_usd_gt": return `Pause when step spend > $${threshold.toFixed(2)}`;
    case "hybrid_score_lt": return `Pause when hybrid score < ${threshold.toFixed(2)}`;
    case "before_shell_tool": return "Pause before shell_exec tool";
    case "before_p10_gate": return "Pause before P-10 human gate";
    case "line_match": return `Pause on line matching "${pattern || "ledger"}"`;
    default: { const _exhaustive: never = cond; return _exhaustive; }
  }
}

function matchBreakpoint(step: DebuggerStepFrame, bp: DebuggerBreakpoint): string | null {
  if (!bp.enabled) return null;
  switch (bp.condition_type) {
    case "always": return "always (step boundary)";
    case "cost_usd_gt": return step.cost_usd > bp.threshold ? `cost_usd_gt (${step.cost_usd.toFixed(2)} > ${bp.threshold.toFixed(2)})` : null;
    case "hybrid_score_lt": return step.hybrid_score < bp.threshold ? `hybrid_score_lt (${step.hybrid_score.toFixed(2)} < ${bp.threshold.toFixed(2)})` : null;
    case "before_shell_tool": return step.tool_name.includes("shell") ? `before_shell_tool (${step.tool_name})` : null;
    case "before_p10_gate": return step.requires_p10 ? `before_p10_gate (${step.node_id})` : null;
    case "line_match": { const needle = bp.line_pattern || "ledger"; return step.source_line.includes(needle) || step.node_id.includes(needle) ? `line_match (${needle})` : null; }
    default: { const _exhaustive: never = bp.condition_type; return _exhaustive; }
  }
}

function getOrSeedBreakpoints(ws: string): DebuggerBreakpoint[] {
  const existing = breakpointsByWs.get(ws);
  if (existing) return existing;
  const seeded: DebuggerBreakpoint[] = [{ breakpoint_id: `bp-seed-${ws}`, workspace_id: ws, condition_type: "cost_usd_gt", threshold: 0.25, label: "Pause when step spend > $0.25", enabled: true, created_at: "2026-11-15T00:00:00.000Z" }];
  breakpointsByWs.set(ws, seeded);
  return seeded;
}

function buildCallStack(steps: ReadonlyArray<DebuggerStepFrame>, idx: number, depth: number): DebuggerCallStackEntry[] {
  const active = steps[idx] ?? DEFAULT_STEPS[0]!;
  const stack: DebuggerCallStackEntry[] = [{ frame_index: idx, node_id: active.node_id, agent_id: active.agent_id, tool_name: active.tool_name, depth: 0 }];
  for (let d = 1; d <= depth; d += 1) stack.unshift({ frame_index: idx, node_id: `${active.node_id}::${active.tool_name}`, agent_id: active.agent_id, tool_name: active.tool_name, depth: d });
  return stack;
}

export function normalizeDebuggerSession(raw: Record<string, unknown>, fallbackWs = "default"): DebuggerSession {
  const idx = typeof raw.current_step_index === "number" ? raw.current_step_index : 0;
  const depth = typeof raw.step_depth === "number" ? raw.step_depth : 0;
  const s = isRecord(raw.active_frame) ? raw.active_frame : isRecord(raw.active_step) ? raw.active_step : {};
  const activeFrame: DebuggerStepFrame = {
    step_index: typeof s.step_index === "number" ? s.step_index : idx, node_id: String(s.node_id ?? "step_1"),
    agent_id: String(s.agent_id ?? "governed-agent"), tool_name: String(s.tool_name ?? "step"),
    cost_usd: typeof s.cost_usd === "number" ? s.cost_usd : 0, hybrid_score: typeof s.hybrid_score === "number" ? s.hybrid_score : 1,
    requires_p10: Boolean(s.requires_p10), source_line: typeof s.source_line === "string" ? s.source_line : `workflows/refund_agent.py:${typeof s.line_number === "number" ? s.line_number : 1}`,
  };
  const rawStack = Array.isArray(raw.call_stack) ? raw.call_stack.filter(isRecord) : [];
  const callStack: DebuggerCallStackEntry[] = rawStack.length > 0
    ? rawStack.map((e) => ({ frame_index: typeof e.frame_index === "number" ? e.frame_index : idx, node_id: String(e.node_id ?? activeFrame.node_id), agent_id: String(e.agent_id ?? activeFrame.agent_id), tool_name: String(e.tool_name ?? activeFrame.tool_name ?? "step"), depth: typeof e.depth === "number" ? e.depth : 0 }))
    : buildCallStack([activeFrame], 0, depth);
  const status: DebuggerSessionStatus = raw.status === "COMPLETED" ? "COMPLETED" : raw.status === "READY" ? "READY" : "PAUSED";
  const sid = String(raw.session_id ?? `dbg-${fallbackWs}`);
  return {
    session_id: sid, workspace_id: String(raw.workspace_id ?? fallbackWs), workflow_id: String(raw.workflow_id ?? "WF-STUDIO-01"),
    status, current_step_index: idx, total_steps: typeof raw.total_steps === "number" ? raw.total_steps : Math.max(idx + 1, 3), step_depth: depth,
    hit_reason: typeof raw.hit_reason === "string" ? raw.hit_reason : null, active_frame: activeFrame, call_stack: callStack,
    variables: isRecord(raw.variables) ? raw.variables : {}, mutation_count: typeof raw.mutation_count === "number" ? raw.mutation_count : 0,
    frame_sha256: typeof raw.frame_sha256 === "string" ? raw.frame_sha256 : computeFrameSha256(`${sid}:${idx}:${depth}`),
    steps: Array.isArray(raw.steps) ? (raw.steps as DebuggerStepFrame[]) : DEFAULT_STEPS.map((st) => ({ ...st })),
  };
}

export function normalizeCodeLensResponse(raw: Record<string, unknown>, fallbackWs = "default"): DebuggerCodeLensResponse {
  const ws = String(raw.workspace_id ?? fallbackWs);
  const bridge = isRecord(raw.bridge) ? raw.bridge : {};
  const cursorUri = String(raw.cursor_attach_uri ?? bridge.cursor_attach_uri ?? `cursor://keelway.vscode-keelway/attach?workspace=${encodeURIComponent(ws)}&port=7420`);
  const vscodeUri = String(raw.vscode_attach_uri ?? bridge.vscode_attach_uri ?? `vscode://keelway.vscode-keelway/attach?workspace=${encodeURIComponent(ws)}&port=7420`);
  const rootFile = typeof raw.file_path === "string" ? raw.file_path : "workflows/refund_agent.py";
  const rawLenses = Array.isArray(raw.lenses) ? raw.lenses.filter(isRecord) : [];
  return {
    workspace_id: ws, cursor_attach_uri: cursorUri, vscode_attach_uri: vscodeUri,
    lenses: rawLenses.map((l) => {
      const sym = String(l.symbol ?? "step");
      return {
        symbol: sym, file_path: String(l.file_path ?? rootFile), line: typeof l.line === "number" ? l.line : typeof l.line_start === "number" ? l.line_start : 1,
        model_checkpoint: String(l.model_checkpoint ?? "keelway-core:7b"), p50_latency_ms: typeof l.p50_latency_ms === "number" ? l.p50_latency_ms : typeof l.p50_ms === "number" ? l.p50_ms : 120,
        avg_cost_usd: typeof l.avg_cost_usd === "number" ? l.avg_cost_usd : 0, provenance_4d: String(l.provenance_4d ?? ""),
        cursor_attach_uri: String(l.cursor_attach_uri ?? `${cursorUri}&symbol=${encodeURIComponent(sym)}`), vscode_attach_uri: String(l.vscode_attach_uri ?? `${vscodeUri}&symbol=${encodeURIComponent(sym)}`),
      };
    }),
  };
}

const evaluateStepHit = (step: DebuggerStepFrame, bps: ReadonlyArray<DebuggerBreakpoint>): string | null => {
  const hits = bps.map((bp) => matchBreakpoint(step, bp)).filter((r): r is string => r !== null);
  return hits.length > 0 ? hits.join(" · ") : null;
};
const assertMutateRbac = (role: WorkspaceRbacRole): void => {
  if (!canRbacMutateDebugger(role)) throw new PlatformDebuggerHttpError(403, "RBAC Denied (viewer): Viewer role cannot mutate debugger breakpoints or sessions.");
};

export async function setDebuggerBreakpoint(req: SetDebuggerBreakpointRequest, role: WorkspaceRbacRole = "owner"): Promise<DebuggerBreakpoint> {
  const ws = req.workspace_id ?? "default";
  const threshold = req.threshold ?? 0.25;
  const label = req.label?.trim() || formatBreakpointLabel(req.condition_type, threshold, req.line_pattern);
  const res = await apiRequest("/v1/platform/debugger/breakpoints", { method: "POST", body: JSON.stringify({ ...req, workspace_id: ws, threshold, label }) }, undefined, role);
  const raw = isRecord(res.data) && isRecord(res.data.breakpoint) ? res.data.breakpoint : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && typeof raw.breakpoint_id === "string") return { ...raw, threshold: typeof raw.threshold === "number" ? raw.threshold : threshold } as DebuggerBreakpoint;
  assertMutateRbac(role);
  fallbackSeq += 1;
  const bp: DebuggerBreakpoint = { breakpoint_id: `bp-${computeLocalFingerprintHex(`${ws}:${req.condition_type}:${fallbackSeq}`).slice(0, 8)}`, workspace_id: ws, condition_type: req.condition_type, threshold, line_pattern: req.line_pattern, label, enabled: req.enabled ?? true, created_at: new Date().toISOString() };
  breakpointsByWs.set(ws, [...getOrSeedBreakpoints(ws), bp]);
  return bp;
}

export async function listDebuggerBreakpoints(workspaceId = "default", role: WorkspaceRbacRole = "owner"): Promise<DebuggerBreakpoint[]> {
  const res = await apiRequest("/v1/platform/debugger/breakpoints", { method: "GET" }, { workspace_id: workspaceId }, role);
  const list = Array.isArray(res.data) ? res.data : isRecord(res.data) && Array.isArray(res.data.breakpoints) ? res.data.breakpoints : null;
  return res.ok && list ? (list as DebuggerBreakpoint[]) : [...getOrSeedBreakpoints(workspaceId)];
}

export async function deleteDebuggerBreakpoint(breakpointId: string, workspaceId = "default", role: WorkspaceRbacRole = "owner"): Promise<{ deleted: boolean; breakpoint_id: string }> {
  const res = await apiRequest(`/v1/platform/debugger/breakpoints/${encodeURIComponent(breakpointId)}`, { method: "DELETE" }, { workspace_id: workspaceId }, role);
  if (res.ok && isRecord(res.data) && typeof res.data.deleted === "boolean") return { deleted: res.data.deleted, breakpoint_id: breakpointId };
  assertMutateRbac(role);
  breakpointsByWs.set(workspaceId, getOrSeedBreakpoints(workspaceId).filter((b) => b.breakpoint_id !== breakpointId));
  return { deleted: true, breakpoint_id: breakpointId };
}

export async function startDebuggerSession(req: StartDebuggerSessionRequest = {}, role: WorkspaceRbacRole = "owner"): Promise<DebuggerSession> {
  const ws = req.workspace_id ?? "default";
  const wf = req.workflow_id ?? "WF-STUDIO-01";
  const res = await apiRequest("/v1/platform/debugger/sessions", { method: "POST", body: JSON.stringify({ workspace_id: ws, workflow_id: wf, initial_state: req.initial_variables, initial_variables: req.initial_variables }) }, undefined, role);
  const raw = isRecord(res.data) && isRecord(res.data.session) ? res.data.session : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && typeof raw.session_id === "string") return normalizeDebuggerSession(raw, ws);
  assertMutateRbac(role);
  fallbackSeq += 1;
  const steps = DEFAULT_STEPS.map((s) => ({ ...s }));
  const bps = getOrSeedBreakpoints(ws);
  const hitIdx = steps.findIndex((st) => evaluateStepHit(st, bps) !== null);
  const pausedIdx = hitIdx >= 0 ? hitIdx : steps.length - 1;
  const hitReason = hitIdx >= 0 ? evaluateStepHit(steps[hitIdx]!, bps) : null;
  const status: DebuggerSessionStatus = hitReason ? "PAUSED" : "COMPLETED";
  const vars: Record<string, unknown> = { route_mode: "hybrid_4d", claim_amount_usd: 1420, ...(req.initial_variables ?? {}) };
  const sid = `dbg-${computeLocalFingerprintHex(`${ws}:${wf}:${fallbackSeq}`).slice(0, 10)}`;
  const session: DebuggerSession = { session_id: sid, workspace_id: ws, workflow_id: wf, status, current_step_index: pausedIdx, total_steps: steps.length, step_depth: 0, hit_reason: hitReason, active_frame: steps[pausedIdx]!, call_stack: buildCallStack(steps, pausedIdx, 0), variables: vars, mutation_count: 0, frame_sha256: computeFrameSha256(`${sid}:${pausedIdx}:0:0:${JSON.stringify(vars)}`), steps };
  sessionsByWs.set(ws, [session, ...(sessionsByWs.get(ws) ?? [])]);
  return session;
}

export async function listDebuggerSessions(workspaceId = "default", role: WorkspaceRbacRole = "owner"): Promise<DebuggerSession[]> {
  const res = await apiRequest("/v1/platform/debugger/sessions", { method: "GET" }, { workspace_id: workspaceId }, role);
  const list = Array.isArray(res.data) ? res.data : isRecord(res.data) && Array.isArray(res.data.sessions) ? res.data.sessions : null;
  return res.ok && list ? list.filter(isRecord).map((s) => normalizeDebuggerSession(s, workspaceId)) : [...(sessionsByWs.get(workspaceId) ?? [])];
}

export async function stepDebuggerSession(sessionId: string, req: StepDebuggerSessionRequest, role: WorkspaceRbacRole = "owner"): Promise<DebuggerSession> {
  const ws = req.workspace_id ?? "default";
  const res = await apiRequest(`/v1/platform/debugger/sessions/${encodeURIComponent(sessionId)}/step`, { method: "POST", body: JSON.stringify({ ...req, workspace_id: ws }) }, undefined, role);
  const raw = isRecord(res.data) && isRecord(res.data.session) ? res.data.session : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && typeof raw.session_id === "string") return normalizeDebuggerSession(raw, ws);
  assertMutateRbac(role);
  if (req.state_patch && DLP_STATE_PATCH_RE.test(JSON.stringify(req.state_patch))) throw new PlatformDebuggerHttpError(422, "DLP Policy Violation: Secret token detected in state_patch; mutation blocked before SQLite persistence.");
  const list = sessionsByWs.get(ws) ?? [];
  const base = list.find((s) => s.session_id === sessionId) ?? (await startDebuggerSession({ workspace_id: ws }, role));
  const bps = getOrSeedBreakpoints(ws);
  let { current_step_index: idx, step_depth: depth, status, hit_reason: reason, mutation_count: muts } = base;
  let vars = { ...base.variables };
  switch (req.action) {
    case "step_into": depth += 1; status = "PAUSED"; reason = `step_into (${base.steps[idx]!.tool_name} @ depth ${depth})`; break;
    case "mutate_state": vars = { ...vars, ...(req.state_patch ?? {}) }; muts += 1; reason = `state_mutated (patch #${muts})`; break;
    case "step_over": depth = 0; if (idx + 1 >= base.steps.length) { status = "COMPLETED"; reason = null; } else { idx += 1; status = "PAUSED"; reason = evaluateStepHit(base.steps[idx]!, bps) ?? `step_over (${base.steps[idx]!.node_id})`; } break;
    case "continue": { depth = 0; const hitIdx = base.steps.findIndex((st, i) => i > idx && evaluateStepHit(st, bps) !== null); if (hitIdx >= 0) { idx = hitIdx; status = "PAUSED"; reason = evaluateStepHit(base.steps[hitIdx]!, bps); } else { idx = base.steps.length - 1; status = "COMPLETED"; reason = null; } break; }
    default: { const _exhaustive: never = req.action; return _exhaustive; }
  }
  const updated: DebuggerSession = { ...base, status, current_step_index: idx, step_depth: depth, hit_reason: reason, active_frame: base.steps[idx]!, call_stack: buildCallStack(base.steps, idx, depth), variables: vars, mutation_count: muts, frame_sha256: computeFrameSha256(`${base.session_id}:${idx}:${depth}:${muts}:${status}:${JSON.stringify(vars)}`) };
  sessionsByWs.set(ws, [updated, ...list.filter((s) => s.session_id !== updated.session_id)]);
  return updated;
}

export async function getDebuggerCodeLens(workspaceId = "default", role: WorkspaceRbacRole = "owner"): Promise<DebuggerCodeLensResponse> {
  const res = await apiRequest("/v1/platform/debugger/codelens", { method: "GET" }, { workspace_id: workspaceId }, role);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.lenses)) return normalizeCodeLensResponse(res.data, workspaceId);
  const cursorUri = `cursor://keelway.vscode-keelway/attach?workspace=${encodeURIComponent(workspaceId)}&port=7420`;
  const vscodeUri = `vscode://keelway.vscode-keelway/attach?workspace=${encodeURIComponent(workspaceId)}&port=7420`;
  return {
    workspace_id: workspaceId, cursor_attach_uri: cursorUri, vscode_attach_uri: vscodeUri,
    lenses: [
      { symbol: "triage_claim", file_path: "core/claims/workflow.py", line: 18, model_checkpoint: "keelway-core:7b", p50_latency_ms: 142, avg_cost_usd: 0.04, provenance_4d: "4D[code:L18 · weight:q4_k_m · wal:seq#101 · policy:local_only]", cursor_attach_uri: `${cursorUri}&symbol=triage_claim`, vscode_attach_uri: `${vscodeUri}&symbol=triage_claim` },
      { symbol: "verify_ledger", file_path: "core/billing/ledger.py", line: 42, model_checkpoint: "keelway-reasoning:14b", p50_latency_ms: 318, avg_cost_usd: 0.31, provenance_4d: "4D[code:L42 · weight:fp16 · wal:seq#102 · policy:seatbelt_shell]", cursor_attach_uri: `${cursorUri}&symbol=verify_ledger`, vscode_attach_uri: `${vscodeUri}&symbol=verify_ledger` },
      { symbol: "approve_payout", file_path: "core/security/p10_gate.py", line: 67, model_checkpoint: "keelway-core:7b", p50_latency_ms: 96, avg_cost_usd: 0.09, provenance_4d: "4D[code:L67 · weight:q4_k_m · wal:seq#103 · policy:p10_human_gate]", cursor_attach_uri: `${cursorUri}&symbol=approve_payout`, vscode_attach_uri: `${vscodeUri}&symbol=approve_payout` },
    ],
  };
}
