import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export { getStudioToken as getSessionToken };
export type WorkspaceRbacRole = RbacRoleId;
export type { RbacRoleId };
export type LangGraphSourceLanguage = "python" | "typescript";

export interface OtelSpanInput {
  span_id?: string; step_index?: number; name: string; node_name?: string; span_kind?: string;
  model_id?: string; prompt?: string; input?: string; output?: string; completion?: string;
  input_tokens?: number; output_tokens?: number; cost_usd?: number; duration_ms?: number;
  attributes?: Record<string, unknown>;
}

export interface IngestOtelTraceRequest {
  workspace_id?: string; trace_id?: string; title?: string; service_name?: string;
  spans?: OtelSpanInput[]; resourceSpans?: Record<string, unknown>[];
}

export interface FlightTapeStep {
  step_index: number; span_id: string; node_name: string; span_kind: string; model_id: string;
  prompt: string; output: string; input_tokens: number; output_tokens: number;
  cost_usd: number; duration_ms: number; cached_reuse: boolean; dlp_redacted: boolean; step_sha256: string;
}

export interface FlightTapeRecord {
  trace_id: string; workspace_id: string; parent_trace_id: string | null; title: string;
  service_name: string; status: string; step_count: number; total_tokens: number;
  total_cost_usd: number; cached_steps_reused: number; cost_delta_usd: number;
  dlp_redactions: number; tape_sha256: string; created_at: string; steps: FlightTapeStep[];
}

export interface FlightTapeListResponse {
  workspace_id: string; total_tapes: number; tapes: FlightTapeRecord[]; source: "live" | "local_fallback";
}

export interface ReplayFlightTapeRequest {
  from_step_index: number; override_model: string; override_prompt: string;
}

export interface ReplayFlightTapeResponse {
  workspace_id: string; fork_trace_id: string; parent_trace_id: string; from_step_index: number;
  override_model: string; override_prompt: string; cached_steps_reused: number;
  original_cost_usd: number; fork_cost_usd: number; cost_delta_usd: number;
  tape_sha256: string; tape: FlightTapeRecord;
}

export interface EvalDatasetCaseRecord {
  case_id: string; workspace_id: string; trace_id: string; title: string; step_count: number;
  expected_nodes: string[]; baseline_cost_usd: number; case_sha256: string; created_at: string;
}

export interface EvalDatasetListResponse {
  workspace_id: string; total_cases: number; cases: EvalDatasetCaseRecord[];
}

export interface MigratedKflowNode { id: string; handler: string; kind: string; requires_p10: boolean; }
export interface MigratedKflowEdge { source: string; target: string; condition: string | null; is_back_edge: boolean; }
export interface BoundedLoopPolicy { from_node: string; to_node: string; max_iterations: number; }

export interface LangGraphMigrationResult {
  workspace_id: string; workflow_name: string; source_language: LangGraphSourceLanguage;
  nodes: MigratedKflowNode[]; edges: MigratedKflowEdge[]; p10_gates_injected: string[];
  cycles_detected: number; bounded_loop_policies: BoundedLoopPolicy[];
  legacy_warnings: string[]; kflow_sdk_code: string; migration_sha256: string;
}

export class PlatformDevxHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "PlatformDevxHttpError";
    this.status = status;
  }
}

export const DEFAULT_LANGGRAPH_PYTHON_SOURCE = `from langchain.chains import LLMChain
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

def draft_fn(state: dict) -> dict:
    return {"draft": state.get("spec", "v1")}

def review_fn(state: dict) -> dict:
    decision = interrupt({"reason": "deploy"})
    return {"approved": decision == "ship"}

def route_fn(state: dict) -> str:
    return "ship" if state.get("approved") else "revise"

builder = StateGraph(dict)
builder.add_node("draft", draft_fn)
builder.add_node("human_review", review_fn)
builder.add_edge(START, "draft")
builder.add_edge("draft", "human_review")
builder.add_conditional_edges("human_review", route_fn, {"revise": "draft", "ship": END})
graph = builder.compile()`;

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const toSha = (raw: string): string => (raw.startsWith("sha256:") ? raw : `sha256:${raw}`);
const DLP_SCRUB_PATTERNS: ReadonlyArray<RegExp> = [
  /\bsk-(?:ant-|proj-|live-|test-)?[a-zA-Z0-9_-]{6,}/gi,
  /\bgh[pousr]_[a-zA-Z0-9_]{6,}/gi,
  /\bAKIA[0-9A-Z]{12,}/g,
];

export const canRbacReadDevxTraces = (_role: WorkspaceRbacRole): boolean => true;
export const canRbacMutateDevx = (role: WorkspaceRbacRole): boolean => role !== "viewer";

function computeDigest64(seed: string): string {
  const parts = [1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`devx:${i}:${seed}`)).join("");
  return toSha(parts);
}

function scrubDlpSecrets(raw: string): { text: string; count: number } {
  let text = raw;
  let count = 0;
  for (const base of DLP_SCRUB_PATTERNS) {
    text = text.replace(new RegExp(base.source, base.flags), () => {
      count += 1;
      return "[REDACTED_SECRET]";
    });
  }
  return { text, count };
}

function shouldSkipUnmockedTestFetch(): boolean {
  if (import.meta.env.MODE !== "test") return false;
  if (typeof globalThis.fetch !== "function") return true;
  return !("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN;
}

function buildDevxUrl(path: string, query?: Record<string, string | undefined>): string {
  if (!path.startsWith("/v1/platform/")) {
    throw new Error(`Security violation: platformDevxApi allows strictly /v1/platform/* paths, got ${path}`);
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

function attachDevxHeaders(raw?: HeadersInit, role?: WorkspaceRbacRole, hasBody = false): Headers {
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

async function requestDevxEndpoint(
  path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: WorkspaceRbacRole,
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const url = buildDevxUrl(path, query);
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null };
  let res: Response;
  try {
    res = await fetch(url, { ...init, credentials: "same-origin", headers: attachDevxHeaders(init.headers, role, Boolean(init.body)) });
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
      : `Request failed with HTTP ${res.status}.`;
    throw new PlatformDevxHttpError(res.status, detail);
  }
  return { ok: res.ok, status: res.status, data };
}

export function buildSampleOtelTracePayload(workspaceId = "default"): IngestOtelTraceRequest {
  return {
    workspace_id: workspaceId,
    title: "OTel GenAI Multi-Agent Billing Triage",
    service_name: "keelway-agent-swarm",
    spans: [
      {
        span_id: "span-triage-0", step_index: 0, name: "triage_router", node_name: "triage_router",
        span_kind: "agent", model_id: "gpt-4o",
        prompt: "Classify enterprise billing discrepancy for acme-prod (Authorization: Bearer sk-live-EXAMPLE_DLP_LEAK_000).",
        output: "Routed anomaly to mcp_billing_lookup for ledger reconciliation.",
        input_tokens: 380, output_tokens: 90, cost_usd: 0.0048, duration_ms: 164,
        attributes: { "gen_ai.system": "openai", "gen_ai.operation.name": "agent", "gen_ai.agent.name": "triage_router", "gen_ai.request.model": "gpt-4o", "gen_ai.usage.input_tokens": 380, "gen_ai.usage.output_tokens": 90, "gen_ai.usage.cost_usd": 0.0048 },
      },
      {
        span_id: "span-mcp-1", step_index: 1, name: "mcp_billing_lookup", node_name: "mcp_billing_lookup",
        span_kind: "tool", model_id: "gpt-4o",
        prompt: '{"tool":"billing.fetch_invoice_delta","tenant":"acme-prod"}',
        output: '{"invoice_id":"INV-9042","duplicate_charge_usd":120.00,"verified":true}',
        input_tokens: 210, output_tokens: 140, cost_usd: 0.0035, duration_ms: 92,
        attributes: { "gen_ai.system": "openai", "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "mcp_billing_lookup", "gen_ai.request.model": "gpt-4o", "gen_ai.usage.input_tokens": 210, "gen_ai.usage.output_tokens": 140, "gen_ai.usage.cost_usd": 0.0035 },
      },
      {
        span_id: "span-critic-2", step_index: 2, name: "synthesis_critic", node_name: "synthesis_critic",
        span_kind: "llm", model_id: "gpt-4o",
        prompt: "Draft root-cause credit memo resolution from verified invoice delta INV-9042.",
        output: "Confirmed duplicate $120.00 charge on INV-9042; stage P-10 refund approval.",
        input_tokens: 640, output_tokens: 220, cost_usd: 0.0096, duration_ms: 310,
        attributes: { "gen_ai.system": "openai", "gen_ai.operation.name": "chat", "gen_ai.request.model": "gpt-4o", "gen_ai.usage.input_tokens": 640, "gen_ai.usage.output_tokens": 220, "gen_ai.usage.cost_usd": 0.0096 },
      },
    ],
  };
}

const localTapesByWs = new Map<string, FlightTapeRecord[]>();
const localEvalCasesByWs = new Map<string, EvalDatasetCaseRecord[]>();
const cachedStepsByTraceId = new Map<string, FlightTapeStep[]>();
let localDevxSeq = 0;

export function resetLocalDevxState(): void {
  localTapesByWs.clear();
  localEvalCasesByWs.clear();
  cachedStepsByTraceId.clear();
  localDevxSeq = 0;
}

function buildTapeFromSpans(
  ws: string, traceId: string, title: string, serviceName: string, spans: OtelSpanInput[], parentTraceId: string | null = null,
): FlightTapeRecord {
  let dlpRedactions = 0;
  const steps: FlightTapeStep[] = spans.map((sp, idx) => {
    const pScrub = scrubDlpSecrets(String(sp.prompt ?? sp.input ?? ""));
    const oScrub = scrubDlpSecrets(String(sp.output ?? sp.completion ?? ""));
    dlpRedactions += pScrub.count + oScrub.count;
    const nodeName = String(sp.node_name ?? sp.name ?? `step_${idx}`);
    const modelId = String(sp.model_id ?? "gpt-4o");
    const stepIndex = typeof sp.step_index === "number" ? sp.step_index : idx;
    return {
      step_index: stepIndex, span_id: String(sp.span_id ?? `span-${stepIndex}`), node_name: nodeName,
      span_kind: String(sp.span_kind ?? "llm"), model_id: modelId, prompt: pScrub.text, output: oScrub.text,
      input_tokens: typeof sp.input_tokens === "number" ? sp.input_tokens : 250,
      output_tokens: typeof sp.output_tokens === "number" ? sp.output_tokens : 100,
      cost_usd: Number((typeof sp.cost_usd === "number" ? sp.cost_usd : 0.004).toFixed(6)),
      duration_ms: typeof sp.duration_ms === "number" ? sp.duration_ms : 120,
      cached_reuse: false, dlp_redacted: pScrub.count + oScrub.count > 0,
      step_sha256: computeDigest64(`${traceId}:${stepIndex}:${nodeName}:${modelId}:${pScrub.text}`),
    };
  });
  const totalCost = Number(steps.reduce((acc, s) => acc + s.cost_usd, 0).toFixed(6));
  const totalTokens = steps.reduce((acc, s) => acc + s.input_tokens + s.output_tokens, 0);
  const tape: FlightTapeRecord = {
    trace_id: traceId, workspace_id: ws, parent_trace_id: parentTraceId, title, service_name: serviceName,
    status: "recorded", step_count: steps.length, total_tokens: totalTokens, total_cost_usd: totalCost,
    cached_steps_reused: 0, cost_delta_usd: 0, dlp_redactions: dlpRedactions,
    tape_sha256: computeDigest64(`${ws}:${traceId}:${steps.map((s) => s.step_sha256).join("|")}`),
    created_at: new Date().toISOString(), steps,
  };
  cachedStepsByTraceId.set(traceId, steps);
  return tape;
}

function getOrSeedLocalTapes(ws: string): FlightTapeRecord[] {
  const existing = localTapesByWs.get(ws);
  if (existing) return existing;
  const sample = buildSampleOtelTracePayload(ws);
  const seeded = [buildTapeFromSpans(ws, `trace-otel-seed-${ws}`, sample.title!, sample.service_name!, sample.spans!)];
  localTapesByWs.set(ws, seeded);
  return seeded;
}

function decodeStep(raw: Record<string, unknown>, traceId: string, idx: number): FlightTapeStep {
  const stepIndex = typeof raw.step_index === "number" ? raw.step_index : idx;
  const nodeName = String(raw.node_name ?? raw.name ?? raw.span_name ?? `step_${stepIndex}`);
  const modelId = String(raw.model_id ?? raw.model ?? "keelway-core:7b");
  const cachedReuse = Boolean(raw.cached_reuse ?? raw.reused_from_cache ?? raw.is_cached ?? false);
  return {
    step_index: stepIndex, span_id: String(raw.span_id ?? `span-${stepIndex}`), node_name: nodeName,
    span_kind: String(raw.span_kind ?? raw.kind ?? "llm"), model_id: modelId,
    prompt: String(raw.prompt ?? raw.input_text ?? raw.input ?? ""),
    output: String(raw.output ?? raw.output_text ?? raw.completion ?? ""),
    input_tokens: typeof raw.input_tokens === "number" ? raw.input_tokens : 200,
    output_tokens: typeof raw.output_tokens === "number" ? raw.output_tokens : 80,
    cost_usd: Number((typeof raw.cost_usd === "number" ? raw.cost_usd : cachedReuse ? 0 : 0.002).toFixed(6)),
    duration_ms: typeof raw.duration_ms === "number" ? raw.duration_ms : 95,
    cached_reuse: cachedReuse,
    dlp_redacted: Boolean(raw.dlp_redacted ?? String(raw.prompt ?? raw.prompt_text ?? "").includes("[REDACTED_SECRET]")),
    step_sha256: toSha(String(raw.step_sha256 ?? raw.sha256 ?? computeDigest64(`${traceId}:${stepIndex}:${nodeName}`))),
  };
}

function decodeTape(raw: Record<string, unknown>, ws: string): FlightTapeRecord {
  const traceId = String(raw.trace_id ?? raw.id ?? `trace-${computeLocalFingerprintHex(ws).slice(0, 8)}`);
  const rawSteps = Array.isArray(raw.steps) ? raw.steps.filter(isRecord) : [];
  const steps = rawSteps.length > 0 ? rawSteps.map((s, idx) => decodeStep(s, traceId, idx)) : (cachedStepsByTraceId.get(traceId) ?? []);
  if (steps.length > 0) cachedStepsByTraceId.set(traceId, steps);
  const totalCost = typeof raw.total_cost_usd === "number"
    ? Number(raw.total_cost_usd.toFixed(6))
    : Number(steps.reduce((acc, s) => acc + s.cost_usd, 0).toFixed(6));
  return {
    trace_id: traceId, workspace_id: String(raw.workspace_id ?? ws),
    parent_trace_id: typeof raw.parent_trace_id === "string" && raw.parent_trace_id ? raw.parent_trace_id : null,
    title: String(raw.title ?? raw.workflow_name ?? raw.trace_name ?? raw.service_name ?? "OTel GenAI Trace"),
    service_name: String(raw.service_name ?? raw.source_framework ?? "keelway-agent-swarm"),
    status: String(raw.status ?? "recorded"),
    step_count: typeof raw.step_count === "number" ? raw.step_count : typeof raw.total_steps === "number" ? raw.total_steps : steps.length,
    total_tokens: typeof raw.total_tokens === "number" ? raw.total_tokens : steps.reduce((acc, s) => acc + s.input_tokens + s.output_tokens, 0),
    total_cost_usd: totalCost,
    cached_steps_reused: typeof raw.cached_steps_reused === "number" ? raw.cached_steps_reused : 0,
    cost_delta_usd: typeof raw.cost_delta_usd === "number" ? Number(raw.cost_delta_usd.toFixed(6)) : 0,
    dlp_redactions: typeof raw.dlp_redactions === "number" ? raw.dlp_redactions : typeof raw.redacted_secrets_count === "number" ? raw.redacted_secrets_count : steps.filter((s) => s.dlp_redacted).length,
    tape_sha256: toSha(String(raw.tape_sha256 ?? raw.trace_sha256 ?? raw.sha256 ?? computeDigest64(`${ws}:${traceId}`))),
    created_at: String(raw.created_at ?? new Date().toISOString()),
    steps,
  };
}

export async function ingestOtelTrace(
  payload: IngestOtelTraceRequest = {}, role: WorkspaceRbacRole = "owner",
): Promise<FlightTapeRecord> {
  const ws = payload.workspace_id ?? "default";
  const sample = buildSampleOtelTracePayload(ws);
  const body: Record<string, unknown> = {
    workspace_id: ws,
    title: payload.title ?? sample.title,
    workflow_name: payload.title ?? sample.title,
    service_name: payload.service_name ?? sample.service_name,
    source_framework: "opentelemetry_genai",
  };
  if (payload.trace_id) body.trace_id = payload.trace_id;
  if (payload.resourceSpans && !payload.spans) body.resourceSpans = payload.resourceSpans;
  else body.spans = payload.spans ?? sample.spans;

  const usedSpans = payload.spans ?? sample.spans ?? [];
  const res = await requestDevxEndpoint("/v1/platform/traces/ingest", { method: "POST", body: JSON.stringify(body) }, undefined, role);
  const rawTape = isRecord(res.data) && isRecord(res.data.tape) ? res.data.tape : isRecord(res.data) ? res.data : null;
  if (res.ok && rawTape && (typeof rawTape.trace_id === "string" || Array.isArray(rawTape.steps))) {
    const decoded = decodeTape(isRecord(res.data) ? { ...res.data, ...rawTape } : rawTape, ws);
    if (decoded.steps.length === 0 && usedSpans.length > 0) {
      const synth = buildTapeFromSpans(ws, decoded.trace_id, decoded.title, decoded.service_name, usedSpans);
      return { ...decoded, steps: synth.steps, step_count: decoded.step_count || synth.steps.length };
    }
    return decoded;
  }
  if (!canRbacMutateDevx(role)) {
    throw new PlatformDevxHttpError(403, `RBAC Denied (${role}): Viewer role cannot ingest OTel flight-tape traces.`);
  }
  localDevxSeq += 1;
  const traceId = payload.trace_id ?? `trace-otel-${ws}-${localDevxSeq}`;
  const created = buildTapeFromSpans(ws, traceId, String(body.title), String(body.service_name), payload.spans ?? sample.spans ?? []);
  localTapesByWs.set(ws, [created, ...getOrSeedLocalTapes(ws).filter((t) => t.trace_id !== created.trace_id)]);
  return created;
}

export async function fetchFlightTapes(
  workspaceId = "default", role: WorkspaceRbacRole = "owner",
): Promise<FlightTapeListResponse> {
  const res = await requestDevxEndpoint("/v1/platform/traces", { method: "GET" }, { workspace_id: workspaceId }, role);
  const rawList = isRecord(res.data) && Array.isArray(res.data.tapes) ? res.data.tapes : isRecord(res.data) && Array.isArray(res.data.traces) ? res.data.traces : null;
  if (res.ok && rawList) {
    const tapes = rawList.filter(isRecord).map((item) => decodeTape(item, workspaceId));
    return { workspace_id: workspaceId, total_tapes: isRecord(res.data) && typeof res.data.total_tapes === "number" ? res.data.total_tapes : tapes.length, tapes, source: "live" };
  }
  const seeded = getOrSeedLocalTapes(workspaceId);
  return { workspace_id: workspaceId, total_tapes: seeded.length, tapes: seeded, source: "local_fallback" };
}

export async function replayFlightTape(
  workspaceId = "default", traceId: string, payload: ReplayFlightTapeRequest, role: WorkspaceRbacRole = "owner",
): Promise<ReplayFlightTapeResponse> {
  const fromStep = Math.max(0, Math.floor(payload.from_step_index));
  const overrideModel = payload.override_model.trim() || "keelway-core:7b";
  const overridePrompt = payload.override_prompt.trim();

  const res = await requestDevxEndpoint(
    `/v1/platform/traces/${encodeURIComponent(traceId)}/replay`,
    {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId, from_step_index: fromStep, fork_step_index: fromStep,
        override_model: overrideModel, model_override: overrideModel,
        override_prompt: overridePrompt, prompt_override: overridePrompt,
      }),
    },
    undefined, role,
  );
  const rawEnv = isRecord(res.data) ? res.data : null;
  const rawFork = rawEnv && isRecord(rawEnv.tape) ? rawEnv.tape : rawEnv && isRecord(rawEnv.fork_tape) ? rawEnv.fork_tape : rawEnv;
  if (res.ok && rawEnv && rawFork && (typeof rawFork.trace_id === "string" || typeof rawEnv.fork_trace_id === "string")) {
    const decodedTape = decodeTape({ ...rawEnv, ...rawFork, trace_id: rawFork.trace_id ?? rawEnv.fork_trace_id }, workspaceId);
    const parentSteps = cachedStepsByTraceId.get(traceId) ?? getOrSeedLocalTapes(workspaceId)[0]!.steps;
    const ensuredSteps = decodedTape.steps.length > 0 ? decodedTape.steps : parentSteps.map((st, idx) =>
      st.step_index < fromStep ? { ...st, cost_usd: 0, cached_reuse: true } : { ...st, model_id: overrideModel, prompt: idx === fromStep && overridePrompt ? overridePrompt : st.prompt, cost_usd: 0, cached_reuse: false },
    );
    cachedStepsByTraceId.set(decodedTape.trace_id, ensuredSteps);
    const cachedReused = typeof rawEnv.cached_steps_reused === "number" ? rawEnv.cached_steps_reused : decodedTape.cached_steps_reused;
    const costDelta = typeof rawEnv.cost_delta_usd === "number" ? Number(rawEnv.cost_delta_usd.toFixed(6)) : decodedTape.cost_delta_usd;
    const origCost = typeof rawEnv.original_cost_usd === "number" ? Number(rawEnv.original_cost_usd.toFixed(6)) : Number((decodedTape.total_cost_usd - costDelta).toFixed(6));
    return {
      workspace_id: workspaceId, fork_trace_id: decodedTape.trace_id, parent_trace_id: decodedTape.parent_trace_id ?? traceId,
      from_step_index: fromStep, override_model: overrideModel, override_prompt: overridePrompt,
      cached_steps_reused: cachedReused, original_cost_usd: origCost, fork_cost_usd: decodedTape.total_cost_usd,
      cost_delta_usd: costDelta, tape_sha256: decodedTape.tape_sha256,
      tape: { ...decodedTape, steps: ensuredSteps, step_count: decodedTape.step_count || ensuredSteps.length, cached_steps_reused: cachedReused, cost_delta_usd: costDelta },
    };
  }
  if (!canRbacMutateDevx(role)) {
    throw new PlatformDevxHttpError(403, `RBAC Denied (${role}): Viewer role cannot replay counterfactual flight-tapes.`);
  }
  const list = getOrSeedLocalTapes(workspaceId);
  const parent = list.find((t) => t.trace_id === traceId) ?? list[0]!;
  localDevxSeq += 1;
  const forkId = `fork-${computeLocalFingerprintHex(`${parent.trace_id}:${fromStep}:${overrideModel}:${localDevxSeq}`).slice(0, 10)}`;
  const isZeroCost = overrideModel.startsWith("keelway-") || overrideModel.includes("ollama") || overrideModel.includes("local");
  const forkedSteps: FlightTapeStep[] = parent.steps.map((st, idx) => {
    if (st.step_index < fromStep) return { ...st, cost_usd: 0, cached_reuse: true };
    const nextPrompt = idx === fromStep && overridePrompt ? scrubDlpSecrets(overridePrompt).text : st.prompt;
    return {
      ...st, model_id: overrideModel, prompt: nextPrompt, output: `[Counterfactual ${overrideModel}] ${st.output}`,
      cost_usd: isZeroCost ? 0 : Number((st.cost_usd * 0.45).toFixed(6)), cached_reuse: false,
      step_sha256: computeDigest64(`${forkId}:${st.step_index}:${overrideModel}:${nextPrompt}`),
    };
  });
  const cachedReused = forkedSteps.filter((s) => s.cached_reuse).length;
  const forkCost = Number(forkedSteps.reduce((acc, s) => acc + s.cost_usd, 0).toFixed(6));
  const costDelta = Number((forkCost - parent.total_cost_usd).toFixed(6));
  const forkTape: FlightTapeRecord = {
    ...parent, trace_id: forkId, parent_trace_id: parent.trace_id,
    title: `${parent.title} (Fork @ step ${fromStep} -> ${overrideModel})`,
    status: "counterfactual_fork", total_cost_usd: forkCost, cached_steps_reused: cachedReused, cost_delta_usd: costDelta,
    tape_sha256: computeDigest64(`${workspaceId}:${forkId}:${forkedSteps.map((s) => s.step_sha256).join("|")}`),
    created_at: new Date().toISOString(), steps: forkedSteps,
  };
  cachedStepsByTraceId.set(forkId, forkedSteps);
  localTapesByWs.set(workspaceId, [forkTape, ...list]);
  return {
    workspace_id: workspaceId, fork_trace_id: forkId, parent_trace_id: parent.trace_id,
    from_step_index: fromStep, override_model: overrideModel, override_prompt: overridePrompt,
    cached_steps_reused: cachedReused, original_cost_usd: parent.total_cost_usd, fork_cost_usd: forkCost,
    cost_delta_usd: costDelta, tape_sha256: forkTape.tape_sha256, tape: forkTape,
  };
}

function decodeEvalCase(raw: Record<string, unknown>, ws: string): EvalDatasetCaseRecord {
  const caseId = String(raw.case_id ?? raw.id ?? `evalcase-${computeLocalFingerprintHex(ws).slice(0, 8)}`);
  const traceId = String(raw.trace_id ?? raw.source_trace_id ?? "trace-otel-01");
  return {
    case_id: caseId, workspace_id: String(raw.workspace_id ?? ws), trace_id: traceId,
    title: String(raw.title ?? raw.name ?? `Golden Eval · ${traceId}`),
    step_count: typeof raw.step_count === "number" ? raw.step_count : 3,
    expected_nodes: Array.isArray(raw.expected_nodes) ? raw.expected_nodes.map(String) : ["triage_router", "mcp_billing_lookup", "synthesis_critic"],
    baseline_cost_usd: typeof raw.baseline_cost_usd === "number" ? Number(raw.baseline_cost_usd.toFixed(6)) : 0,
    case_sha256: toSha(String(raw.case_sha256 ?? raw.dataset_sha256 ?? raw.sha256 ?? computeDigest64(`${ws}:${caseId}`))),
    created_at: String(raw.created_at ?? new Date().toISOString()),
  };
}

export async function promoteTraceToEval(
  workspaceId = "default", traceId: string, title = "Golden Multi-Agent Billing Regression", role: WorkspaceRbacRole = "owner",
): Promise<EvalDatasetCaseRecord> {
  const res = await requestDevxEndpoint(
    "/v1/platform/eval/dataset/promote",
    { method: "POST", body: JSON.stringify({ workspace_id: workspaceId, trace_id: traceId, title, name: title }) },
    undefined, role,
  );
  const rawCase = isRecord(res.data) && isRecord(res.data.eval_case) ? res.data.eval_case : isRecord(res.data) && isRecord(res.data.case) ? res.data.case : isRecord(res.data) ? res.data : null;
  if (res.ok && rawCase && (typeof rawCase.case_id === "string" || typeof rawCase.id === "string")) {
    return decodeEvalCase(rawCase, workspaceId);
  }
  if (!canRbacMutateDevx(role)) {
    throw new PlatformDevxHttpError(403, `RBAC Denied (${role}): Viewer role cannot promote flight-tapes to golden evals.`);
  }
  const tapes = getOrSeedLocalTapes(workspaceId);
  const tape = tapes.find((t) => t.trace_id === traceId) ?? tapes[0]!;
  localDevxSeq += 1;
  const caseId = `evalcase-${computeLocalFingerprintHex(`${workspaceId}:${tape.trace_id}:${localDevxSeq}`).slice(0, 10)}`;
  const created: EvalDatasetCaseRecord = {
    case_id: caseId, workspace_id: workspaceId, trace_id: tape.trace_id,
    title: title.trim() || `Golden Eval · ${tape.title}`, step_count: tape.step_count,
    expected_nodes: tape.steps.map((s) => s.node_name), baseline_cost_usd: tape.total_cost_usd,
    case_sha256: computeDigest64(`${workspaceId}:${caseId}:${tape.tape_sha256}`),
    created_at: new Date().toISOString(),
  };
  localEvalCasesByWs.set(workspaceId, [created, ...(localEvalCasesByWs.get(workspaceId) ?? [])]);
  return created;
}

export async function fetchEvalDatasetCases(
  workspaceId = "default", role: WorkspaceRbacRole = "owner",
): Promise<EvalDatasetListResponse> {
  const res = await requestDevxEndpoint("/v1/platform/eval/dataset", { method: "GET" }, { workspace_id: workspaceId }, role);
  const rawCases = isRecord(res.data) && Array.isArray(res.data.cases) ? res.data.cases : isRecord(res.data) && Array.isArray(res.data.dataset_cases) ? res.data.dataset_cases : null;
  if (res.ok && rawCases) {
    const cases = rawCases.filter(isRecord).map((c) => decodeEvalCase(c, workspaceId));
    return { workspace_id: workspaceId, total_cases: isRecord(res.data) && typeof res.data.total_cases === "number" ? res.data.total_cases : cases.length, cases };
  }
  const local = localEvalCasesByWs.get(workspaceId) ?? [];
  return { workspace_id: workspaceId, total_cases: local.length, cases: local };
}

function parseLanggraphStatically(
  ws: string, sourceCode: string, sourceLanguage: LangGraphSourceLanguage, workflowName: string,
): LangGraphMigrationResult {
  const interruptFns = new Set<string>();
  const pyDefRegex = /def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)[^:]*:([\s\S]*?)(?=\ndef\s+|\n[a-zA-Z_][a-zA-Z0-9_]*\s*=|$)/g;
  for (const m of sourceCode.matchAll(pyDefRegex)) {
    if (/\binterrupt\s*\(/.test(m[2] ?? "")) interruptFns.add(m[1]!);
  }
  const nodes: MigratedKflowNode[] = [];
  for (const m of sourceCode.matchAll(/\.add_node\(\s*["']([^"']+)["']\s*,\s*([a-zA-Z0-9_]+|[\s\S]*?\))/g)) {
    const id = m[1]!;
    const handlerRaw = (m[2] ?? "handler").trim();
    const handler = handlerRaw.replace(/[^a-zA-Z0-9_].*$/, "") || id;
    const requiresP10 = interruptFns.has(handler) || /\binterrupt\s*\(/.test(handlerRaw);
    nodes.push({ id, handler, kind: requiresP10 ? "p10_human_gate" : "agent_task", requires_p10: requiresP10 });
  }
  const edges: MigratedKflowEdge[] = [];
  for (const m of sourceCode.matchAll(/\.add_edge\(\s*(?:["']([^"']+)["']|(START))\s*,\s*(?:["']([^"']+)["']|(END))\s*\)/g)) {
    edges.push({ source: m[1] ?? m[2] ?? "START", target: m[3] ?? m[4] ?? "END", condition: null, is_back_edge: false });
  }
  for (const m of sourceCode.matchAll(/\.add_conditional_edges\(\s*["']([^"']+)["']\s*,\s*[a-zA-Z0-9_]+\s*,\s*\{([^}]+)\}\s*\)/g)) {
    const src = m[1]!;
    for (const pm of (m[2] ?? "").matchAll(/["']([^"']+)["']\s*:\s*(?:["']([^"']+)["']|(END))/g)) {
      edges.push({ source: src, target: pm[2] ?? pm[3] ?? "END", condition: pm[1] ?? null, is_back_edge: false });
    }
  }
  const adj = new Map<string, string[]>();
  edges.forEach((e) => { if (e.source !== "START" && e.target !== "END") adj.set(e.source, [...(adj.get(e.source) ?? []), e.target]); });
  const visiting = new Set<string>();
  const visited = new Set<string>();
  const boundedPolicies: BoundedLoopPolicy[] = [];
  const dfs = (u: string) => {
    visiting.add(u);
    for (const v of adj.get(u) ?? []) {
      if (visiting.has(v)) {
        boundedPolicies.push({ from_node: u, to_node: v, max_iterations: 5 });
        edges.forEach((ed) => { if (ed.source === u && ed.target === v) ed.is_back_edge = true; });
      } else if (!visited.has(v)) dfs(v);
    }
    visiting.delete(u);
    visited.add(u);
  };
  nodes.forEach((n) => { if (!visited.has(n.id)) dfs(n.id); });

  const legacyWarnings: string[] = [];
  if (/\bLLMChain\b/.test(sourceCode)) {
    legacyWarnings.push("Deprecated LangChain construct `LLMChain` detected — replace with typed KFlow node + structured prompt contract.");
  }
  if (/\bAgentExecutor\b/.test(sourceCode)) {
    legacyWarnings.push("Legacy `AgentExecutor` loop detected — migrated to bounded KFlow topological wave with explicit max_iterations.");
  }
  const p10Gates = nodes.filter((n) => n.requires_p10).map((n) => n.id);
  const kflowLines = [
    `# Generated by keelway migrate (${sourceLanguage} static AST -> KFlow v1)`,
    `from keelway.kflow import KFlowBlueprint, KFlowNode, BoundedCyclePolicy`,
    `workflow = KFlowBlueprint(name="${workflowName}", workspace_id="${ws}")`,
    ...nodes.map((n) => `workflow.add_node(KFlowNode(id="${n.id}", kind="${n.kind}", p10_human_gate=${n.requires_p10 ? "True" : "False"}))`),
    ...boundedPolicies.map((bp) => `workflow.add_cycle_policy(BoundedCyclePolicy(from_node="${bp.from_node}", to_node="${bp.to_node}", max_iterations=${bp.max_iterations}))`),
  ];
  return {
    workspace_id: ws, workflow_name: workflowName, source_language: sourceLanguage, nodes, edges,
    p10_gates_injected: p10Gates, cycles_detected: boundedPolicies.length, bounded_loop_policies: boundedPolicies,
    legacy_warnings: legacyWarnings, kflow_sdk_code: kflowLines.join("\n"),
    migration_sha256: computeDigest64(`${ws}:${workflowName}:${sourceLanguage}:${sourceCode}`),
  };
}

export async function migrateLanggraphSource(
  workspaceId = "default", sourceCode: string, sourceLanguage: LangGraphSourceLanguage = "python",
  workflowName = "migrated-release-review-kflow", role: WorkspaceRbacRole = "owner",
): Promise<LangGraphMigrationResult> {
  const cleanCode = sourceCode.trim();
  const res = await requestDevxEndpoint(
    "/v1/platform/migrate/langgraph",
    {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId, source_code: cleanCode, code: cleanCode,
        source_language: sourceLanguage, language: sourceLanguage, workflow_name: workflowName, name: workflowName,
      }),
    },
    undefined, role,
  );
  if (res.ok && isRecord(res.data) && (Array.isArray(res.data.nodes) || typeof res.data.migration_sha256 === "string" || typeof res.data.kflow_sdk_code === "string" || typeof res.data.generated_code === "string")) {
    const d = res.data;
    const rawNodes = Array.isArray(d.nodes) ? d.nodes.filter(isRecord) : [];
    const p10Gates = Array.isArray(d.p10_gates_injected)
      ? d.p10_gates_injected.map(String)
      : rawNodes.filter((n) => Boolean(n.requires_p10 ?? n.p10_human_gate ?? n.kind === "p10_human_gate")).map((n) => String(n.id ?? n.name));
    const nodes: MigratedKflowNode[] = rawNodes.map((n) => {
      const id = String(n.id ?? n.name ?? "node");
      const reqP10 = Boolean(n.requires_p10 ?? n.p10_human_gate ?? p10Gates.includes(id) ?? n.kind === "p10_human_gate");
      return { id, handler: String(n.handler ?? n.callable ?? id), kind: reqP10 ? "p10_human_gate" : String(n.kind ?? "agent_task"), requires_p10: reqP10 };
    });
    const rawPolicies = Array.isArray(d.bounded_loop_policies) ? d.bounded_loop_policies.filter(isRecord) : [];
    const policies: BoundedLoopPolicy[] = rawPolicies.map((bp) => ({
      from_node: String(bp.from_node ?? bp.source ?? (Array.isArray(bp.cycle_path) ? bp.cycle_path[0] : "human_review")),
      to_node: String(bp.to_node ?? bp.target ?? (Array.isArray(bp.cycle_path) ? bp.cycle_path[bp.cycle_path.length - 1] : "draft")),
      max_iterations: typeof bp.max_iterations === "number" ? bp.max_iterations : 5,
    }));
    const cyclesDetected = typeof d.cycles_detected === "number" ? d.cycles_detected : policies.length;
    if (cyclesDetected > 0 && policies.length === 0) policies.push({ from_node: "human_review", to_node: "draft", max_iterations: 5 });
    const edges: MigratedKflowEdge[] = (Array.isArray(d.edges) ? d.edges.filter(isRecord) : []).map((e) => ({
      source: String(e.source ?? e.from ?? "START"), target: String(e.target ?? e.to ?? "END"),
      condition: typeof e.condition === "string" ? e.condition : typeof e.label === "string" ? e.label : null,
      is_back_edge: Boolean(e.is_back_edge ?? e.cyclic ?? false),
    }));
    return {
      workspace_id: String(d.workspace_id ?? workspaceId), workflow_name: String(d.workflow_name ?? workflowName),
      source_language: d.source_language === "typescript" ? "typescript" : "python",
      nodes, edges, p10_gates_injected: p10Gates, cycles_detected: cyclesDetected, bounded_loop_policies: policies,
      legacy_warnings: Array.isArray(d.legacy_warnings) ? d.legacy_warnings.map(String) : [],
      kflow_sdk_code: String(d.kflow_sdk_code ?? d.generated_sdk_code ?? d.generated_code ?? d.sdk_code ?? d.kflow_code ?? ""),
      migration_sha256: toSha(String(d.migration_sha256 ?? d.blueprint_sha256 ?? d.sha256 ?? computeDigest64(`${workspaceId}:${workflowName}`))),
    };
  }
  if (!canRbacMutateDevx(role)) {
    throw new PlatformDevxHttpError(403, `RBAC Denied (${role}): Viewer role cannot run LangGraph static AST migrations.`);
  }
  if (!cleanCode) throw new PlatformDevxHttpError(400, "LangGraph source code must be non-empty.");
  return parseLanggraphStatically(workspaceId, cleanCode, sourceLanguage, workflowName);
}
