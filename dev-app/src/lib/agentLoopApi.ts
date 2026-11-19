/**
 * Typed client for the Autonomous Agent Loop (`/v1/agent/*`).
 *
 * Backend contract (core/api/routes.py + core/orchestration/agent_loop.py):
 * every mutating call returns the full `agent_state` synchronously — the loop
 * is operator-stepped, not self-driving — so this client performs no polling.
 * State hydrates plan steps, recent tool events, and pending approvals.
 */
import { getStudioToken } from "@/lib/api";
import type {
  P10ApprovalKind,
  P10ApprovalProposal,
  StepReceiptItem,
  StepReceiptKind,
} from "@/lib/types";

/* ============================== State shapes ============================= */

export interface AgentPlanStep {
  id: string;
  description: string;
  status: string;
  observation?: string | null;
}

export interface AgentLoopEvent {
  timestamp: number;
  event_type: string;
  data: Record<string, unknown>;
}

export interface AgentPendingApproval {
  task_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  is_mutation: boolean;
  step_id?: string | null;
  requires_quorum?: boolean;
  quorum_id?: string;
  required_roles?: string[];
}

export interface AgentRunState {
  task_id: string;
  goal: string;
  status: string;
  policy: string;
  plan: AgentPlanStep[];
  pending_approval: AgentPendingApproval | null;
  events_count: number;
  recent_events: AgentLoopEvent[];
}

export interface AgentRunResponse {
  task_id: string;
  goal: string;
  policy: string;
  state?: AgentRunState;
}

export interface AgentStepResponse {
  step_result: Record<string, unknown>;
  agent_state: AgentRunState;
}

export interface AgentApproveResponse {
  approval_result: Record<string, unknown>;
  rule?: Record<string, unknown> | null;
  agent_state?: AgentRunState;
}

export interface AgentApiResult<T> {
  ok: boolean;
  status: number;
  data: T | null;
  detail?: string;
}

/* ============================== Request plumbing ========================= */

const INITIAL_FETCH_FN = typeof globalThis.fetch === "function" ? globalThis.fetch : undefined;
const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

function shouldSkipUnmockedTestFetch(): boolean {
  if (import.meta.env.MODE !== "test") return false;
  if (typeof globalThis.fetch !== "function") return true;
  return !("mock" in (globalThis.fetch as unknown as Record<string, unknown>)) && globalThis.fetch === INITIAL_FETCH_FN;
}

function buildUrl(path: string): string {
  if (!path.startsWith("/v1/agent")) {
    throw new Error(`Security violation: agentLoopApi allows strictly /v1/agent/* paths, got ${path}`);
  }
  const token = getStudioToken();
  return token ? `${path}?token=${encodeURIComponent(token)}` : path;
}

function attachHeaders(raw?: HeadersInit, hasBody = false): Headers {
  const headers = new Headers(raw);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (hasBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = getStudioToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("X-Studio-Token", token);
  }
  return headers;
}

async function requestAgentJson<T>(path: string, init: RequestInit): Promise<AgentApiResult<T>> {
  if (shouldSkipUnmockedTestFetch()) return { ok: false, status: 0, data: null };
  try {
    const res = await fetch(buildUrl(path), {
      ...init,
      credentials: "same-origin",
      headers: attachHeaders(init.headers, Boolean(init.body)),
    });
    const data = (await res.json().catch(() => null)) as T | null;
    const detail = isRecord(data) && typeof data.detail === "string" ? data.detail : undefined;
    return { ok: res.ok, status: res.status, data, detail };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

/* ============================== Endpoint calls =========================== */

export type AutonomyPolicyId = "confirm_all" | "confirm_mutation" | "autonomous";

export async function runAgentTask(input: {
  goal: string;
  policy?: AutonomyPolicyId;
  modelId?: string;
  promptVersion?: string;
}): Promise<AgentApiResult<AgentRunResponse>> {
  const body: Record<string, unknown> = { goal: input.goal, policy: input.policy ?? "confirm_mutation" };
  if (input.modelId) body.model_id = input.modelId;
  if (input.promptVersion) body.prompt_version = input.promptVersion;
  return requestAgentJson<AgentRunResponse>("/v1/agent/run", { method: "POST", body: JSON.stringify(body) });
}

export async function getAgentStatus(taskId: string): Promise<AgentApiResult<AgentRunState>> {
  return requestAgentJson<AgentRunState>(`/v1/agent/status/${encodeURIComponent(taskId)}`, { method: "GET" });
}

export async function stepAgentTool(
  taskId: string,
  step: { toolName: string; arguments: Record<string, unknown>; stepId?: string },
): Promise<AgentApiResult<AgentStepResponse>> {
  const body: Record<string, unknown> = { tool_name: step.toolName, arguments: step.arguments };
  if (step.stepId) body.step_id = step.stepId;
  return requestAgentJson<AgentStepResponse>(`/v1/agent/step/${encodeURIComponent(taskId)}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function approveAgentStep(
  taskId: string,
  decision: { approved: boolean; remember?: { scope?: string; model_id?: string; prompt_version?: string } },
): Promise<AgentApiResult<AgentApproveResponse>> {
  const body: Record<string, unknown> = { approved: decision.approved };
  if (decision.remember) body.remember = decision.remember;
  return requestAgentJson<AgentApproveResponse>(`/v1/agent/approve/${encodeURIComponent(taskId)}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function cancelAgentTask(taskId: string): Promise<AgentApiResult<{ agent_state?: AgentRunState }>> {
  return requestAgentJson(`/v1/agent/cancel/${encodeURIComponent(taskId)}`, { method: "POST", body: "{}" });
}

/* ============================== UI mappers =============================== */

const TOOL_RECEIPT_KIND: Record<string, StepReceiptKind> = {
  read_file: "read",
  list_dir: "read",
  search_codebase: "searched",
  edit_file: "edited",
  write_file: "edited",
  run_command: "command",
};

function receiptTarget(args: Record<string, unknown>): string {
  const target = args.path ?? args.command ?? args.query ?? args.pattern;
  return typeof target === "string" && target.trim() ? target.trim() : "workspace";
}

/** Maps one agent-loop event to a receipts row. Returns null for non-tool events. */
export function mapEventToReceipt(ev: AgentLoopEvent, index: number): StepReceiptItem | null {
  const tool = typeof ev.data.tool === "string" ? ev.data.tool : undefined;
  const args = isRecord(ev.data.arguments) ? ev.data.arguments : {};
  if (ev.event_type === "tool_call" && tool) {
    return {
      id: `live-ev-${index}`,
      kind: TOOL_RECEIPT_KIND[tool] ?? "command",
      title: `Called ${tool}`,
      target: receiptTarget(args),
      status: "running",
      timestamp: new Date(ev.timestamp * 1000).toISOString(),
    };
  }
  if (ev.event_type === "tool_success" && tool) {
    const dur = typeof ev.data.duration_ms === "number" ? ev.data.duration_ms : undefined;
    const result = isRecord(ev.data.result) ? ev.data.result : {};
    const exitCode = typeof result.exit_code === "number" ? result.exit_code : undefined;
    const stdout = typeof result.stdout === "string" ? result.stdout : undefined;
    return {
      id: `live-ev-${index}`,
      kind: TOOL_RECEIPT_KIND[tool] ?? "command",
      title: `${tool} succeeded`,
      target: receiptTarget(args),
      status: exitCode !== undefined && exitCode !== 0 ? "failed" : "passed",
      durationMs: dur,
      exitCode,
      output: stdout ? stdout.slice(0, 400) : undefined,
      timestamp: new Date(ev.timestamp * 1000).toISOString(),
    };
  }
  if (ev.event_type === "tool_error" && tool) {
    return {
      id: `live-ev-${index}`,
      kind: TOOL_RECEIPT_KIND[tool] ?? "command",
      title: `${tool} failed`,
      target: receiptTarget(args),
      status: "failed",
      detail: typeof ev.data.error === "string" ? ev.data.error.slice(0, 300) : undefined,
      timestamp: new Date(ev.timestamp * 1000).toISOString(),
    };
  }
  return null;
}

export function mapEventsToReceipts(events: AgentLoopEvent[]): StepReceiptItem[] {
  return events.map(mapEventToReceipt).filter((r): r is StepReceiptItem => r !== null).slice(-20);
}

const LIVE_TOOL_P10_KIND: Record<string, P10ApprovalKind> = {
  run_command: "command",
  edit_file: "file_edit",
  write_file: "file_edit",
};

/**
 * Maps a live pending_approval to the P-10 proposal shape so it flows through
 * the existing approval card UX (keyboard shortcuts, scoped-rule grants).
 */
export function pendingToProposal(
  pending: AgentPendingApproval,
  meta: { modelId?: string; promptVersion?: string },
): P10ApprovalProposal {
  const args = pending.arguments;
  const target = receiptTarget(args);
  const kind = LIVE_TOOL_P10_KIND[pending.tool_name] ?? "file_edit";
  return {
    id: `live-${pending.task_id}-${pending.tool_name}`,
    taskId: pending.task_id,
    kind,
    title: `${pending.tool_name} requires approval`,
    summary: kind === "command"
      ? `Sandboxed command: ${String(args.command ?? "")}`
      : `Workspace file: ${target}`,
    whyReason: `Autonomy policy gates ${pending.is_mutation ? "mutating" : "this"} tool calls; a human must grant or deny.`,
    targetPath: typeof args.path === "string" ? args.path : undefined,
    command: typeof args.command === "string" ? args.command : undefined,
    previewStatus: "ready",
    modelId: meta.modelId ?? "agent-loop",
    modelVersion: meta.modelId ?? "unbound",
    promptVersion: meta.promptVersion ?? "unbound",
    createdAt: new Date().toISOString(),
  };
}

/** Default per-tool step arguments, mirroring Studio's operator-driven stepping. */
export function defaultStepArgs(tool: string, goal: string): Record<string, unknown> {
  switch (tool) {
    case "list_dir": return { path: "." };
    case "search_codebase": return { query: goal };
    case "read_file": return { path: "README.md" };
    case "edit_file": return { path: "README.md", target: "", replacement: "" };
    case "write_file": return { path: "notes.md", content: "" };
    case "run_command": return { command: "pytest -q" };
    default: return {};
  }
}

export const STEPABLE_TOOLS = [
  "list_dir",
  "read_file",
  "search_codebase",
  "edit_file",
  "write_file",
  "run_command",
] as const;
