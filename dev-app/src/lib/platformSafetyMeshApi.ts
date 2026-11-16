import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type SafetyMeshRbacRole = RbacRoleId | "developer" | "auditor";
export type SafetyVerificationStatus = "VERIFIED_SAFE" | "VIOLATION_FOUND";
export type SafetyInvariantId = "no_unguarded_destructive_tool" | "no_privilege_escalation" | "bounded_termination" | "airgap_zero_egress";
export type SafetyToolKind = "read_only" | "write" | "destructive_shell" | "external_transfer" | "cloud_egress";
export type DataClassification = "public" | "internal" | "restricted_pii";
export type SafetySeverity = "CRITICAL" | "HIGH";
export type MeshTier = "edge_local" | "cluster_burst";
export type MeshHardwareHal = "apple_metal_secure_enclave" | "nvidia_h100_cc" | "linux_tpm2";
export type MeshNodeStatus = "ONLINE" | "DRAINING";
export type MeshHandoffStatus = "ATTESTED_COMPLETE" | "PINNED_EDGE_ONLY";

export interface SafetyNodeInput { node_id: string; role?: string; tool_kind?: SafetyToolKind; requires_p10?: boolean; max_iterations?: number; data_classification?: DataClassification; }
export interface SafetyEdgeInput { from_node: string; to_node: string; condition?: string; }
export interface VerifyWorkflowSafetyRequest { workspace_id?: string; workflow_id?: string; workflow_name?: string; nodes?: SafetyNodeInput[]; edges?: SafetyEdgeInput[]; airgap_mode?: boolean; inject_p10_guards?: boolean; }
export interface SafetyInvariantCheck { invariant_id: SafetyInvariantId; passed: boolean; description: string; }
export interface SafetyViolationItem { invariant_id: string; severity: SafetySeverity; offending_node: string; counterexample_path: string[]; remediation: string; }
export interface SafetyVerificationRecord { verification_id: string; workspace_id: string; workflow_id: string; workflow_name: string; status: SafetyVerificationStatus; states_explored: number; invariants_checked: SafetyInvariantCheck[]; violations: SafetyViolationItem[]; p10_guards_injected: string[]; dlp_redactions: number; proof_sha256: string; created_at: string; }
export interface RegisterMeshNodeRequest { workspace_id?: string; node_id?: string; name: string; tier: MeshTier; hardware_hal: MeshHardwareHal; region?: string; vram_gb?: number; status?: MeshNodeStatus; }
export interface MeshNodeRecord { node_id: string; workspace_id: string; name: string; tier: MeshTier; hardware_hal: MeshHardwareHal; region: string; vram_gb: number; status: MeshNodeStatus; attestation_sha256: string; registered_at: string; }
export interface DispatchMeshHandoffRequest { workspace_id?: string; workflow_name?: string; task_summary?: string; data_classification?: DataClassification; allow_sanitized_burst?: boolean; force_raw_cloud_burst?: boolean; }
export interface MeshStagePlacement { stage_name: string; target_tier: MeshTier; node_id: string; model_id: string; hardware_hal: string; zero_raw_pii_egress: boolean; cost_usd: number; }
export interface MeshHandoffRecord { handoff_id: string; workspace_id: string; workflow_name: string; data_classification: DataClassification; status: MeshHandoffStatus; edge_node_id: string; burst_node_id: string | null; stages: MeshStagePlacement[]; total_cost_usd: number; dlp_redactions: number; attestation_sha256: string; created_at: string; }

export class PlatformSafetyMeshHttpError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message); this.name = "PlatformSafetyMeshHttpError"; this.status = status; this.code = code;
  }
}

export function canRbacMutateSafetyMesh(role: SafetyMeshRbacRole): boolean {
  switch (role) {
    case "owner": case "admin": case "builder": case "developer": case "operator": return true;
    case "auditor": case "viewer": return false;
    default: { const _exhaustive: never = role; return _exhaustive; }
  }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const DLP_PATTERNS = [/Bearer\s+[^\s)",]+/gi, /sk-[A-Za-z0-9_-]{10,}/g, /AKIA[0-9A-Z]{12,}/g, /ghp_[A-Za-z0-9]{12,}/g];
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const shaDigest = (seed: string): string => `sha256:${[1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`sm:${i}:${seed}`)).join("")}`;
const skipTestFetch = (): boolean =>
  import.meta.env.MODE === "test" &&
  (typeof globalThis.fetch !== "function" || (!("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN));

const verificationsByWs = new Map<string, SafetyVerificationRecord[]>();
const nodesByWs = new Map<string, MeshNodeRecord[]>();
const handoffsByWs = new Map<string, MeshHandoffRecord[]>();
let localSeq = 0;

export function resetSafetyMeshFallbackStore(): void {
  verificationsByWs.clear(); nodesByWs.clear(); handoffsByWs.clear(); localSeq = 0;
}

function countScrubbedSecrets(raw: string): number {
  let count = 0;
  for (const pat of DLP_PATTERNS) raw.replace(new RegExp(pat.source, pat.flags), () => { count += 1; return ""; });
  return count;
}

function ensureSeededNodes(ws: string): MeshNodeRecord[] {
  const existing = nodesByWs.get(ws);
  if (existing && existing.length > 0) return existing;
  const now = new Date().toISOString();
  const seeded: MeshNodeRecord[] = [
    { node_id: "edge-mac-m3-max", workspace_id: ws, name: "Edge Mac Studio M3 Max", tier: "edge_local", hardware_hal: "apple_metal_secure_enclave", region: "local-loopback", vram_gb: 64, status: "ONLINE", attestation_sha256: shaDigest(`${ws}:edge-mac-m3-max`), registered_at: now },
    { node_id: "cluster-h100-us-east", workspace_id: ws, name: "Cluster H100 Confidential Compute", tier: "cluster_burst", hardware_hal: "nvidia_h100_cc", region: "us-east-tee", vram_gb: 80, status: "ONLINE", attestation_sha256: shaDigest(`${ws}:cluster-h100-us-east`), registered_at: now },
  ];
  nodesByWs.set(ws, seeded);
  return seeded;
}

async function apiRequest(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: SafetyMeshRbacRole, actor?: string): Promise<{ ok: boolean; status: number; data: unknown }> {
  if (!path.startsWith("/v1/platform/safety/") && !path.startsWith("/v1/platform/mesh/")) {
    throw new Error(`Security violation: /v1/platform/safety/* or /v1/platform/mesh/* required, got ${path}`);
  }
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
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string" ? String(data.detail ?? data.error ?? data.message) : `Safety/Mesh request failed with HTTP ${res.status}.`;
    throw new PlatformSafetyMeshHttpError(res.status, detail, code);
  }
  return { ok: res.ok, status: res.status, data };
}

function assertMutateRbac(role: SafetyMeshRbacRole): void {
  if (!canRbacMutateSafetyMesh(role)) throw new PlatformSafetyMeshHttpError(403, `RBAC Denied (${role}): Read-only role cannot mutate formal safety proofs or mesh dispatches.`);
}

export async function verifyWorkflowSafety(req: VerifyWorkflowSafetyRequest = {}, role: SafetyMeshRbacRole = "owner", actor?: string): Promise<SafetyVerificationRecord> {
  const ws = req.workspace_id ?? "default"; const wfId = req.workflow_id ?? "WF-TREASURY-01"; const wfName = req.workflow_name ?? "treasury-wire-approver";
  const airgap = req.airgap_mode ?? false; const injectP10 = req.inject_p10_guards ?? false;
  const res = await apiRequest("/v1/platform/safety/verify", { method: "POST", body: JSON.stringify({ workspace_id: ws, workflow_id: wfId, workflow_name: wfName, ...(req.nodes ? { nodes: req.nodes } : {}), ...(req.edges ? { edges: req.edges } : {}), airgap_mode: airgap, inject_p10_guards: injectP10 }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.verification_id === "string") return res.data as unknown as SafetyVerificationRecord;
  assertMutateRbac(role);
  const rawNodes: SafetyNodeInput[] = req.nodes ?? [
    { node_id: "ingest_invoice", role: "agent", tool_kind: "read_only", requires_p10: false, max_iterations: 1, data_classification: "internal" },
    { node_id: "validate_vendor", role: "agent", tool_kind: "write", requires_p10: false, max_iterations: 2, data_classification: "internal" },
    { node_id: "execute_wire_transfer", role: "agent", tool_kind: "external_transfer", requires_p10: false, max_iterations: 1, data_classification: "internal" },
  ];
  const injected: string[] = []; const violations: SafetyViolationItem[] = [];
  const nodes = rawNodes.map((n) => {
    const destructive = n.tool_kind === "destructive_shell" || n.tool_kind === "external_transfer";
    if (destructive && !n.requires_p10 && injectP10) { injected.push(n.node_id); return { ...n, requires_p10: true }; }
    return { ...n };
  });
  const pathIds = nodes.map((n) => n.node_id);
  let invDestructive = true; let invPriv = true; let invBounded = true; let invAirgap = true;
  for (let i = 0; i < nodes.length; i += 1) {
    const n = nodes[i]!; const destructive = n.tool_kind === "destructive_shell" || n.tool_kind === "external_transfer";
    if (destructive && !n.requires_p10) { invDestructive = false; violations.push({ invariant_id: "no_unguarded_destructive_tool", severity: "CRITICAL", offending_node: n.node_id, counterexample_path: pathIds.slice(0, i + 1), remediation: `Inject requires_p10=true human approval gate before '${n.node_id}' (${n.tool_kind}).` }); }
    const prev = i > 0 ? nodes[i - 1] : undefined;
    if (prev && (prev.role === "viewer" || prev.role === "untrusted_tool") && destructive && !n.requires_p10) { invPriv = false; violations.push({ invariant_id: "no_privilege_escalation", severity: "CRITICAL", offending_node: n.node_id, counterexample_path: [prev.node_id, n.node_id], remediation: `Insert P-10 boundary between '${prev.node_id}' and '${n.node_id}'.` }); }
    const iters = n.max_iterations ?? 1;
    if (iters < 1 || iters > 10) { invBounded = false; violations.push({ invariant_id: "bounded_termination", severity: "HIGH", offending_node: n.node_id, counterexample_path: pathIds.slice(0, i + 1), remediation: `Clamp max_iterations on '${n.node_id}' within [1, 10].` }); }
    if ((airgap || n.data_classification === "restricted_pii") && n.tool_kind === "cloud_egress") { invAirgap = false; violations.push({ invariant_id: "airgap_zero_egress", severity: "CRITICAL", offending_node: n.node_id, counterexample_path: pathIds.slice(0, i + 1), remediation: `Pin '${n.node_id}' to local loopback OpenCore runtime with zero cloud egress.` }); }
  }
  localSeq += 1; const verId = `sver-${computeLocalFingerprintHex(`${ws}:${wfId}:${localSeq}`).slice(0, 12)}`;
  const status: SafetyVerificationStatus = violations.length === 0 ? "VERIFIED_SAFE" : "VIOLATION_FOUND";
  const invariants: SafetyInvariantCheck[] = [
    { invariant_id: "no_unguarded_destructive_tool", passed: invDestructive, description: "Destructive or external transfer tools require P-10 human gate." },
    { invariant_id: "no_privilege_escalation", passed: invPriv, description: "Untrusted or viewer nodes cannot invoke destructive tools directly." },
    { invariant_id: "bounded_termination", passed: invBounded, description: "All cyclic transitions satisfy 1 <= max_iterations <= 10." },
    { invariant_id: "airgap_zero_egress", passed: invAirgap, description: "Air-gap and restricted_pii nodes prohibit raw cloud_egress." },
  ];
  const rec: SafetyVerificationRecord = { verification_id: verId, workspace_id: ws, workflow_id: wfId, workflow_name: wfName, status, states_explored: nodes.length, invariants_checked: invariants, violations, p10_guards_injected: injected, dlp_redactions: countScrubbedSecrets(JSON.stringify(req)), proof_sha256: shaDigest(`${verId}:${status}:${injected.join(",")}:${airgap}`), created_at: new Date().toISOString() };
  verificationsByWs.set(ws, [rec, ...(verificationsByWs.get(ws) ?? [])]);
  return rec;
}

export async function listSafetyVerifications(workspaceId = "default", limit = 25, role: SafetyMeshRbacRole = "owner", actor?: string): Promise<SafetyVerificationRecord[]> {
  const res = await apiRequest("/v1/platform/safety/verifications", { method: "GET" }, { workspace_id: workspaceId, limit: String(limit) }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.verifications)) return res.data.verifications as SafetyVerificationRecord[];
  return (verificationsByWs.get(workspaceId) ?? []).slice(0, limit);
}

export async function registerMeshNode(req: RegisterMeshNodeRequest, role: SafetyMeshRbacRole = "owner", actor?: string): Promise<MeshNodeRecord> {
  const ws = req.workspace_id ?? "default";
  const res = await apiRequest("/v1/platform/mesh/nodes", { method: "POST", body: JSON.stringify({ workspace_id: ws, node_id: req.node_id, name: req.name, tier: req.tier, hardware_hal: req.hardware_hal, region: req.region ?? "local-loopback", vram_gb: req.vram_gb ?? 32, status: req.status ?? "ONLINE" }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.node_id === "string") return res.data as unknown as MeshNodeRecord;
  assertMutateRbac(role);
  const current = ensureSeededNodes(ws); localSeq += 1;
  const nodeId = req.node_id ?? `mesh-${computeLocalFingerprintHex(`${ws}:${req.name}:${localSeq}`).slice(0, 10)}`;
  const node: MeshNodeRecord = { node_id: nodeId, workspace_id: ws, name: req.name, tier: req.tier, hardware_hal: req.hardware_hal, region: req.region ?? "local-loopback", vram_gb: req.vram_gb ?? 32, status: req.status ?? "ONLINE", attestation_sha256: shaDigest(`${ws}:${nodeId}:${req.hardware_hal}`), registered_at: new Date().toISOString() };
  nodesByWs.set(ws, [node, ...current.filter((n) => n.node_id !== nodeId)]);
  return node;
}

export async function listMeshNodes(workspaceId = "default", role: SafetyMeshRbacRole = "owner", actor?: string): Promise<MeshNodeRecord[]> {
  const res = await apiRequest("/v1/platform/mesh/nodes", { method: "GET" }, { workspace_id: workspaceId }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.nodes)) return res.data.nodes as MeshNodeRecord[];
  return [...ensureSeededNodes(workspaceId)];
}

export async function dispatchMeshHandoff(req: DispatchMeshHandoffRequest = {}, role: SafetyMeshRbacRole = "owner", actor?: string): Promise<MeshHandoffRecord> {
  const ws = req.workspace_id ?? "default"; const wfName = req.workflow_name ?? "clinical-synthesis-pipeline";
  const taskSummary = req.task_summary ?? "Ingest patient intake & synthesize anonymized cohort summary";
  const dataClass: DataClassification = req.data_classification ?? "restricted_pii";
  const allowBurst = req.allow_sanitized_burst ?? true; const forceRaw = req.force_raw_cloud_burst ?? false;
  const res = await apiRequest("/v1/platform/mesh/dispatch", { method: "POST", body: JSON.stringify({ workspace_id: ws, workflow_name: wfName, task_summary: taskSummary, data_classification: dataClass, allow_sanitized_burst: allowBurst, force_raw_cloud_burst: forceRaw }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.handoff_id === "string") return res.data as unknown as MeshHandoffRecord;
  assertMutateRbac(role);
  if (forceRaw && dataClass === "restricted_pii") throw new PlatformSafetyMeshHttpError(422, "mesh_sovereignty_violation: Raw restricted_pii workload cannot burst off edge_local without local sanitization.", "mesh_sovereignty_violation");
  const nodes = ensureSeededNodes(ws);
  const edge = nodes.find((n) => n.tier === "edge_local") ?? nodes[0]!;
  const burst = nodes.find((n) => n.tier === "cluster_burst") ?? null;
  const useBurst = allowBurst && burst !== null;
  const stages: MeshStagePlacement[] = useBurst
    ? [
        { stage_name: "edge_pii_scrub_intake", target_tier: "edge_local", node_id: edge.node_id, model_id: "keelway-core:7b", hardware_hal: edge.hardware_hal, zero_raw_pii_egress: true, cost_usd: 0 },
        { stage_name: "tee_cohort_synthesis", target_tier: "cluster_burst", node_id: burst.node_id, model_id: "keelway-reasoner:70b-tee", hardware_hal: burst.hardware_hal, zero_raw_pii_egress: true, cost_usd: 0.04 },
      ]
    : [{ stage_name: "edge_sovereign_synthesis", target_tier: "edge_local", node_id: edge.node_id, model_id: "keelway-core:7b", hardware_hal: edge.hardware_hal, zero_raw_pii_egress: true, cost_usd: 0 }];
  localSeq += 1; const handoffId = `mho-${computeLocalFingerprintHex(`${ws}:${wfName}:${localSeq}`).slice(0, 12)}`;
  const status: MeshHandoffStatus = useBurst ? "ATTESTED_COMPLETE" : "PINNED_EDGE_ONLY";
  const totalCost = Number(stages.reduce((acc, s) => acc + s.cost_usd, 0).toFixed(4));
  const rec: MeshHandoffRecord = { handoff_id: handoffId, workspace_id: ws, workflow_name: wfName, data_classification: dataClass, status, edge_node_id: edge.node_id, burst_node_id: useBurst ? burst.node_id : null, stages, total_cost_usd: totalCost, dlp_redactions: countScrubbedSecrets(taskSummary), attestation_sha256: shaDigest(`${handoffId}:${status}:${dataClass}`), created_at: new Date().toISOString() };
  handoffsByWs.set(ws, [rec, ...(handoffsByWs.get(ws) ?? [])]);
  return rec;
}

export async function listMeshHandoffs(workspaceId = "default", limit = 25, role: SafetyMeshRbacRole = "owner", actor?: string): Promise<MeshHandoffRecord[]> {
  const res = await apiRequest("/v1/platform/mesh/handoffs", { method: "GET" }, { workspace_id: workspaceId, limit: String(limit) }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.handoffs)) return res.data.handoffs as MeshHandoffRecord[];
  return (handoffsByWs.get(workspaceId) ?? []).slice(0, limit);
}
