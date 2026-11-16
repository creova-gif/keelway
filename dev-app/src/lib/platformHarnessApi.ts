import { getStudioToken } from "@/lib/api";
import { computeLocalFingerprintHex, type RbacRoleId } from "@/lib/platformRuntimeApi";

export type HarnessRbacRole = RbacRoleId | "developer" | "auditor";
export type AgentHostId = "claude_code" | "cursor" | "codex_cli";
export type HookEnforcementMode = "enforce" | "audit_only";
export type HarnessVerdict = "ALLOW" | "ALLOW_WITH_TICKET" | "HOLD_TICKET" | "DENY";
export type HarnessTicketStatus = "PENDING" | "APPROVED" | "DENIED" | "CONSUMED";
export type HarnessTicketDecision = "APPROVED" | "DENIED";
export type WorktreeProviderTier = "local_opencore" | "frontier_byom";
export type WorktreeCiGateStatus = "PASS" | "FAIL_REGRESSION" | "FAIL_SAFETY";

export interface RenderAgentHookConfigRequest { workspace_id?: string; agent_host?: AgentHostId; mode?: HookEnforcementMode; }
export interface HookManifestResponse { workspace_id: string; agent_host: AgentHostId; mode: HookEnforcementMode; target_config_path: string; hook_event: "PreToolUse"; config_content: string; cli_install_hint: string; config_sha256: string; }
export interface InterceptAgentToolCallRequest { workspace_id?: string; agent_host?: AgentHostId; tool_name?: string; command?: string; ticket_id?: string | null; }
export interface HarnessInterceptionRecord { interception_id: string; workspace_id: string; agent_host: AgentHostId; tool_name: string; scrubbed_command: string; command_sha256: string; verdict: HarnessVerdict; reason_code: string; explanation: string; ticket_id: string | null; dlp_redactions: number; event_sha256: string; created_at: string; }
export interface ApprovalTicketRecord { ticket_id: string; workspace_id: string; agent_host: AgentHostId; tool_name: string; scrubbed_command: string; command_sha256: string; status: HarnessTicketStatus; reviewer: string | null; decision_reason: string | null; created_at: string; decided_at: string | null; consumed_at: string | null; ticket_sha256: string; }
export interface DecideHarnessTicketRequest { workspace_id?: string; decision: HarnessTicketDecision; reviewer?: string; reason?: string; }
export interface WorktreeCandidateInput { candidate_id: string; worktree_branch: string; model_id: string; provider_tier: WorktreeProviderTier; tests_passed: boolean; eval_score: number; cost_usd: number; diff_excerpt?: string; }
export interface EvaluateWorktreeCiGateRequest { workspace_id?: string; workflow_name?: string; diff_summary?: string; min_eval_score?: number; candidates?: WorktreeCandidateInput[]; }
export interface WorktreeCiGateRunRecord { gate_run_id: string; workspace_id: string; workflow_name: string; status: WorktreeCiGateStatus; min_eval_score: number; winner_candidate_id: string | null; winner_model: string | null; cost_saved_usd: number; dlp_redactions: number; candidates: WorktreeCandidateInput[]; gate_sha256: string; created_at: string; }

export class PlatformHarnessHttpError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message); this.name = "PlatformHarnessHttpError"; this.status = status; this.code = code;
  }
}

export function canRbacMutateHarness(role: HarnessRbacRole): boolean {
  switch (role) {
    case "owner": case "admin": case "builder": case "developer": case "operator": return true;
    case "auditor": case "viewer": return false;
    default: { const _exhaustive: never = role; return _exhaustive; }
  }
}

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const DLP_PATTERNS = [/Bearer\s+[^\s)",']+/gi, /sk-[A-Za-z0-9_-]{8,}/g, /AKIA[0-9A-Z]{12,}/g, /ghp_[A-Za-z0-9]{10,}/g, /-----BEGIN [A-Z ]*PRIVATE KEY-----/g];
const HARD_DENY_TOKENS = ["rm -rf /", "mkfs", "dd if=", "~/.ssh/id_", "/etc/shadow", "PRIVATE KEY"];
const SENSITIVE_MUTATION_TOKENS = ["git push", "drop table", "delete from", "kubectl apply", "terraform apply", "docker push", "curl -x post", "chmod 777"];
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const shaDigest = (seed: string): string => `sha256:${[1, 2, 3, 4].map((i) => computeLocalFingerprintHex(`ch:${i}:${seed}`)).join("")}`;
const skipTestFetch = (): boolean =>
  import.meta.env.MODE === "test" &&
  (typeof globalThis.fetch !== "function" || (!("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN));

const ticketsByWs = new Map<string, ApprovalTicketRecord[]>();
const ciRunsByWs = new Map<string, WorktreeCiGateRunRecord[]>();
let localSeq = 0;

export function resetHarnessFallbackStore(): void {
  ticketsByWs.clear(); ciRunsByWs.clear(); localSeq = 0;
}

function scrubDlpText(raw: string): { scrubbed: string; redactions: number } {
  let scrubbed = raw;
  let redactions = 0;
  for (const pat of DLP_PATTERNS) {
    scrubbed = scrubbed.replace(new RegExp(pat.source, pat.flags), () => { redactions += 1; return "[REDACTED_SECRET]"; });
  }
  return { scrubbed, redactions };
}

function assertMutateRbac(role: HarnessRbacRole): void {
  if (!canRbacMutateHarness(role)) throw new PlatformHarnessHttpError(403, `RBAC Denied (${role}): Read-only role cannot mutate agent co-harness tickets or CI gate runs.`);
}

async function apiRequest(path: string, init: RequestInit, query?: Record<string, string | undefined>, role?: HarnessRbacRole, actor?: string): Promise<{ ok: boolean; status: number; data: unknown }> {
  if (!path.startsWith("/v1/platform/harness/")) throw new Error(`Security violation: /v1/platform/harness/* required, got ${path}`);
  const search = new URLSearchParams();
  if (query) for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== "") search.set(k, v);
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
    const detail = isRecord(data) && typeof (data.detail ?? data.error ?? data.message) === "string" ? String(data.detail ?? data.error ?? data.message) : `Harness request failed with HTTP ${res.status}.`;
    throw new PlatformHarnessHttpError(res.status, detail, code);
  }
  return { ok: res.ok, status: res.status, data };
}

function resolveHookConfigSpec(host: AgentHostId, ws: string, mode: HookEnforcementMode): { targetPath: string; content: string } {
  const cmd = `keelway harness intercept --workspace ${ws} --host ${host} --mode ${mode}`;
  switch (host) {
    case "claude_code": return { targetPath: ".claude/settings.local.json", content: JSON.stringify({ hooks: { PreToolUse: [{ matcher: "Bash", hooks: [{ type: "command", command: cmd }] }] } }) };
    case "cursor": return { targetPath: ".cursor/hooks.json", content: JSON.stringify({ version: 1, hooks: { beforeShellExecution: [{ command: cmd }] } }) };
    case "codex_cli": return { targetPath: ".codex/hooks.toml", content: `[hooks.PreToolUse]\ncommand = "${cmd}"\n` };
    default: { const _exhaustive: never = host; return _exhaustive; }
  }
}

export async function renderAgentHookConfig(req: RenderAgentHookConfigRequest = {}, role: HarnessRbacRole = "owner", actor?: string): Promise<HookManifestResponse> {
  const ws = req.workspace_id ?? "default"; const host: AgentHostId = req.agent_host ?? "claude_code"; const mode: HookEnforcementMode = req.mode ?? "enforce";
  const res = await apiRequest("/v1/platform/harness/hooks/render", { method: "POST", body: JSON.stringify({ workspace_id: ws, agent_host: host, mode }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.target_config_path === "string") return res.data as unknown as HookManifestResponse;
  const spec = resolveHookConfigSpec(host, ws, mode);
  return { workspace_id: ws, agent_host: host, mode, target_config_path: spec.targetPath, hook_event: "PreToolUse", config_content: spec.content, cli_install_hint: `keelway harness install --host ${host} --workspace ${ws}`, config_sha256: shaDigest(`${ws}:${host}:${mode}:${spec.content}`) };
}

export async function interceptAgentToolCall(req: InterceptAgentToolCallRequest = {}, role: HarnessRbacRole = "owner", actor?: string): Promise<HarnessInterceptionRecord> {
  const ws = req.workspace_id ?? "default"; const host: AgentHostId = req.agent_host ?? "claude_code";
  const tool = req.tool_name ?? "Bash"; const rawCmd = req.command ?? "git push origin main"; const ticketId = req.ticket_id ?? null;
  const res = await apiRequest("/v1/platform/harness/intercept", { method: "POST", body: JSON.stringify({ workspace_id: ws, agent_host: host, tool_name: tool, command: rawCmd, ticket_id: ticketId }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.interception_id === "string") return res.data as unknown as HarnessInterceptionRecord;
  assertMutateRbac(role);
  const { scrubbed, redactions } = scrubDlpText(rawCmd);
  const cmdSha = shaDigest(`cmd:${rawCmd}`);
  const lower = rawCmd.toLowerCase();
  const now = new Date().toISOString();
  localSeq += 1;
  const icpId = `icp-${computeLocalFingerprintHex(`${ws}:${localSeq}:${cmdSha}`).slice(0, 12)}`;
  const buildRec = (verdict: HarnessVerdict, reasonCode: string, explanation: string, boundTicket: string | null): HarnessInterceptionRecord => ({
    interception_id: icpId, workspace_id: ws, agent_host: host, tool_name: tool, scrubbed_command: scrubbed, command_sha256: cmdSha,
    verdict, reason_code: reasonCode, explanation, ticket_id: boundTicket, dlp_redactions: redactions,
    event_sha256: shaDigest(`${icpId}:${verdict}:${reasonCode}:${boundTicket ?? "none"}`), created_at: now,
  });
  if (redactions > 0 || HARD_DENY_TOKENS.some((tok) => rawCmd.includes(tok) || lower.includes(tok.toLowerCase()))) {
    const code = redactions > 0 ? "dlp_secret_exfiltration_blocked" : "destructive_command_blocked";
    return buildRec("DENY", code, "PreToolUse co-harness blocked destructive or secret-bearing shell invocation.", null);
  }
  const wsTickets = ticketsByWs.get(ws) ?? [];
  if (ticketId) {
    const found = wsTickets.find((t) => t.ticket_id === ticketId);
    if (!found) return buildRec("DENY", "ticket_not_found", `Approval ticket '${ticketId}' not found in workspace '${ws}'.`, ticketId);
    if (found.command_sha256 !== cmdSha) return buildRec("DENY", "ticket_command_mismatch", "Submitted command SHA-256 does not match ticket command binding.", ticketId);
    if (found.status === "CONSUMED") return buildRec("DENY", "ticket_already_consumed", "Single-use P-10 approval ticket has already been consumed.", ticketId);
    if (found.status === "DENIED") return buildRec("DENY", "ticket_denied", "P-10 approval ticket was explicitly denied.", ticketId);
    if (found.status === "PENDING") return buildRec("HOLD_TICKET", "ticket_pending_approval", "P-10 ticket awaits human approval before replay.", ticketId);
    const updated: ApprovalTicketRecord = { ...found, status: "CONSUMED", consumed_at: now, ticket_sha256: shaDigest(`${found.ticket_id}:CONSUMED:${now}`) };
    ticketsByWs.set(ws, wsTickets.map((t) => (t.ticket_id === ticketId ? updated : t)));
    return buildRec("ALLOW_WITH_TICKET", "p10_ticket_verified_consumed", "Single-use SHA-256 P-10 ticket verified and atomically consumed.", ticketId);
  }
  if (SENSITIVE_MUTATION_TOKENS.some((tok) => lower.includes(tok))) {
    const newTicketId = `tkt-${computeLocalFingerprintHex(`${ws}:tkt:${localSeq}:${cmdSha}`).slice(0, 12)}`;
    const ticket: ApprovalTicketRecord = {
      ticket_id: newTicketId, workspace_id: ws, agent_host: host, tool_name: tool, scrubbed_command: scrubbed, command_sha256: cmdSha,
      status: "PENDING", reviewer: null, decision_reason: null, created_at: now, decided_at: null, consumed_at: null, ticket_sha256: shaDigest(`${newTicketId}:PENDING:${cmdSha}`),
    };
    ticketsByWs.set(ws, [ticket, ...wsTickets]);
    return buildRec("HOLD_TICKET", "p10_approval_required", "Sensitive mutation held pending single-use P-10 human approval ticket.", newTicketId);
  }
  return buildRec("ALLOW", "safe_readonly_or_test_command", "Read-only or local test command cleared PreToolUse co-harness.", null);
}

export async function listHarnessTickets(workspaceId = "default", status?: HarnessTicketStatus | "", limit = 25, role: HarnessRbacRole = "owner", actor?: string): Promise<ApprovalTicketRecord[]> {
  const res = await apiRequest("/v1/platform/harness/tickets", { method: "GET" }, { workspace_id: workspaceId, status: status || undefined, limit: String(limit) }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.tickets)) return res.data.tickets as ApprovalTicketRecord[];
  const all = ticketsByWs.get(workspaceId) ?? [];
  return (status ? all.filter((t) => t.status === status) : all).slice(0, limit);
}

export async function decideHarnessTicket(ticketId: string, req: DecideHarnessTicketRequest, role: HarnessRbacRole = "owner", actor?: string): Promise<ApprovalTicketRecord> {
  const ws = req.workspace_id ?? "default"; const reviewer = req.reviewer ?? "lead-engineer"; const reason = req.reason ?? "Verified safe workspace scope";
  const res = await apiRequest(`/v1/platform/harness/tickets/${encodeURIComponent(ticketId)}/decide`, { method: "POST", body: JSON.stringify({ workspace_id: ws, decision: req.decision, reviewer, reason }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.ticket_id === "string") return res.data as unknown as ApprovalTicketRecord;
  assertMutateRbac(role);
  const wsTickets = ticketsByWs.get(ws) ?? [];
  const target = wsTickets.find((t) => t.ticket_id === ticketId);
  if (!target) throw new PlatformHarnessHttpError(404, `Harness ticket '${ticketId}' not found in workspace '${ws}'.`, "ticket_not_found");
  if (target.status === "CONSUMED") throw new PlatformHarnessHttpError(409, `Harness ticket '${ticketId}' is already CONSUMED.`, "ticket_already_consumed");
  const now = new Date().toISOString();
  const decided: ApprovalTicketRecord = { ...target, status: req.decision, reviewer, decision_reason: reason, decided_at: now, ticket_sha256: shaDigest(`${ticketId}:${req.decision}:${now}`) };
  ticketsByWs.set(ws, wsTickets.map((t) => (t.ticket_id === ticketId ? decided : t)));
  return decided;
}

export async function evaluateWorktreeCiGate(req: EvaluateWorktreeCiGateRequest = {}, role: HarnessRbacRole = "owner", actor?: string): Promise<WorktreeCiGateRunRecord> {
  const ws = req.workspace_id ?? "default"; const wfName = req.workflow_name ?? "pr-worktree-arena";
  const diffSummary = req.diff_summary ?? "Refactor retry backoff & add unit test in core/platform/";
  const minEval = req.min_eval_score ?? 0.85;
  const res = await apiRequest("/v1/platform/harness/ci-gate/evaluate", { method: "POST", body: JSON.stringify({ workspace_id: ws, workflow_name: wfName, diff_summary: diffSummary, min_eval_score: minEval, ...(req.candidates ? { candidates: req.candidates } : {}) }) }, undefined, role, actor);
  if (res.ok && isRecord(res.data) && typeof res.data.gate_run_id === "string") return res.data as unknown as WorktreeCiGateRunRecord;
  assertMutateRbac(role);
  const rawCandidates: WorktreeCandidateInput[] = req.candidates ?? [
    { candidate_id: "cand-local", worktree_branch: "wt/opencore-7b", model_id: "keelway-core:7b", provider_tier: "local_opencore", tests_passed: true, eval_score: 0.92, cost_usd: 0.0, diff_excerpt: "+ assert retry_budget <= 3" },
    { candidate_id: "cand-frontier", worktree_branch: "wt/sonnet-byom", model_id: "claude-3-7-sonnet", provider_tier: "frontier_byom", tests_passed: true, eval_score: 0.93, cost_usd: 0.048, diff_excerpt: "+ assert retry_budget <= 3" },
  ];
  let redactions = scrubDlpText(diffSummary).redactions;
  const candidates = rawCandidates.map((c) => {
    const sc = scrubDlpText(c.diff_excerpt ?? "");
    redactions += sc.redactions;
    return { ...c, ...(c.diff_excerpt !== undefined ? { diff_excerpt: sc.scrubbed } : {}) };
  });
  const qualifying = candidates.filter((c) => c.tests_passed && c.eval_score >= minEval);
  const status: WorktreeCiGateStatus = redactions > 0 ? "FAIL_SAFETY" : qualifying.length === 0 ? "FAIL_REGRESSION" : "PASS";
  const winner = status === "PASS" ? (qualifying.find((c) => c.provider_tier === "local_opencore") ?? qualifying.sort((a, b) => b.eval_score - a.eval_score)[0] ?? null) : null;
  const maxFrontierCost = candidates.filter((c) => c.provider_tier === "frontier_byom").reduce((m, c) => Math.max(m, c.cost_usd), 0);
  const costSaved = winner ? Number(Math.max(0, maxFrontierCost - winner.cost_usd).toFixed(4)) : 0;
  localSeq += 1;
  const runId = `cigate-${computeLocalFingerprintHex(`${ws}:${wfName}:${localSeq}`).slice(0, 12)}`;
  const rec: WorktreeCiGateRunRecord = {
    gate_run_id: runId, workspace_id: ws, workflow_name: wfName, status, min_eval_score: minEval,
    winner_candidate_id: winner?.candidate_id ?? null, winner_model: winner?.model_id ?? null,
    cost_saved_usd: costSaved, dlp_redactions: redactions, candidates,
    gate_sha256: shaDigest(`${runId}:${status}:${winner?.candidate_id ?? "none"}:${minEval}`), created_at: new Date().toISOString(),
  };
  ciRunsByWs.set(ws, [rec, ...(ciRunsByWs.get(ws) ?? [])]);
  return rec;
}

export async function listWorktreeCiGateRuns(workspaceId = "default", limit = 25, role: HarnessRbacRole = "owner", actor?: string): Promise<WorktreeCiGateRunRecord[]> {
  const res = await apiRequest("/v1/platform/harness/ci-gate/runs", { method: "GET" }, { workspace_id: workspaceId, limit: String(limit) }, role, actor);
  if (res.ok && isRecord(res.data) && Array.isArray(res.data.runs)) return res.data.runs as WorktreeCiGateRunRecord[];
  return (ciRunsByWs.get(workspaceId) ?? []).slice(0, limit);
}
