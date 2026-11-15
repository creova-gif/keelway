/**
 * Keelway Official TypeScript SDK — Phase 14 Live Step-Through Debugger,
 * Conditional Gutter Breakpoints, DLP-Guarded State Mutation & 4D Routing CodeLens
 * (`client.platform` / `client.platform.debugger`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type DebuggerConditionType =
  | "always"
  | "cost_usd_gt"
  | "hybrid_score_lt"
  | "before_shell_tool"
  | "before_p10_gate"
  | "line_match";

export type DebuggerStepAction = "step_over" | "step_into" | "continue" | "mutate_state";

export interface SetBreakpointRequest {
  workspace_id?: string;
  workflow_id?: string;
  node_id?: string;
  file_path?: string;
  line_number?: number;
  condition_type?: DebuggerConditionType;
  threshold?: number;
  enabled?: boolean;
  label?: string;
}

export interface DebuggerBreakpointRecord {
  breakpoint_id: string;
  workspace_id: string;
  workflow_id: string;
  node_id: string | null;
  file_path: string;
  line_number: number | null;
  condition_type: DebuggerConditionType;
  threshold: number | null;
  enabled: boolean;
  label: string;
  created_at: string;
  [key: string]: unknown;
}

export interface ListBreakpointsParams {
  workspace_id?: string;
  workflow_id?: string;
}

export interface DebuggerBreakpointListResponse {
  workspace_id: string;
  count: number;
  breakpoints: DebuggerBreakpointRecord[];
  [key: string]: unknown;
}

export interface DeleteBreakpointParams {
  workspace_id?: string;
}

export interface DeleteBreakpointResponse {
  deleted: boolean;
  breakpoint_id: string;
  workspace_id: string;
  [key: string]: unknown;
}

export interface DebuggerStepInput {
  node_id?: string;
  agent_id?: string;
  tool_name?: string;
  cost_usd?: number;
  hybrid_score?: number;
  requires_p10?: boolean;
  line_number?: number;
  variables?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface StartDebugSessionRequest {
  workspace_id?: string;
  workflow_id?: string;
  steps?: DebuggerStepInput[];
  initial_state?: Record<string, unknown>;
}

export interface DebuggerSessionRecord {
  session_id: string;
  workspace_id: string;
  workflow_id: string;
  status: string;
  current_step_index: number;
  step_depth: number;
  total_steps: number;
  hit_breakpoint_id: string | null;
  hit_reason: string | null;
  active_step: Record<string, unknown>;
  active_frame: Record<string, unknown>;
  variables: Record<string, unknown>;
  call_stack: Array<Record<string, unknown>>;
  mutation_count: number;
  mutations: Array<Record<string, unknown>>;
  frame_sha256: string;
  updated_at: string;
  [key: string]: unknown;
}

export interface ListDebugSessionsParams {
  workspace_id?: string;
  limit?: number;
}

export interface DebuggerSessionListResponse {
  workspace_id: string;
  count: number;
  sessions: DebuggerSessionRecord[];
  [key: string]: unknown;
}

export interface StepDebugSessionRequest {
  workspace_id?: string;
  action?: DebuggerStepAction;
  state_patch?: Record<string, unknown>;
}

export interface GetDebuggerCodelensParams {
  workspace_id?: string;
  workflow_id?: string;
  file_path?: string;
  source_code?: string;
}

export interface DebuggerCodelensItem {
  symbol: string;
  file_path: string;
  line_start: number;
  line: number;
  model_checkpoint: string;
  p50_ms: number;
  p50_latency_ms: number;
  avg_cost_usd: number;
  provenance_4d: string;
  attached_breakpoints: number;
  [key: string]: unknown;
}

export interface DebuggerCodelensResponse {
  workspace_id: string;
  workflow_id: string;
  file_path: string;
  vscode_attach_uri: string;
  cursor_attach_uri: string;
  bridge: Record<string, unknown>;
  lenses: DebuggerCodelensItem[];
  [key: string]: unknown;
}

function assertConditionType(cond: DebuggerConditionType): DebuggerConditionType {
  switch (cond) {
    case "always":
    case "cost_usd_gt":
    case "hybrid_score_lt":
    case "before_shell_tool":
    case "before_p10_gate":
    case "line_match":
      return cond;
    default: {
      const _exhaustive: never = cond;
      throw new Error(`Invalid condition_type '${String(_exhaustive)}'.`);
    }
  }
}

function assertStepAction(action: DebuggerStepAction): DebuggerStepAction {
  switch (action) {
    case "step_over":
    case "step_into":
    case "continue":
    case "mutate_state":
      return action;
    default: {
      const _exhaustive: never = action;
      throw new Error(`Invalid debugger action '${String(_exhaustive)}'.`);
    }
  }
}

function debuggerWsId(params?: { workspace_id?: string } | string): string {
  return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}

function encodePathSeg(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

export class PlatformDebuggerClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public setBreakpoint(
    payload: SetBreakpointRequest = {},
    options?: RequestOptions,
  ): Promise<DebuggerBreakpointRecord> {
    const workflowId = (payload.workflow_id ?? "WF-STUDIO-01").trim();
    if (!workflowId) throw new Error("workflow_id must be non-empty.");
    const conditionType = assertConditionType(payload.condition_type ?? "always");
    if (payload.line_number !== undefined && (!Number.isInteger(payload.line_number) || payload.line_number < 1)) {
      throw new Error("line_number must be >= 1.");
    }
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      workflow_id: workflowId,
      file_path: (payload.file_path ?? "workflows/refund_agent.py").trim() || "workflows/refund_agent.py",
      condition_type: conditionType,
      enabled: payload.enabled ?? true,
    };
    if (payload.node_id !== undefined && payload.node_id.trim() !== "") body.node_id = payload.node_id.trim();
    if (payload.line_number !== undefined) body.line_number = payload.line_number;
    if (payload.threshold !== undefined) body.threshold = payload.threshold;
    if (payload.label !== undefined && payload.label.trim() !== "") body.label = payload.label.trim();
    return this.requestJson("POST", "/v1/platform/debugger/breakpoints", { body, options });
  }

  public listBreakpoints(
    paramsOrWorkspaceId: ListBreakpointsParams | string = {},
    options?: RequestOptions,
  ): Promise<DebuggerBreakpointListResponse> {
    const query: Record<string, string> = { workspace_id: debuggerWsId(paramsOrWorkspaceId) };
    if (typeof paramsOrWorkspaceId !== "string" && paramsOrWorkspaceId.workflow_id !== undefined) {
      const wf = paramsOrWorkspaceId.workflow_id.trim();
      if (wf) query.workflow_id = wf;
    }
    return this.requestJson("GET", "/v1/platform/debugger/breakpoints", { query, options });
  }

  public deleteBreakpoint(
    breakpointId: string,
    paramsOrWorkspaceId: DeleteBreakpointParams | string = {},
    options?: RequestOptions,
  ): Promise<DeleteBreakpointResponse> {
    const seg = encodePathSeg(breakpointId, "breakpoint_id");
    const query: Record<string, string> = { workspace_id: debuggerWsId(paramsOrWorkspaceId) };
    return this.requestJson("DELETE", `/v1/platform/debugger/breakpoints/${seg}`, { query, options });
  }

  public startDebugSession(
    payload: StartDebugSessionRequest = {},
    options?: RequestOptions,
  ): Promise<DebuggerSessionRecord> {
    const workflowId = (payload.workflow_id ?? "WF-STUDIO-01").trim();
    if (!workflowId) throw new Error("workflow_id must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      workflow_id: workflowId,
    };
    if (payload.steps !== undefined) body.steps = payload.steps;
    if (payload.initial_state !== undefined) body.initial_state = payload.initial_state;
    return this.requestJson("POST", "/v1/platform/debugger/sessions", { body, options });
  }

  public listDebugSessions(
    paramsOrWorkspaceId: ListDebugSessionsParams | string = {},
    options?: RequestOptions,
  ): Promise<DebuggerSessionListResponse> {
    const limit = typeof paramsOrWorkspaceId === "string" ? 20 : (paramsOrWorkspaceId.limit ?? 20);
    if (limit < 1) throw new Error("limit must be >= 1.");
    const query: Record<string, string> = {
      workspace_id: debuggerWsId(paramsOrWorkspaceId),
      limit: String(limit),
    };
    return this.requestJson("GET", "/v1/platform/debugger/sessions", { query, options });
  }

  public stepDebugSession(
    sessionId: string,
    payloadOrAction: StepDebugSessionRequest | DebuggerStepAction = {},
    options?: RequestOptions,
  ): Promise<DebuggerSessionRecord> {
    const seg = encodePathSeg(sessionId, "session_id");
    const payload: StepDebugSessionRequest =
      typeof payloadOrAction === "string" ? { action: payloadOrAction } : payloadOrAction;
    const action = assertStepAction(payload.action ?? "step_over");
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      action,
    };
    if (payload.state_patch !== undefined) body.state_patch = payload.state_patch;
    return this.requestJson("POST", `/v1/platform/debugger/sessions/${seg}/step`, { body, options });
  }

  public getDebuggerCodelens(
    paramsOrWorkspaceId: GetDebuggerCodelensParams | string = {},
    options?: RequestOptions,
  ): Promise<DebuggerCodelensResponse> {
    const query: Record<string, string> = { workspace_id: debuggerWsId(paramsOrWorkspaceId) };
    if (typeof paramsOrWorkspaceId !== "string") {
      if (paramsOrWorkspaceId.workflow_id !== undefined && paramsOrWorkspaceId.workflow_id.trim() !== "") {
        query.workflow_id = paramsOrWorkspaceId.workflow_id.trim();
      }
      if (paramsOrWorkspaceId.file_path !== undefined && paramsOrWorkspaceId.file_path.trim() !== "") {
        query.file_path = paramsOrWorkspaceId.file_path.trim();
      }
      if (paramsOrWorkspaceId.source_code !== undefined) {
        query.source_code = paramsOrWorkspaceId.source_code;
      }
    }
    return this.requestJson("GET", "/v1/platform/debugger/codelens", { query, options });
  }
}

export { PlatformDebuggerClient as PlatformDebuggerDelegate };
