package keelway

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

func BoolPtr(v bool) *bool {
	return &v
}

func Float64Ptr(v float64) *float64 {
	return &v
}

type StudioKflowNodeInput struct {
	ID          string   `json:"id"`
	Label       string   `json:"label,omitempty"`
	AgentID     string   `json:"agent_id,omitempty"`
	DependsOn   []string `json:"depends_on,omitempty"`
	RequiresP10 bool     `json:"requires_p10"`
	LineStart   int      `json:"line_start,omitempty"`
	LineEnd     int      `json:"line_end,omitempty"`
	Wave        int      `json:"wave,omitempty"`
	X           float64  `json:"x,omitempty"`
	Y           float64  `json:"y,omitempty"`
}

type StudioKflowNode struct {
	ID          string   `json:"id"`
	Label       string   `json:"label"`
	AgentID     string   `json:"agent_id"`
	DependsOn   []string `json:"depends_on"`
	RequiresP10 bool     `json:"requires_p10"`
	LineStart   int      `json:"line_start"`
	LineEnd     int      `json:"line_end"`
	Wave        int      `json:"wave"`
	X           float64  `json:"x"`
	Y           float64  `json:"y"`
}

type StudioKflowEdge struct {
	From    string `json:"from"`
	To      string `json:"to"`
	IsCycle bool   `json:"is_cycle"`
}

type StudioKflowCycleEdge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

type SyncKflowStudioRequest struct {
	WorkspaceID string                 `json:"workspace_id,omitempty"`
	Direction   string                 `json:"direction,omitempty"`
	Language    string                 `json:"language,omitempty"`
	WorkflowID  string                 `json:"workflow_id,omitempty"`
	SourceCode  string                 `json:"source_code,omitempty"`
	Nodes       []StudioKflowNodeInput `json:"nodes,omitempty"`
	Persist     *bool                  `json:"persist,omitempty"`
}

type StudioKflowSyncResult struct {
	WorkspaceID    string                 `json:"workspace_id"`
	WorkflowID     string                 `json:"workflow_id"`
	Direction      string                 `json:"direction"`
	Language       string                 `json:"language"`
	Nodes          []StudioKflowNode      `json:"nodes"`
	Edges          []StudioKflowEdge      `json:"edges"`
	CycleBackEdges []StudioKflowCycleEdge `json:"cycle_back_edges"`
	P10LockedNodes []string               `json:"p10_locked_nodes"`
	SourceCode     string                 `json:"source_code"`
	Persisted      bool                   `json:"persisted"`
	SyncSHA256     string                 `json:"sync_sha256"`
}

type RecordBlastRadiusRequest struct {
	WorkspaceID        string   `json:"workspace_id,omitempty"`
	TraceID            string   `json:"trace_id,omitempty"`
	WorkflowID         string   `json:"workflow_id,omitempty"`
	FSReads            []string `json:"fs_reads,omitempty"`
	FSWrites           []string `json:"fs_writes,omitempty"`
	BlockedPaths       []string `json:"blocked_paths,omitempty"`
	EgressAttempts     int      `json:"egress_attempts,omitempty"`
	BlockedEgressHosts []string `json:"blocked_egress_hosts,omitempty"`
	P10GatesTriggered  int      `json:"p10_gates_triggered,omitempty"`
	Seatbelted         *bool    `json:"seatbelted,omitempty"`
}

type BlastRadiusAuditRecord struct {
	AuditID              string   `json:"audit_id"`
	WorkspaceID          string   `json:"workspace_id"`
	TraceID              string   `json:"trace_id,omitempty"`
	WorkflowID           string   `json:"workflow_id,omitempty"`
	FSReads              []string `json:"fs_reads"`
	FSWrites             []string `json:"fs_writes"`
	BlockedPaths         []string `json:"blocked_paths"`
	EgressAttempts       int      `json:"egress_attempts"`
	BlockedEgressHosts   []string `json:"blocked_egress_hosts"`
	P10GatesTriggered    int      `json:"p10_gates_triggered"`
	Seatbelted           bool     `json:"seatbelted"`
	ZeroUnapprovedEgress bool     `json:"zero_unapproved_egress"`
	SyscallsAudited      int      `json:"syscalls_audited"`
	RiskTier             string   `json:"risk_tier"`
	AuditSHA256          string   `json:"audit_sha256"`
	RecordedAt           string   `json:"recorded_at"`
}

type BlastRadiusAuditListResponse struct {
	WorkspaceID string                   `json:"workspace_id"`
	Count       int                      `json:"count"`
	Audits      []BlastRadiusAuditRecord `json:"audits"`
}

type EvaluatePromptGateRequest struct {
	WorkspaceID            string   `json:"workspace_id,omitempty"`
	CandidatePromptVersion string   `json:"candidate_prompt_version"`
	CandidateModelID       string   `json:"candidate_model_id"`
	CandidatePromptText    string   `json:"candidate_prompt_text,omitempty"`
	RequiredJSONKeys       []string `json:"required_json_keys,omitempty"`
	MinPassRate            *float64 `json:"min_pass_rate,omitempty"`
}

type PromptGateEvaluationResult struct {
	GateRunID              string  `json:"gate_run_id"`
	WorkspaceID            string  `json:"workspace_id"`
	CandidatePromptVersion string  `json:"candidate_prompt_version"`
	CandidateModelID       string  `json:"candidate_model_id"`
	Verdict                string  `json:"verdict"`
	CasesEvaluated         int     `json:"cases_evaluated"`
	PassedCases            int     `json:"passed_cases"`
	PassRate               float64 `json:"pass_rate"`
	MinPassRate            float64 `json:"min_pass_rate"`
	SchemaValidCount       int     `json:"schema_valid_count"`
	DLPViolations          int     `json:"dlp_violations"`
	CostDeltaUSD           float64 `json:"cost_delta_usd"`
	DatasetSource          string  `json:"dataset_source"`
	GateSHA256             string  `json:"gate_sha256"`
	EvaluatedAt            string  `json:"evaluated_at"`
}

type PromptGateRunListResponse struct {
	WorkspaceID string                       `json:"workspace_id"`
	Count       int                          `json:"count"`
	Runs        []PromptGateEvaluationResult `json:"runs"`
}

func (p *PlatformService) SyncKflowStudio(ctx context.Context, req SyncKflowStudioRequest) (*StudioKflowSyncResult, error) {
	direction := strings.TrimSpace(firstString(req.Direction, "code_to_graph"))
	if direction != "code_to_graph" && direction != "graph_to_code" {
		return nil, fmt.Errorf("keelway: direction must be 'code_to_graph' or 'graph_to_code'")
	}
	language := strings.TrimSpace(firstString(req.Language, "python"))
	if language != "python" && language != "typescript" {
		return nil, fmt.Errorf("keelway: language must be 'python' or 'typescript'")
	}
	wfID := strings.TrimSpace(firstString(req.WorkflowID, "WF-STUDIO-01"))
	if wfID == "" {
		return nil, fmt.Errorf("keelway: workflow_id must be non-empty")
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"direction":    direction,
		"language":     language,
		"workflow_id":  wfID,
	}
	if req.SourceCode != "" {
		body["source_code"] = req.SourceCode
	}
	if req.Nodes != nil {
		body["nodes"] = req.Nodes
	}
	if req.Persist != nil {
		body["persist"] = *req.Persist
	}
	return doPlatformJSON[StudioKflowSyncResult](ctx, p.client, http.MethodPost, "/v1/platform/studio/kflow/sync", nil, body)
}

func (p *PlatformService) RecordBlastRadius(ctx context.Context, req RecordBlastRadiusRequest) (*BlastRadiusAuditRecord, error) {
	if req.EgressAttempts < 0 {
		return nil, fmt.Errorf("keelway: egress_attempts must be >= 0")
	}
	if req.P10GatesTriggered < 0 {
		return nil, fmt.Errorf("keelway: p10_gates_triggered must be >= 0")
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
	}
	if tid := strings.TrimSpace(req.TraceID); tid != "" {
		body["trace_id"] = tid
	}
	if wf := strings.TrimSpace(req.WorkflowID); wf != "" {
		body["workflow_id"] = wf
	}
	if req.FSReads != nil {
		body["fs_reads"] = req.FSReads
	}
	if req.FSWrites != nil {
		body["fs_writes"] = req.FSWrites
	}
	if req.BlockedPaths != nil {
		body["blocked_paths"] = req.BlockedPaths
	}
	if req.EgressAttempts > 0 {
		body["egress_attempts"] = req.EgressAttempts
	}
	if req.BlockedEgressHosts != nil {
		body["blocked_egress_hosts"] = req.BlockedEgressHosts
	}
	if req.P10GatesTriggered > 0 {
		body["p10_gates_triggered"] = req.P10GatesTriggered
	}
	if req.Seatbelted != nil {
		body["seatbelted"] = *req.Seatbelted
	}
	return doPlatformJSON[BlastRadiusAuditRecord](ctx, p.client, http.MethodPost, "/v1/platform/studio/blast-radius/record", nil, body)
}

func (p *PlatformService) ListBlastRadiusAudits(ctx context.Context, workspaceID string, traceID string, limit int) (*BlastRadiusAuditListResponse, error) {
	q := wsQuery(workspaceID)
	if tid := strings.TrimSpace(traceID); tid != "" {
		q.Set("trace_id", tid)
	}
	if limit <= 0 {
		limit = 25
	}
	q.Set("limit", strconv.Itoa(limit))
	return doPlatformJSON[BlastRadiusAuditListResponse](ctx, p.client, http.MethodGet, "/v1/platform/studio/blast-radius", q, nil)
}

func (p *PlatformService) EvaluatePromptGate(ctx context.Context, req EvaluatePromptGateRequest) (*PromptGateEvaluationResult, error) {
	cleanVer := strings.TrimSpace(req.CandidatePromptVersion)
	if cleanVer == "" {
		return nil, fmt.Errorf("keelway: candidate_prompt_version must be non-empty")
	}
	cleanModel := strings.TrimSpace(req.CandidateModelID)
	if cleanModel == "" {
		return nil, fmt.Errorf("keelway: candidate_model_id must be non-empty")
	}
	if req.MinPassRate != nil && (*req.MinPassRate < 0.0 || *req.MinPassRate > 1.0) {
		return nil, fmt.Errorf("keelway: min_pass_rate must be between 0.0 and 1.0")
	}
	body := map[string]any{
		"workspace_id":             firstString(req.WorkspaceID, "default"),
		"candidate_prompt_version": cleanVer,
		"candidate_model_id":       cleanModel,
	}
	if req.CandidatePromptText != "" {
		body["candidate_prompt_text"] = req.CandidatePromptText
	}
	if req.RequiredJSONKeys != nil {
		body["required_json_keys"] = req.RequiredJSONKeys
	}
	if req.MinPassRate != nil {
		body["min_pass_rate"] = *req.MinPassRate
	}
	return doPlatformJSON[PromptGateEvaluationResult](ctx, p.client, http.MethodPost, "/v1/platform/studio/prompt-gate/evaluate", nil, body)
}

func (p *PlatformService) ListPromptGateRuns(ctx context.Context, workspaceID string, limit int) (*PromptGateRunListResponse, error) {
	q := wsQuery(workspaceID)
	if limit <= 0 {
		limit = 20
	}
	q.Set("limit", strconv.Itoa(limit))
	return doPlatformJSON[PromptGateRunListResponse](ctx, p.client, http.MethodGet, "/v1/platform/studio/prompt-gate/runs", q, nil)
}

func (c *Client) SyncKflowStudio(ctx context.Context, req SyncKflowStudioRequest) (*StudioKflowSyncResult, error) {
	return c.Platform.SyncKflowStudio(ctx, req)
}

func (c *Client) RecordBlastRadius(ctx context.Context, req RecordBlastRadiusRequest) (*BlastRadiusAuditRecord, error) {
	return c.Platform.RecordBlastRadius(ctx, req)
}

func (c *Client) ListBlastRadiusAudits(ctx context.Context, workspaceID string, traceID string, limit int) (*BlastRadiusAuditListResponse, error) {
	return c.Platform.ListBlastRadiusAudits(ctx, workspaceID, traceID, limit)
}

func (c *Client) EvaluatePromptGate(ctx context.Context, req EvaluatePromptGateRequest) (*PromptGateEvaluationResult, error) {
	return c.Platform.EvaluatePromptGate(ctx, req)
}

func (c *Client) ListPromptGateRuns(ctx context.Context, workspaceID string, limit int) (*PromptGateRunListResponse, error) {
	return c.Platform.ListPromptGateRuns(ctx, workspaceID, limit)
}
