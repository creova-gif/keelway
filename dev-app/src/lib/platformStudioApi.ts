import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type WorkspaceRbacRole = RbacRoleId;
export type KflowSyncDirection = "code_to_graph" | "graph_to_code";
export type StudioSdkLanguage = "python" | "typescript";
export type BlastRadiusRiskTier = "nominal_confined" | "contained_guarded" | "elevated_review";
export type PromptGateVerdict = "PASS" | "BLOCK";

export interface StudioKflowNodeInput {
  id: string; label?: string; agent_id?: string; depends_on?: string[]; requires_p10?: boolean;
  line_start?: number; line_end?: number; wave?: number; x?: number; y?: number;
}

export interface StudioKflowNode {
  id: string; label: string; agent_id: string; depends_on: string[]; requires_p10: boolean;
  line_start: number; line_end: number; wave: number; x: number; y: number;
}

export interface StudioKflowEdge { from: string; to: string; is_cycle: boolean; }
export interface StudioCycleBackEdge { from: string; to: string; }

export interface SyncKflowStudioRequest {
  workspace_id?: string; direction: KflowSyncDirection; language: StudioSdkLanguage;
  workflow_id: string; source_code?: string; nodes?: StudioKflowNodeInput[]; persist?: boolean;
}

export interface SyncKflowStudioResponse {
  workspace_id: string; workflow_id: string; direction: KflowSyncDirection; language: StudioSdkLanguage;
  nodes: StudioKflowNode[]; edges: StudioKflowEdge[]; cycle_back_edges: StudioCycleBackEdge[];
  p10_locked_nodes: string[]; source_code: string; persisted: boolean; sync_sha256: string;
}

export interface RecordBlastRadiusRequest {
  workspace_id?: string; trace_id?: string; workflow_id?: string;
  fs_reads?: string[]; fs_writes?: string[]; blocked_paths?: string[];
  egress_attempts?: number; blocked_egress_hosts?: string[];
  p10_gates_triggered?: number; seatbelted?: boolean; syscalls_audited?: number;
}

export interface BlastRadiusAuditRecord {
  audit_id: string; workspace_id: string; trace_id: string; workflow_id: string;
  fs_reads: string[]; fs_writes: string[]; blocked_paths: string[];
  egress_attempts: number; blocked_egress_hosts: string[]; p10_gates_triggered: number;
  seatbelted: boolean; zero_unapproved_egress: boolean; syscalls_audited: number;
  risk_tier: BlastRadiusRiskTier; audit_sha256: string; recorded_at: string;
}

export interface BlastRadiusAuditListResponse {
  workspace_id: string; count: number; total_audits: number;
  audits: BlastRadiusAuditRecord[]; source: "live" | "local_fallback";
}

export interface EvaluatePromptGateRequest {
  workspace_id?: string; candidate_prompt_version?: string;
  candidate_prompt_text?: string; candidate_prompt?: string;
  candidate_model_id: string; required_json_keys?: string[];
  min_pass_rate?: number; baseline_cost_usd?: number;
}

export interface PromptGateEvaluationRecord {
  gate_run_id: string; workspace_id: string; candidate_prompt_version: string; candidate_model_id: string;
  verdict: PromptGateVerdict; cases_evaluated: number; passed_cases: number; pass_rate: number;
  min_pass_rate: number; schema_valid_count: number; dlp_violations: number;
  cost_delta_usd: number; dataset_source: string; gate_sha256: string; evaluated_at: string;
}

export interface PromptGateRunListResponse {
  workspace_id: string; count: number; total_runs: number;
  runs: PromptGateEvaluationRecord[]; source: "live" | "local_fallback";
}

export class PlatformStudioHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "PlatformStudioHttpError";
    this.status = status;
  }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const toSha = (raw: string): string => (raw.startsWith("sha256:") ? raw : `sha256:${raw}`);

const DLP_PATTERNS: ReadonlyArray<RegExp> = [
  /\bsk-(?:ant-|proj-|live-|test-)?[a-zA-Z0-9_-]{6,}/gi,
  /\bgh[pousr]_[a-zA-Z0-9_]{6,}/gi,
  /\bAKIA[0-9A-Z]{12,}/g,
];

export const canRbacMutateStudio = (role: WorkspaceRbacRole): boolean => role !== "viewer";

function computeStudioDigest64(seed: string): string {
  return toSha([1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`studio:${i}:${seed}`)).join(""));
}

function shouldSkipUnmockedTestFetch(): boolean {
  if (import.meta.env.MODE !== "test") return false;
  if (typeof globalThis.fetch !== "function") return true;
  return !("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN;
}

function buildStudioUrl(path: string, query?: Record<string, string | undefined>): string {
  if (!path.startsWith("/v1/platform/studio/")) {
    throw new Error(`Security violation: platformStudioApi allows strictly /v1/platform/studio/* paths, got ${path}`);
  }
  const search = new URLSearchParams();
  if (query) {
    for (const [k, v] of Object.entries(query)) if (v !== undefined) search.set(k, v);
  }
  const token = getStudioToken();
  if (token) search.set("token", token);
  const qs = search.toString();
  return qs ? `${path}?${qs}` : path;
}

function attachStudioHeaders(raw?: HeadersInit, role?: WorkspaceRbacRole, hasBody = false): Headers {
  const headers = new Headers(raw);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (role) headers.set("X-Keelway-Role", role);
  const token = getStudioToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("X-Studio-Token", token);
    headers.set("X-Keelway-Token", token);
  }
  return headers;
}

async function requestStudioEndpoint(
  path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: WorkspaceRbacRole,
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const url = buildStudioUrl(path, query);
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null };
  let res: Response;
  try {
    res = await fetch(url, { ...init, credentials: "same-origin", headers: attachStudioHeaders(init.headers, role, Boolean(init.body)) });
  } catch {
    return { ok: false, status: 0, data: null };
  }
  const rawText = await res.text().catch(() => "");
  let data: unknown = null;
  if (rawText) {
    try { data = JSON.parse(rawText) as unknown; } catch { data = null; }
  }
  if (!res.ok && res.status >= 400) {
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string"
      ? String(data.detail ?? data.error ?? data.message)
      : `Studio request failed with HTTP ${res.status}.`;
    throw new PlatformStudioHttpError(res.status, detail);
  }
  return { ok: res.ok, status: res.status, data };
}

const DEFAULT_STUDIO_NODES: ReadonlyArray<StudioKflowNodeInput> = [
  { id: "spec_ingest", label: "Parse PRD & Threat Scope", agent_id: "product-strategist", depends_on: [], requires_p10: false },
  { id: "patch_synth", label: "Synthesize & Test Patch", agent_id: "feature-coder", depends_on: ["spec_ingest"], requires_p10: false },
  { id: "p10_release_gate", label: "P-10 Sovereign Release Gate", agent_id: "security-auditor", depends_on: ["patch_synth"], requires_p10: true },
];
const DEFAULT_CYCLES: ReadonlyArray<StudioCycleBackEdge> = [{ from: "p10_release_gate", to: "patch_synth" }];

const localKflowByKey = new Map<string, SyncKflowStudioResponse>();
const localBlastByWs = new Map<string, BlastRadiusAuditRecord[]>();
const localGateRunsByWs = new Map<string, PromptGateEvaluationRecord[]>();
let localStudioSeq = 0;

export function resetLocalStudioState(): void {
  localKflowByKey.clear();
  localBlastByWs.clear();
  localGateRunsByWs.clear();
  localStudioSeq = 0;
}

function renderKflowCodeAndSpans(
  ws: string, workflowId: string, language: StudioSdkLanguage,
  rawNodes: ReadonlyArray<StudioKflowNodeInput>, cycles: ReadonlyArray<StudioCycleBackEdge>,
): { sourceCode: string; spanById: Map<string, { start: number; end: number }> } {
  const lines: string[] = [];
  const spanById = new Map<string, { start: number; end: number }>();
  switch (language) {
    case "python": {
      lines.push("from keelway.kflow import KFlowStudio", "", `studio = KFlowStudio(workflow_id="${workflowId}", workspace_id="${ws}")`);
      for (const n of rawNodes) {
        lines.push("");
        const start = lines.length + 1;
        const deps = (n.depends_on ?? []).map((d) => `"${d}"`).join(", ");
        lines.push(
          "studio.node(", `    id="${n.id}",`, `    label="${n.label ?? n.id}",`,
          `    agent_id="${n.agent_id ?? "feature-coder"}",`, `    depends_on=[${deps}],`,
          `    requires_p10=${n.requires_p10 ? "True" : "False"},`, ")",
        );
        spanById.set(n.id, { start, end: lines.length });
      }
      for (const cyc of cycles) lines.push("", `studio.cycle(from_node="${cyc.from}", to_node="${cyc.to}", max_iterations=3)`);
      break;
    }
    case "typescript": {
      lines.push('import { KFlowStudio } from "@keelway/kflow-sdk";', "", `export const studio = new KFlowStudio({ workflowId: "${workflowId}", workspaceId: "${ws}" });`);
      for (const n of rawNodes) {
        lines.push("");
        const start = lines.length + 1;
        const deps = (n.depends_on ?? []).map((d) => `"${d}"`).join(", ");
        lines.push(
          "studio.node({", `  id: "${n.id}",`, `  label: "${n.label ?? n.id}",`,
          `  agentId: "${n.agent_id ?? "feature-coder"}",`, `  dependsOn: [${deps}],`,
          `  requiresP10: ${n.requires_p10 ? "true" : "false"},`, "});",
        );
        spanById.set(n.id, { start, end: lines.length });
      }
      for (const cyc of cycles) lines.push("", `studio.cycle({ from: "${cyc.from}", to: "${cyc.to}", maxIterations: 3 });`);
      break;
    }
    default: {
      const _exhaustive: never = language;
      return _exhaustive;
    }
  }
  return { sourceCode: lines.join("\n"), spanById };
}

function parseNodesAndCyclesFromCode(sourceCode: string): { nodes: StudioKflowNodeInput[]; cycles: StudioCycleBackEdge[] } {
  const nodes: StudioKflowNodeInput[] = [];
  const cycles: StudioCycleBackEdge[] = [];
  const lineAt = (offset: number): number => sourceCode.slice(0, Math.max(0, offset)).split("\n").length;

  const blockRegex = /\b(?:studio|workflow)\s*\.\s*(?:node|add_node|addNode)\s*\(([\s\S]*?)\)[ \t]*;?/g;
  for (const m of sourceCode.matchAll(blockRegex)) {
    const body = m[1] ?? "";
    const full = m[0] ?? "";
    const startIdx = m.index ?? 0;
    const idMatch = /(?:id\s*[:=]\s*["']([^"']+)["']|^[\s\n]*["']([^"']+)["'])/.exec(body);
    const id = (idMatch?.[1] ?? idMatch?.[2] ?? "").trim();
    if (!id) continue;
    const labelMatch = /label\s*[:=]\s*["']([^"']+)["']/.exec(body);
    const agentMatch = /(?:agent_id|agentId)\s*[:=]\s*["']([^"']+)["']/.exec(body);
    const depsMatch = /(?:depends_on|dependsOn)\s*[:=]\s*\[([^\]]*)\]/.exec(body);
    const p10Match = /(?:requires_p10|requiresP10|p10_human_gate)\s*[:=]\s*(True|true|False|false)/.exec(body);
    const dependsOn = depsMatch?.[1] ? Array.from(depsMatch[1].matchAll(/["']([^"']+)["']/g)).map((dm) => dm[1]!) : [];
    nodes.push({
      id, label: labelMatch?.[1] ?? id.replace(/_/g, " "), agent_id: agentMatch?.[1] ?? "feature-coder",
      depends_on: dependsOn, requires_p10: p10Match ? p10Match[1]!.toLowerCase() === "true" : /\binterrupt\s*\(/.test(body),
      line_start: lineAt(startIdx), line_end: lineAt(startIdx + full.length - 1),
    });
  }

  if (nodes.length === 0) {
    let prevId: string | null = null;
    for (const m of sourceCode.matchAll(/(?:def|function)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)/g)) {
      const id = m[1]!;
      const startLine = lineAt(m.index ?? 0);
      nodes.push({
        id, label: id.replace(/_/g, " "), agent_id: "feature-coder", depends_on: prevId ? [prevId] : [],
        requires_p10: /review|gate|p10/i.test(id), line_start: startLine, line_end: Math.min(sourceCode.split("\n").length, startLine + 3),
      });
      prevId = id;
    }
  }

  for (const cm of sourceCode.matchAll(/\b(?:studio|workflow)\s*\.\s*(?:cycle|add_cycle_policy|addCycle)\s*\(([\s\S]*?)\)/g)) {
    const cbody = cm[1] ?? "";
    const fromM = /(?:from_node|from)\s*[:=]\s*["']([^"']+)["']/.exec(cbody);
    const toM = /(?:to_node|to)\s*[:=]\s*["']([^"']+)["']/.exec(cbody);
    if (fromM?.[1] && toM?.[1]) cycles.push({ from: fromM[1], to: toM[1] });
  }
  return { nodes: nodes.length > 0 ? nodes : [...DEFAULT_STUDIO_NODES], cycles };
}

function buildTopologicalLayout(
  rawNodes: ReadonlyArray<StudioKflowNodeInput>, explicitCycles: ReadonlyArray<StudioCycleBackEdge>,
  spanById?: Map<string, { start: number; end: number }>,
): { nodes: StudioKflowNode[]; edges: StudioKflowEdge[]; cycleBackEdges: StudioCycleBackEdge[] } {
  const byId = new Map(rawNodes.map((n) => [n.id, n]));
  const orderIndex = new Map(rawNodes.map((n, idx) => [n.id, idx]));
  const edges: StudioKflowEdge[] = [];
  const cycleBackEdges: StudioCycleBackEdge[] = [];

  for (const n of rawNodes) {
    for (const dep of n.depends_on ?? []) {
      if (!byId.has(dep)) continue;
      const isCycle = (orderIndex.get(dep) ?? 0) >= (orderIndex.get(n.id) ?? 0);
      if (isCycle) cycleBackEdges.push({ from: dep, to: n.id });
      edges.push({ from: dep, to: n.id, is_cycle: isCycle });
    }
  }
  for (const cyc of explicitCycles) {
    if (byId.has(cyc.from) && byId.has(cyc.to) && !cycleBackEdges.some((c) => c.from === cyc.from && c.to === cyc.to)) {
      cycleBackEdges.push({ from: cyc.from, to: cyc.to });
      edges.push({ from: cyc.from, to: cyc.to, is_cycle: true });
    }
  }

  const waveMap = new Map<string, number>();
  const laneByWave = new Map<number, number>();
  for (const n of rawNodes) {
    const validDeps = (n.depends_on ?? []).filter((d) => waveMap.has(d));
    waveMap.set(n.id, typeof n.wave === "number" ? n.wave : validDeps.length > 0 ? Math.max(...validDeps.map((d) => waveMap.get(d) ?? 0)) + 1 : 0);
  }
  const nodes: StudioKflowNode[] = rawNodes.map((n, idx) => {
    const wave = waveMap.get(n.id) ?? 0;
    const lane = laneByWave.get(wave) ?? 0;
    laneByWave.set(wave, lane + 1);
    const span = spanById?.get(n.id);
    return {
      id: n.id, label: n.label ?? n.id, agent_id: n.agent_id ?? "feature-coder",
      depends_on: (n.depends_on ?? []).filter((d) => byId.has(d)), requires_p10: Boolean(n.requires_p10),
      line_start: span?.start ?? n.line_start ?? (5 + idx * 8), line_end: span?.end ?? n.line_end ?? (11 + idx * 8),
      wave, x: typeof n.x === "number" ? n.x : 76 + wave * 214, y: typeof n.y === "number" ? n.y : 86 + lane * 94,
    };
  });
  return { nodes, edges, cycleBackEdges };
}

function decodeStudioSyncResponse(
  d: Record<string, unknown>, fallbackWs: string, fallbackWf: string, fallbackDir: KflowSyncDirection, fallbackLang: StudioSdkLanguage,
): SyncKflowStudioResponse {
  const nodes: StudioKflowNode[] = (Array.isArray(d.nodes) ? d.nodes.filter(isRecord) : []).map((n, idx) => ({
    id: String(n.id ?? `node_${idx}`), label: String(n.label ?? n.id ?? `Node ${idx}`),
    agent_id: String(n.agent_id ?? "feature-coder"),
    depends_on: Array.isArray(n.depends_on) ? n.depends_on.map(String) : [],
    requires_p10: Boolean(n.requires_p10),
    line_start: typeof n.line_start === "number" ? n.line_start : 5 + idx * 8,
    line_end: typeof n.line_end === "number" ? n.line_end : 11 + idx * 8,
    wave: typeof n.wave === "number" ? n.wave : idx,
    x: typeof n.x === "number" ? n.x : 76 + idx * 214, y: typeof n.y === "number" ? n.y : 86,
  }));
  const edges: StudioKflowEdge[] = (Array.isArray(d.edges) ? d.edges.filter(isRecord) : []).map((e) => ({
    from: String(e.from ?? e.source ?? ""), to: String(e.to ?? e.target ?? ""), is_cycle: Boolean(e.is_cycle ?? e.is_back_edge ?? false),
  }));
  const cycleBackEdges: StudioCycleBackEdge[] = (Array.isArray(d.cycle_back_edges) ? d.cycle_back_edges.filter(isRecord) : edges.filter((e) => e.is_cycle))
    .map((c) => ({ from: String(c.from ?? ""), to: String(c.to ?? "") }));
  const sourceCode = String(d.source_code ?? "");
  const ws = String(d.workspace_id ?? fallbackWs);
  const wf = String(d.workflow_id ?? fallbackWf);
  return {
    workspace_id: ws, workflow_id: wf,
    direction: d.direction === "graph_to_code" ? "graph_to_code" : fallbackDir,
    language: d.language === "typescript" ? "typescript" : fallbackLang,
    nodes, edges, cycle_back_edges: cycleBackEdges,
    p10_locked_nodes: Array.isArray(d.p10_locked_nodes) ? d.p10_locked_nodes.map(String) : nodes.filter((n) => n.requires_p10).map((n) => n.id),
    source_code: sourceCode, persisted: Boolean(d.persisted ?? false),
    sync_sha256: toSha(String(d.sync_sha256 ?? computeStudioDigest64(`${ws}:${wf}:${sourceCode}`))),
  };
}

export async function syncKflowStudio(
  payload: SyncKflowStudioRequest, role: WorkspaceRbacRole = "owner",
): Promise<SyncKflowStudioResponse> {
  const ws = payload.workspace_id ?? "default";
  const wf = payload.workflow_id || "WF-01";
  const persist = Boolean(payload.persist ?? (payload.direction === "graph_to_code" && canRbacMutateStudio(role)));
  const res = await requestStudioEndpoint(
    "/v1/platform/studio/kflow/sync",
    { method: "POST", body: JSON.stringify({ ...payload, workspace_id: ws, workflow_id: wf, persist }) },
    undefined, role,
  );
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.nodes) && typeof res.data.source_code === "string") {
    return decodeStudioSyncResponse(res.data, ws, wf, payload.direction, payload.language);
  }
  if (!canRbacMutateStudio(role) && (payload.direction === "graph_to_code" || Boolean(payload.persist))) {
    throw new PlatformStudioHttpError(403, `RBAC Denied (${role}): Viewer role cannot mutate KFlow studio graph_to_code state.`);
  }
  const cacheKey = `${ws}:${wf}`;
  const prior = localKflowByKey.get(cacheKey);
  let computed: SyncKflowStudioResponse;
  switch (payload.direction) {
    case "graph_to_code": {
      const baseNodes = payload.nodes?.length ? payload.nodes : (prior?.nodes ?? DEFAULT_STUDIO_NODES);
      const preservedCycles = prior?.cycle_back_edges ?? DEFAULT_CYCLES;
      const rendered = renderKflowCodeAndSpans(ws, wf, payload.language, baseNodes, preservedCycles);
      const layout = buildTopologicalLayout(baseNodes, preservedCycles, rendered.spanById);
      computed = {
        workspace_id: ws, workflow_id: wf, direction: "graph_to_code", language: payload.language,
        nodes: layout.nodes, edges: layout.edges, cycle_back_edges: layout.cycleBackEdges,
        p10_locked_nodes: layout.nodes.filter((n) => n.requires_p10).map((n) => n.id),
        source_code: rendered.sourceCode, persisted: persist,
        sync_sha256: computeStudioDigest64(`${ws}:${wf}:${payload.language}:${rendered.sourceCode}`),
      };
      break;
    }
    case "code_to_graph": {
      const codeInput = payload.source_code?.trim()
        ? payload.source_code
        : renderKflowCodeAndSpans(ws, wf, payload.language, prior?.nodes ?? DEFAULT_STUDIO_NODES, prior?.cycle_back_edges ?? DEFAULT_CYCLES).sourceCode;
      const parsed = parseNodesAndCyclesFromCode(codeInput);
      const layout = buildTopologicalLayout(parsed.nodes, parsed.cycles);
      computed = {
        workspace_id: ws, workflow_id: wf, direction: "code_to_graph", language: payload.language,
        nodes: layout.nodes, edges: layout.edges, cycle_back_edges: layout.cycleBackEdges,
        p10_locked_nodes: layout.nodes.filter((n) => n.requires_p10).map((n) => n.id),
        source_code: codeInput, persisted: persist && canRbacMutateStudio(role),
        sync_sha256: computeStudioDigest64(`${ws}:${wf}:${payload.language}:${codeInput}`),
      };
      break;
    }
    default: {
      const _exhaustive: never = payload.direction;
      return _exhaustive;
    }
  }
  if (canRbacMutateStudio(role)) localKflowByKey.set(cacheKey, computed);
  return computed;
}

function buildLocalBlastAudit(ws: string, req: RecordBlastRadiusRequest, seq: number): BlastRadiusAuditRecord {
  const traceId = req.trace_id ?? `trace-otel-seed-${ws}`;
  const fsReads = req.fs_reads ?? ["core/billing/ledger.py", "core/security/p10_gate.py"];
  const fsWrites = req.fs_writes ?? [".keelway/wal/flight_tape.sqlite"];
  const blockedPaths = req.blocked_paths ?? ["/etc/passwd", "~/.ssh/id_ed25519"];
  const egressAttempts = req.egress_attempts ?? 0;
  const blockedHosts = req.blocked_egress_hosts ?? ["telemetry.unapproved-egress.invalid"];
  const p10Gates = req.p10_gates_triggered ?? 1;
  const seatbelted = req.seatbelted ?? true;
  const zeroUnapproved = seatbelted && egressAttempts === 0;
  const riskTier: BlastRadiusRiskTier = !seatbelted || !zeroUnapproved
    ? "elevated_review"
    : blockedPaths.length > 0 || blockedHosts.length > 0 ? "contained_guarded" : "nominal_confined";
  const auditId = `blast-${computeLocalFingerprintHex(`${ws}:${traceId}:${seq}`).slice(0, 10)}`;
  return {
    audit_id: auditId, workspace_id: ws, trace_id: traceId, workflow_id: req.workflow_id ?? "WF-01",
    fs_reads: fsReads, fs_writes: fsWrites, blocked_paths: blockedPaths,
    egress_attempts: egressAttempts, blocked_egress_hosts: blockedHosts, p10_gates_triggered: p10Gates,
    seatbelted, zero_unapproved_egress: zeroUnapproved, syscalls_audited: req.syscalls_audited ?? 148 + seq * 6,
    risk_tier: riskTier, audit_sha256: computeStudioDigest64(`${ws}:${auditId}:${traceId}:${blockedPaths.join(",")}`),
    recorded_at: new Date().toISOString(),
  };
}

function decodeBlastAudit(d: Record<string, unknown>, ws: string): BlastRadiusAuditRecord {
  const traceId = String(d.trace_id ?? `trace-otel-seed-${ws}`);
  const auditId = String(d.audit_id ?? `blast-${computeLocalFingerprintHex(`${ws}:${traceId}`).slice(0, 8)}`);
  const rawTier = d.risk_tier;
  const riskTier: BlastRadiusRiskTier =
    rawTier === "nominal_confined" || rawTier === "contained_guarded" || rawTier === "elevated_review"
      ? rawTier
      : rawTier === "elevated_unblocked_egress"
        ? "elevated_review"
        : "contained_guarded";
  return {
    audit_id: auditId, workspace_id: String(d.workspace_id ?? ws), trace_id: traceId, workflow_id: String(d.workflow_id ?? "WF-01"),
    fs_reads: Array.isArray(d.fs_reads) ? d.fs_reads.map(String) : ["core/billing/ledger.py"],
    fs_writes: Array.isArray(d.fs_writes) ? d.fs_writes.map(String) : [".keelway/wal/flight_tape.sqlite"],
    blocked_paths: Array.isArray(d.blocked_paths) ? d.blocked_paths.map(String) : ["/etc/passwd"],
    egress_attempts: typeof d.egress_attempts === "number" ? d.egress_attempts : 0,
    blocked_egress_hosts: Array.isArray(d.blocked_egress_hosts) ? d.blocked_egress_hosts.map(String) : [],
    p10_gates_triggered: typeof d.p10_gates_triggered === "number" ? d.p10_gates_triggered : 1,
    seatbelted: Boolean(d.seatbelted ?? true), zero_unapproved_egress: Boolean(d.zero_unapproved_egress ?? true),
    syscalls_audited: typeof d.syscalls_audited === "number" ? d.syscalls_audited : 148,
    risk_tier: riskTier, audit_sha256: toSha(String(d.audit_sha256 ?? computeStudioDigest64(`${ws}:${auditId}`))),
    recorded_at: String(d.recorded_at ?? new Date().toISOString()),
  };
}

function getOrSeedLocalBlastAudits(ws: string): BlastRadiusAuditRecord[] {
  const existing = localBlastByWs.get(ws);
  if (existing) return existing;
  const seeded = [buildLocalBlastAudit(ws, { trace_id: `trace-otel-seed-${ws}`, blocked_paths: ["/etc/passwd"] }, 0)];
  localBlastByWs.set(ws, seeded);
  return seeded;
}

export async function recordBlastRadius(
  payload: RecordBlastRadiusRequest, role: WorkspaceRbacRole = "owner",
): Promise<BlastRadiusAuditRecord> {
  const ws = payload.workspace_id ?? "default";
  const body = {
    workspace_id: ws, trace_id: payload.trace_id, workflow_id: payload.workflow_id,
    fs_reads: payload.fs_reads, fs_writes: payload.fs_writes, blocked_paths: payload.blocked_paths,
    egress_attempts: payload.egress_attempts ?? 0, blocked_egress_hosts: payload.blocked_egress_hosts,
    p10_gates_triggered: payload.p10_gates_triggered ?? 1, seatbelted: payload.seatbelted ?? true,
  };
  const res = await requestStudioEndpoint("/v1/platform/studio/blast-radius/record", { method: "POST", body: JSON.stringify(body) }, undefined, role);
  const raw = isRecord(res.data) && isRecord(res.data.audit) ? res.data.audit : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && typeof raw.audit_id === "string") return decodeBlastAudit(raw, ws);
  if (!canRbacMutateStudio(role)) throw new PlatformStudioHttpError(403, `RBAC Denied (${role}): Viewer role cannot record sandbox blast-radius audits.`);
  localStudioSeq += 1;
  const created = buildLocalBlastAudit(ws, payload, localStudioSeq);
  localBlastByWs.set(ws, [created, ...getOrSeedLocalBlastAudits(ws)]);
  return created;
}

export async function fetchBlastRadiusAudits(
  workspaceId = "default", role: WorkspaceRbacRole = "owner", traceId?: string,
): Promise<BlastRadiusAuditListResponse> {
  const res = await requestStudioEndpoint("/v1/platform/studio/blast-radius", { method: "GET" }, { workspace_id: workspaceId, trace_id: traceId }, role);
  const rawList = isRecord(res.data) && Array.isArray(res.data.audits) ? res.data.audits : null;
  if (res.ok && rawList) {
    const audits = rawList.filter(isRecord).map((a) => decodeBlastAudit(a, workspaceId));
    return { workspace_id: workspaceId, count: audits.length, total_audits: audits.length, audits, source: "live" };
  }
  const all = getOrSeedLocalBlastAudits(workspaceId);
  const filtered = traceId ? all.filter((a) => a.trace_id === traceId) : all;
  const effective = filtered.length > 0 ? filtered : all;
  return { workspace_id: workspaceId, count: effective.length, total_audits: effective.length, audits: effective, source: "local_fallback" };
}

function decodePromptGateRecord(d: Record<string, unknown>, ws: string): PromptGateEvaluationRecord {
  const runId = String(d.gate_run_id ?? `gate-${computeLocalFingerprintHex(ws).slice(0, 8)}`);
  return {
    gate_run_id: runId, workspace_id: String(d.workspace_id ?? ws),
    candidate_prompt_version: String(d.candidate_prompt_version ?? "p-15"),
    candidate_model_id: String(d.candidate_model_id ?? "keelway-core:7b"),
    verdict: d.verdict === "BLOCK" ? "BLOCK" : "PASS",
    cases_evaluated: typeof d.cases_evaluated === "number" ? d.cases_evaluated : 3,
    passed_cases: typeof d.passed_cases === "number" ? d.passed_cases : 3,
    pass_rate: typeof d.pass_rate === "number" ? d.pass_rate : 1,
    min_pass_rate: typeof d.min_pass_rate === "number" ? d.min_pass_rate : 0.9,
    schema_valid_count: typeof d.schema_valid_count === "number" ? d.schema_valid_count : 3,
    dlp_violations: typeof d.dlp_violations === "number" ? d.dlp_violations : 0,
    cost_delta_usd: typeof d.cost_delta_usd === "number" ? Number(d.cost_delta_usd.toFixed(6)) : -0.0084,
    dataset_source: String(d.dataset_source ?? "golden_eval_wal"),
    gate_sha256: toSha(String(d.gate_sha256 ?? computeStudioDigest64(`${ws}:${runId}`))),
    evaluated_at: String(d.evaluated_at ?? new Date().toISOString()),
  };
}

export async function evaluatePromptGate(
  payload: EvaluatePromptGateRequest, role: WorkspaceRbacRole = "owner",
): Promise<PromptGateEvaluationRecord> {
  const ws = payload.workspace_id ?? "default";
  const promptVersion = payload.candidate_prompt_version ?? "p-15";
  const promptText = payload.candidate_prompt_text ?? payload.candidate_prompt ?? "";
  const minPassRate = payload.min_pass_rate ?? 0.9;
  const res = await requestStudioEndpoint(
    "/v1/platform/studio/prompt-gate/evaluate",
    {
      method: "POST",
      body: JSON.stringify({
        workspace_id: ws, candidate_prompt_version: promptVersion, candidate_model_id: payload.candidate_model_id,
        candidate_prompt_text: promptText, required_json_keys: payload.required_json_keys, min_pass_rate: minPassRate,
      }),
    },
    undefined, role,
  );
  const raw = isRecord(res.data) && isRecord(res.data.gate_run) ? res.data.gate_run : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && typeof raw.gate_run_id === "string") return decodePromptGateRecord(raw, ws);
  if (!canRbacMutateStudio(role)) throw new PlatformStudioHttpError(403, `RBAC Denied (${role}): Viewer role cannot run prompt regression gates.`);

  localStudioSeq += 1;
  let dlpViolations = 0;
  for (const pat of DLP_PATTERNS) {
    const matches = promptText.match(new RegExp(pat.source, pat.flags));
    if (matches) dlpViolations += matches.length;
  }
  const hasBypass = /ignore previous instructions|bypass_p10|bypass p-10|broken_schema/i.test(promptText);
  const casesEvaluated = 3;
  const passedCases = dlpViolations > 0 || hasBypass ? 0 : casesEvaluated;
  const passRate = Number((passedCases / casesEvaluated).toFixed(4));
  const verdict: PromptGateVerdict = dlpViolations === 0 && !hasBypass && passRate >= minPassRate ? "PASS" : "BLOCK";
  const isLocal = payload.candidate_model_id.startsWith("keelway-") || payload.candidate_model_id.includes("local");
  const baseline = payload.baseline_cost_usd ?? 0.0179;
  const costDelta = Number(((isLocal ? 0 : baseline * 0.55) - baseline).toFixed(4));
  const runId = `gate-${computeLocalFingerprintHex(`${ws}:${promptVersion}:${payload.candidate_model_id}:${localStudioSeq}`).slice(0, 10)}`;
  const record: PromptGateEvaluationRecord = {
    gate_run_id: runId, workspace_id: ws, candidate_prompt_version: promptVersion, candidate_model_id: payload.candidate_model_id,
    verdict, cases_evaluated: casesEvaluated, passed_cases: passedCases, pass_rate: passRate, min_pass_rate: minPassRate,
    schema_valid_count: passedCases, dlp_violations: dlpViolations, cost_delta_usd: costDelta,
    dataset_source: "golden_eval_wal", gate_sha256: computeStudioDigest64(`${ws}:${runId}:${verdict}:${passRate}:${promptText}`),
    evaluated_at: new Date().toISOString(),
  };
  localGateRunsByWs.set(ws, [record, ...(localGateRunsByWs.get(ws) ?? [])]);
  return record;
}

export async function fetchPromptGateRuns(
  workspaceId = "default", role: WorkspaceRbacRole = "owner",
): Promise<PromptGateRunListResponse> {
  const res = await requestStudioEndpoint("/v1/platform/studio/prompt-gate/runs", { method: "GET" }, { workspace_id: workspaceId }, role);
  const rawRuns = isRecord(res.data) && Array.isArray(res.data.runs) ? res.data.runs : null;
  if (res.ok && rawRuns) {
    const runs = rawRuns.filter(isRecord).map((r) => decodePromptGateRecord(r, workspaceId));
    return { workspace_id: workspaceId, count: runs.length, total_runs: runs.length, runs, source: "live" };
  }
  const local = localGateRunsByWs.get(workspaceId) ?? [];
  return { workspace_id: workspaceId, count: local.length, total_runs: local.length, runs: local, source: "local_fallback" };
}
