/**
 * Keelway Official TypeScript SDK — Phase 11 OpenTelemetry GenAI Flight-Tape Time-Travel,
 * 1-Click Trace-to-Eval Promotion & Static AST LangGraph Migration.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type OtelSourceFramework = "opentelemetry_genai" | "langgraph" | "langchain" | "crewai" | "autogen" | "keelway" | (string & {});
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
export declare class PlatformDevxDelegate {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    ingestOtelTraces(payload: IngestOtelTracesRequest, options?: RequestOptions): Promise<FlightTapeRecord>;
    listFlightTapes(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<FlightTapeListResponse>;
    listFlightTapes(params?: ListFlightTapesParams, options?: RequestOptions): Promise<FlightTapeListResponse>;
    replayFlightTape(traceId: string, payload?: ReplayFlightTapeRequest, options?: RequestOptions): Promise<FlightTapeRecord>;
    promoteTraceToEval(payload: PromoteTraceToEvalRequest, options?: RequestOptions): Promise<EvalDatasetCase>;
    listEvalDatasetCases(workspaceId?: string, options?: RequestOptions): Promise<EvalDatasetListResponse>;
    listEvalDatasetCases(params?: ListEvalDatasetCasesParams, options?: RequestOptions): Promise<EvalDatasetListResponse>;
    migrateLanggraphSource(payload: MigrateLanggraphRequest, options?: RequestOptions): Promise<LanggraphMigrationResult>;
}
//# sourceMappingURL=platformDevx.d.ts.map