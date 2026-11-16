/**
 * Keelway Official TypeScript SDK — Phase 16 Typed Structured-Output & Content-Block Normalizer
 * + Autonomous Self-Healing Failure Root-Causer (`client.platform` / `client.platform.healing`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type HealingProviderFormat = "deepseek_opencore" | "openai" | "anthropic" | "gemini";
export type ContentBlockKind = "reasoning" | "text" | "tool_call" | "citation" | "structured_json";
export type StructuredOutputStatus = "VALID" | "REPAIRED_VALID" | "SCHEMA_REJECTED";
export type FailureRootCauseClass = "schema_mismatch" | "context_truncation" | "prompt_ambiguity" | "kbrain_conflict" | "airgap_egress_blocked";
export type SelfHealingDiagnosisStatus = "DIAGNOSED" | "VERIFIED_HEALED";
export type SelfHealingTargetSurface = "json_schema" | "system_prompt" | "routing_policy" | "kbrain_memory";
export interface NormalizeContentBlocksRequest {
    workspace_id?: string;
    provider_format?: HealingProviderFormat;
    model_id?: string;
    raw_payload: Record<string, unknown> | string;
}
export interface NormalizedContentBlock {
    index: number;
    kind: ContentBlockKind;
    content: string;
    tool_name?: string | null;
    tool_call_id?: string | null;
    tool_args?: Record<string, unknown> | null;
    source_uri?: string | null;
    structured_data?: Record<string, unknown> | null;
    [key: string]: unknown;
}
export interface NormalizedContentEnvelope {
    workspace_id: string;
    provider_format: HealingProviderFormat;
    model_id: string;
    block_count: number;
    content_blocks: NormalizedContentBlock[];
    dlp_redactions: number;
    envelope_sha256: string;
    [key: string]: unknown;
}
export interface EnforceStructuredOutputRequest {
    workspace_id?: string;
    schema_name?: string;
    provider_format?: HealingProviderFormat;
    model_id?: string;
    json_schema: Record<string, unknown>;
    raw_output: string | Record<string, unknown>;
    strict_mode?: boolean;
    fail_closed?: boolean;
}
export interface StructuredOutputRunRecord {
    run_id: string;
    workspace_id: string;
    schema_name: string;
    provider_format: string;
    model_id: string;
    status: StructuredOutputStatus;
    repair_applied: boolean;
    repair_actions: string[];
    validated_data: Record<string, unknown> | null;
    validation_errors: string[];
    dlp_redactions: number;
    run_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ListStructuredOutputRunsParams {
    workspace_id?: string;
    limit?: number;
}
export interface StructuredOutputRunListResponse {
    workspace_id: string;
    count: number;
    runs: StructuredOutputRunRecord[];
    [key: string]: unknown;
}
export interface FailedStepInput {
    step_index?: number;
    node_name?: string;
    model_id?: string;
    prompt_text?: string;
    output_text?: string;
    error_message?: string;
    expected_schema?: Record<string, unknown> | null;
    [key: string]: unknown;
}
export interface DiagnoseFailureRootCauseRequest {
    workspace_id?: string;
    trace_id?: string | null;
    workflow_name?: string;
    failed_step?: FailedStepInput | null;
}
export interface ProposedSelfHealingPatch {
    target_surface: SelfHealingTargetSurface;
    recommended_model: string;
    unified_diff: string;
    patched_prompt: string;
    [key: string]: unknown;
}
export interface SelfHealingDiagnosisRecord {
    diagnosis_id: string;
    workspace_id: string;
    trace_id: string | null;
    workflow_name: string;
    failure_class: FailureRootCauseClass;
    status: SelfHealingDiagnosisStatus;
    confidence: number;
    failed_node: string;
    diagnostic_model: string;
    summary: string;
    root_cause_evidence: string[];
    proposed_patch: ProposedSelfHealingPatch;
    verification_replay_trace_id: string | null;
    promoted_eval_case_id: string | null;
    dlp_redactions: number;
    diagnosis_sha256: string;
    created_at: string;
    [key: string]: unknown;
}
export interface ApplySelfHealingPatchRequest {
    workspace_id?: string;
    promote_to_eval?: boolean;
    eval_title?: string | null;
}
export interface PromotedEvalCaseSummary {
    case_id: string;
    title: string;
    case_sha256: string;
    [key: string]: unknown;
}
export interface ApplySelfHealingResponse {
    diagnosis: SelfHealingDiagnosisRecord;
    verified_healed: boolean;
    cached_steps_reused: number;
    replay_cost_usd: number;
    promoted_eval_case: PromotedEvalCaseSummary | null;
    [key: string]: unknown;
}
export interface ListSelfHealingDiagnosesParams {
    workspace_id?: string;
    limit?: number;
}
export interface SelfHealingDiagnosisListResponse {
    workspace_id: string;
    count: number;
    diagnoses: SelfHealingDiagnosisRecord[];
    [key: string]: unknown;
}
export declare class PlatformHealingClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    normalizeContentBlocks(req: NormalizeContentBlocksRequest, options?: RequestOptions): Promise<NormalizedContentEnvelope>;
    enforceStructuredOutput(req: EnforceStructuredOutputRequest, options?: RequestOptions): Promise<StructuredOutputRunRecord>;
    listStructuredOutputRuns(params?: ListStructuredOutputRunsParams | string, options?: RequestOptions): Promise<StructuredOutputRunListResponse>;
    diagnoseFailureRootCause(req?: DiagnoseFailureRootCauseRequest, options?: RequestOptions): Promise<SelfHealingDiagnosisRecord>;
    applySelfHealingPatch(diagnosisId: string, req?: ApplySelfHealingPatchRequest, options?: RequestOptions): Promise<ApplySelfHealingResponse>;
    listSelfHealingDiagnoses(params?: ListSelfHealingDiagnosesParams | string, options?: RequestOptions): Promise<SelfHealingDiagnosisListResponse>;
}
export { PlatformHealingClient as PlatformHealingDelegate };
//# sourceMappingURL=platformHealing.d.ts.map