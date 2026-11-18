package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

type NormalizeContentBlocksRequest struct {
	WorkspaceID    string `json:"workspace_id,omitempty"`
	ProviderFormat string `json:"provider_format"`
	ModelID        string `json:"model_id,omitempty"`
	RawPayload     any    `json:"raw_payload"`
}
type NormalizedContentBlock struct {
	Index          int            `json:"index"`
	Kind           string         `json:"kind"`
	Content        string         `json:"content"`
	ToolName       string         `json:"tool_name,omitempty"`
	ToolCallID     string         `json:"tool_call_id,omitempty"`
	ToolArgs       map[string]any `json:"tool_args,omitempty"`
	SourceURI      string         `json:"source_uri,omitempty"`
	StructuredData map[string]any `json:"structured_data,omitempty"`
}
type NormalizedContentEnvelope struct {
	WorkspaceID    string                   `json:"workspace_id"`
	ProviderFormat string                   `json:"provider_format"`
	ModelID        string                   `json:"model_id"`
	BlockCount     int                      `json:"block_count"`
	ContentBlocks  []NormalizedContentBlock `json:"content_blocks"`
	DLPRedactions  int                      `json:"dlp_redactions"`
	EnvelopeSHA256 string                   `json:"envelope_sha256"`
}
type EnforceStructuredOutputRequest struct {
	WorkspaceID    string         `json:"workspace_id,omitempty"`
	SchemaName     string         `json:"schema_name,omitempty"`
	ProviderFormat string         `json:"provider_format,omitempty"`
	ModelID        string         `json:"model_id,omitempty"`
	JSONSchema     map[string]any `json:"json_schema"`
	RawOutput      any            `json:"raw_output"`
	StrictMode     *bool          `json:"strict_mode,omitempty"`
	FailClosed     *bool          `json:"fail_closed,omitempty"`
}
type StructuredOutputRunRecord struct {
	RunID            string         `json:"run_id"`
	WorkspaceID      string         `json:"workspace_id"`
	SchemaName       string         `json:"schema_name"`
	ProviderFormat   string         `json:"provider_format"`
	ModelID          string         `json:"model_id"`
	Status           string         `json:"status"`
	RepairApplied    bool           `json:"repair_applied"`
	RepairActions    []string       `json:"repair_actions"`
	ValidatedData    map[string]any `json:"validated_data,omitempty"`
	ValidationErrors []string       `json:"validation_errors"`
	DLPRedactions    int            `json:"dlp_redactions"`
	RunSHA256        string         `json:"run_sha256"`
	CreatedAt        string         `json:"created_at"`
}
type ListStructuredOutputRunsParams struct {
	WorkspaceID string
	Limit       int
}
type StructuredOutputRunListResponse struct {
	WorkspaceID string                      `json:"workspace_id"`
	Count       int                         `json:"count"`
	Runs        []StructuredOutputRunRecord `json:"runs"`
}
type FailedStepInput struct {
	StepIndex      *int           `json:"step_index,omitempty"`
	NodeName       string         `json:"node_name,omitempty"`
	ModelID        string         `json:"model_id,omitempty"`
	PromptText     string         `json:"prompt_text,omitempty"`
	OutputText     string         `json:"output_text,omitempty"`
	ErrorMessage   string         `json:"error_message,omitempty"`
	ExpectedSchema map[string]any `json:"expected_schema,omitempty"`
}
type DiagnoseFailureRootCauseRequest struct {
	WorkspaceID  string           `json:"workspace_id,omitempty"`
	TraceID      string           `json:"trace_id,omitempty"`
	WorkflowName string           `json:"workflow_name,omitempty"`
	FailedStep   *FailedStepInput `json:"failed_step,omitempty"`
}
type ProposedSelfHealingPatch struct {
	TargetSurface    string `json:"target_surface"`
	RecommendedModel string `json:"recommended_model"`
	UnifiedDiff      string `json:"unified_diff"`
	PatchedPrompt    string `json:"patched_prompt"`
}
type SelfHealingDiagnosisRecord struct {
	DiagnosisID               string                   `json:"diagnosis_id"`
	WorkspaceID               string                   `json:"workspace_id"`
	TraceID                   string                   `json:"trace_id,omitempty"`
	WorkflowName              string                   `json:"workflow_name"`
	FailureClass              string                   `json:"failure_class"`
	Status                    string                   `json:"status"`
	Confidence                float64                  `json:"confidence"`
	FailedNode                string                   `json:"failed_node"`
	DiagnosticModel           string                   `json:"diagnostic_model"`
	Summary                   string                   `json:"summary"`
	RootCauseEvidence         []string                 `json:"root_cause_evidence"`
	ProposedPatch             ProposedSelfHealingPatch `json:"proposed_patch"`
	VerificationReplayTraceID string                   `json:"verification_replay_trace_id,omitempty"`
	PromotedEvalCaseID        string                   `json:"promoted_eval_case_id,omitempty"`
	DLPRedactions             int                      `json:"dlp_redactions"`
	DiagnosisSHA256           string                   `json:"diagnosis_sha256"`
	CreatedAt                 string                   `json:"created_at"`
}
type ApplySelfHealingPatchRequest struct {
	WorkspaceID   string `json:"workspace_id,omitempty"`
	PromoteToEval *bool  `json:"promote_to_eval,omitempty"`
	EvalTitle     string `json:"eval_title,omitempty"`
}
type PromotedEvalCaseSummary struct {
	CaseID     string `json:"case_id"`
	Title      string `json:"title"`
	CaseSHA256 string `json:"case_sha256"`
}
type ApplySelfHealingResponse struct {
	Diagnosis         SelfHealingDiagnosisRecord `json:"diagnosis"`
	VerifiedHealed    bool                       `json:"verified_healed"`
	CachedStepsReused int                        `json:"cached_steps_reused"`
	ReplayCostUSD     float64                    `json:"replay_cost_usd"`
	PromotedEvalCase  *PromotedEvalCaseSummary   `json:"promoted_eval_case,omitempty"`
}
type ListSelfHealingDiagnosesParams = ListStructuredOutputRunsParams
type SelfHealingDiagnosisListResponse struct {
	WorkspaceID string                       `json:"workspace_id"`
	Count       int                          `json:"count"`
	Diagnoses   []SelfHealingDiagnosisRecord `json:"diagnoses"`
}

func isValidProviderFormat(fmtName string) bool {
	switch fmtName {
	case "deepseek_opencore", "openai", "anthropic", "gemini":
		return true
	default:
		return false
	}
}

func buildHealingListQuery(wsID string, limit int) (url.Values, error) {
	if limit < 0 {
		return nil, fmt.Errorf("keelway: limit must be >= 1")
	}
	if limit == 0 {
		limit = 25
	}
	q := wsQuery(wsID)
	q.Set("limit", strconv.Itoa(limit))
	return q, nil
}

func (p *PlatformService) NormalizeContentBlocks(ctx context.Context, req NormalizeContentBlocksRequest) (*NormalizedContentEnvelope, error) {
	prov := firstString(strings.TrimSpace(req.ProviderFormat), "deepseek_opencore")
	if !isValidProviderFormat(prov) {
		return nil, fmt.Errorf("keelway: invalid provider_format %q", prov)
	}
	if req.RawPayload == nil {
		return nil, fmt.Errorf("keelway: raw_payload must be non-nil")
	}
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	req.ProviderFormat = prov
	req.ModelID = firstString(strings.TrimSpace(req.ModelID), "keelway-core:7b")
	return doPlatformJSON[NormalizedContentEnvelope](ctx, p.client, http.MethodPost, "/v1/platform/healing/content-blocks/normalize", nil, req)
}

func (p *PlatformService) EnforceStructuredOutput(ctx context.Context, req EnforceStructuredOutputRequest) (*StructuredOutputRunRecord, error) {
	prov := firstString(strings.TrimSpace(req.ProviderFormat), "deepseek_opencore")
	if !isValidProviderFormat(prov) {
		return nil, fmt.Errorf("keelway: invalid provider_format %q", prov)
	}
	if req.JSONSchema == nil {
		return nil, fmt.Errorf("keelway: json_schema must be non-nil")
	}
	if req.RawOutput == nil {
		return nil, fmt.Errorf("keelway: raw_output must be non-nil")
	}
	strict := false
	if req.StrictMode != nil {
		strict = *req.StrictMode
	}
	failClosed := true
	if req.FailClosed != nil {
		failClosed = *req.FailClosed
	}
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	req.SchemaName = firstString(strings.TrimSpace(req.SchemaName), "AgentDecisionContract")
	req.ProviderFormat = prov
	req.ModelID = firstString(strings.TrimSpace(req.ModelID), "keelway-core:7b")
	req.StrictMode = &strict
	req.FailClosed = &failClosed
	return doPlatformJSON[StructuredOutputRunRecord](ctx, p.client, http.MethodPost, "/v1/platform/healing/structured/enforce", nil, req)
}

func (p *PlatformService) ListStructuredOutputRuns(ctx context.Context, params ListStructuredOutputRunsParams) (*StructuredOutputRunListResponse, error) {
	q, err := buildHealingListQuery(params.WorkspaceID, params.Limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[StructuredOutputRunListResponse](ctx, p.client, http.MethodGet, "/v1/platform/healing/structured/runs", q, nil)
}

func (p *PlatformService) DiagnoseFailureRootCause(ctx context.Context, req DiagnoseFailureRootCauseRequest) (*SelfHealingDiagnosisRecord, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	req.WorkflowName = firstString(strings.TrimSpace(req.WorkflowName), "invoice-triage-agent")
	req.TraceID = strings.TrimSpace(req.TraceID)
	return doPlatformJSON[SelfHealingDiagnosisRecord](ctx, p.client, http.MethodPost, "/v1/platform/healing/root-cause/diagnose", nil, req)
}

func (p *PlatformService) ApplySelfHealingPatch(ctx context.Context, diagnosisID string, req ApplySelfHealingPatchRequest) (*ApplySelfHealingResponse, error) {
	promote := true
	if req.PromoteToEval != nil {
		promote = *req.PromoteToEval
	}
	body := map[string]any{
		"workspace_id":    firstString(req.WorkspaceID, "default"),
		"promote_to_eval": promote,
	}
	if title := strings.TrimSpace(req.EvalTitle); title != "" {
		body["eval_title"] = title
	}
	return doSegJSON[ApplySelfHealingResponse](ctx, p.client, http.MethodPost, "/v1/platform/healing/root-cause/", diagnosisID, "diagnosisID", "/apply", nil, body)
}

func (p *PlatformService) ListSelfHealingDiagnoses(ctx context.Context, params ListSelfHealingDiagnosesParams) (*SelfHealingDiagnosisListResponse, error) {
	q, err := buildHealingListQuery(params.WorkspaceID, params.Limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[SelfHealingDiagnosisListResponse](ctx, p.client, http.MethodGet, "/v1/platform/healing/root-cause/diagnoses", q, nil)
}

func (c *Client) NormalizeContentBlocks(ctx context.Context, req NormalizeContentBlocksRequest) (*NormalizedContentEnvelope, error) {
	return c.Platform.NormalizeContentBlocks(ctx, req)
}
func (c *Client) EnforceStructuredOutput(ctx context.Context, req EnforceStructuredOutputRequest) (*StructuredOutputRunRecord, error) {
	return c.Platform.EnforceStructuredOutput(ctx, req)
}
func (c *Client) ListStructuredOutputRuns(ctx context.Context, params ListStructuredOutputRunsParams) (*StructuredOutputRunListResponse, error) {
	return c.Platform.ListStructuredOutputRuns(ctx, params)
}
func (c *Client) DiagnoseFailureRootCause(ctx context.Context, req DiagnoseFailureRootCauseRequest) (*SelfHealingDiagnosisRecord, error) {
	return c.Platform.DiagnoseFailureRootCause(ctx, req)
}
func (c *Client) ApplySelfHealingPatch(ctx context.Context, diagnosisID string, req ApplySelfHealingPatchRequest) (*ApplySelfHealingResponse, error) {
	return c.Platform.ApplySelfHealingPatch(ctx, diagnosisID, req)
}
func (c *Client) ListSelfHealingDiagnoses(ctx context.Context, params ListSelfHealingDiagnosesParams) (*SelfHealingDiagnosisListResponse, error) {
	return c.Platform.ListSelfHealingDiagnoses(ctx, params)
}
