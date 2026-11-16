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
export type FailureRootCauseClass =
  | "schema_mismatch"
  | "context_truncation"
  | "prompt_ambiguity"
  | "kbrain_conflict"
  | "airgap_egress_blocked";
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

function assertProviderFormat(fmt: HealingProviderFormat): HealingProviderFormat {
  switch (fmt) {
    case "deepseek_opencore":
    case "openai":
    case "anthropic":
    case "gemini":
      return fmt;
    default: {
      const _exhaustive: never = fmt;
      throw new Error(`Invalid provider_format '${String(_exhaustive)}'.`);
    }
  }
}

function encodePathSeg(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

function buildHealingListQuery(paramsOrWs: { workspace_id?: string; limit?: number } | string): Record<string, string> {
  const params = typeof paramsOrWs === "string" ? { workspace_id: paramsOrWs } : paramsOrWs;
  const limit = params.limit ?? 25;
  if (!Number.isInteger(limit) || limit < 1) throw new Error("limit must be >= 1.");
  return { workspace_id: params.workspace_id ?? "default", limit: String(limit) };
}

export class PlatformHealingClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public normalizeContentBlocks(
    req: NormalizeContentBlocksRequest,
    options?: RequestOptions,
  ): Promise<NormalizedContentEnvelope> {
    const modelId = (req.model_id ?? "keelway-core:7b").trim();
    if (!modelId) throw new Error("model_id must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: req.workspace_id ?? "default",
      provider_format: assertProviderFormat(req.provider_format ?? "deepseek_opencore"),
      model_id: modelId,
      raw_payload: req.raw_payload,
    };
    return this.requestJson("POST", "/v1/platform/healing/content-blocks/normalize", { body, options });
  }

  public enforceStructuredOutput(
    req: EnforceStructuredOutputRequest,
    options?: RequestOptions,
  ): Promise<StructuredOutputRunRecord> {
    const schemaName = (req.schema_name ?? "AgentDecisionContract").trim();
    if (!schemaName) throw new Error("schema_name must be non-empty.");
    const modelId = (req.model_id ?? "keelway-core:7b").trim();
    if (!modelId) throw new Error("model_id must be non-empty.");
    if (req.json_schema === null || typeof req.json_schema !== "object" || Array.isArray(req.json_schema)) {
      throw new Error("json_schema must be an object.");
    }
    const body: Record<string, unknown> = {
      workspace_id: req.workspace_id ?? "default",
      schema_name: schemaName,
      provider_format: assertProviderFormat(req.provider_format ?? "deepseek_opencore"),
      model_id: modelId,
      json_schema: req.json_schema,
      raw_output: req.raw_output,
      strict_mode: req.strict_mode ?? false,
      fail_closed: req.fail_closed ?? true,
    };
    return this.requestJson("POST", "/v1/platform/healing/structured/enforce", { body, options });
  }

  public listStructuredOutputRuns(
    params: ListStructuredOutputRunsParams | string = {},
    options?: RequestOptions,
  ): Promise<StructuredOutputRunListResponse> {
    return this.requestJson("GET", "/v1/platform/healing/structured/runs", {
      query: buildHealingListQuery(params),
      options,
    });
  }

  public diagnoseFailureRootCause(
    req: DiagnoseFailureRootCauseRequest = {},
    options?: RequestOptions,
  ): Promise<SelfHealingDiagnosisRecord> {
    const wfName = (req.workflow_name ?? "invoice-triage-agent").trim();
    if (!wfName) throw new Error("workflow_name must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: req.workspace_id ?? "default",
      workflow_name: wfName,
    };
    if (req.trace_id !== undefined && req.trace_id !== null && req.trace_id.trim() !== "") {
      body.trace_id = req.trace_id.trim();
    }
    if (req.failed_step !== undefined && req.failed_step !== null) {
      body.failed_step = req.failed_step;
    }
    return this.requestJson("POST", "/v1/platform/healing/root-cause/diagnose", { body, options });
  }

  public applySelfHealingPatch(
    diagnosisId: string,
    req: ApplySelfHealingPatchRequest = {},
    options?: RequestOptions,
  ): Promise<ApplySelfHealingResponse> {
    const seg = encodePathSeg(diagnosisId, "diagnosis_id");
    const body: Record<string, unknown> = {
      workspace_id: req.workspace_id ?? "default",
      promote_to_eval: req.promote_to_eval ?? true,
    };
    if (req.eval_title !== undefined && req.eval_title !== null && req.eval_title.trim() !== "") {
      body.eval_title = req.eval_title.trim();
    }
    return this.requestJson("POST", `/v1/platform/healing/root-cause/${seg}/apply`, { body, options });
  }

  public listSelfHealingDiagnoses(
    params: ListSelfHealingDiagnosesParams | string = {},
    options?: RequestOptions,
  ): Promise<SelfHealingDiagnosisListResponse> {
    return this.requestJson("GET", "/v1/platform/healing/root-cause/diagnoses", {
      query: buildHealingListQuery(params),
      options,
    });
  }
}

export { PlatformHealingClient as PlatformHealingDelegate };
