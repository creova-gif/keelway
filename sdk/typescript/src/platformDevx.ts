/**
 * Keelway Official TypeScript SDK — Phase 11 OpenTelemetry GenAI Flight-Tape Time-Travel,
 * 1-Click Trace-to-Eval Promotion & Static AST LangGraph Migration.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type OtelSourceFramework =
  | "opentelemetry_genai"
  | "langgraph"
  | "langchain"
  | "crewai"
  | "autogen"
  | "keelway"
  | (string & {});

export type MigrationSourceLanguage = "python" | "typescript" | (string & {});

export interface OtelSpanInput {
  span_id?: string;
  spanId?: string;
  parent_span_id?: string | null;
  parentSpanId?: string | null;
  trace_id?: string;
  traceId?: string;
  name: string;
  kind?: string;
  attributes?: Record<string, unknown>;
  status?: Record<string, unknown> | string;
  start_time_unix_nano?: string | number;
  end_time_unix_nano?: string | number;
  [key: string]: unknown;
}

export interface IngestOtelTracesRequest {
  workspace_id?: string;
  workflow_name?: string;
  source_framework?: OtelSourceFramework;
  spans?: OtelSpanInput[];
  resourceSpans?: Record<string, unknown>[];
  resource_spans?: Record<string, unknown>[];
  trace_id?: string;
}

export interface FlightTapeStep {
  step_index: number;
  span_id?: string;
  parent_span_id?: string | null;
  name?: string;
  kind?: string;
  model?: string;
  prompt?: string;
  output?: string;
  state?: Record<string, unknown>;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  attributes?: Record<string, unknown>;
  step_sha256?: string;
  [key: string]: unknown;
}

export interface FlightTapeRecord {
  trace_id: string;
  id?: string;
  workspace_id: string;
  workflow_name?: string;
  source_framework?: OtelSourceFramework;
  parent_trace_id?: string | null;
  forked_from_trace_id?: string | null;
  forked_from_step_index?: number | null;
  span_count?: number;
  step_count?: number;
  steps?: FlightTapeStep[];
  spans?: Record<string, unknown>[];
  tape_sha256?: string;
  digest_sha256?: string;
  status?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface ListFlightTapesParams {
  workspace_id?: string;
  limit?: number;
}

export interface FlightTapeListResponse {
  workspace_id: string;
  total?: number;
  total_tapes?: number;
  count?: number;
  tapes?: FlightTapeRecord[];
  traces?: FlightTapeRecord[];
  [key: string]: unknown;
}

export interface ReplayFlightTapeRequest {
  workspace_id?: string;
  from_step_index?: number;
  override_prompt?: string;
  override_model?: string;
  override_state?: Record<string, unknown>;
}

export interface PromoteTraceToEvalRequest {
  workspace_id?: string;
  trace_id: string;
  title?: string;
  expected_substrings?: string[];
  forbidden_substrings?: string[];
}

export interface EvalDatasetCase {
  case_id?: string;
  id?: string;
  workspace_id: string;
  source_trace_id?: string;
  trace_id?: string;
  title?: string;
  prompt?: string;
  reference_output?: string;
  expected_substrings?: string[];
  forbidden_substrings?: string[];
  case_sha256?: string;
  digest_sha256?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface ListEvalDatasetCasesParams {
  workspace_id?: string;
}

export interface EvalDatasetListResponse {
  workspace_id: string;
  total?: number;
  total_cases?: number;
  count?: number;
  cases: EvalDatasetCase[];
  [key: string]: unknown;
}

export interface MigrateLanggraphRequest {
  workspace_id?: string;
  source_code: string;
  source_language?: MigrationSourceLanguage;
  workflow_name?: string;
}

export interface LanggraphMigrationResult {
  workspace_id?: string;
  workflow_id?: string;
  workflow_name?: string;
  source_framework?: string;
  source_language?: MigrationSourceLanguage;
  nodes: Record<string, unknown>[];
  edges?: Record<string, unknown>[];
  conditional_edges?: Record<string, unknown>[];
  p10_gates_injected?: number;
  kflow_dag?: Record<string, unknown>;
  warnings?: string[];
  ast_digest_sha256?: string;
  manifest_sha256?: string;
  [key: string]: unknown;
}

function devxSeg(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

export class PlatformDevxDelegate {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public ingestOtelTraces(
    payload: IngestOtelTracesRequest,
    options?: RequestOptions,
  ): Promise<FlightTapeRecord> {
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      workflow_name: payload.workflow_name ?? "agent-trace",
      source_framework: payload.source_framework ?? "opentelemetry_genai",
    };
    if (payload.spans !== undefined) {
      body.spans = payload.spans;
    }
    const resSpans = payload.resourceSpans ?? payload.resource_spans;
    if (resSpans !== undefined) {
      body.resourceSpans = resSpans;
      body.resource_spans = resSpans;
    }
    if (payload.trace_id !== undefined && payload.trace_id.trim() !== "") {
      body.trace_id = payload.trace_id.trim();
    }
    return this.requestJson("POST", "/v1/platform/traces/ingest", { body, options });
  }

  public listFlightTapes(
    workspaceId?: string,
    limit?: number,
    options?: RequestOptions,
  ): Promise<FlightTapeListResponse>;
  public listFlightTapes(
    params?: ListFlightTapesParams,
    options?: RequestOptions,
  ): Promise<FlightTapeListResponse>;
  public listFlightTapes(
    workspaceIdOrParams: string | ListFlightTapesParams = "default",
    limitOrOptions?: number | RequestOptions,
    options?: RequestOptions,
  ): Promise<FlightTapeListResponse> {
    const isObj = typeof workspaceIdOrParams === "object" && workspaceIdOrParams !== null;
    const workspaceId = isObj
      ? (workspaceIdOrParams.workspace_id ?? "default")
      : (workspaceIdOrParams || "default");
    const limit = isObj
      ? (workspaceIdOrParams.limit ?? 20)
      : typeof limitOrOptions === "number"
        ? limitOrOptions
        : 20;
    const resolvedOptions = isObj
      ? (limitOrOptions as RequestOptions | undefined)
      : typeof limitOrOptions === "object"
        ? limitOrOptions
        : options;
    return this.requestJson("GET", "/v1/platform/traces", {
      query: { workspace_id: workspaceId, limit: String(limit) },
      options: resolvedOptions,
    });
  }

  public replayFlightTape(
    traceId: string,
    payload: ReplayFlightTapeRequest = {},
    options?: RequestOptions,
  ): Promise<FlightTapeRecord> {
    const fromStep = payload.from_step_index ?? 0;
    if (fromStep < 0) throw new Error("from_step_index must be >= 0.");
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      from_step_index: fromStep,
    };
    if (payload.override_prompt !== undefined) body.override_prompt = payload.override_prompt;
    if (payload.override_model !== undefined) body.override_model = payload.override_model;
    if (payload.override_state !== undefined) body.override_state = payload.override_state;
    return this.requestJson(
      "POST",
      `/v1/platform/traces/${devxSeg(traceId, "traceId")}/replay`,
      { body, options },
    );
  }

  public promoteTraceToEval(
    payload: PromoteTraceToEvalRequest,
    options?: RequestOptions,
  ): Promise<EvalDatasetCase> {
    const cleanTraceId = payload.trace_id.trim();
    if (!cleanTraceId) throw new Error("trace_id must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      trace_id: cleanTraceId,
    };
    if (payload.title !== undefined) body.title = payload.title;
    if (payload.expected_substrings !== undefined) {
      body.expected_substrings = payload.expected_substrings;
    }
    if (payload.forbidden_substrings !== undefined) {
      body.forbidden_substrings = payload.forbidden_substrings;
    }
    return this.requestJson("POST", "/v1/platform/eval/dataset/promote", { body, options });
  }

  public listEvalDatasetCases(
    workspaceId?: string,
    options?: RequestOptions,
  ): Promise<EvalDatasetListResponse>;
  public listEvalDatasetCases(
    params?: ListEvalDatasetCasesParams,
    options?: RequestOptions,
  ): Promise<EvalDatasetListResponse>;
  public listEvalDatasetCases(
    workspaceIdOrParams: string | ListEvalDatasetCasesParams = "default",
    options?: RequestOptions,
  ): Promise<EvalDatasetListResponse> {
    const workspaceId =
      typeof workspaceIdOrParams === "string"
        ? (workspaceIdOrParams || "default")
        : (workspaceIdOrParams?.workspace_id ?? "default");
    return this.requestJson("GET", "/v1/platform/eval/dataset", {
      query: { workspace_id: workspaceId },
      options,
    });
  }

  public migrateLanggraphSource(
    payload: MigrateLanggraphRequest,
    options?: RequestOptions,
  ): Promise<LanggraphMigrationResult> {
    if (!payload.source_code || !payload.source_code.trim()) {
      throw new Error("source_code must be non-empty.");
    }
    const body: Record<string, unknown> = {
      workspace_id: payload.workspace_id ?? "default",
      source_code: payload.source_code,
      source_language: payload.source_language ?? "python",
    };
    if (payload.workflow_name !== undefined) {
      body.workflow_name = payload.workflow_name;
    }
    return this.requestJson("POST", "/v1/platform/migrate/langgraph", { body, options });
  }
}
