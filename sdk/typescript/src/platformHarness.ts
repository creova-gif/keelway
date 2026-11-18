/**
 * Keelway Official TypeScript SDK — Phase 18 Universal Coding-Agent Co-Harness
 * + Parallel Worktree CI Gate (`client.platform` / `client.platform.harness`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type HarnessAgentHost = "claude_code" | "cursor" | "codex_cli";
export type HarnessHookMode = "enforce" | "audit_only";
export type HarnessInterceptionVerdict = "ALLOW" | "ALLOW_WITH_TICKET" | "HOLD_TICKET" | "DENY";
export type HarnessTicketStatus = "PENDING" | "APPROVED" | "DENIED" | "CONSUMED";
export type HarnessTicketDecision = "APPROVED" | "DENIED";
export type WorktreeProviderTier = "local_opencore" | "frontier_byom";
export type WorktreeCiGateStatus = "PASS" | "FAIL_REGRESSION" | "FAIL_SAFETY";

export interface RenderAgentHookConfigRequest {
  workspace_id?: string;
  agent_host?: HarnessAgentHost;
  mode?: HarnessHookMode;
}
export interface HookManifestResponse {
  workspace_id: string;
  agent_host: HarnessAgentHost;
  mode: HarnessHookMode;
  target_config_path: string;
  hook_event: string;
  config_content: string;
  cli_install_hint: string;
  config_sha256: string;
  [key: string]: unknown;
}
export interface InterceptAgentToolCallRequest {
  workspace_id?: string;
  agent_host?: HarnessAgentHost;
  tool_name?: string;
  command?: string;
  ticket_id?: string | null;
}
export interface HarnessInterceptionRecord {
  interception_id: string;
  workspace_id: string;
  agent_host: HarnessAgentHost;
  tool_name: string;
  scrubbed_command: string;
  command_sha256: string;
  verdict: HarnessInterceptionVerdict;
  reason_code: string;
  explanation: string;
  ticket_id: string | null;
  dlp_redactions: number;
  event_sha256: string;
  created_at: string;
  [key: string]: unknown;
}
export interface ApprovalTicketRecord {
  ticket_id: string;
  workspace_id: string;
  agent_host: HarnessAgentHost;
  tool_name: string;
  scrubbed_command: string;
  command_sha256: string;
  status: HarnessTicketStatus;
  reviewer: string | null;
  decision_reason: string | null;
  created_at: string;
  decided_at: string | null;
  consumed_at: string | null;
  ticket_sha256: string;
  [key: string]: unknown;
}
export interface ListHarnessTicketsOptions {
  workspace_id?: string;
  status?: HarnessTicketStatus;
  limit?: number;
}
export type ListHarnessTicketsParams = ListHarnessTicketsOptions;
export interface ApprovalTicketListResponse {
  workspace_id: string;
  count: number;
  tickets: ApprovalTicketRecord[];
  [key: string]: unknown;
}
export interface DecideHarnessTicketRequest {
  workspace_id?: string;
  decision: HarnessTicketDecision;
  reviewer?: string;
  reason?: string;
}
export interface WorktreeCandidateInput {
  candidate_id: string;
  worktree_branch: string;
  model_id: string;
  provider_tier: WorktreeProviderTier;
  tests_passed: boolean;
  eval_score: number;
  cost_usd: number;
  diff_excerpt?: string;
  [key: string]: unknown;
}
export interface EvaluateWorktreeCiGateRequest {
  workspace_id?: string;
  workflow_name?: string;
  diff_summary?: string;
  min_eval_score?: number;
  candidates?: WorktreeCandidateInput[];
}
export interface WorktreeCiGateRunRecord {
  gate_run_id: string;
  workspace_id: string;
  workflow_name: string;
  status: WorktreeCiGateStatus;
  min_eval_score: number;
  winner_candidate_id: string | null;
  winner_model: string | null;
  cost_saved_usd: number;
  dlp_redactions: number;
  candidates: WorktreeCandidateInput[];
  gate_sha256: string;
  created_at: string;
  [key: string]: unknown;
}
export interface ListWorktreeCiGateRunsParams {
  workspace_id?: string;
  limit?: number;
}
export type ListWorktreeCiGateRunsOptions = ListWorktreeCiGateRunsParams;
export interface WorktreeCiGateRunListResponse {
  workspace_id: string;
  count: number;
  runs: WorktreeCiGateRunRecord[];
  [key: string]: unknown;
}

function assertAgentHost(host: HarnessAgentHost): HarnessAgentHost {
  switch (host) {
    case "claude_code":
    case "cursor":
    case "codex_cli":
      return host;
    default: {
      const _exhaustive: never = host;
      throw new Error(`Invalid agent_host '${String(_exhaustive)}'.`);
    }
  }
}
function assertHookMode(mode: HarnessHookMode): HarnessHookMode {
  switch (mode) {
    case "enforce":
    case "audit_only":
      return mode;
    default: {
      const _exhaustive: never = mode;
      throw new Error(`Invalid mode '${String(_exhaustive)}'.`);
    }
  }
}
function assertTicketStatus(status: HarnessTicketStatus): HarnessTicketStatus {
  switch (status) {
    case "PENDING":
    case "APPROVED":
    case "DENIED":
    case "CONSUMED":
      return status;
    default: {
      const _exhaustive: never = status;
      throw new Error(`Invalid status '${String(_exhaustive)}'.`);
    }
  }
}
function assertTicketDecision(decision: HarnessTicketDecision): HarnessTicketDecision {
  switch (decision) {
    case "APPROVED":
    case "DENIED":
      return decision;
    default: {
      const _exhaustive: never = decision;
      throw new Error(`Invalid decision '${String(_exhaustive)}'.`);
    }
  }
}
function encodeSeg(value: string, fieldName: string): string {
  const clean = (value ?? "").trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

function resolveTicketsListCall(
  wsOrOpts: string | ListHarnessTicketsOptions | undefined,
  limitOrOpts: number | RequestOptions | undefined,
  options: RequestOptions | undefined,
): { query: Record<string, string>; options?: RequestOptions } {
  const isObj = typeof wsOrOpts === "object" && wsOrOpts !== null;
  const wsId = ((isObj ? wsOrOpts.workspace_id : wsOrOpts) ?? "default").trim() || "default";
  const limit = isObj ? (wsOrOpts.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
  const opts = isObj ? (limitOrOpts as RequestOptions | undefined) : typeof limitOrOpts === "object" ? limitOrOpts : options;
  if (!Number.isInteger(limit) || limit < 1) throw new Error("limit must be >= 1.");
  const query: Record<string, string> = { workspace_id: wsId, limit: String(limit) };
  if (isObj && wsOrOpts.status !== undefined) query.status = assertTicketStatus(wsOrOpts.status);
  return { query, options: opts };
}

export class PlatformHarnessClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public renderAgentHookConfig(req: RenderAgentHookConfigRequest = {}, options?: RequestOptions): Promise<HookManifestResponse> {
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      agent_host: assertAgentHost(req.agent_host ?? "claude_code"),
      mode: assertHookMode(req.mode ?? "enforce"),
    };
    return this.requestJson("POST", "/v1/platform/harness/hooks/render", { body, options });
  }

  public interceptAgentToolCall(req: InterceptAgentToolCallRequest = {}, options?: RequestOptions): Promise<HarnessInterceptionRecord> {
    const toolName = (req.tool_name ?? "Bash").trim();
    if (!toolName) throw new Error("tool_name must be non-empty.");
    const command = (req.command ?? "git push origin main").trim();
    if (!command) throw new Error("command must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      agent_host: assertAgentHost(req.agent_host ?? "claude_code"),
      tool_name: toolName,
      command,
    };
    if (req.ticket_id !== undefined && req.ticket_id !== null && req.ticket_id.trim() !== "") body.ticket_id = req.ticket_id.trim();
    return this.requestJson("POST", "/v1/platform/harness/intercept", { body, options });
  }

  public listHarnessTickets(workspaceId?: string | ListHarnessTicketsOptions, limit?: number): Promise<ApprovalTicketListResponse>;
  public listHarnessTickets(params?: ListHarnessTicketsOptions, options?: RequestOptions): Promise<ApprovalTicketListResponse>;
  public listHarnessTickets(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<ApprovalTicketListResponse>;
  public listHarnessTickets(wsOrOpts?: string | ListHarnessTicketsOptions, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<ApprovalTicketListResponse> {
    return this.requestJson("GET", "/v1/platform/harness/tickets", resolveTicketsListCall(wsOrOpts, limitOrOpts, options));
  }

  public decideHarnessTicket(ticketId: string, req: DecideHarnessTicketRequest, options?: RequestOptions): Promise<ApprovalTicketRecord> {
    const seg = encodeSeg(ticketId, "ticket_id");
    const reviewer = (req.reviewer ?? "lead-engineer").trim();
    if (!reviewer) throw new Error("reviewer must be non-empty.");
    const reason = (req.reason ?? "Verified safe workspace scope").trim();
    if (!reason) throw new Error("reason must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      decision: assertTicketDecision(req.decision),
      reviewer,
      reason,
    };
    return this.requestJson("POST", `/v1/platform/harness/tickets/${seg}/decide`, { body, options });
  }

  public evaluateWorktreeCiGate(req: EvaluateWorktreeCiGateRequest = {}, options?: RequestOptions): Promise<WorktreeCiGateRunRecord> {
    const workflowName = (req.workflow_name ?? "pr-worktree-arena").trim();
    if (!workflowName) throw new Error("workflow_name must be non-empty.");
    const diffSummary = (req.diff_summary ?? "Refactor retry backoff & add unit test in core/platform/").trim();
    if (!diffSummary) throw new Error("diff_summary must be non-empty.");
    const minScore = req.min_eval_score ?? 0.85;
    if (typeof minScore !== "number" || Number.isNaN(minScore) || minScore < 0 || minScore > 1) throw new Error("min_eval_score must be between 0.0 and 1.0.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      workflow_name: workflowName,
      diff_summary: diffSummary,
      min_eval_score: minScore,
    };
    if (req.candidates !== undefined) body.candidates = req.candidates;
    return this.requestJson("POST", "/v1/platform/harness/ci-gate/evaluate", { body, options });
  }

  public listWorktreeCiGateRuns(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<WorktreeCiGateRunListResponse>;
  public listWorktreeCiGateRuns(params?: ListWorktreeCiGateRunsParams, options?: RequestOptions): Promise<WorktreeCiGateRunListResponse>;
  public listWorktreeCiGateRuns(wsOrParams?: string | ListWorktreeCiGateRunsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<WorktreeCiGateRunListResponse> {
    return this.requestJson("GET", "/v1/platform/harness/ci-gate/runs", resolveTicketsListCall(wsOrParams, limitOrOpts, options));
  }
}

export { PlatformHarnessClient as PlatformHarnessDelegate };
