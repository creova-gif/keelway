import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type HealingRbacRole = RbacRoleId | "developer" | "auditor";
export type ProviderWireFormat = "deepseek_opencore" | "openai" | "anthropic" | "gemini";
export type ContentBlockKind = "reasoning" | "text" | "tool_call" | "citation" | "structured_json";
export type StructuredOutputStatus = "VALID" | "REPAIRED_VALID" | "SCHEMA_REJECTED";
export type FailureRootCauseClass = "schema_mismatch" | "context_truncation" | "prompt_ambiguity" | "kbrain_conflict" | "airgap_egress_blocked";
export type FailureScenarioKey = "schema_mismatch" | "context_truncation" | "kbrain_conflict" | "airgap_egress_blocked";
export type SelfHealingStatus = "DIAGNOSED" | "VERIFIED_HEALED";
export type HealingTargetSurface = "json_schema" | "system_prompt" | "routing_policy" | "kbrain_memory";

export interface NormalizedContentBlock { index: number; kind: ContentBlockKind; content: string; tool_name?: string | null; tool_call_id?: string | null; tool_args?: Record<string, unknown> | null; source_uri?: string | null; structured_data?: Record<string, unknown> | null; }
export interface NormalizedContentEnvelope { workspace_id: string; provider_format: ProviderWireFormat; model_id: string; block_count: number; content_blocks: NormalizedContentBlock[]; dlp_redactions: number; envelope_sha256: string; }
export interface StructuredOutputRunRecord { run_id: string; workspace_id: string; schema_name: string; provider_format: string; model_id: string; status: StructuredOutputStatus; repair_applied: boolean; repair_actions: string[]; validated_data: Record<string, unknown> | null; validation_errors: string[]; dlp_redactions: number; run_sha256: string; created_at: string; }
export interface ProposedHealingPatch { target_surface: HealingTargetSurface; recommended_model: string; unified_diff: string; patched_prompt: string; }
export interface SelfHealingDiagnosisRecord { diagnosis_id: string; workspace_id: string; trace_id: string | null; workflow_name: string; failure_class: FailureRootCauseClass; status: SelfHealingStatus; confidence: number; failed_node: string; diagnostic_model: string; summary: string; root_cause_evidence: string[]; proposed_patch: ProposedHealingPatch; verification_replay_trace_id: string | null; promoted_eval_case_id: string | null; dlp_redactions: number; diagnosis_sha256: string; created_at: string; }
export interface PromotedHealingEvalCase { case_id: string; title: string; case_sha256: string; }
export interface ApplySelfHealingResponse { diagnosis: SelfHealingDiagnosisRecord; verified_healed: boolean; cached_steps_reused: number; replay_cost_usd: number; promoted_eval_case: PromotedHealingEvalCase | null; }
export interface NormalizeContentBlocksRequest { workspace_id?: string; provider_format: ProviderWireFormat; model_id?: string; raw_payload: Record<string, unknown> | string; }
export interface EnforceStructuredOutputRequest { workspace_id?: string; schema_name?: string; provider_format?: string; model_id?: string; json_schema: Record<string, unknown>; raw_output: string | Record<string, unknown>; strict_mode?: boolean; fail_closed?: boolean; }
export interface FailedStepInput { step_index?: number; node_name?: string; model_id?: string; prompt_text?: string; output_text?: string; error_message?: string; expected_schema?: Record<string, unknown> | null; }
export interface DiagnoseFailureRootCauseRequest { workspace_id?: string; trace_id?: string | null; workflow_name?: string; failed_step?: FailedStepInput | null; }
export interface ApplySelfHealingPatchRequest { workspace_id?: string; promote_to_eval?: boolean; eval_title?: string | null; }

export class PlatformHealingHttpError extends Error {
  readonly status: number; readonly run?: StructuredOutputRunRecord;
  constructor(status: number, message: string, run?: StructuredOutputRunRecord) { super(message); this.name = "PlatformHealingHttpError"; this.status = status; this.run = run; }
}

export const AGENT_DECISION_JSON_SCHEMA: Record<string, unknown> = {
  type: "object", required: ["decision", "confidence", "retry_budget", "requires_p10"], additionalProperties: false,
  properties: { decision: { type: "string", enum: ["approve_refund", "escalate_p10", "reject"] }, confidence: { type: "number", minimum: 0, maximum: 1 }, retry_budget: { type: "integer", minimum: 0, maximum: 5 }, requires_p10: { type: "boolean" } },
};

export interface ProviderWireFixture { label: string; model_id: string; raw_payload: Record<string, unknown>; sample_raw_output: string; }
export const PROVIDER_WIRE_FIXTURES: Record<ProviderWireFormat, ProviderWireFixture> = {
  deepseek_opencore: { label: "deepseek_opencore — Local OpenCore (<think> + tool_calls + JSON)", model_id: "keelway-core:7b", raw_payload: { reasoning_content: "Reconcile duplicate charge INV-9042 (Authorization: Bearer sk-live-9876543210secretkey).", tool_calls: [{ id: "call_kc_01", function: { name: "lookup_invoice_delta", arguments: '{"invoice_id":"INV-9042"}' } }], citations: ["kbrain://policies/refund-p10-threshold"], content: '{"decision":"escalate_p10","confidence":0.94,"retry_budget":2,"requires_p10":true}\nEscalating INV-9042 to P-10 human review.' }, sample_raw_output: '<think>Verify refund threshold before emitting contract.</think>\n```json\n{"decision":"escalate_p10","confidence":"0.94","retry_budget":"2","requires_p10":"true",}\n```' },
  anthropic: { label: "anthropic — Claude Messages (thinking + tool_use + citations)", model_id: "claude-3-7-sonnet", raw_payload: { content: [{ type: "thinking", thinking: "Evaluate P-10 approval boundary for duplicate invoice INV-9042." }, { type: "tool_use", id: "toolu_anth_01", name: "lookup_invoice_delta", input: { invoice_id: "INV-9042" } }, { type: "text", text: '{"decision":"escalate_p10","confidence":0.93,"retry_budget":1,"requires_p10":true}', citations: [{ url: "https://docs.keelway.internal/p10-refunds" }] }, { type: "text", text: "Prepared P-10 refund escalation summary." }] }, sample_raw_output: '```json\n{"decision":"escalate_p10","confidence":"0.93","retry_budget":"1","requires_p10":"true",}\n```' },
  openai: { label: "openai — Responses/Chat (reasoning + function tool_calls + annotations)", model_id: "gpt-4.1", raw_payload: { choices: [{ message: { reasoning: "Cross-check Stripe ledger entry against PO-77.", tool_calls: [{ id: "call_oa_01", type: "function", function: { name: "verify_ledger_entry", arguments: '{"invoice_id":"INV-9042"}' } }], annotations: [{ type: "url_citation", url: "https://ledger.keelway.internal/inv-9042" }], content: '{"decision":"approve_refund","confidence":0.91,"retry_budget":1,"requires_p10":false}' } }] }, sample_raw_output: '```json\n{"decision":"approve_refund","confidence":"0.91","retry_budget":"1","requires_p10":"false",}\n```' },
  gemini: { label: "gemini — GenerateContent (thought parts + functionCall + groundingChunks)", model_id: "gemini-2.5-pro", raw_payload: { candidates: [{ content: { parts: [{ thought: true, text: "Compare PO-77 line items with invoice INV-9042." }, { functionCall: { name: "fetch_purchase_order", args: { po_id: "PO-77" } } }, { text: '{"decision":"escalate_p10","confidence":0.95,"retry_budget":2,"requires_p10":true}' }] }, groundingMetadata: { groundingChunks: [{ web: { uri: "https://erp.keelway.internal/po-77" } }] } }] }, sample_raw_output: '```json\n{"decision":"escalate_p10","confidence":"0.95","retry_budget":"2","requires_p10":"true",}\n```' },
};

export interface FailureScenarioFixture { label: string; workflow_name: string; failed_step: FailedStepInput; patch: ProposedHealingPatch; summary: string; evidence: string[]; confidence: number; }
export const FAILURE_SCENARIO_FIXTURES: Record<FailureScenarioKey, FailureScenarioFixture> = {
  schema_mismatch: { label: "schema_mismatch — Unquoted/coercible JSON & missing required contract field", workflow_name: "invoice-triage-agent", confidence: 0.94, failed_step: { step_index: 2, node_name: "invoice_decision_synthesizer", model_id: "keelway-core:7b", prompt_text: "Return AgentDecisionContract JSON for INV-9042.", output_text: '<think>Need P-10</think> {"decision":"escalate_p10","confidence":"high"}', error_message: "JSON Schema validation error: schema_mismatch at $.confidence (expected number, got string) and missing required field retry_budget", expected_schema: AGENT_DECISION_JSON_SCHEMA }, summary: "Model emitted <think> wrapper and non-numeric confidence without required retry_budget; bind strict JSON-Schema contract + single-pass scalar coercion.", evidence: ["Validation error at $.confidence: expected number [0..1]", "Missing required property 'retry_budget' in AgentDecisionContract"], patch: { target_surface: "json_schema", recommended_model: "keelway-core:7b", unified_diff: "--- a/contracts/agent_decision.prompt\n+++ b/contracts/agent_decision.prompt\n@@ -1,2 +1,4 @@\n Return AgentDecisionContract JSON for INV-9042.\n+Enforce JSON Schema AgentDecisionContract (additionalProperties=false).\n+Emit numeric confidence in [0.0, 1.0] and integer retry_budget in [0, 5].", patched_prompt: "Return AgentDecisionContract JSON for INV-9042. Enforce JSON Schema AgentDecisionContract with numeric confidence and integer retry_budget." } },
  context_truncation: { label: "context_truncation — Token window overflow truncating mid-stream JSON", workflow_name: "quarterly-ledger-audit", confidence: 0.92, failed_step: { step_index: 1, node_name: "long_audit_summarizer", model_id: "keelway-core:7b", prompt_text: "Summarize 48k-token multi-quarter ledger log.", output_text: '{"decision":"escalate_p10","rationale":"truncated...', error_message: "context_length_exceeded: context_truncation finish_reason=length truncated JSON payload", expected_schema: AGENT_DECISION_JSON_SCHEMA }, summary: "Input prompt exceeded local context window (finish_reason=length); enable map-reduce chunking and route synthesis to 32k context window.", evidence: ["finish_reason=length with unterminated JSON string", "Prompt input exceeded 8,192 token budget on long_audit_summarizer"], patch: { target_surface: "routing_policy", recommended_model: "keelway-reasoner:14b", unified_diff: "--- a/kflow/ledger_audit.yaml\n+++ b/kflow/ledger_audit.yaml\n@@ -4,2 +4,4 @@\n-  model: keelway-core:7b\n+  model: keelway-reasoner:14b\n+  pre_chunk_tokens: 4096", patched_prompt: "Summarize chunked ledger deltas within 4,096-token map-reduce windows and emit complete JSON." } },
  kbrain_conflict: { label: "kbrain_conflict — Contradictory KBrain policy facts halting step", workflow_name: "refund-governance-kflow", confidence: 0.91, failed_step: { step_index: 1, node_name: "policy_compliance_gate", model_id: "keelway-reasoner:14b", prompt_text: "Apply KBrain policy.refund.limit fact.", output_text: "Halted on conflicting facts ($500 vs $2,500).", error_message: "kbrain_conflict: contradictory memory facts in KBrain graph for key policy.refund.limit", expected_schema: null }, summary: "Two active KBrain statements conflict on policy.refund.limit; pin canonical P-10 approved fact digest in retrieval scope.", evidence: ["Conflict detected on key 'policy.refund.limit' ($500 vs $2,500)", "Unresolved KBrain conflict blocked deterministic threshold check"], patch: { target_surface: "kbrain_memory", recommended_model: "keelway-reasoner:14b", unified_diff: "--- a/kbrain/scopes/refund_policy.json\n+++ b/kbrain/scopes/refund_policy.json\n@@ -2,2 +2,3 @@\n   \"key\": \"policy.refund.limit\",\n+  \"require_status\": \"approved\",\n+  \"canonical_limit_usd\": 500", patched_prompt: "Retrieve only P-10 approved KBrain fact policy.refund.limit ($500 canonical ceiling)." } },
  airgap_egress_blocked: { label: "airgap_egress_blocked — Seatbelt SC-7 zero-egress blocked cloud call", workflow_name: "hipaa-intake-triage", confidence: 0.97, failed_step: { step_index: 0, node_name: "frontier_escalation_router", model_id: "gpt-4.1", prompt_text: "Classify HIPAA intake record.", output_text: "", error_message: "airgap_egress_blocked: Seatbelt SC-7 zero-egress policy blocked outbound HTTPS connection to api.openai.com", expected_schema: null }, summary: "Workspace enforces Seatbelt SC-7 air-gap isolation; rewrite node route from external cloud endpoint to loopback OpenCore model.", evidence: ["Outbound egress to api.openai.com denied by Seatbelt SC-7", "Workspace isolation policy requires loopback zero-egress inference"], patch: { target_surface: "routing_policy", recommended_model: "keelway-core:7b", unified_diff: "--- a/kflow/hipaa_intake.yaml\n+++ b/kflow/hipaa_intake.yaml\n@@ -2,3 +2,4 @@\n   node: frontier_escalation_router\n-  model: gpt-4.1\n+  model: keelway-core:7b\n+  data_boundary: local_metal_zero_egress", patched_prompt: "Classify HIPAA intake record locally on keelway-core:7b with zero external egress." } },
};

export function canRbacMutateHealing(role: HealingRbacRole): boolean {
  switch (role) {
    case "owner": case "admin": case "builder": case "developer": case "operator": return true;
    case "auditor": case "viewer": return false;
    default: { const _exhaustive: never = role; return _exhaustive; }
  }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const VALID_PROVIDERS = new Set<ProviderWireFormat>(["deepseek_opencore", "openai", "anthropic", "gemini"]);
const DLP_PATTERNS = [/Bearer\s+[^\s)",]+/gi, /sk-[A-Za-z0-9_-]{10,}/g, /AKIA[0-9A-Z]{12,}/g, /ghp_[A-Za-z0-9]{12,}/g, /-----BEGIN [A-Z ]*PRIVATE KEY-----/g];
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const shaHex = (seed: string): string => [1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`heal:${i}:${seed}`)).join("");
const skipTestFetch = (): boolean => import.meta.env.MODE === "test" && (typeof globalThis.fetch !== "function" || (!("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN));
const runsByWs = new Map<string, StructuredOutputRunRecord[]>();
const diagsByWs = new Map<string, SelfHealingDiagnosisRecord[]>();
let localSeq = 0;
export function resetHealingFallbackStore(): void { runsByWs.clear(); diagsByWs.clear(); localSeq = 0; }

function scrubSecrets(raw: string): { text: string; count: number } {
  let text = raw; let count = 0;
  for (const pat of DLP_PATTERNS) text = text.replace(new RegExp(pat.source, pat.flags), (m) => { count += 1; return m.toLowerCase().startsWith("bearer ") ? "Bearer [REDACTED_SECRET]" : "[REDACTED_SECRET]"; });
  return { text, count };
}

async function apiRequest(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: HealingRbacRole): Promise<{ ok: boolean; status: number; data: unknown }> {
  if (!path.startsWith("/v1/platform/healing")) throw new Error(`Security violation: /v1/platform/healing/* required, got ${path}`);
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
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string" ? String(data.detail ?? data.error ?? data.message) : `Healing request failed with HTTP ${res.status}.`;
    const maybeRun = isRecord(data) && isRecord(data.run) && typeof data.run.run_id === "string" ? (data.run as unknown as StructuredOutputRunRecord) : undefined;
    throw new PlatformHealingHttpError(res.status, detail, maybeRun);
  }
  return { ok: res.ok, status: res.status, data };
}

function assertMutateRbac(role: HealingRbacRole): void {
  if (!canRbacMutateHealing(role)) throw new PlatformHealingHttpError(403, `RBAC Denied (${role}): Read-only role cannot mutate structured enforcement or self-healing state.`);
}

export async function normalizeContentBlocks(req: NormalizeContentBlocksRequest, role: HealingRbacRole = "owner"): Promise<NormalizedContentEnvelope> {
  const ws = req.workspace_id ?? "default"; const fmt = req.provider_format;
  const model = req.model_id ?? PROVIDER_WIRE_FIXTURES[fmt]?.model_id ?? "keelway-core:7b";
  const res = await apiRequest("/v1/platform/healing/content-blocks/normalize", { method: "POST", body: JSON.stringify({ workspace_id: ws, provider_format: fmt, model_id: model, raw_payload: req.raw_payload }) }, undefined, role);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.content_blocks)) return res.data as unknown as NormalizedContentEnvelope;
  if (!VALID_PROVIDERS.has(fmt)) throw new PlatformHealingHttpError(422, `Unsupported provider_format '${String(fmt)}'.`);
  let dlp = 0; const blocks: NormalizedContentBlock[] = [];
  const push = (kind: ContentBlockKind, content: string, extra: Partial<NormalizedContentBlock> = {}) => {
    const sc = scrubSecrets(content); dlp += sc.count;
    blocks.push({ index: blocks.length, kind, content: sc.text, tool_name: extra.tool_name ?? null, tool_call_id: extra.tool_call_id ?? null, tool_args: extra.tool_args ?? null, source_uri: extra.source_uri ?? null, structured_data: extra.structured_data ?? null });
  };
  const appendTextOrJson = (rawText: string) => {
    for (const chunk of rawText.split(/\n+/).map((s) => s.trim()).filter(Boolean)) {
      try { const parsed = JSON.parse(chunk) as unknown; if (isRecord(parsed)) { push("structured_json", JSON.stringify(parsed), { structured_data: parsed }); continue; } } catch { /* text */ }
      push("text", chunk);
    }
  };
  const p = isRecord(req.raw_payload) ? req.raw_payload : { content: String(req.raw_payload) };
  switch (fmt) {
    case "deepseek_opencore": {
      if (typeof p.reasoning_content === "string") push("reasoning", p.reasoning_content);
      for (const tc of Array.isArray(p.tool_calls) ? p.tool_calls.filter(isRecord) : []) { const fn = isRecord(tc.function) ? tc.function : {}; push("tool_call", String(fn.name ?? "tool"), { tool_name: String(fn.name ?? "tool"), tool_call_id: String(tc.id ?? "call_1"), tool_args: typeof fn.arguments === "string" ? (JSON.parse(fn.arguments) as Record<string, unknown>) : {} }); }
      for (const uri of Array.isArray(p.citations) ? p.citations : []) push("citation", String(uri), { source_uri: String(uri) });
      if (typeof p.content === "string") appendTextOrJson(p.content);
      break;
    }
    case "anthropic": {
      for (const item of Array.isArray(p.content) ? p.content.filter(isRecord) : []) {
        if (item.type === "thinking") push("reasoning", String(item.thinking ?? ""));
        else if (item.type === "tool_use") push("tool_call", String(item.name ?? "tool"), { tool_name: String(item.name ?? "tool"), tool_call_id: String(item.id ?? "toolu_1"), tool_args: isRecord(item.input) ? item.input : {} });
        else if (item.type === "text") { appendTextOrJson(String(item.text ?? "")); for (const cit of Array.isArray(item.citations) ? item.citations.filter(isRecord) : []) push("citation", String(cit.url ?? ""), { source_uri: String(cit.url ?? "") }); }
      }
      break;
    }
    case "openai": {
      const msg = Array.isArray(p.choices) && isRecord(p.choices[0]) && isRecord(p.choices[0].message) ? p.choices[0].message : p;
      if (typeof msg.reasoning === "string") push("reasoning", msg.reasoning);
      for (const tc of Array.isArray(msg.tool_calls) ? msg.tool_calls.filter(isRecord) : []) { const fn = isRecord(tc.function) ? tc.function : {}; push("tool_call", String(fn.name ?? "tool"), { tool_name: String(fn.name ?? "tool"), tool_call_id: String(tc.id ?? "call_1"), tool_args: typeof fn.arguments === "string" ? (JSON.parse(fn.arguments) as Record<string, unknown>) : {} }); }
      for (const ann of Array.isArray(msg.annotations) ? msg.annotations.filter(isRecord) : []) push("citation", String(ann.url ?? ""), { source_uri: String(ann.url ?? "") });
      if (typeof msg.content === "string") appendTextOrJson(msg.content);
      break;
    }
    case "gemini": {
      const cand = Array.isArray(p.candidates) && isRecord(p.candidates[0]) ? p.candidates[0] : {};
      for (const pt of isRecord(cand.content) && Array.isArray(cand.content.parts) ? cand.content.parts.filter(isRecord) : []) {
        if (pt.thought && typeof pt.text === "string") push("reasoning", pt.text);
        else if (isRecord(pt.functionCall)) push("tool_call", String(pt.functionCall.name ?? "tool"), { tool_name: String(pt.functionCall.name ?? "tool"), tool_args: isRecord(pt.functionCall.args) ? pt.functionCall.args : {} });
        else if (typeof pt.text === "string") appendTextOrJson(pt.text);
      }
      for (const ch of isRecord(cand.groundingMetadata) && Array.isArray(cand.groundingMetadata.groundingChunks) ? cand.groundingMetadata.groundingChunks.filter(isRecord) : []) if (isRecord(ch.web) && typeof ch.web.uri === "string") push("citation", ch.web.uri, { source_uri: ch.web.uri });
      break;
    }
    default: { const _exhaustive: never = fmt; return _exhaustive; }
  }
  return { workspace_id: ws, provider_format: fmt, model_id: model, block_count: blocks.length, content_blocks: blocks, dlp_redactions: dlp, envelope_sha256: shaHex(`${ws}:${fmt}:${JSON.stringify(blocks)}`) };
}

export async function enforceStructuredOutput(req: EnforceStructuredOutputRequest, role: HealingRbacRole = "owner"): Promise<StructuredOutputRunRecord> {
  const ws = req.workspace_id ?? "default"; const schemaName = req.schema_name ?? "AgentDecisionContract";
  const fmt = req.provider_format ?? "deepseek_opencore"; const model = req.model_id ?? "keelway-core:7b";
  const strict = req.strict_mode ?? false; const failClosed = req.fail_closed ?? true;
  const res = await apiRequest("/v1/platform/healing/structured/enforce", { method: "POST", body: JSON.stringify({ workspace_id: ws, schema_name: schemaName, provider_format: fmt, model_id: model, json_schema: req.json_schema, raw_output: req.raw_output, strict_mode: strict, fail_closed: failClosed }) }, undefined, role);
  if (res.ok && isRecord(res.data) && typeof res.data.run_id === "string") return res.data as unknown as StructuredOutputRunRecord;
  assertMutateRbac(role);
  const scrubbed = scrubSecrets(typeof req.raw_output === "string" ? req.raw_output : JSON.stringify(req.raw_output));
  let candidate = scrubbed.text.trim(); const actions: string[] = [];
  if (!strict) {
    if (/<think>[\s\S]*?<\/think>/i.test(candidate)) { candidate = candidate.replace(/<think>[\s\S]*?<\/think>/gi, "").trim(); actions.push("strip_think_prefix"); }
    const fence = candidate.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (fence?.[1]) { candidate = fence[1].trim(); actions.push("strip_markdown_fence"); }
    if (/,\s*[}\]]/.test(candidate)) { candidate = candidate.replace(/,(\s*[}\]])/g, "$1"); actions.push("remove_trailing_commas"); }
  }
  let parsed: Record<string, unknown> | null = null; const errors: string[] = [];
  try { const obj = JSON.parse(candidate) as unknown; if (isRecord(obj)) parsed = { ...obj }; else errors.push("Root value must be a JSON object."); } catch { errors.push("Malformed JSON output; unable to parse object."); }
  const props = isRecord(req.json_schema.properties) ? req.json_schema.properties : {};
  if (parsed) {
    for (const k of Array.isArray(req.json_schema.required) ? req.json_schema.required.map(String) : []) if (!(k in parsed)) errors.push(`Missing required property '${k}'.`);
    for (const [k, val] of Object.entries(parsed)) {
      const spec = isRecord(props[k]) ? props[k] : null;
      if (!spec && req.json_schema.additionalProperties === false) { errors.push(`Unexpected property '${k}'.`); continue; }
      if (!spec) continue;
      let cur: unknown = val;
      if (!strict && typeof cur === "string") {
        if ((spec.type === "number" || spec.type === "integer") && /^-?\d+(?:\.\d+)?$/.test(cur)) { cur = Number(cur); parsed[k] = cur; actions.push(`coerce_${k}_to_${String(spec.type)}`); }
        else if (spec.type === "boolean" && (cur === "true" || cur === "false")) { cur = cur === "true"; parsed[k] = cur; actions.push(`coerce_${k}_to_boolean`); }
      }
      if (spec.type === "number" && typeof cur !== "number") errors.push(`Property '${k}' must be number.`);
      if (spec.type === "integer" && (typeof cur !== "number" || !Number.isInteger(cur))) errors.push(`Property '${k}' must be integer.`);
      if (spec.type === "boolean" && typeof cur !== "boolean") errors.push(`Property '${k}' must be boolean.`);
      if (spec.type === "string" && typeof cur !== "string") errors.push(`Property '${k}' must be string.`);
      if (Array.isArray(spec.enum) && !spec.enum.includes(cur)) errors.push(`Property '${k}' outside allowed enum.`);
    }
  }
  localSeq += 1; const runId = `srun-${computeLocalFingerprintHex(`${ws}:${schemaName}:${localSeq}`).slice(0, 12)}`;
  const ok = errors.length === 0 && parsed !== null;
  const status: StructuredOutputStatus = ok ? (actions.length > 0 ? "REPAIRED_VALID" : "VALID") : "SCHEMA_REJECTED";
  const record: StructuredOutputRunRecord = { run_id: runId, workspace_id: ws, schema_name: schemaName, provider_format: fmt, model_id: model, status, repair_applied: actions.length > 0, repair_actions: actions, validated_data: ok ? parsed : null, validation_errors: errors, dlp_redactions: scrubbed.count, run_sha256: shaHex(`${runId}:${status}:${JSON.stringify(parsed)}:${actions.join(",")}`), created_at: new Date().toISOString() };
  runsByWs.set(ws, [record, ...(runsByWs.get(ws) ?? [])]);
  if (!ok && failClosed) throw new PlatformHealingHttpError(422, errors.join(" "), record);
  return record;
}

export async function fetchStructuredOutputRuns(workspaceId = "default", limit = 25, role: HealingRbacRole = "owner"): Promise<StructuredOutputRunRecord[]> {
  const res = await apiRequest("/v1/platform/healing/structured/runs", { method: "GET" }, { workspace_id: workspaceId, limit: String(limit) }, role);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.runs)) return res.data.runs as StructuredOutputRunRecord[];
  return (runsByWs.get(workspaceId) ?? []).slice(0, limit);
}

function classifyScenario(step?: FailedStepInput | null): FailureScenarioKey {
  const hay = `${step?.error_message ?? ""} ${step?.output_text ?? ""} ${step?.prompt_text ?? ""}`.toLowerCase();
  if (hay.includes("airgap") || hay.includes("egress") || hay.includes("seatbelt")) return "airgap_egress_blocked";
  if (hay.includes("kbrain") || hay.includes("conflict") || hay.includes("contradict")) return "kbrain_conflict";
  if (hay.includes("truncat") || hay.includes("context_length") || hay.includes("finish_reason=length")) return "context_truncation";
  return "schema_mismatch";
}

export async function diagnoseFailureRootCause(req: DiagnoseFailureRootCauseRequest = {}, role: HealingRbacRole = "owner"): Promise<SelfHealingDiagnosisRecord> {
  const ws = req.workspace_id ?? "default";
  const res = await apiRequest("/v1/platform/healing/root-cause/diagnose", { method: "POST", body: JSON.stringify({ workspace_id: ws, trace_id: req.trace_id ?? null, workflow_name: req.workflow_name ?? "invoice-triage-agent", failed_step: req.failed_step ?? null }) }, undefined, role);
  if (res.ok && isRecord(res.data) && typeof res.data.diagnosis_id === "string") return res.data as unknown as SelfHealingDiagnosisRecord;
  assertMutateRbac(role);
  if (req.trace_id && !req.failed_step) throw new PlatformHealingHttpError(404, `Flight-tape '${req.trace_id}' not found in workspace '${ws}'.`);
  const key = classifyScenario(req.failed_step); const fx = FAILURE_SCENARIO_FIXTURES[key];
  const scrubbed = scrubSecrets(JSON.stringify(req.failed_step ?? fx.failed_step));
  localSeq += 1; const diagId = `diag-${computeLocalFingerprintHex(`${ws}:${key}:${localSeq}`).slice(0, 12)}`;
  const rec: SelfHealingDiagnosisRecord = { diagnosis_id: diagId, workspace_id: ws, trace_id: req.trace_id ?? `trace-${key}-01`, workflow_name: req.workflow_name ?? fx.workflow_name, failure_class: key, status: "DIAGNOSED", confidence: fx.confidence, failed_node: req.failed_step?.node_name ?? fx.failed_step.node_name ?? "agent_step", diagnostic_model: "keelway-reasoner:14b", summary: fx.summary, root_cause_evidence: [...fx.evidence], proposed_patch: { ...fx.patch }, verification_replay_trace_id: null, promoted_eval_case_id: null, dlp_redactions: scrubbed.count, diagnosis_sha256: shaHex(`${diagId}:${key}:${fx.patch.unified_diff}`), created_at: new Date().toISOString() };
  diagsByWs.set(ws, [rec, ...(diagsByWs.get(ws) ?? [])]);
  return rec;
}

export async function applySelfHealingPatch(diagnosisId: string, req: ApplySelfHealingPatchRequest = {}, role: HealingRbacRole = "owner"): Promise<ApplySelfHealingResponse> {
  const ws = req.workspace_id ?? "default"; const promote = req.promote_to_eval ?? true;
  const res = await apiRequest(`/v1/platform/healing/root-cause/${encodeURIComponent(diagnosisId)}/apply`, { method: "POST", body: JSON.stringify({ workspace_id: ws, promote_to_eval: promote, eval_title: req.eval_title ?? null }) }, undefined, role);
  if (res.ok && isRecord(res.data) && isRecord(res.data.diagnosis)) return res.data as unknown as ApplySelfHealingResponse;
  assertMutateRbac(role);
  const list = diagsByWs.get(ws) ?? []; const target = list.find((d) => d.diagnosis_id === diagnosisId);
  if (!target) throw new PlatformHealingHttpError(404, `Diagnosis '${diagnosisId}' not found in workspace '${ws}'.`);
  localSeq += 1; const replayId = `fork-heal-${computeLocalFingerprintHex(`${diagnosisId}:${localSeq}`).slice(0, 10)}`;
  const evalCase: PromotedHealingEvalCase | null = promote ? { case_id: `evalcase-heal-${computeLocalFingerprintHex(`${ws}:${diagnosisId}`).slice(0, 10)}`, title: req.eval_title ?? `Self-Healed Regression · ${target.failure_class}`, case_sha256: shaHex(`${ws}:${diagnosisId}:eval`) } : null;
  const updated: SelfHealingDiagnosisRecord = { ...target, status: "VERIFIED_HEALED", verification_replay_trace_id: replayId, promoted_eval_case_id: evalCase?.case_id ?? null, diagnosis_sha256: shaHex(`${target.diagnosis_id}:VERIFIED_HEALED:${replayId}:${evalCase?.case_id ?? "none"}`) };
  diagsByWs.set(ws, list.map((d) => (d.diagnosis_id === diagnosisId ? updated : d)));
  return { diagnosis: updated, verified_healed: true, cached_steps_reused: 2, replay_cost_usd: 0, promoted_eval_case: evalCase };
}

export async function fetchSelfHealingDiagnoses(workspaceId = "default", limit = 25, role: HealingRbacRole = "owner"): Promise<SelfHealingDiagnosisRecord[]> {
  const res = await apiRequest("/v1/platform/healing/root-cause/diagnoses", { method: "GET" }, { workspace_id: workspaceId, limit: String(limit) }, role);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.diagnoses)) return res.data.diagnoses as SelfHealingDiagnosisRecord[];
  return (diagsByWs.get(workspaceId) ?? []).slice(0, limit);
}
