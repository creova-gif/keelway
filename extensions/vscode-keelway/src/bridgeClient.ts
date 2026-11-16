/**
 * Keelway Loopback Debugger Bridge Client for VS Code & Cursor Extension Host.
 * Authenticates via Bearer token and strips any browser Origin header to preserve zero-CSRF loopback posture.
 */

export type AttachScheme = "vscode" | "cursor";
export type DebugStepAction = "step_over" | "step_into" | "continue" | "mutate_state";
export type HarnessTicketDecision = "APPROVED" | "DENIED";
export type BridgeDistillationPromotionVerdict = "PROMOTE_TO_OPENCORE" | "NEEDS_MORE_PAIRS" | "HOLD_ON_FRONTIER";

export interface BridgeDistillationPromotionOptions {
  workspaceId?: string;
  taskTag?: string;
  targetLocalModel?: string;
  minPairs?: number;
  minAvgParity?: number;
  monthlyRequestVolume?: number;
}

export interface BridgeDistillationPromotionEvaluation {
  evaluation_id: string;
  workspace_id: string;
  task_tag: string;
  target_local_model: string;
  verdict: BridgeDistillationPromotionVerdict;
  pair_count: number;
  min_pairs: number;
  avg_parity_score: number;
  min_avg_parity: number;
  avg_frontier_cost_usd: number;
  monthly_request_volume: number;
  projected_monthly_savings_usd: number;
  recommendation: string;
  gate_sha256: string;
  evaluated_at: string;
  [key: string]: unknown;
}

export interface BridgeHarnessTicketRecord {
  ticket_id: string;
  workspace_id: string;
  agent_host: string;
  tool_name: string;
  scrubbed_command: string;
  command_sha256: string;
  status: "PENDING" | "APPROVED" | "DENIED" | "CONSUMED";
  reviewer?: string | null;
  decision_reason?: string | null;
  created_at?: string;
  decided_at?: string | null;
  consumed_at?: string | null;
  ticket_sha256?: string;
  [key: string]: unknown;
}

export interface AttachTarget {
  readonly scheme: AttachScheme;
  readonly port: number;
  readonly baseUrl: string;
  readonly workspaceId: string;
  readonly workflowId: string;
  readonly sessionId?: string;
}

export interface BridgeBreakpointRecord {
  breakpoint_id: string;
  workspace_id: string;
  workflow_id: string;
  node_id?: string | null;
  file_path?: string;
  line_number?: number | null;
  condition_type?: string;
  condition?: string | null;
  threshold?: number | null;
  enabled: boolean;
  label?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface BridgeDebugSession {
  session_id: string;
  workspace_id: string;
  workflow_id: string;
  status: string;
  current_step_index?: number;
  step_index?: number;
  step_depth?: number;
  total_steps?: number;
  hit_breakpoint_id?: string | null;
  hit_reason?: string | null;
  active_step?: { node_id?: string; agent_id?: string; tool_name?: string; line_number?: number; [key: string]: unknown };
  current_node_id?: string | null;
  variables?: Record<string, unknown>;
  state?: Record<string, unknown>;
  call_stack?: Array<Record<string, unknown>>;
  mutation_count?: number;
  frame_sha256?: string;
  [key: string]: unknown;
}

export interface BridgeCodelensItem {
  symbol?: string;
  node_id?: string;
  file_path?: string;
  line_start?: number;
  model_checkpoint?: string;
  model_id?: string;
  p50_ms?: number;
  p50_latency_ms?: number;
  avg_cost_usd?: number;
  cost_usd?: number;
  provenance_4d?: string;
  zero_egress?: boolean;
  attached_breakpoints?: number;
  breakpoint_count?: number;
  [key: string]: unknown;
}

export interface BridgeClientOptions {
  baseUrl?: string;
  workspaceId?: string;
  workflowId?: string;
  apiToken?: string;
  getToken?: () => PromiseLike<string | undefined> | string | undefined;
  fetchImpl?: typeof fetch;
}

export class BridgeHttpError extends Error {
  constructor(public readonly status: number, public readonly detail: string, public readonly payload?: unknown) {
    super(`Keelway bridge HTTP ${status}: ${detail}`);
    this.name = "BridgeHttpError";
  }
}

export function parseAttachUri(uriString: string): AttachTarget {
  let parsed: URL;
  try {
    parsed = new URL(uriString.trim());
  } catch {
    throw new Error(`Invalid Keelway attach URI: ${uriString}`);
  }
  const rawScheme = parsed.protocol.replace(/:$/, "").toLowerCase();
  if (rawScheme !== "vscode" && rawScheme !== "cursor") {
    throw new Error(`Unsupported URI scheme '${rawScheme}': expected 'vscode' or 'cursor'.`);
  }
  const authority = parsed.host.toLowerCase();
  if (authority && authority !== "keelway.vscode-keelway") throw new Error(`Unexpected extension authority '${authority}'.`);
  if (parsed.pathname !== "/attach") throw new Error(`Unsupported attach path '${parsed.pathname}': expected '/attach'.`);
  const rawPort = parsed.searchParams.get("port") ?? "7420";
  const port = Number(rawPort);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid loopback port '${rawPort}'.`);
  const workspaceId = (parsed.searchParams.get("workspace") ?? parsed.searchParams.get("workspace_id") ?? "default").trim() || "default";
  const workflowId = (parsed.searchParams.get("workflow") ?? parsed.searchParams.get("workflow_id") ?? "WF-STUDIO-01").trim() || "WF-STUDIO-01";
  const sessionParam = (parsed.searchParams.get("session") ?? parsed.searchParams.get("session_id") ?? "").trim();
  return { scheme: rawScheme, port, baseUrl: `http://127.0.0.1:${port}`, workspaceId, workflowId, ...(sessionParam ? { sessionId: sessionParam } : {}) };
}

function encodeSeg(value: string, label: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${label} must be non-empty.`);
  return encodeURIComponent(clean);
}

export class KeelwayBridgeClient {
  private baseUrl: string;
  private workspaceId: string;
  private workflowId: string;
  private apiToken: string | undefined;
  private readonly getTokenFn: (() => PromiseLike<string | undefined> | string | undefined) | undefined;
  private readonly fetchFn: typeof fetch;

  constructor(options: BridgeClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://127.0.0.1:7420").replace(/\/+$/, "");
    this.workspaceId = options.workspaceId ?? "default";
    this.workflowId = options.workflowId ?? "WF-STUDIO-01";
    this.apiToken = options.apiToken;
    this.getTokenFn = options.getToken;
    this.fetchFn = options.fetchImpl ?? globalThis.fetch;
  }

  public getTarget(): { baseUrl: string; workspaceId: string; workflowId: string } {
    return { baseUrl: this.baseUrl, workspaceId: this.workspaceId, workflowId: this.workflowId };
  }

  public configureTarget(target: { baseUrl?: string; workspaceId?: string; workflowId?: string; apiToken?: string }): void {
    if (target.baseUrl) this.baseUrl = target.baseUrl.replace(/\/+$/, "");
    if (target.workspaceId) this.workspaceId = target.workspaceId;
    if (target.workflowId) this.workflowId = target.workflowId;
    if (target.apiToken !== undefined) this.apiToken = target.apiToken;
  }

  private async request<T>(method: string, path: string, opts?: { query?: Record<string, string | undefined>; body?: Record<string, unknown>; extraHeaders?: Record<string, string> }): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [k, v] of Object.entries(opts?.query ?? {})) {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    }
    const headers: Record<string, string> = { Accept: "application/json" };
    for (const [hk, hv] of Object.entries(opts?.extraHeaders ?? {})) {
      if (hk.toLowerCase() !== "origin") headers[hk] = hv;
    }
    const resolvedToken = this.apiToken ?? (this.getTokenFn ? await this.getTokenFn() : undefined);
    if (resolvedToken && resolvedToken.trim()) headers.Authorization = `Bearer ${resolvedToken.trim()}`;
    if (opts?.body !== undefined) headers["Content-Type"] = "application/json";
    delete headers.Origin;
    delete headers.origin;

    const response = await this.fetchFn(url.toString(), { method, headers, body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined });
    const text = await response.text();
    const parsed: unknown = text ? JSON.parse(text) : {};
    if (!response.ok) {
      const detail = typeof parsed === "object" && parsed !== null && "detail" in parsed ? String((parsed as { detail: unknown }).detail) : response.statusText || `HTTP ${response.status}`;
      throw new BridgeHttpError(response.status, detail, parsed);
    }
    return parsed as T;
  }

  public setBreakpoint(payload: { node_id?: string; workflow_id?: string; workspace_id?: string; condition_type?: string; threshold?: number; condition?: string; enabled?: boolean; file_path?: string; line_number?: number; label?: string }): Promise<BridgeBreakpointRecord> {
    const body: Record<string, unknown> = { workspace_id: payload.workspace_id ?? this.workspaceId, workflow_id: payload.workflow_id ?? this.workflowId, condition_type: payload.condition_type ?? "always", enabled: payload.enabled ?? true };
    if (payload.node_id !== undefined) body.node_id = payload.node_id.trim();
    if (payload.threshold !== undefined) body.threshold = payload.threshold;
    if (payload.condition !== undefined) body.condition = payload.condition;
    if (payload.file_path !== undefined) body.file_path = payload.file_path;
    if (payload.line_number !== undefined) body.line_number = payload.line_number;
    if (payload.label !== undefined) body.label = payload.label;
    return this.request<BridgeBreakpointRecord>("POST", "/v1/platform/debugger/breakpoints", { body });
  }

  public listBreakpoints(params: { workspace_id?: string; workflow_id?: string } = {}): Promise<{ workspace_id: string; count: number; breakpoints: BridgeBreakpointRecord[] }> {
    return this.request("GET", "/v1/platform/debugger/breakpoints", { query: { workspace_id: params.workspace_id ?? this.workspaceId, workflow_id: params.workflow_id } });
  }

  public deleteBreakpoint(breakpointId: string, workspaceId?: string): Promise<{ deleted: boolean; breakpoint_id: string; workspace_id: string }> {
    return this.request("DELETE", `/v1/platform/debugger/breakpoints/${encodeSeg(breakpointId, "breakpoint_id")}`, { query: { workspace_id: workspaceId ?? this.workspaceId } });
  }

  public startDebugSession(payload: { workspace_id?: string; workflow_id?: string; steps?: Array<Record<string, unknown>>; initial_state?: Record<string, unknown> } = {}): Promise<BridgeDebugSession> {
    const body: Record<string, unknown> = { workspace_id: payload.workspace_id ?? this.workspaceId, workflow_id: payload.workflow_id ?? this.workflowId };
    if (payload.steps !== undefined) body.steps = payload.steps;
    if (payload.initial_state !== undefined) body.initial_state = payload.initial_state;
    return this.request<BridgeDebugSession>("POST", "/v1/platform/debugger/sessions", { body });
  }

  public listDebugSessions(params: { workspace_id?: string; limit?: number } = {}): Promise<{ workspace_id: string; count: number; sessions: BridgeDebugSession[] }> {
    return this.request("GET", "/v1/platform/debugger/sessions", { query: { workspace_id: params.workspace_id ?? this.workspaceId, limit: String(params.limit ?? 20) } });
  }

  public stepDebugSession(sessionId: string, payload: { action: DebugStepAction; workspace_id?: string; state_patch?: Record<string, unknown>; mutate_state?: Record<string, unknown> }): Promise<BridgeDebugSession> {
    const body: Record<string, unknown> = { workspace_id: payload.workspace_id ?? this.workspaceId, action: payload.action };
    const patch = payload.state_patch ?? payload.mutate_state;
    if (patch !== undefined) body.state_patch = patch;
    return this.request<BridgeDebugSession>("POST", `/v1/platform/debugger/sessions/${encodeSeg(sessionId, "session_id")}/step`, { body });
  }

  public getCodelens(params: { workspace_id?: string; workflow_id?: string; file_path?: string } = {}): Promise<{ workspace_id: string; workflow_id?: string; vscode_attach_uri?: string; cursor_attach_uri?: string; lenses?: BridgeCodelensItem[]; items?: BridgeCodelensItem[] }> {
    return this.request("GET", "/v1/platform/debugger/codelens", { query: { workspace_id: params.workspace_id ?? this.workspaceId, workflow_id: params.workflow_id, file_path: params.file_path } });
  }

  public async listPendingHarnessTickets(workspaceId?: string): Promise<{ workspace_id: string; count: number; tickets: BridgeHarnessTicketRecord[] }> {
    const wsId = (workspaceId ?? this.workspaceId).trim() || "default";
    const res = await this.request<{ workspace_id: string; count: number; tickets: BridgeHarnessTicketRecord[] }>(
      "GET",
      "/v1/platform/harness/tickets",
      { query: { workspace_id: wsId, status: "PENDING" } },
    );
    const pending = Array.isArray(res.tickets) ? res.tickets.filter((t) => t.status === "PENDING") : [];
    return { ...res, workspace_id: res.workspace_id ?? wsId, count: pending.length, tickets: pending };
  }

  public decideHarnessTicket(ticketId: string, decision: "APPROVED" | "DENIED", workspaceId?: string): Promise<BridgeHarnessTicketRecord> {
    let validatedDecision: HarnessTicketDecision;
    switch (decision) {
      case "APPROVED":
      case "DENIED":
        validatedDecision = decision;
        break;
      default: {
        const _exhaustive: never = decision;
        throw new Error(`Invalid harness ticket decision '${String(_exhaustive)}'.`);
      }
    }
    const wsId = (workspaceId ?? this.workspaceId).trim() || "default";
    return this.request<BridgeHarnessTicketRecord>(
      "POST",
      `/v1/platform/harness/tickets/${encodeSeg(ticketId, "ticket_id")}/decide`,
      {
        body: {
          workspace_id: wsId,
          decision: validatedDecision,
          reviewer: "vscode-bridge",
          reason: "Approved via Keelway IDE Bridge",
        },
      },
    );
  }

  public evaluateDistillationPromotion(opts: BridgeDistillationPromotionOptions = {}): Promise<BridgeDistillationPromotionEvaluation> {
    const wsId = (opts.workspaceId ?? this.workspaceId).trim() || "default";
    const taskTag = (opts.taskTag ?? "code-patch").trim() || "code-patch";
    const targetLocalModel = (opts.targetLocalModel ?? "keelway-core:7b").trim() || "keelway-core:7b";
    return this.request<BridgeDistillationPromotionEvaluation>(
      "POST",
      "/v1/platform/distill/promotion/evaluate",
      {
        body: {
          workspace_id: wsId,
          task_tag: taskTag,
          target_local_model: targetLocalModel,
          min_pairs: opts.minPairs ?? 3,
          min_avg_parity: opts.minAvgParity ?? 0.85,
          monthly_request_volume: opts.monthlyRequestVolume ?? 50000,
        },
      },
    );
  }
}
