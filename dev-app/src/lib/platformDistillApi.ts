import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type DistillRbacRole = RbacRoleId | "developer" | "auditor";
export type ShadowVerdict = "CACHE_HIT" | "LOCAL_PARITY_READY" | "SHADOW_CAPTURED";
export type ShadowMatchType = "exact_sha256" | "semantic_shingle" | "cache_miss";
export type ExportFormat = "sft_jsonl" | "dpo_preference";
export type PromotionVerdict = "PROMOTE_TO_OPENCORE" | "NEEDS_MORE_PAIRS" | "HOLD_ON_FRONTIER";

export interface EvaluateShadowPromptRequest {
  workspace_id?: string; task_tag?: string; prompt?: string; frontier_model?: string; local_model?: string;
  frontier_response?: string; local_response?: string; frontier_cost_usd?: number; frontier_latency_ms?: number;
  local_latency_ms?: number; similarity_threshold?: number; bypass_cache?: boolean;
}
export interface ShadowEvaluationRecord {
  evaluation_id: string; pair_id: string | null; cache_entry_id: string; workspace_id: string; task_tag: string;
  verdict: ShadowVerdict; match_type: ShadowMatchType; similarity_score: number; parity_score: number;
  frontier_model: string; local_model: string; scrubbed_prompt: string; cached_response: string;
  cost_saved_usd: number; latency_saved_ms: number; dlp_redactions: number; event_sha256: string; created_at: string;
}
export interface ShadowDistillPairRecord {
  pair_id: string; workspace_id: string; task_tag: string; scrubbed_prompt: string;
  scrubbed_frontier_response: string; scrubbed_local_response: string; frontier_model: string; local_model: string;
  parity_score: number; frontier_cost_usd: number; dlp_redactions: number; pair_sha256: string; created_at: string;
}
export interface ShadowPairListResponse { workspace_id: string; count: number; pairs: ShadowDistillPairRecord[]; }
export interface SemanticCacheStatsResponse {
  workspace_id: string; entry_count: number; total_hits: number; total_lookups: number; hit_rate: number;
  total_cost_saved_usd: number; total_latency_saved_ms: number; total_dlp_redactions: number;
}
export interface CompileDistillationDatasetRequest {
  workspace_id?: string; task_tag?: string; export_format?: ExportFormat; target_base_model?: string; min_parity_score?: number;
}
export interface DistillationDatasetRecord {
  dataset_id: string; workspace_id: string; task_tag: string; export_format: ExportFormat; target_base_model: string;
  record_count: number; avg_parity_score: number; lora_rank: number; lora_alpha: number; dlp_redactions: number;
  jsonl_preview: string; dataset_sha256: string; created_at: string;
}
export interface DistillationDatasetListResponse { workspace_id: string; count: number; datasets: DistillationDatasetRecord[]; }
export interface EvaluateDistillationPromotionRequest {
  workspace_id?: string; task_tag?: string; target_local_model?: string; min_pairs?: number;
  min_avg_parity?: number; monthly_request_volume?: number;
}
export interface DistillationPromotionEvaluation {
  evaluation_id: string; workspace_id: string; task_tag: string; target_local_model: string; verdict: PromotionVerdict;
  pair_count: number; min_pairs: number; avg_parity_score: number; min_avg_parity: number; avg_frontier_cost_usd: number;
  monthly_request_volume: number; projected_monthly_savings_usd: number; recommendation: string; gate_sha256: string; evaluated_at: string;
}

export class PlatformDistillHttpError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message); this.name = "PlatformDistillHttpError"; this.status = status; this.code = code;
  }
}

export function canRbacMutateDistill(role: DistillRbacRole): boolean {
  switch (role) {
    case "owner": case "admin": case "builder": case "developer": case "operator": return true;
    case "auditor": case "viewer": return false;
    default: { const _exhaustive: never = role; return _exhaustive; }
  }
}

interface FallbackCacheEntry { cache_entry_id: string; task_tag: string; scrubbed_prompt: string; cached_response: string; frontier_model: string; local_model: string; parity_score: number; dlp_redactions: number; }
interface FallbackStatsCounter { hits: number; lookups: number; costSaved: number; latencySaved: number; dlpRedactions: number; }

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const DEFAULT_CODE_SAMPLE = "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))";
const DLP_PATTERNS = [/Bearer\s+[^\s)",']+/gi, /sk-[A-Za-z0-9_-]{6,}/g, /AKIA[0-9A-Z]{8,}/g, /ghp_[A-Za-z0-9]{8,}/g, /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----/gi];
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const shaDigest = (seed: string): string => [1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`dst:${i}:${seed}`)).join("");
const skipTestFetch = (): boolean =>
  import.meta.env.MODE === "test" &&
  (typeof globalThis.fetch !== "function" || (!("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN));

const cacheByWs = new Map<string, FallbackCacheEntry[]>();
const pairsByWs = new Map<string, ShadowDistillPairRecord[]>();
const datasetsByWs = new Map<string, DistillationDatasetRecord[]>();
const statsByWs = new Map<string, FallbackStatsCounter>();
let localSeq = 0;

export function resetDistillFallbackStore(): void {
  cacheByWs.clear(); pairsByWs.clear(); datasetsByWs.clear(); statsByWs.clear(); localSeq = 0;
}

function scrubDlpText(raw: string): { scrubbed: string; redactions: number } {
  let scrubbed = raw; let redactions = 0;
  for (const pat of DLP_PATTERNS) scrubbed = scrubbed.replace(new RegExp(pat.source, pat.flags), () => { redactions += 1; return "[REDACTED_SECRET]"; });
  return { scrubbed, redactions };
}

function shingleSimilarity(a: string, b: string): number {
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
  const na = norm(a); const nb = norm(b);
  if (!na && !nb) return 1;
  if (!na || !nb) return 0;
  if (na === nb) return 1;
  const toSet = (s: string) => s.length < 3 ? new Set([s]) : new Set(Array.from({ length: s.length - 2 }, (_, i) => s.slice(i, i + 3)));
  const sa = toSet(na); const sb = toSet(nb);
  let inter = 0;
  for (const g of sa) if (sb.has(g)) inter += 1;
  const union = sa.size + sb.size - inter;
  return union > 0 ? Number((inter / union).toFixed(4)) : 0;
}

function assertMutateRbac(role: DistillRbacRole): void {
  if (!canRbacMutateDistill(role)) throw new PlatformDistillHttpError(403, `RBAC Denied (${role}): Read-only role cannot mutate shadow cache or distillation datasets.`);
}

async function apiRequest(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: DistillRbacRole, actor?: string): Promise<{ ok: boolean; status: number; data: unknown }> {
  if (!path.startsWith("/v1/platform/distill/")) throw new Error(`Security violation: /v1/platform/distill/* required, got ${path}`);
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
  if (actor) headers.set("X-Keelway-Actor", actor);
  else if (role && !headers.has("X-Keelway-Actor")) headers.set("X-Keelway-Actor", `studio-${role}`);
  if (token) { headers.set("Authorization", `Bearer ${token}`); headers.set("X-Studio-Token", token); headers.set("X-Keelway-Token", token); }
  let res: Response;
  try { res = await fetch(url, { ...init, credentials: "same-origin", headers }); } catch { return { ok: false, status: 0, data: null }; }
  const text = await res.text().catch(() => "");
  let data: unknown = null;
  if (text) { try { data = JSON.parse(text) as unknown; } catch { data = null; } }
  if (!res.ok && res.status >= 400) {
    const code = isRecord(data) && typeof data.code === "string" ? data.code : undefined;
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string" ? String(data.detail ?? data.error ?? data.message) : `Distillation request failed with HTTP ${res.status}.`;
    throw new PlatformDistillHttpError(res.status, detail, code);
  }
  return { ok: res.ok, status: res.status, data };
}

export async function evaluateShadowPrompt(req: EvaluateShadowPromptRequest = {}, role: DistillRbacRole = "owner", actor?: string): Promise<ShadowEvaluationRecord> {
  const ws = req.workspace_id ?? "default"; const taskTag = req.task_tag ?? "code-patch";
  const prompt = req.prompt ?? "Refactor retry loop with bounded exponential backoff in Python";
  const frontierModel = req.frontier_model ?? "claude-3-7-sonnet"; const localModel = req.local_model ?? "keelway-core:7b";
  const frontierResp = req.frontier_response ?? DEFAULT_CODE_SAMPLE; const localResp = req.local_response ?? DEFAULT_CODE_SAMPLE;
  const frontierCost = req.frontier_cost_usd ?? 0.018; const frontierLat = req.frontier_latency_ms ?? 840; const localLat = req.local_latency_ms ?? 95;
  const threshold = req.similarity_threshold ?? 0.82; const bypass = req.bypass_cache ?? false;
  const body = { workspace_id: ws, task_tag: taskTag, prompt, frontier_model: frontierModel, local_model: localModel, frontier_response: frontierResp, local_response: localResp, frontier_cost_usd: frontierCost, frontier_latency_ms: frontierLat, local_latency_ms: localLat, similarity_threshold: threshold, bypass_cache: bypass };
  const res = await apiRequest("/v1/platform/distill/shadow/evaluate", { method: "POST", body: JSON.stringify(body) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.evaluation_id === "string") return res.data as unknown as ShadowEvaluationRecord;
  assertMutateRbac(role);
  const sp = scrubDlpText(prompt); const sf = scrubDlpText(frontierResp); const sl = scrubDlpText(localResp);
  const redactions = sp.redactions + sf.redactions + sl.redactions;
  const entries = cacheByWs.get(ws) ?? [];
  const counter = statsByWs.get(ws) ?? { hits: 0, lookups: 0, costSaved: 0, latencySaved: 0, dlpRedactions: 0 };
  counter.lookups += 1; counter.dlpRedactions += redactions;
  let best: { entry: FallbackCacheEntry; sim: number; exact: boolean } | null = null;
  if (!bypass) {
    for (const e of entries) {
      if (e.task_tag !== taskTag) continue;
      const exact = e.scrubbed_prompt === sp.scrubbed;
      const sim = exact ? 1 : shingleSimilarity(sp.scrubbed, e.scrubbed_prompt);
      if (sim >= threshold && (!best || sim > best.sim)) best = { entry: e, sim, exact };
    }
  }
  localSeq += 1; const now = new Date().toISOString();
  const evalId = `shd-${computeLocalFingerprintHex(`${ws}:${taskTag}:${localSeq}`).slice(0, 12)}`;
  if (best) {
    const latencySaved = Math.max(0, frontierLat);
    counter.hits += 1; counter.costSaved = Number((counter.costSaved + frontierCost).toFixed(6)); counter.latencySaved += latencySaved;
    statsByWs.set(ws, counter);
    const matchType: ShadowMatchType = best.exact ? "exact_sha256" : "semantic_shingle";
    return { evaluation_id: evalId, pair_id: null, cache_entry_id: best.entry.cache_entry_id, workspace_id: ws, task_tag: taskTag, verdict: "CACHE_HIT", match_type: matchType, similarity_score: best.sim, parity_score: best.entry.parity_score, frontier_model: frontierModel, local_model: localModel, scrubbed_prompt: sp.scrubbed, cached_response: best.entry.cached_response, cost_saved_usd: frontierCost, latency_saved_ms: latencySaved, dlp_redactions: redactions, event_sha256: shaDigest(`${evalId}:CACHE_HIT:${matchType}:${best.entry.cache_entry_id}`), created_at: now };
  }
  const parity = shingleSimilarity(sf.scrubbed, sl.scrubbed);
  const verdict: ShadowVerdict = parity >= 0.85 ? "LOCAL_PARITY_READY" : "SHADOW_CAPTURED";
  const pairId = `pair-${computeLocalFingerprintHex(`${ws}:pair:${localSeq}`).slice(0, 12)}`;
  const cacheId = `scache-${computeLocalFingerprintHex(`${ws}:cache:${localSeq}`).slice(0, 12)}`;
  const pair: ShadowDistillPairRecord = { pair_id: pairId, workspace_id: ws, task_tag: taskTag, scrubbed_prompt: sp.scrubbed, scrubbed_frontier_response: sf.scrubbed, scrubbed_local_response: sl.scrubbed, frontier_model: frontierModel, local_model: localModel, parity_score: parity, frontier_cost_usd: frontierCost, dlp_redactions: redactions, pair_sha256: shaDigest(`${pairId}:${sp.scrubbed}:${parity}`), created_at: now };
  pairsByWs.set(ws, [pair, ...(pairsByWs.get(ws) ?? [])]);
  cacheByWs.set(ws, [{ cache_entry_id: cacheId, task_tag: taskTag, scrubbed_prompt: sp.scrubbed, cached_response: sf.scrubbed, frontier_model: frontierModel, local_model: localModel, parity_score: parity, dlp_redactions: redactions }, ...entries]);
  statsByWs.set(ws, counter);
  return { evaluation_id: evalId, pair_id: pairId, cache_entry_id: cacheId, workspace_id: ws, task_tag: taskTag, verdict, match_type: "cache_miss", similarity_score: 0, parity_score: parity, frontier_model: frontierModel, local_model: localModel, scrubbed_prompt: sp.scrubbed, cached_response: sf.scrubbed, cost_saved_usd: 0, latency_saved_ms: 0, dlp_redactions: redactions, event_sha256: shaDigest(`${evalId}:${verdict}:${pairId}`), created_at: now };
}

export async function fetchShadowPairs(workspaceId = "default", taskTag = "", limit = 25, role: DistillRbacRole = "owner", actor?: string): Promise<ShadowPairListResponse> {
  const res = await apiRequest("/v1/platform/distill/shadow/pairs", { method: "GET" }, { workspace_id: workspaceId, task_tag: taskTag, limit: String(limit) }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.pairs)) return res.data as unknown as ShadowPairListResponse;
  const filtered = (pairsByWs.get(workspaceId) ?? []).filter((p) => !taskTag || p.task_tag === taskTag).slice(0, limit);
  return { workspace_id: workspaceId, count: filtered.length, pairs: filtered };
}

export async function fetchSemanticCacheStats(workspaceId = "default", role: DistillRbacRole = "owner", actor?: string): Promise<SemanticCacheStatsResponse> {
  const res = await apiRequest("/v1/platform/distill/cache/stats", { method: "GET" }, { workspace_id: workspaceId }, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.entry_count === "number") return res.data as unknown as SemanticCacheStatsResponse;
  const entries = cacheByWs.get(workspaceId) ?? [];
  const c = statsByWs.get(workspaceId) ?? { hits: 0, lookups: 0, costSaved: 0, latencySaved: 0, dlpRedactions: 0 };
  return { workspace_id: workspaceId, entry_count: entries.length, total_hits: c.hits, total_lookups: c.lookups, hit_rate: c.lookups > 0 ? Number((c.hits / c.lookups).toFixed(4)) : 0, total_cost_saved_usd: Number(c.costSaved.toFixed(4)), total_latency_saved_ms: c.latencySaved, total_dlp_redactions: c.dlpRedactions };
}

function renderDatasetLine(fmt: ExportFormat, p: ShadowDistillPairRecord): string {
  switch (fmt) {
    case "dpo_preference": return JSON.stringify({ prompt: p.scrubbed_prompt, chosen: p.scrubbed_frontier_response, rejected: p.scrubbed_local_response, task_tag: p.task_tag });
    case "sft_jsonl": return JSON.stringify({ messages: [{ role: "user", content: p.scrubbed_prompt }, { role: "assistant", content: p.scrubbed_frontier_response }], task_tag: p.task_tag });
    default: { const _exhaustive: never = fmt; return _exhaustive; }
  }
}

export async function compileDistillationDataset(req: CompileDistillationDatasetRequest = {}, role: DistillRbacRole = "owner", actor?: string): Promise<DistillationDatasetRecord> {
  const ws = req.workspace_id ?? "default"; const taskTag = req.task_tag ?? ""; const fmt: ExportFormat = req.export_format ?? "dpo_preference";
  const baseModel = req.target_base_model ?? "keelway-core:7b"; const minParity = req.min_parity_score ?? 0;
  const res = await apiRequest("/v1/platform/distill/datasets/compile", { method: "POST", body: JSON.stringify({ workspace_id: ws, task_tag: taskTag, export_format: fmt, target_base_model: baseModel, min_parity_score: minParity }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.dataset_id === "string") return res.data as unknown as DistillationDatasetRecord;
  assertMutateRbac(role);
  const matching = (pairsByWs.get(ws) ?? []).filter((p) => (!taskTag || p.task_tag === taskTag) && p.parity_score >= minParity);
  const rawPreview = matching.slice(0, 5).map((p) => renderDatasetLine(fmt, p)).join("\n");
  const scrubbedPreview = scrubDlpText(rawPreview);
  const avgParity = matching.length > 0 ? Number((matching.reduce((s, p) => s + p.parity_score, 0) / matching.length).toFixed(4)) : 0;
  const totalDlp = matching.reduce((s, p) => s + p.dlp_redactions, 0) + scrubbedPreview.redactions;
  localSeq += 1; const dsId = `qlora-${computeLocalFingerprintHex(`${ws}:${fmt}:${localSeq}`).slice(0, 12)}`;
  const rec: DistillationDatasetRecord = { dataset_id: dsId, workspace_id: ws, task_tag: taskTag, export_format: fmt, target_base_model: baseModel, record_count: matching.length, avg_parity_score: avgParity, lora_rank: 16, lora_alpha: 32, dlp_redactions: totalDlp, jsonl_preview: scrubbedPreview.scrubbed, dataset_sha256: shaDigest(`${dsId}:${fmt}:${matching.length}:${scrubbedPreview.scrubbed}`), created_at: new Date().toISOString() };
  datasetsByWs.set(ws, [rec, ...(datasetsByWs.get(ws) ?? [])]);
  return rec;
}

export async function fetchDistillationDatasets(workspaceId = "default", limit = 25, role: DistillRbacRole = "owner", actor?: string): Promise<DistillationDatasetListResponse> {
  const res = await apiRequest("/v1/platform/distill/datasets", { method: "GET" }, { workspace_id: workspaceId, limit: String(limit) }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.datasets)) return res.data as unknown as DistillationDatasetListResponse;
  const sliced = (datasetsByWs.get(workspaceId) ?? []).slice(0, limit);
  return { workspace_id: workspaceId, count: sliced.length, datasets: sliced };
}

export async function evaluateDistillationPromotion(req: EvaluateDistillationPromotionRequest = {}, role: DistillRbacRole = "owner", actor?: string): Promise<DistillationPromotionEvaluation> {
  const ws = req.workspace_id ?? "default"; const taskTag = req.task_tag ?? "code-patch"; const targetModel = req.target_local_model ?? "keelway-core:7b";
  const minPairs = req.min_pairs ?? 3; const minAvgParity = req.min_avg_parity ?? 0.85; const monthlyVol = req.monthly_request_volume ?? 50000;
  const res = await apiRequest("/v1/platform/distill/promotion/evaluate", { method: "POST", body: JSON.stringify({ workspace_id: ws, task_tag: taskTag, target_local_model: targetModel, min_pairs: minPairs, min_avg_parity: minAvgParity, monthly_request_volume: monthlyVol }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.evaluation_id === "string") return res.data as unknown as DistillationPromotionEvaluation;
  assertMutateRbac(role);
  const matching = (pairsByWs.get(ws) ?? []).filter((p) => !taskTag || p.task_tag === taskTag);
  const pairCount = matching.length;
  const avgParity = pairCount > 0 ? Number((matching.reduce((s, p) => s + p.parity_score, 0) / pairCount).toFixed(4)) : 0;
  const avgFrontierCost = pairCount > 0 ? Number((matching.reduce((s, p) => s + p.frontier_cost_usd, 0) / pairCount).toFixed(4)) : 0.018;
  const verdict: PromotionVerdict = pairCount < minPairs ? "NEEDS_MORE_PAIRS" : avgParity < minAvgParity ? "HOLD_ON_FRONTIER" : "PROMOTE_TO_OPENCORE";
  const savings = verdict === "PROMOTE_TO_OPENCORE" ? Number((avgFrontierCost * monthlyVol).toFixed(2)) : 0;
  const recommendation = verdict === "PROMOTE_TO_OPENCORE" ? `Promote task '${taskTag}' to local OpenCore (${targetModel}) at $0.00/token.` : verdict === "NEEDS_MORE_PAIRS" ? `Capture at least ${minPairs} shadow pairs (currently ${pairCount}) before canary promotion.` : `Average parity ${avgParity.toFixed(2)} is below ${minAvgParity.toFixed(2)}; compile additional QLoRA preference pairs.`;
  localSeq += 1; const evalId = `promo-${computeLocalFingerprintHex(`${ws}:${taskTag}:${localSeq}`).slice(0, 12)}`;
  return { evaluation_id: evalId, workspace_id: ws, task_tag: taskTag, target_local_model: targetModel, verdict, pair_count: pairCount, min_pairs: minPairs, avg_parity_score: avgParity, min_avg_parity: minAvgParity, avg_frontier_cost_usd: avgFrontierCost, monthly_request_volume: monthlyVol, projected_monthly_savings_usd: savings, recommendation, gate_sha256: shaDigest(`${evalId}:${verdict}:${pairCount}:${avgParity}`), evaluated_at: new Date().toISOString() };
}
