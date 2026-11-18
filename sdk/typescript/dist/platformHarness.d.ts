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
export declare class PlatformHarnessClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    renderAgentHookConfig(req?: RenderAgentHookConfigRequest, options?: RequestOptions): Promise<HookManifestResponse>;
    interceptAgentToolCall(req?: InterceptAgentToolCallRequest, options?: RequestOptions): Promise<HarnessInterceptionRecord>;
    listHarnessTickets(workspaceId?: string | ListHarnessTicketsOptions, limit?: number): Promise<ApprovalTicketListResponse>;
    listHarnessTickets(params?: ListHarnessTicketsOptions, options?: RequestOptions): Promise<ApprovalTicketListResponse>;
    listHarnessTickets(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<ApprovalTicketListResponse>;
    decideHarnessTicket(ticketId: string, req: DecideHarnessTicketRequest, options?: RequestOptions): Promise<ApprovalTicketRecord>;
    evaluateWorktreeCiGate(req?: EvaluateWorktreeCiGateRequest, options?: RequestOptions): Promise<WorktreeCiGateRunRecord>;
    listWorktreeCiGateRuns(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<WorktreeCiGateRunListResponse>;
    listWorktreeCiGateRuns(params?: ListWorktreeCiGateRunsParams, options?: RequestOptions): Promise<WorktreeCiGateRunListResponse>;
}
export { PlatformHarnessClient as PlatformHarnessDelegate };
//# sourceMappingURL=platformHarness.d.ts.map