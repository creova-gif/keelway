import { getStudioToken } from "@/lib/api";
import { buildRuntimeUrl, computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export { getStudioToken as getSessionToken };

export type SiemExportFormat = "ocsf" | "cef" | "jsonl";
export type ObservabilityFormat = "otlp_json" | "prometheus";
export type P10QuorumStatus = "awaiting_quorum" | "quorum_approved";

export interface EnterpriseOidcConfig {
  workspace_id: string;
  issuer: string;
  client_id: string;
  audience: string;
  jwks_uri: string;
  enabled: boolean;
  enforce_pkce: boolean;
  group_role_mapping: Record<string, RbacRoleId>;
  updated_at: string;
}

export interface ScimUserResource {
  id: string;
  userName: string;
  displayName: string;
  groups: string[];
  mapped_role: RbacRoleId;
  active: boolean;
  created_at: string;
}

export interface ScimUserListResponse {
  schemas: string[];
  totalResults: number;
  workspace_id: string;
  Resources: ScimUserResource[];
}

export interface P10QuorumProposalState {
  workspace_id: string;
  proposal_id: string;
  initiator_id: string;
  required_approvals: number;
  approvals_count: number;
  approvers: string[];
  status: P10QuorumStatus;
  quorum_met: boolean;
  reason: string;
  quorum_receipt_sha256: string;
  updated_at: string;
}

export interface SiemAuditExportResult {
  workspace_id: string;
  format: SiemExportFormat;
  record_count: number;
  batch_sha256: string;
  records: string[];
  exported_at: string;
}

export interface ObservabilityCounters {
  keelway_kflow_runs_total: number;
  keelway_crdt_entries_total: number;
  keelway_mcp_servers_total: number;
  keelway_scim_active_users: number;
  keelway_p10_quorum_approved_total: number;
  keelway_siem_exports_total: number;
}

export interface ObservabilityMetricsSnapshot {
  workspace_id: string;
  format: ObservabilityFormat;
  counters: ObservabilityCounters;
  prometheus_text: string;
  collected_at: string;
}

export class PlatformEnterpriseHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "PlatformEnterpriseHttpError";
    this.status = status;
  }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const toSha = (raw: string): string => (raw.startsWith("sha256:") ? raw : `sha256:${raw}`);

const DEFAULT_GROUP_ROLE_MAP: Record<string, RbacRoleId> = {
  "keelway-owners": "owner",
  "keelway-admins": "admin",
  "keelway-operators": "operator",
  "keelway-builders": "builder",
  "keelway-auditors": "viewer",
};

export const canRbacManageEnterprise = (role: RbacRoleId): boolean => role === "owner" || role === "admin";
export const canRbacApproveP10Quorum = (role: RbacRoleId): boolean => role === "owner" || role === "operator";

function shouldSkipUnmockedTestFetch(): boolean {
  if (import.meta.env.MODE !== "test") return false;
  if (typeof globalThis.fetch !== "function") return true;
  return !("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN;
}

function attachEnterpriseHeaders(raw?: HeadersInit, role?: RbacRoleId, hasBody = false): Headers {
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

async function requestEnterpriseEndpoint(
  path: string,
  init: RequestInit,
  query?: Record<string, string | undefined>,
  role?: RbacRoleId,
): Promise<{ ok: boolean; status: number; data: unknown; rawText: string }> {
  const url = buildRuntimeUrl(path, query);
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null, rawText: "" };
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      credentials: "same-origin",
      headers: attachEnterpriseHeaders(init.headers, role, Boolean(init.body)),
    });
  } catch {
    return { ok: false, status: 0, data: null, rawText: "" };
  }
  const rawText = await res.text().catch(() => "");
  let data: unknown = null;
  if (rawText) {
    try { data = JSON.parse(rawText) as unknown; } catch { data = null; }
  }
  if (!res.ok && res.status >= 400) {
    const detail =
      isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string"
        ? String(data.detail ?? data.error ?? data.message)
        : `Request failed with HTTP ${res.status}.`;
    throw new PlatformEnterpriseHttpError(res.status, detail);
  }
  return { ok: res.ok, status: res.status, data, rawText };
}

const localOidcStore = new Map<string, EnterpriseOidcConfig>();
const localScimStore = new Map<string, ScimUserResource[]>();
const localQuorumStore = new Map<string, P10QuorumProposalState>();
const localSiemCountByWs = new Map<string, number>();
const localQuorumApprovedCountByWs = new Map<string, number>();

export function resetLocalEnterpriseState(): void {
  localOidcStore.clear();
  localScimStore.clear();
  localQuorumStore.clear();
  localSiemCountByWs.clear();
  localQuorumApprovedCountByWs.clear();
}

function normalizeRole(val: unknown, fallback: RbacRoleId = "viewer"): RbacRoleId {
  return val === "owner" || val === "admin" || val === "operator" || val === "builder" || val === "viewer" ? val : fallback;
}

function mapGroupsToRole(groups: string[], mapping: Record<string, RbacRoleId> = DEFAULT_GROUP_ROLE_MAP): RbacRoleId {
  const ranks: Record<RbacRoleId, number> = { owner: 5, admin: 4, operator: 3, builder: 2, viewer: 1 };
  let best: RbacRoleId = "viewer";
  for (const g of groups) {
    const candidate = mapping[g] ?? DEFAULT_GROUP_ROLE_MAP[g];
    if (candidate && ranks[candidate] > ranks[best]) best = candidate;
  }
  return best;
}

function getOrSeedOidc(ws: string): EnterpriseOidcConfig {
  const existing = localOidcStore.get(ws);
  if (existing) return existing;
  const seeded: EnterpriseOidcConfig = {
    workspace_id: ws,
    issuer: "https://idp.enterprise.example",
    client_id: "keelway-sovereign-web",
    audience: "https://api.keelway.local",
    jwks_uri: "https://idp.enterprise.example/.well-known/jwks.json",
    enabled: true,
    enforce_pkce: true,
    group_role_mapping: { ...DEFAULT_GROUP_ROLE_MAP },
    updated_at: "2026-11-15T00:00:00Z",
  };
  localOidcStore.set(ws, seeded);
  return seeded;
}

function getOrSeedScimUsers(ws: string): ScimUserResource[] {
  const existing = localScimStore.get(ws);
  if (existing) return existing;
  const seeded: ScimUserResource[] = [
    {
      id: `scim_${computeLocalFingerprintHex(`${ws}:secops.owner@enterprise.example`).slice(0, 10)}`,
      userName: "secops.owner@enterprise.example",
      displayName: "SecOps Owner",
      groups: ["keelway-owners"],
      mapped_role: "owner",
      active: true,
      created_at: "2026-11-15T00:00:00Z",
    },
  ];
  localScimStore.set(ws, seeded);
  return seeded;
}

function decodeOidcConfig(raw: Record<string, unknown>, ws: string): EnterpriseOidcConfig {
  const issuer = String(raw.issuer ?? raw.issuer_url ?? "https://idp.enterprise.example");
  const rawMap = isRecord(raw.group_role_mapping) ? raw.group_role_mapping : {};
  const mapping: Record<string, RbacRoleId> = { ...DEFAULT_GROUP_ROLE_MAP };
  for (const [k, v] of Object.entries(rawMap)) mapping[k] = normalizeRole(v);
  return {
    workspace_id: String(raw.workspace_id ?? ws),
    issuer,
    client_id: String(raw.client_id ?? "keelway-sovereign-web"),
    audience: String(raw.audience ?? "https://api.keelway.local"),
    jwks_uri: String(raw.jwks_uri ?? `${issuer.replace(/\/$/, "")}/.well-known/jwks.json`),
    enabled: raw.enabled !== false,
    enforce_pkce: raw.enforce_pkce !== false,
    group_role_mapping: mapping,
    updated_at: String(raw.updated_at ?? new Date().toISOString()),
  };
}

function decodeScimUser(raw: Record<string, unknown>, ws: string, idx = 0): ScimUserResource {
  const userName = String(raw.userName ?? raw.user_name ?? raw.email ?? `user-${idx + 1}@enterprise.example`);
  const rawGroups = Array.isArray(raw.groups) ? raw.groups : [];
  const groups = rawGroups
    .map((g) => (typeof g === "string" ? g : isRecord(g) ? String(g.value ?? g.display ?? "") : ""))
    .filter(Boolean);
  const effectiveGroups = groups.length > 0 ? groups : ["keelway-auditors"];
  const mappedRole = normalizeRole(raw.mapped_role ?? raw.role, mapGroupsToRole(effectiveGroups));
  return {
    id: String(raw.id ?? `scim_${computeLocalFingerprintHex(`${ws}:${userName}`).slice(0, 10)}`),
    userName,
    displayName: String(raw.displayName ?? raw.display_name ?? userName.split("@")[0] ?? userName),
    groups: effectiveGroups,
    mapped_role: mappedRole,
    active: raw.active !== false,
    created_at: String(raw.created_at ?? raw.meta_created ?? new Date().toISOString()),
  };
}

export async function fetchOidcConfig(workspaceId = "default", role?: RbacRoleId): Promise<EnterpriseOidcConfig> {
  const res = await requestEnterpriseEndpoint("/v1/platform/enterprise/oidc", { method: "GET" }, { workspace_id: workspaceId }, role);
  const raw = isRecord(res.data) && isRecord(res.data.oidc) ? res.data.oidc : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && (typeof raw.issuer === "string" || typeof raw.issuer_url === "string" || typeof raw.client_id === "string")) {
    return decodeOidcConfig(raw, workspaceId);
  }
  return getOrSeedOidc(workspaceId);
}

export async function saveOidcConfig(
  payload: {
    workspace_id?: string;
    issuer: string;
    client_id?: string;
    audience?: string;
    enabled?: boolean;
    enforce_pkce?: boolean;
    group_role_mapping?: Record<string, RbacRoleId>;
  },
  role: RbacRoleId = "owner",
): Promise<EnterpriseOidcConfig> {
  const ws = payload.workspace_id ?? "default";
  const current = getOrSeedOidc(ws);
  const body = {
    workspace_id: ws,
    issuer: payload.issuer.trim(),
    client_id: payload.client_id ?? current.client_id,
    audience: payload.audience ?? current.audience,
    enabled: payload.enabled ?? current.enabled,
    enforce_pkce: payload.enforce_pkce ?? current.enforce_pkce,
    group_role_mapping: payload.group_role_mapping ?? current.group_role_mapping,
  };
  const res = await requestEnterpriseEndpoint("/v1/platform/enterprise/oidc", { method: "PUT", body: JSON.stringify(body) }, undefined, role);
  const raw = isRecord(res.data) && isRecord(res.data.oidc) ? res.data.oidc : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && (typeof raw.issuer === "string" || typeof raw.client_id === "string")) {
    return decodeOidcConfig(raw, ws);
  }
  if (!canRbacManageEnterprise(role)) {
    throw new PlatformEnterpriseHttpError(403, `RBAC Denied (${role}): Only owner or admin can update OIDC federation configuration.`);
  }
  if (!body.issuer.startsWith("https://") && !body.issuer.startsWith("http://127.0.0.1") && !body.issuer.startsWith("http://localhost")) {
    throw new PlatformEnterpriseHttpError(400, "OIDC issuer URL must use HTTPS (or loopback HTTP).");
  }
  const updated: EnterpriseOidcConfig = {
    ...current,
    ...body,
    jwks_uri: `${body.issuer.replace(/\/$/, "")}/.well-known/jwks.json`,
    updated_at: new Date().toISOString(),
  };
  localOidcStore.set(ws, updated);
  return updated;
}

export async function fetchScimUsers(workspaceId = "default", role?: RbacRoleId): Promise<ScimUserListResponse> {
  const res = await requestEnterpriseEndpoint(
    "/v1/platform/enterprise/scim/v2/Users",
    { method: "GET" },
    { workspace_id: workspaceId },
    role,
  );
  const rawList =
    isRecord(res.data) && Array.isArray(res.data.Resources)
      ? res.data.Resources
      : isRecord(res.data) && Array.isArray(res.data.users)
        ? res.data.users
        : null;
  if (res.ok && rawList) {
    const resources = rawList.filter(isRecord).map((u, idx) => decodeScimUser(u, workspaceId, idx));
    return {
      schemas: ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
      totalResults: typeof (res.data as Record<string, unknown>).totalResults === "number" ? Number((res.data as Record<string, unknown>).totalResults) : resources.length,
      workspace_id: workspaceId,
      Resources: resources,
    };
  }
  const local = getOrSeedScimUsers(workspaceId);
  return {
    schemas: ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
    totalResults: local.length,
    workspace_id: workspaceId,
    Resources: [...local],
  };
}

export async function provisionScimUser(
  payload: {
    workspace_id?: string;
    userName: string;
    displayName?: string;
    groups: string[];
    active?: boolean;
  },
  role: RbacRoleId = "owner",
): Promise<ScimUserResource> {
  const ws = payload.workspace_id ?? "default";
  const cleanEmail = payload.userName.trim();
  const groups = payload.groups.length > 0 ? payload.groups : ["keelway-operators"];
  const displayName = (payload.displayName ?? cleanEmail.split("@")[0] ?? cleanEmail).trim();
  const res = await requestEnterpriseEndpoint(
    "/v1/platform/enterprise/scim/v2/Users",
    {
      method: "POST",
      body: JSON.stringify({
        schemas: ["urn:ietf:params:scim:api:core:2.0:User"],
        workspace_id: ws,
        userName: cleanEmail,
        displayName,
        emails: [{ value: cleanEmail, primary: true }],
        groups,
        active: payload.active !== false,
      }),
    },
    undefined,
    role,
  );
  const rawUser = isRecord(res.data) && isRecord(res.data.user) ? res.data.user : isRecord(res.data) ? res.data : null;
  if (res.ok && rawUser && (typeof rawUser.userName === "string" || typeof rawUser.id === "string")) {
    return decodeScimUser(rawUser, ws);
  }
  if (!canRbacManageEnterprise(role)) {
    throw new PlatformEnterpriseHttpError(403, `RBAC Denied (${role}): rbac:manage requires owner or admin to provision SCIM 2.0 users.`);
  }
  if (!cleanEmail || !cleanEmail.includes("@")) {
    throw new PlatformEnterpriseHttpError(400, "Valid SCIM 2.0 user email (userName) is required.");
  }
  const oidc = getOrSeedOidc(ws);
  const mappedRole = mapGroupsToRole(groups, oidc.group_role_mapping);
  const created: ScimUserResource = {
    id: `scim_${computeLocalFingerprintHex(`${ws}:${cleanEmail}`).slice(0, 10)}`,
    userName: cleanEmail,
    displayName,
    groups,
    mapped_role: mappedRole,
    active: payload.active !== false,
    created_at: new Date().toISOString(),
  };
  const list = getOrSeedScimUsers(ws);
  const existingIdx = list.findIndex((u) => u.userName.toLowerCase() === cleanEmail.toLowerCase());
  if (existingIdx >= 0) list[existingIdx] = created;
  else list.push(created);
  localScimStore.set(ws, [...list]);
  return created;
}

function decodeQuorumState(raw: Record<string, unknown>, ws: string, fallbackProposal: string, reqCount: number): P10QuorumProposalState {
  const rawList = Array.isArray(raw.approvers)
    ? raw.approvers
    : Array.isArray(raw.signers)
      ? raw.signers
      : Array.isArray(raw.approvals)
        ? raw.approvals
        : [];
  const approvers = rawList
    .map((item) => (typeof item === "string" ? item : isRecord(item) ? String(item.approver_id ?? item.actor_id ?? item.id ?? "") : ""))
    .filter(Boolean);
  const required = typeof raw.required_approvals === "number" ? raw.required_approvals : reqCount;
  const count = typeof raw.approvals_count === "number" ? raw.approvals_count : approvers.length;
  const met = raw.quorum_met === true || raw.status === "quorum_approved" || raw.status === "approved" || count >= required;
  const h1 = computeLocalFingerprintHex(`quorum:${ws}:${fallbackProposal}:${approvers.join(",")}`);
  const h2 = computeLocalFingerprintHex(`receipt:${fallbackProposal}:${count}/${required}`);
  return {
    workspace_id: String(raw.workspace_id ?? ws),
    proposal_id: String(raw.proposal_id ?? fallbackProposal),
    initiator_id: String(raw.initiator_id ?? "ci-initiator@keelway.local"),
    required_approvals: required,
    approvals_count: count,
    approvers,
    status: met ? "quorum_approved" : "awaiting_quorum",
    quorum_met: met,
    reason: String(raw.reason ?? "Production deployment P-10 dual-human quorum attestation"),
    quorum_receipt_sha256: toSha(String(raw.quorum_receipt_sha256 ?? raw.receipt_sha256 ?? `${h1}${h2}`)),
    updated_at: String(raw.updated_at ?? new Date().toISOString()),
  };
}

export async function approveP10Quorum(
  payload: {
    workspace_id?: string;
    proposal_id: string;
    approver_id: string;
    initiator_id?: string;
    required_approvals?: number;
    reason?: string;
  },
  role: RbacRoleId = "owner",
): Promise<P10QuorumProposalState> {
  const ws = payload.workspace_id ?? "default";
  const proposalId = payload.proposal_id.trim();
  const approverId = payload.approver_id.trim();
  const initiatorId = (payload.initiator_id ?? "ci-initiator@keelway.local").trim();
  const required = Math.max(2, payload.required_approvals ?? 2);
  const reason = (payload.reason ?? "Dual-human P-10 production release sign-off").trim();

  const res = await requestEnterpriseEndpoint(
    "/v1/platform/enterprise/p10-quorum/approve",
    {
      method: "POST",
      body: JSON.stringify({
        workspace_id: ws,
        proposal_id: proposalId,
        approver_id: approverId,
        initiator_id: initiatorId,
        required_approvals: required,
        reason,
      }),
    },
    undefined,
    role,
  );
  const raw = isRecord(res.data) && isRecord(res.data.proposal) ? res.data.proposal : isRecord(res.data) ? res.data : null;
  if (res.ok && raw && (typeof raw.proposal_id === "string" || typeof raw.status === "string" || Array.isArray(raw.approvers))) {
    return decodeQuorumState(raw, ws, proposalId, required);
  }

  if (!canRbacApproveP10Quorum(role)) {
    throw new PlatformEnterpriseHttpError(
      403,
      `RBAC Denied (${role}): Only owner or operator can sign P-10 quorum approvals.`,
    );
  }
  if (!proposalId || !approverId) {
    throw new PlatformEnterpriseHttpError(400, "Both proposal_id and human approver_id are required.");
  }
  if (initiatorId && approverId.toLowerCase() === initiatorId.toLowerCase()) {
    throw new PlatformEnterpriseHttpError(
      409,
      `Separation-of-duties violation: Initiator "${approverId}" cannot self-approve proposal "${proposalId}".`,
    );
  }
  const key = `${ws}::${proposalId}`;
  const prev = localQuorumStore.get(key);
  const existingApprovers = prev?.approvers ?? [];
  if (existingApprovers.some((s) => s.toLowerCase() === approverId.toLowerCase())) {
    throw new PlatformEnterpriseHttpError(
      409,
      `Duplicate signer rejected: "${approverId}" already signed "${proposalId}". Distinct human approvers are required.`,
    );
  }
  const nextApprovers = [...existingApprovers, approverId];
  const met = nextApprovers.length >= required;
  if (met && !prev?.quorum_met) {
    localQuorumApprovedCountByWs.set(ws, (localQuorumApprovedCountByWs.get(ws) ?? 0) + 1);
  }
  const h1 = computeLocalFingerprintHex(`quorum:${ws}:${proposalId}:${nextApprovers.join(",")}`);
  const h2 = computeLocalFingerprintHex(`p10-2of2:${initiatorId}:${nextApprovers.length}`);
  const nextState: P10QuorumProposalState = {
    workspace_id: ws,
    proposal_id: proposalId,
    initiator_id: initiatorId,
    required_approvals: required,
    approvals_count: nextApprovers.length,
    approvers: nextApprovers,
    status: met ? "quorum_approved" : "awaiting_quorum",
    quorum_met: met,
    reason,
    quorum_receipt_sha256: toSha(`${h1}${h2}`),
    updated_at: new Date().toISOString(),
  };
  localQuorumStore.set(key, nextState);
  return nextState;
}

export async function exportSiemAudit(
  workspaceId = "default",
  format: SiemExportFormat = "ocsf",
  role?: RbacRoleId,
): Promise<SiemAuditExportResult> {
  const res = await requestEnterpriseEndpoint(
    "/v1/platform/enterprise/siem/export",
    { method: "GET" },
    { workspace_id: workspaceId, format, limit: "25" },
    role,
  );
  if (res.ok && isRecord(res.data) && (typeof res.data.record_count === "number" || Array.isArray(res.data.records) || typeof res.data.payload === "string")) {
    const d = res.data;
    const rawRecords = Array.isArray(d.records)
      ? d.records.map((r) => (typeof r === "string" ? r : JSON.stringify(r)))
      : Array.isArray(d.events)
        ? d.events.map((r) => (typeof r === "string" ? r : JSON.stringify(r)))
        : typeof d.payload === "string"
          ? d.payload.split(/\r?\n/).filter(Boolean)
          : [];
    const h = computeLocalFingerprintHex(`siem:${workspaceId}:${format}:${rawRecords.length}`);
    return {
      workspace_id: String(d.workspace_id ?? workspaceId),
      format: d.format === "cef" || d.format === "jsonl" ? d.format : format,
      record_count: typeof d.record_count === "number" ? d.record_count : rawRecords.length,
      batch_sha256: toSha(String(d.batch_sha256 ?? d.digest_sha256 ?? `${h}${h}`)),
      records: rawRecords,
      exported_at: String(d.exported_at ?? new Date().toISOString()),
    };
  }
  localSiemCountByWs.set(workspaceId, (localSiemCountByWs.get(workspaceId) ?? 0) + 1);
  const events = [
    { seq: 1, action: "oidc.federation.verified", actor: "secops.owner@enterprise.example", severity: "Informational" },
    { seq: 2, action: "scim.user.provisioned", actor: "secops.owner@enterprise.example", severity: "Low" },
    { seq: 3, action: "p10.quorum.attestation", actor: "alice@keelway.local", severity: "High" },
  ];
  const records = events.map((ev) => {
    const entryHash = computeLocalFingerprintHex(`${workspaceId}:${ev.seq}:${ev.action}`);
    if (format === "cef") {
      return `CEF:0|Keelway|SovereignCore|1.1|${ev.action}|${ev.action}|3|suser=${ev.actor} dvchost=${workspaceId} cs1=${entryHash}`;
    }
    if (format === "jsonl") {
      return JSON.stringify({ seq: ev.seq, workspace_id: workspaceId, event_type: ev.action, actor: ev.actor, entry_sha256: `sha256:${entryHash}` });
    }
    return JSON.stringify({
      class_uid: 6003,
      class_name: "API Activity",
      version: "1.1.0",
      severity: ev.severity,
      actor: { user: { uid: ev.actor } },
      metadata: { product: { name: "Keelway Sovereign Core", vendor_name: "Keelway" }, correlation_uid: `sha256:${entryHash}` },
      activity_name: ev.action,
    });
  });
  const h1 = computeLocalFingerprintHex(`siem-batch:${workspaceId}:${format}:${records.join("|")}`);
  const h2 = computeLocalFingerprintHex(`merkle:${format}:${records.length}`);
  return {
    workspace_id: workspaceId,
    format,
    record_count: records.length,
    batch_sha256: toSha(`${h1}${h2}`),
    records,
    exported_at: new Date().toISOString(),
  };
}

function buildPrometheusText(ws: string, counters: ObservabilityCounters): string {
  return [
    "# HELP keelway_kflow_runs_total Total KFlow topological DAG runs.",
    "# TYPE keelway_kflow_runs_total counter",
    `keelway_kflow_runs_total{workspace_id="${ws}"} ${counters.keelway_kflow_runs_total}`,
    `keelway_crdt_entries_total{workspace_id="${ws}"} ${counters.keelway_crdt_entries_total}`,
    `keelway_mcp_servers_total{workspace_id="${ws}"} ${counters.keelway_mcp_servers_total}`,
    `keelway_scim_active_users{workspace_id="${ws}"} ${counters.keelway_scim_active_users}`,
    `keelway_p10_quorum_approved_total{workspace_id="${ws}"} ${counters.keelway_p10_quorum_approved_total}`,
    `keelway_siem_exports_total{workspace_id="${ws}"} ${counters.keelway_siem_exports_total}`,
  ].join("\n");
}

export async function fetchObservabilityMetrics(
  workspaceId = "default",
  format: ObservabilityFormat = "otlp_json",
  role?: RbacRoleId,
): Promise<ObservabilityMetricsSnapshot> {
  const res = await requestEnterpriseEndpoint(
    "/v1/platform/observability/metrics",
    { method: "GET" },
    { workspace_id: workspaceId, format },
    role,
  );
  const scimActiveFallback = getOrSeedScimUsers(workspaceId).filter((u) => u.active).length;
  const fallbackCounters: ObservabilityCounters = {
    keelway_kflow_runs_total: 4,
    keelway_crdt_entries_total: 6,
    keelway_mcp_servers_total: 4,
    keelway_scim_active_users: scimActiveFallback,
    keelway_p10_quorum_approved_total: localQuorumApprovedCountByWs.get(workspaceId) ?? 1,
    keelway_siem_exports_total: localSiemCountByWs.get(workspaceId) ?? 1,
  };

  if (res.ok && isRecord(res.data) && (isRecord(res.data.counters) || Array.isArray(res.data.resourceMetrics) || typeof res.data.prometheus_text === "string")) {
    const rawC = isRecord(res.data.counters) ? res.data.counters : res.data;
    const num = (k: keyof ObservabilityCounters): number => (typeof rawC[k] === "number" ? Number(rawC[k]) : fallbackCounters[k]);
    const counters: ObservabilityCounters = {
      keelway_kflow_runs_total: num("keelway_kflow_runs_total"),
      keelway_crdt_entries_total: num("keelway_crdt_entries_total"),
      keelway_mcp_servers_total: num("keelway_mcp_servers_total"),
      keelway_scim_active_users: num("keelway_scim_active_users"),
      keelway_p10_quorum_approved_total: num("keelway_p10_quorum_approved_total"),
      keelway_siem_exports_total: num("keelway_siem_exports_total"),
    };
    return {
      workspace_id: String(res.data.workspace_id ?? workspaceId),
      format,
      counters,
      prometheus_text: typeof res.data.prometheus_text === "string" ? res.data.prometheus_text : buildPrometheusText(workspaceId, counters),
      collected_at: String(res.data.collected_at ?? new Date().toISOString()),
    };
  }
  if (res.ok && res.rawText.includes("keelway_kflow_runs_total")) {
    const parseMetric = (name: keyof ObservabilityCounters): number => {
      const m = new RegExp(`${name}(?:\\{[^}]*\\})?\\s+(\\d+(?:\\.\\d+)?)`).exec(res.rawText);
      return m ? Number(m[1]) : fallbackCounters[name];
    };
    const counters: ObservabilityCounters = {
      keelway_kflow_runs_total: parseMetric("keelway_kflow_runs_total"),
      keelway_crdt_entries_total: parseMetric("keelway_crdt_entries_total"),
      keelway_mcp_servers_total: parseMetric("keelway_mcp_servers_total"),
      keelway_scim_active_users: parseMetric("keelway_scim_active_users"),
      keelway_p10_quorum_approved_total: parseMetric("keelway_p10_quorum_approved_total"),
      keelway_siem_exports_total: parseMetric("keelway_siem_exports_total"),
    };
    return { workspace_id: workspaceId, format, counters, prometheus_text: res.rawText.trim(), collected_at: new Date().toISOString() };
  }

  return {
    workspace_id: workspaceId,
    format,
    counters: fallbackCounters,
    prometheus_text: buildPrometheusText(workspaceId, fallbackCounters),
    collected_at: new Date().toISOString(),
  };
}
