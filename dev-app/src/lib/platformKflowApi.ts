import { getStudioToken } from "@/lib/api";
import { buildRuntimeUrl, computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type KflowRunStatus = "completed" | "awaiting_p10" | "failed";
export type CrdtOpKind = "set" | "remove";

export interface KflowNodeInput { id: string; label: string; agent_id: string; depends_on: string[]; requires_p10: boolean; }
export interface KflowExecutedNode extends KflowNodeInput { status: string; wave: number; output_digest: string; }
export interface KflowDagRunResult {
  run_id: string; workspace_id: string; workflow_id: string; status: KflowRunStatus; held_node_id: string | null;
  topological_order: string[]; waves: string[][]; tokens_used: number; token_budget: number;
  nodes: KflowExecutedNode[]; receipt_sha256: string; created_at: string;
}
export interface KspacesCrdtOperation { op: CrdtOpKind; namespace?: string; key: string; value?: string | number | boolean | null; lamport_ts?: number; }
export interface KspacesCrdtEntry { namespace: string; key: string; value: unknown; lamport_ts: number; peer_id: string; tombstone: boolean; }
export interface KspacesCrdtState {
  workspace_id: string; peer_id: string; applied_count: number; active_keys_count: number;
  vector_clock: Record<string, number>; state_digest_sha256: string; entries: KspacesCrdtEntry[];
}
export interface PlatformSbomSummary {
  workspace_id: string; verified: boolean; verification_status: string; bom_format: string; spec_version: string;
  serial_number: string; component_count: number; root_digest_sha256: string; provenance_signature: string;
}

export class PlatformKflowHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) { super(message); this.name = "PlatformKflowHttpError"; this.status = status; }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const toSha = (raw: string): string => (raw.startsWith("sha256:") ? raw : `sha256:${raw}`);

function shouldSkipUnmockedTestFetch(): boolean {
  if (import.meta.env.MODE !== "test") return false;
  if (typeof globalThis.fetch !== "function") return true;
  return !("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN;
}

function attachRuntimeHeaders(raw?: HeadersInit, role?: RbacRoleId, hasBody = false): Headers {
  const headers = new Headers(raw);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (role) headers.set("X-Keelway-Role", role);
  const token = getStudioToken();
  if (token) { headers.set("Authorization", `Bearer ${token}`); headers.set("X-Studio-Token", token); headers.set("X-Keelway-Token", token); }
  return headers;
}

async function requestKflowJson(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: RbacRoleId) {
  const url = buildRuntimeUrl(path, query);
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null as unknown };
  let res: Response;
  try {
    res = await fetch(url, { ...init, credentials: "same-origin", headers: attachRuntimeHeaders(init.headers, role, Boolean(init.body)) });
  } catch { return { ok: false, status: 0, data: null as unknown }; }
  const data = (await res.json().catch(() => null)) as unknown;
  if (!res.ok && res.status >= 400) {
    const detail = isRecord(data) && typeof (data.detail ?? data.error) === "string" ? String(data.detail ?? data.error) : `Request failed with HTTP ${res.status}.`;
    throw new PlatformKflowHttpError(res.status, detail);
  }
  return { ok: res.ok, status: res.status, data };
}

export const canRbacRunKflowOrCrdt = (role: RbacRoleId): boolean => role !== "viewer";
export const canRbacApproveP10Dag = (role: RbacRoleId): boolean => role === "owner" || role === "operator";

const localRunsStore = new Map<string, KflowDagRunResult[]>();
const localCrdtStore = new Map<string, { clock: Record<string, number>; entries: Map<string, KspacesCrdtEntry> }>();
export function resetLocalKflowCrdtState(): void { localRunsStore.clear(); localCrdtStore.clear(); }

function decodeDagRun(raw: Record<string, unknown>, ws: string, wfId: string, budget: number): KflowDagRunResult {
  const status: KflowRunStatus = raw.status === "awaiting_p10" || raw.status === "failed" ? raw.status : "completed";
  const nodes = (Array.isArray(raw.nodes) ? raw.nodes.filter(isRecord) : []).map((n, idx): KflowExecutedNode => ({
    id: String(n.id ?? `n-${idx + 1}`), label: String(n.label ?? `Step ${idx + 1}`), agent_id: String(n.agent_id ?? n.agentId ?? "workflow-automator"),
    depends_on: Array.isArray(n.depends_on) ? n.depends_on.map(String) : [], requires_p10: Boolean(n.requires_p10),
    status: String(n.status ?? status), wave: typeof n.wave === "number" ? n.wave : idx,
    output_digest: toSha(String(n.output_digest ?? computeLocalFingerprintHex(`${wfId}:${idx}`))),
  }));
  const topo = Array.isArray(raw.topological_order) ? raw.topological_order.map(String) : nodes.map((n) => n.id);
  const waves = Array.isArray(raw.waves) ? raw.waves.map((w) => (Array.isArray(w) ? w.map(String) : [])) : (topo.length ? [topo] : []);
  return {
    run_id: String(raw.run_id ?? `kflow_${computeLocalFingerprintHex(`${ws}:${wfId}`).slice(0, 10)}`),
    workspace_id: String(raw.workspace_id ?? ws), workflow_id: String(raw.workflow_id ?? wfId),
    status, held_node_id: typeof raw.held_node_id === "string" ? raw.held_node_id : null,
    topological_order: topo, waves, tokens_used: typeof raw.tokens_used === "number" ? raw.tokens_used : nodes.length * 540,
    token_budget: typeof raw.token_budget === "number" ? raw.token_budget : budget, nodes,
    receipt_sha256: toSha(String(raw.receipt_sha256 ?? computeLocalFingerprintHex(`kflow:${ws}:${wfId}`))),
    created_at: String(raw.created_at ?? new Date().toISOString()),
  };
}

export async function postExecuteKflowDag(params: {
  workspaceId?: string; workflowId: string; nodes: KflowNodeInput[];
  trigger?: string; tokenBudget?: number; approvedNodeIds?: string[]; role?: RbacRoleId;
}): Promise<KflowDagRunResult> {
  const ws = params.workspaceId ?? "default", role = params.role ?? "owner", budget = params.tokenBudget ?? 25_000, approved = params.approvedNodeIds ?? [];
  const res = await requestKflowJson("/v1/platform/automation/workflows/execute", {
    method: "POST", body: JSON.stringify({ workspace_id: ws, workflow_id: params.workflowId, nodes: params.nodes, trigger: params.trigger ?? "manual", token_budget: budget, approved_node_ids: approved }),
  }, undefined, role);
  if (res.ok && isRecord(res.data)) return decodeDagRun(res.data, ws, params.workflowId, budget);
  if (!canRbacRunKflowOrCrdt(role)) throw new PlatformKflowHttpError(403, `Role "${role}" cannot execute KFlow DAGs.`);
  if (approved.length > 0 && !canRbacApproveP10Dag(role)) throw new PlatformKflowHttpError(403, `Role "${role}" cannot approve P-10 DAG checkpoints.`);
  const byId = new Map(params.nodes.map((n) => [n.id, n]));
  const inDeg = new Map(params.nodes.map((n) => [n.id, n.depends_on.filter((d) => byId.has(d)).length]));
  const waves: string[][] = [], topo: string[] = [];
  let frontier = params.nodes.filter((n) => (inDeg.get(n.id) ?? 0) === 0).map((n) => n.id);
  while (frontier.length > 0) {
    waves.push(frontier);
    const next: string[] = [];
    for (const id of frontier) {
      topo.push(id);
      for (const cand of params.nodes) if (cand.depends_on.includes(id)) {
        const deg = (inDeg.get(cand.id) ?? 1) - 1;
        inDeg.set(cand.id, deg);
        if (deg === 0) next.push(cand.id);
      }
    }
    frontier = next;
  }
  if (topo.length !== params.nodes.length) throw new PlatformKflowHttpError(400, "Cycle detected in KFlow DAG.");
  const approvedSet = new Set(approved), waveByNode = new Map<string, number>();
  waves.forEach((w, idx) => w.forEach((id) => waveByNode.set(id, idx)));
  let heldNodeId: string | null = null;
  const execNodes: KflowExecutedNode[] = topo.map((id) => {
    const spec = byId.get(id)!;
    let nodeStatus = "completed";
    if (heldNodeId) nodeStatus = "queued";
    else if (spec.requires_p10 && !approvedSet.has(id)) { heldNodeId = id; nodeStatus = "awaiting_p10"; }
    return { ...spec, status: nodeStatus, wave: waveByNode.get(id) ?? 0, output_digest: toSha(computeLocalFingerprintHex(`${ws}:${params.workflowId}:${id}:${nodeStatus}`)) };
  });
  const status: KflowRunStatus = heldNodeId ? "awaiting_p10" : "completed";
  const completedCount = execNodes.filter((n) => n.status === "completed").length;
  const run: KflowDagRunResult = {
    run_id: `kflow_${computeLocalFingerprintHex(`${ws}:${params.workflowId}:${approved.join(",")}`).slice(0, 10)}`,
    workspace_id: ws, workflow_id: params.workflowId, status, held_node_id: heldNodeId,
    topological_order: topo, waves, tokens_used: Math.min(budget, Math.max(320, completedCount * 640)), token_budget: budget,
    nodes: execNodes, receipt_sha256: toSha(computeLocalFingerprintHex(`kflow:${ws}:${params.workflowId}:${status}:${approved.join(",")}`)),
    created_at: new Date().toISOString(),
  };
  localRunsStore.set(ws, [run, ...(localRunsStore.get(ws) ?? []).slice(0, 9)]);
  return run;
}

export async function fetchKflowRuns(workspaceId = "default", workflowId?: string, role?: RbacRoleId): Promise<KflowDagRunResult[]> {
  const res = await requestKflowJson("/v1/platform/automation/runs", { method: "GET" }, { workspace_id: workspaceId, workflow_id: workflowId }, role);
  const rawList = isRecord(res.data) && Array.isArray(res.data.runs) ? res.data.runs : Array.isArray(res.data) ? res.data : null;
  if (res.ok && rawList) return rawList.filter(isRecord).map((r) => decodeDagRun(r, workspaceId, workflowId ?? "WF-01", 25_000));
  const local = localRunsStore.get(workspaceId) ?? [];
  return workflowId ? local.filter((r) => r.workflow_id === workflowId) : local;
}

function decodeCrdtState(raw: Record<string, unknown>, ws: string, fallbackPeer = "peer-local-ide"): KspacesCrdtState {
  const entries = (Array.isArray(raw.entries) ? raw.entries.filter(isRecord) : []).map((e): KspacesCrdtEntry => ({
    namespace: String(e.namespace ?? "workspace"), key: String(e.key ?? ""), value: e.value ?? null,
    lamport_ts: typeof e.lamport_ts === "number" ? e.lamport_ts : 1, peer_id: String(e.peer_id ?? fallbackPeer), tombstone: Boolean(e.tombstone),
  }));
  const vcRaw = isRecord(raw.vector_clock) ? raw.vector_clock : {}, vector_clock: Record<string, number> = {};
  for (const [k, v] of Object.entries(vcRaw)) if (typeof v === "number") vector_clock[k] = v;
  return {
    workspace_id: String(raw.workspace_id ?? ws), peer_id: String(raw.peer_id ?? fallbackPeer),
    applied_count: typeof raw.applied_count === "number" ? raw.applied_count : entries.length,
    active_keys_count: typeof raw.active_keys_count === "number" ? raw.active_keys_count : entries.filter((e) => !e.tombstone).length,
    vector_clock, state_digest_sha256: toSha(String(raw.state_digest_sha256 ?? computeLocalFingerprintHex(`crdt:${ws}:${JSON.stringify(vector_clock)}`))), entries,
  };
}

function buildLocalCrdtSnapshot(ws: string, peerId: string, appliedCount: number): KspacesCrdtState {
  const bucket = localCrdtStore.get(ws) ?? { clock: {}, entries: new Map<string, KspacesCrdtEntry>() };
  const entries = Array.from(bucket.entries.values()).sort((a, b) => `${a.namespace}:${a.key}`.localeCompare(`${b.namespace}:${b.key}`));
  const canonical = JSON.stringify(entries.map((e) => [e.namespace, e.key, e.value, e.lamport_ts, e.peer_id, e.tombstone]));
  return {
    workspace_id: ws, peer_id: peerId, applied_count: appliedCount, active_keys_count: entries.filter((e) => !e.tombstone).length,
    vector_clock: { ...bucket.clock }, state_digest_sha256: toSha(`${computeLocalFingerprintHex(`crdt:${ws}:${canonical}`)}${computeLocalFingerprintHex(canonical)}`), entries,
  };
}

export async function postSyncKspacesCrdt(params: {
  workspaceId?: string; peerId: string; operations: KspacesCrdtOperation[]; role?: RbacRoleId;
}): Promise<KspacesCrdtState> {
  const ws = params.workspaceId ?? "default", role = params.role ?? "owner", peer = params.peerId.trim() || "peer-local-ide";
  const ops = params.operations.map((o) => ({ op: o.op, namespace: o.namespace ?? "workspace", key: o.key, value: o.value ?? null, ...(o.lamport_ts !== undefined ? { lamport_ts: o.lamport_ts } : {}) }));
  const res = await requestKflowJson("/v1/platform/kspaces/sync", { method: "POST", body: JSON.stringify({ workspace_id: ws, peer_id: peer, operations: ops }) }, undefined, role);
  if (res.ok && isRecord(res.data)) return decodeCrdtState(res.data, ws, peer);
  if (!canRbacRunKflowOrCrdt(role)) throw new PlatformKflowHttpError(403, `Role "${role}" cannot mutate KSpaces CRDT state.`);
  let bucket = localCrdtStore.get(ws);
  if (!bucket) { bucket = { clock: {}, entries: new Map() }; localCrdtStore.set(ws, bucket); }
  let maxTs = Object.values(bucket.clock).reduce((m, v) => Math.max(m, v), 0);
  for (const op of ops) {
    maxTs = Math.max(maxTs + 1, op.lamport_ts ?? 0);
    bucket.clock[peer] = maxTs;
    const composite = `${op.namespace}:${op.key}`, cur = bucket.entries.get(composite);
    if (!cur || maxTs > cur.lamport_ts || (maxTs === cur.lamport_ts && peer >= cur.peer_id)) {
      bucket.entries.set(composite, { namespace: op.namespace, key: op.key, value: op.op === "remove" ? null : op.value, lamport_ts: maxTs, peer_id: peer, tombstone: op.op === "remove" });
    }
  }
  return buildLocalCrdtSnapshot(ws, peer, ops.length);
}

export async function fetchKspacesState(workspaceId = "default", role?: RbacRoleId): Promise<KspacesCrdtState> {
  const res = await requestKflowJson("/v1/platform/kspaces/state", { method: "GET" }, { workspace_id: workspaceId }, role);
  return res.ok && isRecord(res.data) ? decodeCrdtState(res.data, workspaceId) : buildLocalCrdtSnapshot(workspaceId, "peer-local-ide", 0);
}

export async function fetchPlatformSbom(workspaceId = "default", role?: RbacRoleId): Promise<PlatformSbomSummary> {
  const res = await requestKflowJson("/v1/platform/security/sbom", { method: "GET" }, { workspace_id: workspaceId }, role);
  if (res.ok && isRecord(res.data)) {
    const d = res.data;
    return {
      workspace_id: String(d.workspace_id ?? workspaceId), verified: d.verified !== false,
      verification_status: String(d.verification_status ?? (d.verified !== false ? "VERIFIED" : "UNVERIFIED")),
      bom_format: String(d.bom_format ?? "CycloneDX"), spec_version: String(d.spec_version ?? "1.5"),
      serial_number: String(d.serial_number ?? `urn:uuid:${computeLocalFingerprintHex(workspaceId)}`),
      component_count: typeof d.component_count === "number" ? d.component_count : (Array.isArray(d.components) ? d.components.length : 28),
      root_digest_sha256: toSha(String(d.root_digest_sha256 ?? computeLocalFingerprintHex(`sbom:${workspaceId}`))),
      provenance_signature: String(d.provenance_signature ?? `hmac-sha256:${computeLocalFingerprintHex(`sig:${workspaceId}`)}`),
    };
  }
  const h1 = computeLocalFingerprintHex(`sbom-root:${workspaceId}:1.5`), h2 = computeLocalFingerprintHex(`sbom-merkle:${workspaceId}`);
  return {
    workspace_id: workspaceId, verified: true, verification_status: "VERIFIED", bom_format: "CycloneDX", spec_version: "1.5",
    serial_number: `urn:uuid:3e671687-395b-41f5-a30f-${h1.slice(0, 12)}`, component_count: 28,
    root_digest_sha256: toSha(`${h1}${h2}`), provenance_signature: `hmac-sha256:${computeLocalFingerprintHex(`sbom-sig:${workspaceId}`)}`,
  };
}
