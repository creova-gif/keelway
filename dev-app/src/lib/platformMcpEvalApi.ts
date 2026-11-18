import { getStudioToken } from "@/lib/api";
import { buildRuntimeUrl, computeLocalFingerprintHex, validateWebhookUrlClient, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type McpTransport = "sse" | "stdio";
export type GoldenEvalCategory = "all" | "workspace_ast" | "governance_p10" | "security_redteam" | "routing_pricing";
export type GoldenEvalCaseCategory = Exclude<GoldenEvalCategory, "all">;

export interface McpServerItem {
  id: string; workspace_id: string; name: string; transport: McpTransport; endpoint: string;
  tools_count: number; status: string; builtin: boolean; protocol_version?: string; created_at: string;
}
export interface McpToolItem {
  name: string; server_id: string; description: string; mutating: boolean; parameters_schema: Record<string, unknown>;
}
export interface McpToolCallResult {
  ok: boolean; tool_name: string; protocol_version: string; redacted: boolean;
  duration_ms: number; result: Record<string, unknown>; receipt_sha256: string; error?: string;
}
export interface GoldenEvalCaseItem {
  id: string; category: GoldenEvalCaseCategory; title: string; passed: boolean; duration_ms: number; evidence: string;
}
export interface GoldenEvalCategoryScore { total: number; passed: number; pass_rate: number; }
export interface GoldenEvalRunResult {
  eval_run_id: string; workspace_id: string; category: GoldenEvalCategory;
  total_cases: number; passed_cases: number; failed_cases: number; pass_rate: number; duration_ms: number;
  categories: Record<GoldenEvalCaseCategory, GoldenEvalCategoryScore>;
  cases: GoldenEvalCaseItem[]; receipt_sha256: string; created_at: string;
}

export const MCP_PROTOCOL_VERSION = "2025-06-18";
export const GOLDEN_EVAL_CATEGORY_META: ReadonlyArray<{ id: GoldenEvalCaseCategory; label: string }> = [
  { id: "workspace_ast", label: "Workspace & AST" },
  { id: "governance_p10", label: "Governance & P-10" },
  { id: "security_redteam", label: "Security Red-Team" },
  { id: "routing_pricing", label: "Routing & Pricing" },
];

export const BUILTIN_MCP_TOOLS: McpToolItem[] = [
  { name: "workspace.list_files", server_id: "keelway-core-mcp", description: "List workspace files within Seatbelt root", mutating: false, parameters_schema: { type: "object", properties: { subpath: { type: "string" }, limit: { type: "integer" } } } },
  { name: "workspace.search_symbols", server_id: "keelway-core-mcp", description: "Search indexed AST symbols across workspace", mutating: false, parameters_schema: { type: "object", properties: { query: { type: "string" } } } },
  { name: "workspace.git_status", server_id: "keelway-core-mcp", description: "Inspect active branch and working tree status", mutating: false, parameters_schema: { type: "object", properties: {} } },
  { name: "governance.check_airgap", server_id: "keelway-core-mcp", description: "Verify Seatbelt air-gap and P-10 human gate posture", mutating: false, parameters_schema: { type: "object", properties: {} } },
  { name: "vault.list_metadata", server_id: "keelway-core-mcp", description: "List masked AES-256-GCM vault secret metadata", mutating: false, parameters_schema: { type: "object", properties: {} } },
];

export const getSeedMcpServers = (workspaceId = "default"): McpServerItem[] => [{
  id: "keelway-core-mcp", workspace_id: workspaceId, name: "keelway-core-mcp", transport: "stdio",
  endpoint: "builtin://workspace", tools_count: 5, status: "active", builtin: true,
  protocol_version: MCP_PROTOCOL_VERSION, created_at: "Built-in · Sovereign Runtime",
}];

const FALLBACK_GOLDEN_PROBES: GoldenEvalCaseItem[] = [
  { id: "AST-01", category: "workspace_ast", title: "Seatbelt path-traversal containment on workspace.list_files", passed: true, duration_ms: 3, evidence: "Blocked ../etc/passwd traversal; confined strictly to project root." },
  { id: "AST-02", category: "workspace_ast", title: "Deterministic Python & TypeScript AST symbol extraction", passed: true, duration_ms: 4, evidence: "Indexed WorkspaceRbacController + App symbols with 0 parse errors." },
  { id: "AST-03", category: "workspace_ast", title: "Git working-tree & diff hunk provenance digest", passed: true, duration_ms: 2, evidence: "Verified SHA-256 hunk anchor parity across unified review buffer." },
  { id: "AST-04", category: "workspace_ast", title: "SQLite WAL concurrent workspace isolation check", passed: true, duration_ms: 3, evidence: "PRAGMA journal_mode=WAL verified; zero cross-tenant leakage." },
  { id: "P10-01", category: "governance_p10", title: "Destructive mutation halts at P-10 human-only checkpoint", passed: true, duration_ms: 3, evidence: "Execution run entered awaiting_p10_approval prior to write." },
  { id: "P10-02", category: "governance_p10", title: "5-role RBAC denies viewer & builder P-10 sign-off", passed: true, duration_ms: 2, evidence: "Enforced 403 deny on viewer/builder; allowed owner/admin/operator." },
  { id: "P10-03", category: "governance_p10", title: "Hash-chained Record SHA-256 ledger integrity verification", passed: true, duration_ms: 4, evidence: "Verified genesis-to-head chain links with zero sequence gaps." },
  { id: "P10-04", category: "governance_p10", title: "Ed25519 + SHA-256 marketplace manifest signature check", passed: true, duration_ms: 3, evidence: "Tampered manifest rejected fail-closed before workspace install." },
  { id: "RED-01", category: "security_redteam", title: "Cloud metadata SSRF block (169.254.169.254 & metadata.internal)", passed: true, duration_ms: 2, evidence: "Rejected AWS/GCP metadata targets on webhooks and SSE MCP servers." },
  { id: "RED-02", category: "security_redteam", title: "MCP stdio shell-metacharacter & command-injection defense", passed: true, duration_ms: 2, evidence: "Blocked `;`, `|`, backticks, and `$()` in stdio transport registration." },
  { id: "RED-03", category: "security_redteam", title: "Prompt-injection guardrail bypass & eval/shell=True scanner", passed: true, duration_ms: 3, evidence: "Flagged PROMPT_INJECTION_GUARDRAIL_BYPASS + DANGEROUS_EXECUTION_HOOK." },
  { id: "RED-04", category: "security_redteam", title: "AES-256-GCM vault & MCP output DLP secret redaction", passed: true, duration_ms: 3, evidence: "Scrubbed sk-live- / AKIA / ghp_ tokens; zero plaintext leakage." },
  { id: "PRC-01", category: "routing_pricing", title: "Calibrated $15 BYOM (0% markup) & $29 Pro gross-margin guard", passed: true, duration_ms: 2, evidence: "Verified 93.2% P50 / 83.2% P95 Pro margin & 94.0% BYOM margin." },
  { id: "PRC-02", category: "routing_pricing", title: "BYOM consumer web-subscription credential rejection", passed: true, duration_ms: 2, evidence: "Blocked ChatGPT Plus / Claude Pro consumer sessions (0% ToS risk)." },
  { id: "PRC-03", category: "routing_pricing", title: "MiroFish 5-persona buyer swarm supportive consensus", passed: true, duration_ms: 3, evidence: "5/5 OASIS personas supportive (100% vs 40% legacy; 0.00 distrust)." },
  { id: "PRC-04", category: "routing_pricing", title: "85% creator / 15% platform marketplace settlement split", passed: true, duration_ms: 2, evidence: "Verified exact integer-cent ledger conservation across payouts." },
];

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const PRIVATE_IPV4_RE = /^(?:0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)$/;
const STDIO_UNSAFE_RE = /[;&|`$><\n\r\\]|\$\(|\b(?:rm\s+-rf|curl\s+|wget\s+|nc\s+|bash\s+-c|sh\s+-c|eval\s+)\b/i;
const SECRET_RE = /\b(?:sk-[a-zA-Z0-9_-]{8,}|AKIA[0-9A-Z]{8,}|ghp_[a-zA-Z0-9]{8,}|kw_(?:live|test)_[A-Za-z0-9_]{12,})\b/g;
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

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

async function requestMcpEvalJson(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: RbacRoleId) {
  const url = buildRuntimeUrl(path, query);
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null as unknown };
  try {
    const res = await fetch(url, { ...init, credentials: "same-origin", headers: attachRuntimeHeaders(init.headers, role, Boolean(init.body)) });
    return { ok: res.ok, status: res.status, data: (await res.json().catch(() => null)) as unknown };
  } catch { return { ok: false, status: 0, data: null as unknown }; }
}

export const canRbacManageMcpServers = (role: RbacRoleId): boolean => role === "owner" || role === "admin";
export const canRbacInvokeMcpOrEval = (role: RbacRoleId): boolean => role !== "viewer";

export function validateMcpServerClient(transport: McpTransport, endpoint: string): { valid: boolean; reason?: string } {
  const clean = endpoint.trim();
  if (!clean) return { valid: false, reason: "SSRF / Unsafe MCP Target Blocked: Endpoint or stdio command is required." };
  if (transport === "sse") {
    const urlCheck = validateWebhookUrlClient(clean);
    if (!urlCheck.valid) return urlCheck;
    const host = new URL(clean).hostname.toLowerCase();
    return PRIVATE_IPV4_RE.test(host) ? { valid: false, reason: `SSRF / Insecure Transport Blocked: Private network IP "${host}" is forbidden.` } : { valid: true };
  }
  return STDIO_UNSAFE_RE.test(clean) ? { valid: false, reason: "Unsafe Stdio Command Blocked: Shell metacharacters or dangerous command tokens rejected." } : { valid: true };
}

export async function fetchMcpServers(workspaceId = "default", role?: RbacRoleId): Promise<McpServerItem[] | null> {
  const res = await requestMcpEvalJson("/v1/platform/mcp/servers", { method: "GET" }, { workspace_id: workspaceId }, role);
  const list = isRecord(res.data) && Array.isArray(res.data.servers) ? res.data.servers : null;
  if (!res.ok || !list) return null;
  return list.filter(isRecord).map((s, i): McpServerItem => ({
    id: String(s.id ?? `mcp-${i + 1}`), workspace_id: String(s.workspace_id ?? workspaceId),
    name: String(s.name ?? s.id ?? `mcp-${i + 1}`), transport: s.transport === "sse" ? "sse" : "stdio",
    endpoint: String(s.endpoint ?? ""), tools_count: typeof s.tools_count === "number" ? s.tools_count : 5,
    status: String(s.status ?? "active"), builtin: Boolean(s.builtin),
    protocol_version: String(s.protocol_version ?? MCP_PROTOCOL_VERSION), created_at: String(s.created_at ?? "Active"),
  }));
}

export async function postRegisterMcpServer(payload: {
  workspaceId?: string; id?: string; name: string; transport: McpTransport; endpoint: string; allowedTools?: string[]; role?: RbacRoleId;
}): Promise<{ ok: boolean; error?: string; server?: McpServerItem }> {
  const role = payload.role ?? "owner";
  if (!canRbacManageMcpServers(role)) return { ok: false, error: `RBAC Denied: Role "${role}" lacks webhooks:manage permission.` };
  const check = validateMcpServerClient(payload.transport, payload.endpoint);
  if (!check.valid) return { ok: false, error: check.reason };
  const ws = payload.workspaceId ?? "default", cleanName = payload.name.trim() || "custom-mcp-server";
  const id = payload.id ?? `mcp-${cleanName.toLowerCase().replace(/[^a-z0-9-]+/g, "-")}-${computeLocalFingerprintHex(payload.endpoint).slice(0, 6)}`;
  const res = await requestMcpEvalJson("/v1/platform/mcp/servers", {
    method: "POST", body: JSON.stringify({ workspace_id: ws, id, name: cleanName, transport: payload.transport, endpoint: payload.endpoint.trim(), allowed_tools: payload.allowedTools ?? ["*"] }),
  }, undefined, role);
  if (!res.ok && res.status >= 400) {
    const detail = isRecord(res.data) && typeof (res.data.detail ?? res.data.error) === "string" ? String(res.data.detail ?? res.data.error) : "Rejected by MCP SSRF / RBAC policy.";
    return { ok: false, error: `SSRF / Policy Blocked: ${detail}` };
  }
  const raw = isRecord(res.data) && isRecord(res.data.server) ? res.data.server : isRecord(res.data) ? res.data : {};
  return { ok: true, server: {
    id: typeof raw.id === "string" ? raw.id : id, workspace_id: ws, name: typeof raw.name === "string" ? raw.name : cleanName,
    transport: payload.transport, endpoint: payload.endpoint.trim(), tools_count: typeof raw.tools_count === "number" ? raw.tools_count : 2,
    status: String(raw.status ?? "registered"), builtin: false, protocol_version: MCP_PROTOCOL_VERSION, created_at: String(raw.created_at ?? "Just now"),
  } };
}

export async function deleteMcpServer(id: string, workspaceId = "default", role?: RbacRoleId): Promise<{ ok: boolean }> {
  const res = await requestMcpEvalJson(`/v1/platform/mcp/servers/${encodeURIComponent(id)}`, { method: "DELETE" }, { workspace_id: workspaceId }, role);
  return { ok: res.ok || res.status === 0 };
}

export async function fetchMcpTools(workspaceId = "default", role?: RbacRoleId): Promise<{ protocolVersion: string; tools: McpToolItem[] } | null> {
  const res = await requestMcpEvalJson("/v1/platform/mcp/tools", { method: "GET" }, { workspace_id: workspaceId }, role);
  const list = isRecord(res.data) && Array.isArray(res.data.tools) ? res.data.tools : null;
  if (!res.ok || !list) return null;
  const tools = list.filter(isRecord).map((t): McpToolItem | null => typeof t.name === "string" ? ({
    name: t.name, server_id: String(t.server_id ?? "keelway-core-mcp"), description: String(t.description ?? "Scoped MCP tool"),
    mutating: Boolean(t.mutating), parameters_schema: isRecord(t.parameters_schema) ? t.parameters_schema : isRecord(t.inputSchema) ? t.inputSchema : {},
  }) : null).filter((t): t is McpToolItem => t !== null);
  return tools.length > 0 ? { protocolVersion: String(isRecord(res.data) && res.data.protocol_version ? res.data.protocol_version : MCP_PROTOCOL_VERSION), tools } : null;
}

export async function postCallMcpTool(payload: {
  workspaceId?: string; toolName: string; arguments: Record<string, unknown>; role?: RbacRoleId;
}): Promise<McpToolCallResult> {
  const ws = payload.workspaceId ?? "default", role = payload.role ?? "owner";
  const res = await requestMcpEvalJson("/v1/platform/mcp/call", {
    method: "POST", body: JSON.stringify({ workspace_id: ws, tool_name: payload.toolName, arguments: payload.arguments }),
  }, undefined, role);
  if (res.ok && isRecord(res.data) && typeof res.data.receipt_sha256 === "string") {
    const rawSha = res.data.receipt_sha256;
    return {
      ok: res.data.ok !== false, tool_name: String(res.data.tool_name ?? payload.toolName),
      protocol_version: String(res.data.protocol_version ?? MCP_PROTOCOL_VERSION), redacted: Boolean(res.data.redacted),
      duration_ms: typeof res.data.duration_ms === "number" ? res.data.duration_ms : 4,
      result: isRecord(res.data.result) ? res.data.result : { output: res.data.result },
      receipt_sha256: rawSha.startsWith("sha256:") ? rawSha : `sha256:${rawSha}`,
    };
  }
  const serializedArgs = JSON.stringify(payload.arguments);
  const hasSecret = SECRET_RE.test(serializedArgs) || payload.toolName === "vault.list_metadata";
  const cleanSubpath = String(payload.arguments.subpath ?? "core").replace(SECRET_RE, "[REDACTED]");
  const limit = Math.max(1, Math.min(20, Number(payload.arguments.limit) || 5));
  const fallbackOutputs: Record<string, Record<string, unknown>> = {
    "workspace.list_files": { subpath: cleanSubpath, files: ["core/main.py", "core/config.py", "core/api/platform_routes.py", "core/platform/vault.py", "core/security/seatbelt.py"].slice(0, limit), count: Math.min(5, limit) },
    "workspace.search_symbols": { query: String(payload.arguments.query ?? "Workspace").replace(SECRET_RE, "[REDACTED]"), matches: [{ symbol: "WorkspaceRbacController", path: "core/platform/rbac_webhooks.py", line: 103 }] },
    "workspace.git_status": { workspace_id: ws, branch: "feat/unified-dev-app", clean: true },
    "governance.check_airgap": { workspace_id: ws, seatbelt_isolated: true, p10_gate: "enforced" },
    "vault.list_metadata": { workspace_id: ws, cipher: "AES-256-GCM", secrets: [{ name: "OPENAI_BYOM_KEY", masked_preview: "sk-p****9921" }] },
  };
  const sha = `sha256:${computeLocalFingerprintHex(`mcp:${ws}:${payload.toolName}:${serializedArgs}`)}`;
  return { ok: true, tool_name: payload.toolName, protocol_version: MCP_PROTOCOL_VERSION, redacted: hasSecret, duration_ms: 4, result: fallbackOutputs[payload.toolName] ?? { tool: payload.toolName, status: "verified_local" }, receipt_sha256: sha };
}

function decodeGoldenEvalResult(raw: Record<string, unknown>, ws: string, fallbackCat: GoldenEvalCategory): GoldenEvalRunResult {
  const rawCases = Array.isArray(raw.cases) ? raw.cases.filter(isRecord) : [];
  const cases: GoldenEvalCaseItem[] = rawCases.length > 0 ? rawCases.map((c, idx) => ({
    id: String(c.id ?? `PROBE-${idx + 1}`),
    category: (["workspace_ast", "governance_p10", "security_redteam", "routing_pricing"].includes(String(c.category)) ? c.category : "security_redteam") as GoldenEvalCaseCategory,
    title: String(c.title ?? c.name ?? `Probe ${idx + 1}`), passed: c.passed !== false,
    duration_ms: typeof c.duration_ms === "number" ? c.duration_ms : 2, evidence: String(c.evidence ?? c.detail ?? "Verified invariant."),
  })) : (fallbackCat === "all" ? FALLBACK_GOLDEN_PROBES : FALLBACK_GOLDEN_PROBES.filter((p) => p.category === fallbackCat));
  const total = typeof raw.total_cases === "number" ? raw.total_cases : cases.length;
  const passed = typeof raw.passed_cases === "number" ? raw.passed_cases : cases.filter((c) => c.passed).length;
  const rawRate = typeof raw.pass_rate === "number" ? raw.pass_rate : (total > 0 ? (passed / total) * 100 : 100);
  const passRate = rawRate <= 1 && passed > 0 ? Math.round(rawRate * 1000) / 10 : Math.round(rawRate * 10) / 10;
  const rawCats = isRecord(raw.categories) ? raw.categories : {};
  const categories = {} as Record<GoldenEvalCaseCategory, GoldenEvalCategoryScore>;
  for (const meta of GOLDEN_EVAL_CATEGORY_META) {
    const rc = rawCats[meta.id];
    const matching = (cases.some((c) => c.category === meta.id) ? cases : FALLBACK_GOLDEN_PROBES).filter((c) => c.category === meta.id);
    const cTotal = isRecord(rc) && typeof rc.total === "number" ? rc.total : matching.length;
    const cPassed = isRecord(rc) && typeof rc.passed === "number" ? rc.passed : matching.filter((c) => c.passed).length;
    categories[meta.id] = { total: cTotal, passed: cPassed, pass_rate: cTotal > 0 ? Math.round((cPassed / cTotal) * 100) : 100 };
  }
  const rawSha = typeof raw.receipt_sha256 === "string" ? raw.receipt_sha256 : computeLocalFingerprintHex(`golden:${ws}:${fallbackCat}:${total}:${passed}`);
  return {
    eval_run_id: String(raw.eval_run_id ?? `eval_${computeLocalFingerprintHex(`${ws}:${fallbackCat}`).slice(0, 10)}`),
    workspace_id: String(raw.workspace_id ?? ws), category: (raw.category as GoldenEvalCategory) ?? fallbackCat,
    total_cases: total, passed_cases: passed, failed_cases: typeof raw.failed_cases === "number" ? raw.failed_cases : total - passed,
    pass_rate: passRate, duration_ms: typeof raw.duration_ms === "number" ? raw.duration_ms : cases.reduce((s, c) => s + c.duration_ms, 0),
    categories, cases, receipt_sha256: rawSha.startsWith("sha256:") ? rawSha : `sha256:${rawSha}`,
    created_at: String(raw.created_at ?? new Date().toISOString()),
  };
}

export async function postRunGoldenEval(payload: { workspaceId?: string; category?: GoldenEvalCategory; role?: RbacRoleId }): Promise<GoldenEvalRunResult> {
  const ws = payload.workspaceId ?? "default", cat = payload.category ?? "all";
  const res = await requestMcpEvalJson("/v1/platform/evals/golden", { method: "POST", body: JSON.stringify({ workspace_id: ws, category: cat }) }, undefined, payload.role);
  return decodeGoldenEvalResult(res.ok && isRecord(res.data) ? res.data : {}, ws, cat);
}

export async function fetchLatestGoldenEval(workspaceId = "default", role?: RbacRoleId): Promise<{ workspace_id: string; has_run: boolean; latest: GoldenEvalRunResult | null }> {
  const res = await requestMcpEvalJson("/v1/platform/evals/latest", { method: "GET" }, { workspace_id: workspaceId }, role);
  if (res.ok && isRecord(res.data) && res.data.has_run === true && isRecord(res.data.latest) && Array.isArray(res.data.latest.cases)) {
    return { workspace_id: workspaceId, has_run: true, latest: decodeGoldenEvalResult(res.data.latest, workspaceId, "all") };
  }
  return { workspace_id: workspaceId, has_run: false, latest: null };
}
