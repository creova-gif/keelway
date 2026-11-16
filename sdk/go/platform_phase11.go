package keelway

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

type IngestOtelTracesRequest struct {
	WorkspaceID     string           `json:"workspace_id,omitempty"`
	WorkflowName    string           `json:"workflow_name,omitempty"`
	SourceFramework string           `json:"source_framework,omitempty"`
	Spans           []map[string]any `json:"spans,omitempty"`
	ResourceSpans   []map[string]any `json:"resourceSpans,omitempty"`
	TraceID         string           `json:"trace_id,omitempty"`
}

type FlightTapeStep struct {
	StepIndex    int            `json:"step_index"`
	SpanID       string         `json:"span_id,omitempty"`
	ParentSpanID string         `json:"parent_span_id,omitempty"`
	Name         string         `json:"name,omitempty"`
	Kind         string         `json:"kind,omitempty"`
	Model        string         `json:"model,omitempty"`
	Prompt       string         `json:"prompt,omitempty"`
	Output       string         `json:"output,omitempty"`
	State        map[string]any `json:"state,omitempty"`
	InputTokens  int            `json:"input_tokens,omitempty"`
	OutputTokens int            `json:"output_tokens,omitempty"`
	LatencyMS    float64        `json:"latency_ms,omitempty"`
	Attributes   map[string]any `json:"attributes,omitempty"`
	StepSHA256   string         `json:"step_sha256,omitempty"`
}

type FlightTapeRecord struct {
	TraceID             string           `json:"trace_id"`
	ID                  string           `json:"id,omitempty"`
	WorkspaceID         string           `json:"workspace_id"`
	WorkflowName        string           `json:"workflow_name,omitempty"`
	SourceFramework     string           `json:"source_framework,omitempty"`
	ParentTraceID       string           `json:"parent_trace_id,omitempty"`
	ForkedFromTraceID   string           `json:"forked_from_trace_id,omitempty"`
	ForkedFromStepIndex *int             `json:"forked_from_step_index,omitempty"`
	SpanCount           int              `json:"span_count,omitempty"`
	StepCount           int              `json:"step_count,omitempty"`
	Steps               []FlightTapeStep `json:"steps,omitempty"`
	Spans               []map[string]any `json:"spans,omitempty"`
	TapeSHA256          string           `json:"tape_sha256,omitempty"`
	DigestSHA256        string           `json:"digest_sha256,omitempty"`
	Status              string           `json:"status,omitempty"`
	CreatedAt           string           `json:"created_at,omitempty"`
}

type FlightTapeListResponse struct {
	WorkspaceID string             `json:"workspace_id"`
	Total       int                `json:"total,omitempty"`
	TotalTapes  int                `json:"total_tapes,omitempty"`
	Count       int                `json:"count,omitempty"`
	Tapes       []FlightTapeRecord `json:"tapes,omitempty"`
	Traces      []FlightTapeRecord `json:"traces,omitempty"`
}

type ReplayFlightTapeRequest struct {
	WorkspaceID    string         `json:"workspace_id,omitempty"`
	FromStepIndex  int            `json:"from_step_index"`
	OverridePrompt string         `json:"override_prompt,omitempty"`
	OverrideModel  string         `json:"override_model,omitempty"`
	OverrideState  map[string]any `json:"override_state,omitempty"`
}

type PromoteTraceToEvalRequest struct {
	WorkspaceID         string   `json:"workspace_id,omitempty"`
	TraceID             string   `json:"trace_id"`
	Title               string   `json:"title,omitempty"`
	ExpectedSubstrings  []string `json:"expected_substrings,omitempty"`
	ForbiddenSubstrings []string `json:"forbidden_substrings,omitempty"`
}

type EvalDatasetCase struct {
	CaseID              string   `json:"case_id,omitempty"`
	ID                  string   `json:"id,omitempty"`
	WorkspaceID         string   `json:"workspace_id"`
	SourceTraceID       string   `json:"source_trace_id,omitempty"`
	TraceID             string   `json:"trace_id,omitempty"`
	Title               string   `json:"title,omitempty"`
	Prompt              string   `json:"prompt,omitempty"`
	ReferenceOutput     string   `json:"reference_output,omitempty"`
	ExpectedSubstrings  []string `json:"expected_substrings,omitempty"`
	ForbiddenSubstrings []string `json:"forbidden_substrings,omitempty"`
	CaseSHA256          string   `json:"case_sha256,omitempty"`
	DigestSHA256        string   `json:"digest_sha256,omitempty"`
	CreatedAt           string   `json:"created_at,omitempty"`
}

type EvalDatasetListResponse struct {
	WorkspaceID string            `json:"workspace_id"`
	Total       int               `json:"total,omitempty"`
	TotalCases  int               `json:"total_cases,omitempty"`
	Count       int               `json:"count,omitempty"`
	Cases       []EvalDatasetCase `json:"cases"`
}

type MigrateLanggraphRequest struct {
	WorkspaceID    string `json:"workspace_id,omitempty"`
	SourceCode     string `json:"source_code"`
	SourceLanguage string `json:"source_language,omitempty"`
	WorkflowName   string `json:"workflow_name,omitempty"`
}

type LanggraphMigrationResult struct {
	WorkspaceID       string           `json:"workspace_id,omitempty"`
	WorkflowID        string           `json:"workflow_id,omitempty"`
	WorkflowName      string           `json:"workflow_name,omitempty"`
	SourceFramework   string           `json:"source_framework,omitempty"`
	SourceLanguage    string           `json:"source_language,omitempty"`
	Nodes             []map[string]any `json:"nodes"`
	Edges             []map[string]any `json:"edges,omitempty"`
	ConditionalEdges  []map[string]any `json:"conditional_edges,omitempty"`
	P10GatesInjected  int              `json:"p10_gates_injected,omitempty"`
	KflowDAG          map[string]any   `json:"kflow_dag,omitempty"`
	Warnings          []string         `json:"warnings,omitempty"`
	ASTDigestSHA256   string           `json:"ast_digest_sha256,omitempty"`
	ManifestSHA256    string           `json:"manifest_sha256,omitempty"`
}

func (p *PlatformService) IngestOtelTraces(ctx context.Context, req IngestOtelTracesRequest) (*FlightTapeRecord, error) {
	body := map[string]any{
		"workspace_id":     firstString(req.WorkspaceID, "default"),
		"workflow_name":    firstString(req.WorkflowName, "agent-trace"),
		"source_framework": firstString(req.SourceFramework, "opentelemetry_genai"),
	}
	if req.Spans != nil {
		body["spans"] = req.Spans
	}
	if req.ResourceSpans != nil {
		body["resourceSpans"] = req.ResourceSpans
		body["resource_spans"] = req.ResourceSpans
	}
	if tid := strings.TrimSpace(req.TraceID); tid != "" {
		body["trace_id"] = tid
	}
	return doPlatformJSON[FlightTapeRecord](ctx, p.client, http.MethodPost, "/v1/platform/traces/ingest", nil, body)
}

func (p *PlatformService) ListFlightTapes(ctx context.Context, workspaceID string, limit int) (*FlightTapeListResponse, error) {
	q := wsQuery(workspaceID)
	if limit <= 0 {
		limit = 20
	}
	q.Set("limit", strconv.Itoa(limit))
	return doPlatformJSON[FlightTapeListResponse](ctx, p.client, http.MethodGet, "/v1/platform/traces", q, nil)
}

func (p *PlatformService) ReplayFlightTape(ctx context.Context, traceID string, req ReplayFlightTapeRequest) (*FlightTapeRecord, error) {
	if req.FromStepIndex < 0 {
		return nil, fmt.Errorf("keelway: from_step_index must be >= 0")
	}
	body := map[string]any{
		"workspace_id":    firstString(req.WorkspaceID, "default"),
		"from_step_index": req.FromStepIndex,
	}
	if req.OverridePrompt != "" {
		body["override_prompt"] = req.OverridePrompt
	}
	if req.OverrideModel != "" {
		body["override_model"] = req.OverrideModel
	}
	if req.OverrideState != nil {
		body["override_state"] = req.OverrideState
	}
	return doSegJSON[FlightTapeRecord](ctx, p.client, http.MethodPost, "/v1/platform/traces/", traceID, "traceID", "/replay", nil, body)
}

func (p *PlatformService) PromoteTraceToEval(ctx context.Context, req PromoteTraceToEvalRequest) (*EvalDatasetCase, error) {
	cleanTraceID := strings.TrimSpace(req.TraceID)
	if cleanTraceID == "" {
		return nil, fmt.Errorf("keelway: trace_id must be non-empty")
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"trace_id":     cleanTraceID,
	}
	if req.Title != "" {
		body["title"] = req.Title
	}
	if req.ExpectedSubstrings != nil {
		body["expected_substrings"] = req.ExpectedSubstrings
	}
	if req.ForbiddenSubstrings != nil {
		body["forbidden_substrings"] = req.ForbiddenSubstrings
	}
	return doPlatformJSON[EvalDatasetCase](ctx, p.client, http.MethodPost, "/v1/platform/eval/dataset/promote", nil, body)
}

func (p *PlatformService) ListEvalDatasetCases(ctx context.Context, workspaceID string) (*EvalDatasetListResponse, error) {
	return doPlatformJSON[EvalDatasetListResponse](ctx, p.client, http.MethodGet, "/v1/platform/eval/dataset", wsQuery(workspaceID), nil)
}

func (p *PlatformService) MigrateLanggraphSource(ctx context.Context, req MigrateLanggraphRequest) (*LanggraphMigrationResult, error) {
	if strings.TrimSpace(req.SourceCode) == "" {
		return nil, fmt.Errorf("keelway: source_code must be non-empty")
	}
	body := map[string]any{
		"workspace_id":    firstString(req.WorkspaceID, "default"),
		"source_code":     req.SourceCode,
		"source_language": firstString(req.SourceLanguage, "python"),
	}
	if wf := strings.TrimSpace(req.WorkflowName); wf != "" {
		body["workflow_name"] = wf
	}
	return doPlatformJSON[LanggraphMigrationResult](ctx, p.client, http.MethodPost, "/v1/platform/migrate/langgraph", nil, body)
}

func (c *Client) IngestOtelTraces(ctx context.Context, req IngestOtelTracesRequest) (*FlightTapeRecord, error) {
	return c.Platform.IngestOtelTraces(ctx, req)
}

func (c *Client) ListFlightTapes(ctx context.Context, workspaceID string, limit int) (*FlightTapeListResponse, error) {
	return c.Platform.ListFlightTapes(ctx, workspaceID, limit)
}

func (c *Client) ReplayFlightTape(ctx context.Context, traceID string, req ReplayFlightTapeRequest) (*FlightTapeRecord, error) {
	return c.Platform.ReplayFlightTape(ctx, traceID, req)
}

func (c *Client) PromoteTraceToEval(ctx context.Context, req PromoteTraceToEvalRequest) (*EvalDatasetCase, error) {
	return c.Platform.PromoteTraceToEval(ctx, req)
}

func (c *Client) ListEvalDatasetCases(ctx context.Context, workspaceID string) (*EvalDatasetListResponse, error) {
	return c.Platform.ListEvalDatasetCases(ctx, workspaceID)
}

func (c *Client) MigrateLanggraphSource(ctx context.Context, req MigrateLanggraphRequest) (*LanggraphMigrationResult, error) {
	return c.Platform.MigrateLanggraphSource(ctx, req)
}
