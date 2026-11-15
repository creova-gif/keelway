/**
 * Keelway Official TypeScript SDK — Phase 12 Golden-Thread Bidirectional KFlow Studio,
 * Sandbox Blast-Radius Radar & Prompt Regression Gate (`client.platform` / `client.platform.studio`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type StudioKflowDirection = "code_to_graph" | "graph_to_code";
export type StudioKflowLanguage = "python" | "typescript";
export type PromptGateVerdict = "PASS" | "BLOCK";

export interface StudioKflowNodeInput {
  id: string;
  label?: string;
  agent_id?: string;
  depends_on?: string[];
  requires_p10?: boolean;
  line_start?: number;
  line_end?: number;
  wave?: number;
  x?: number;
  y?: number;
  [key: string]: unknown;
}

export interface StudioKflowNode {
  id: string;
  label: string;
  agent_id: string;
  depends_on: string[];
  requires_p10: boolean;
  line_start: number;
  line_end: number;
  wave: number;
  x: number;
  y: number;
  [key: string]: unknown;
}

export interface StudioKflowEdge {
  from: string;
  to: string;
  is_cycle: boolean;
}

export interface StudioKflowCycleEdge {
  from: string;
  to: string;
}

export interface SyncKflowStudioRequest {
  workspace_id?: string;
  direction?: StudioKflowDirection;
  language?: StudioKflowLanguage;
  workflow_id?: string;
  source_code?: string;
  nodes?: StudioKflowNodeInput[];
  persist?: boolean;
}

export interface StudioKflowSyncResult {
  workspace_id: string;
  workflow_id: string;
  direction: string;
  language: string;
  nodes: StudioKflowNode[];
  edges: StudioKflowEdge[];
  cycle_back_edges: StudioKflowCycleEdge[];
  p10_locked_nodes: string[];
  source_code: string;
  persisted: boolean;
  sync_sha256: string;
  [key: string]: unknown;
}

export interface RecordBlastRadiusRequest {
  workspace_id?: string;
  trace_id?: string;
  workflow_id?: string;
  fs_reads?: string[];
  fs_writes?: string[];
  blocked_paths?: string[];
  egress_attempts?: number;
  blocked_egress_hosts?: string[];
  p10_gates_triggered?: number;
  seatbelted?: boolean;
}

export interface BlastRadiusAuditRecord {
  audit_id: string;
  workspace_id: string;
  trace_id?: string | null;
  workflow_id?: string | null;
  fs_reads: string[];
  fs_writes: string[];
  blocked_paths: string[];
  egress_attempts: number;
  blocked_egress_hosts: string[];
  p10_gates_triggered: number;
  seatbelted: boolean;
  zero_unapproved_egress: boolean;
  syscalls_audited: number;
  risk_tier: string;
  audit_sha256: string;
  recorded_at: string;
  [key: string]: unknown;
}

export interface ListBlastRadiusAuditsParams {
  workspace_id?: string;
  trace_id?: string;
  limit?: number;
}

export interface BlastRadiusAuditListResponse {
  workspace_id: string;
  count: number;
  audits: BlastRadiusAuditRecord[];
  [key: string]: unknown;
}

export interface EvaluatePromptGateRequest {
  workspace_id?: string;
  candidate_prompt_version: string;
  candidate_model_id: string;
  candidate_prompt_text?: string;
  required_json_keys?: string[];
  min_pass_rate?: number;
}

export interface PromptGateEvaluationResult {
  gate_run_id: string;
  workspace_id: string;
  candidate_prompt_version: string;
  candidate_model_id: string;
  verdict: PromptGateVerdict;
  cases_evaluated: number;
  passed_cases: number;
  pass_rate: number;
  min_pass_rate: number;
  schema_valid_count: number;
  dlp_violations: number;
  cost_delta_usd: number;
  dataset_source: string;
  gate_sha256: string;
  evaluated_at: string;
  [key: string]: unknown;
}

export interface ListPromptGateRunsParams {
  workspace_id?: string;
  limit?: number;
}

export interface PromptGateRunListResponse {
  workspace_id: string;
  count: number;
  runs: PromptGateEvaluationResult[];
  [key: string]: unknown;
}

function assertDirection(direction: StudioKflowDirection): StudioKflowDirection {
  switch (direction) {
    case "code_to_graph":
    case "graph_to_code":
      return direction;
    default: {
      const exhaustive: never = direction;
      throw new Error(`Invalid direction '${String(exhaustive)}': must be 'code_to_graph' or 'graph_to_code'.`);
    }
  }
}

function assertLanguage(language: StudioKflowLanguage): StudioKflowLanguage {
  switch (language) {
    case "python":
    case "typescript":
      return language;
    default: {
      const exhaustive: never = language;
      throw new Error(`Invalid language '${String(exhaustive)}': must be 'python' or 'typescript'.`);
    }
  }
}

function studioWsId(params?: { workspace_id?: string } | string): string {
  return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}

export class PlatformStudioClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public syncKflowStudio(
    payload: SyncKflowStudioRequest = {},
    options?: RequestOptions,
  ): Promise<StudioKflowSyncResult> {
    const direction = assertDirection(payload.direction ?? "code_to_graph");
    const language = assertLanguage(payload.language ?? "python");
    const workflowId = (payload.workflow_id ?? "WF-STUDIO-01").trim();
    if (!workflowId) {
      throw new Error("workflow_id must be non-empty.");
    }
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      direction,
      language,
      workflow_id: workflowId,
    };
    if (payload.source_code !== undefined) body.source_code = payload.source_code;
    if (payload.nodes !== undefined) body.nodes = payload.nodes;
    if (payload.persist !== undefined) body.persist = payload.persist;
    return this.requestJson("POST", "/v1/platform/studio/kflow/sync", { body, options });
  }

  public recordBlastRadius(
    payload: RecordBlastRadiusRequest = {},
    options?: RequestOptions,
  ): Promise<BlastRadiusAuditRecord> {
    if (payload.egress_attempts !== undefined && payload.egress_attempts < 0) {
      throw new Error("egress_attempts must be >= 0.");
    }
    if (payload.p10_gates_triggered !== undefined && payload.p10_gates_triggered < 0) {
      throw new Error("p10_gates_triggered must be >= 0.");
    }
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
    };
    if (payload.trace_id !== undefined && payload.trace_id.trim() !== "") {
      body.trace_id = payload.trace_id.trim();
    }
    if (payload.workflow_id !== undefined && payload.workflow_id.trim() !== "") {
      body.workflow_id = payload.workflow_id.trim();
    }
    if (payload.fs_reads !== undefined) body.fs_reads = payload.fs_reads;
    if (payload.fs_writes !== undefined) body.fs_writes = payload.fs_writes;
    if (payload.blocked_paths !== undefined) body.blocked_paths = payload.blocked_paths;
    if (payload.egress_attempts !== undefined) body.egress_attempts = payload.egress_attempts;
    if (payload.blocked_egress_hosts !== undefined) body.blocked_egress_hosts = payload.blocked_egress_hosts;
    if (payload.p10_gates_triggered !== undefined) body.p10_gates_triggered = payload.p10_gates_triggered;
    if (payload.seatbelted !== undefined) body.seatbelted = payload.seatbelted;
    return this.requestJson("POST", "/v1/platform/studio/blast-radius/record", { body, options });
  }

  public listBlastRadiusAudits(
    paramsOrWorkspaceId: ListBlastRadiusAuditsParams | string = {},
    options?: RequestOptions,
  ): Promise<BlastRadiusAuditListResponse> {
    const limit =
      typeof paramsOrWorkspaceId === "string"
        ? 25
        : (paramsOrWorkspaceId.limit ?? 25);
    if (limit < 1) {
      throw new Error("limit must be >= 1.");
    }
    const query: Record<string, string> = {
      workspace_id: studioWsId(paramsOrWorkspaceId),
      limit: String(limit),
    };
    if (typeof paramsOrWorkspaceId !== "string" && paramsOrWorkspaceId.trace_id !== undefined) {
      const cleanTid = paramsOrWorkspaceId.trace_id.trim();
      if (cleanTid) query.trace_id = cleanTid;
    }
    return this.requestJson("GET", "/v1/platform/studio/blast-radius", { query, options });
  }

  public evaluatePromptGate(
    payload: EvaluatePromptGateRequest,
    options?: RequestOptions,
  ): Promise<PromptGateEvaluationResult> {
    const cleanVer = (payload.candidate_prompt_version ?? "").trim();
    if (!cleanVer) {
      throw new Error("candidate_prompt_version must be non-empty.");
    }
    const cleanModel = (payload.candidate_model_id ?? "").trim();
    if (!cleanModel) {
      throw new Error("candidate_model_id must be non-empty.");
    }
    if (
      payload.min_pass_rate !== undefined &&
      (payload.min_pass_rate < 0 || payload.min_pass_rate > 1)
    ) {
      throw new Error("min_pass_rate must be between 0.0 and 1.0.");
    }
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      candidate_prompt_version: cleanVer,
      candidate_model_id: cleanModel,
    };
    if (payload.candidate_prompt_text !== undefined) {
      body.candidate_prompt_text = payload.candidate_prompt_text;
    }
    if (payload.required_json_keys !== undefined) {
      body.required_json_keys = payload.required_json_keys;
    }
    if (payload.min_pass_rate !== undefined) {
      body.min_pass_rate = payload.min_pass_rate;
    }
    return this.requestJson("POST", "/v1/platform/studio/prompt-gate/evaluate", { body, options });
  }

  public listPromptGateRuns(
    paramsOrWorkspaceId: ListPromptGateRunsParams | string = {},
    options?: RequestOptions,
  ): Promise<PromptGateRunListResponse> {
    const limit =
      typeof paramsOrWorkspaceId === "string"
        ? 20
        : (paramsOrWorkspaceId.limit ?? 20);
    if (limit < 1) {
      throw new Error("limit must be >= 1.");
    }
    const query: Record<string, string> = {
      workspace_id: studioWsId(paramsOrWorkspaceId),
      limit: String(limit),
    };
    return this.requestJson("GET", "/v1/platform/studio/prompt-gate/runs", { query, options });
  }
}

export { PlatformStudioClient as PlatformStudioDelegate };
