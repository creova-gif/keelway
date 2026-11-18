package keelway

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

func IntPtr(v int) *int {
	return &v
}

type SetBreakpointRequest struct {
	WorkspaceID   string   `json:"workspace_id,omitempty"`
	WorkflowID    string   `json:"workflow_id,omitempty"`
	NodeID        string   `json:"node_id,omitempty"`
	FilePath      string   `json:"file_path,omitempty"`
	LineNumber    *int     `json:"line_number,omitempty"`
	ConditionType string   `json:"condition_type,omitempty"`
	Threshold     *float64 `json:"threshold,omitempty"`
	Enabled       *bool    `json:"enabled,omitempty"`
	Label         string   `json:"label,omitempty"`
}

type DebuggerBreakpointRecord struct {
	BreakpointID  string   `json:"breakpoint_id"`
	WorkspaceID   string   `json:"workspace_id"`
	WorkflowID    string   `json:"workflow_id"`
	NodeID        string   `json:"node_id,omitempty"`
	FilePath      string   `json:"file_path"`
	LineNumber    *int     `json:"line_number,omitempty"`
	ConditionType string   `json:"condition_type"`
	Threshold     *float64 `json:"threshold,omitempty"`
	Enabled       bool     `json:"enabled"`
	Label         string   `json:"label"`
	CreatedAt     string   `json:"created_at"`
}

type DebuggerBreakpointListResponse struct {
	WorkspaceID string                     `json:"workspace_id"`
	Count       int                        `json:"count"`
	Breakpoints []DebuggerBreakpointRecord `json:"breakpoints"`
}

type DeleteBreakpointResponse struct {
	Deleted      bool   `json:"deleted"`
	BreakpointID string `json:"breakpoint_id"`
	WorkspaceID  string `json:"workspace_id"`
}

type DebuggerStepInput struct {
	NodeID      string         `json:"node_id,omitempty"`
	AgentID     string         `json:"agent_id,omitempty"`
	ToolName    string         `json:"tool_name,omitempty"`
	CostUSD     float64        `json:"cost_usd,omitempty"`
	HybridScore float64        `json:"hybrid_score,omitempty"`
	RequiresP10 bool           `json:"requires_p10,omitempty"`
	LineNumber  int            `json:"line_number,omitempty"`
	Variables   map[string]any `json:"variables,omitempty"`
}

type StartDebugSessionRequest struct {
	WorkspaceID  string              `json:"workspace_id,omitempty"`
	WorkflowID   string              `json:"workflow_id,omitempty"`
	Steps        []DebuggerStepInput `json:"steps,omitempty"`
	InitialState map[string]any      `json:"initial_state,omitempty"`
}

type DebuggerSessionRecord struct {
	SessionID        string           `json:"session_id"`
	WorkspaceID      string           `json:"workspace_id"`
	WorkflowID       string           `json:"workflow_id"`
	Status           string           `json:"status"`
	CurrentStepIndex int              `json:"current_step_index"`
	StepDepth        int              `json:"step_depth"`
	TotalSteps       int              `json:"total_steps"`
	HitBreakpointID  string           `json:"hit_breakpoint_id,omitempty"`
	HitReason        string           `json:"hit_reason,omitempty"`
	ActiveStep       map[string]any   `json:"active_step"`
	ActiveFrame      map[string]any   `json:"active_frame"`
	Variables        map[string]any   `json:"variables"`
	CallStack        []map[string]any `json:"call_stack"`
	MutationCount    int              `json:"mutation_count"`
	Mutations        []map[string]any `json:"mutations"`
	FrameSHA256      string           `json:"frame_sha256"`
	UpdatedAt        string           `json:"updated_at"`
}

type DebuggerSessionListResponse struct {
	WorkspaceID string                  `json:"workspace_id"`
	Count       int                     `json:"count"`
	Sessions    []DebuggerSessionRecord `json:"sessions"`
}

type StepDebugSessionRequest struct {
	WorkspaceID string         `json:"workspace_id,omitempty"`
	Action      string         `json:"action,omitempty"`
	StatePatch  map[string]any `json:"state_patch,omitempty"`
}

type DebuggerCodelensItem struct {
	Symbol              string  `json:"symbol"`
	FilePath            string  `json:"file_path"`
	LineStart           int     `json:"line_start"`
	Line                int     `json:"line"`
	ModelCheckpoint     string  `json:"model_checkpoint"`
	P50MS               int     `json:"p50_ms"`
	P50LatencyMS        int     `json:"p50_latency_ms"`
	AvgCostUSD          float64 `json:"avg_cost_usd"`
	Provenance4D        string  `json:"provenance_4d"`
	AttachedBreakpoints int     `json:"attached_breakpoints"`
}

type DebuggerCodelensResponse struct {
	WorkspaceID     string                 `json:"workspace_id"`
	WorkflowID      string                 `json:"workflow_id"`
	FilePath        string                 `json:"file_path"`
	VSCodeAttachURI string                 `json:"vscode_attach_uri"`
	CursorAttachURI string                 `json:"cursor_attach_uri"`
	Bridge          map[string]any         `json:"bridge"`
	Lenses          []DebuggerCodelensItem `json:"lenses"`
}

func isValidConditionType(cond string) bool {
	switch cond {
	case "always", "cost_usd_gt", "hybrid_score_lt", "before_shell_tool", "before_p10_gate", "line_match":
		return true
	default:
		return false
	}
}

func isValidDebuggerStepAction(action string) bool {
	switch action {
	case "step_over", "step_into", "continue", "mutate_state":
		return true
	default:
		return false
	}
}

func (p *PlatformService) SetBreakpoint(ctx context.Context, req SetBreakpointRequest) (*DebuggerBreakpointRecord, error) {
	wfID := strings.TrimSpace(firstString(req.WorkflowID, "WF-STUDIO-01"))
	if wfID == "" {
		return nil, fmt.Errorf("keelway: workflow_id must be non-empty")
	}
	cond := strings.TrimSpace(firstString(req.ConditionType, "always"))
	if !isValidConditionType(cond) {
		return nil, fmt.Errorf("keelway: invalid condition_type %q", cond)
	}
	if req.LineNumber != nil && *req.LineNumber < 1 {
		return nil, fmt.Errorf("keelway: line_number must be >= 1")
	}
	enabled := true
	if req.Enabled != nil {
		enabled = *req.Enabled
	}
	body := map[string]any{
		"workspace_id":   firstString(req.WorkspaceID, "default"),
		"workflow_id":    wfID,
		"file_path":      firstString(strings.TrimSpace(req.FilePath), "workflows/refund_agent.py"),
		"condition_type": cond,
		"enabled":        enabled,
	}
	if n := strings.TrimSpace(req.NodeID); n != "" {
		body["node_id"] = n
	}
	if req.LineNumber != nil {
		body["line_number"] = *req.LineNumber
	}
	if req.Threshold != nil {
		body["threshold"] = *req.Threshold
	}
	if lbl := strings.TrimSpace(req.Label); lbl != "" {
		body["label"] = lbl
	}
	return doPlatformJSON[DebuggerBreakpointRecord](ctx, p.client, http.MethodPost, "/v1/platform/debugger/breakpoints", nil, body)
}

func (p *PlatformService) ListBreakpoints(ctx context.Context, workspaceID string, workflowID string) (*DebuggerBreakpointListResponse, error) {
	q := wsQuery(workspaceID)
	if wf := strings.TrimSpace(workflowID); wf != "" {
		q.Set("workflow_id", wf)
	}
	return doPlatformJSON[DebuggerBreakpointListResponse](ctx, p.client, http.MethodGet, "/v1/platform/debugger/breakpoints", q, nil)
}

func (p *PlatformService) DeleteBreakpoint(ctx context.Context, breakpointID string, workspaceID string) (*DeleteBreakpointResponse, error) {
	return doSegJSON[DeleteBreakpointResponse](ctx, p.client, http.MethodDelete, "/v1/platform/debugger/breakpoints/", breakpointID, "breakpointID", "", wsQuery(workspaceID), nil)
}

func (p *PlatformService) StartDebugSession(ctx context.Context, req StartDebugSessionRequest) (*DebuggerSessionRecord, error) {
	wfID := strings.TrimSpace(firstString(req.WorkflowID, "WF-STUDIO-01"))
	if wfID == "" {
		return nil, fmt.Errorf("keelway: workflow_id must be non-empty")
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"workflow_id":  wfID,
	}
	if req.Steps != nil {
		body["steps"] = req.Steps
	}
	if req.InitialState != nil {
		body["initial_state"] = req.InitialState
	}
	return doPlatformJSON[DebuggerSessionRecord](ctx, p.client, http.MethodPost, "/v1/platform/debugger/sessions", nil, body)
}

func (p *PlatformService) ListDebugSessions(ctx context.Context, workspaceID string, limit int) (*DebuggerSessionListResponse, error) {
	q := wsQuery(workspaceID)
	if limit <= 0 {
		limit = 20
	}
	q.Set("limit", strconv.Itoa(limit))
	return doPlatformJSON[DebuggerSessionListResponse](ctx, p.client, http.MethodGet, "/v1/platform/debugger/sessions", q, nil)
}

func (p *PlatformService) StepDebugSession(ctx context.Context, sessionID string, req StepDebugSessionRequest) (*DebuggerSessionRecord, error) {
	action := strings.TrimSpace(firstString(req.Action, "step_over"))
	if !isValidDebuggerStepAction(action) {
		return nil, fmt.Errorf("keelway: invalid debugger action %q", action)
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"action":       action,
	}
	if req.StatePatch != nil {
		body["state_patch"] = req.StatePatch
	}
	return doSegJSON[DebuggerSessionRecord](ctx, p.client, http.MethodPost, "/v1/platform/debugger/sessions/", sessionID, "sessionID", "/step", nil, body)
}

func (p *PlatformService) GetDebuggerCodelens(ctx context.Context, workspaceID string, workflowID string, filePath string) (*DebuggerCodelensResponse, error) {
	q := wsQuery(workspaceID)
	if wf := strings.TrimSpace(workflowID); wf != "" {
		q.Set("workflow_id", wf)
	}
	if fp := strings.TrimSpace(filePath); fp != "" {
		q.Set("file_path", fp)
	}
	return doPlatformJSON[DebuggerCodelensResponse](ctx, p.client, http.MethodGet, "/v1/platform/debugger/codelens", q, nil)
}

func (c *Client) SetBreakpoint(ctx context.Context, req SetBreakpointRequest) (*DebuggerBreakpointRecord, error) {
	return c.Platform.SetBreakpoint(ctx, req)
}

func (c *Client) ListBreakpoints(ctx context.Context, workspaceID string, workflowID string) (*DebuggerBreakpointListResponse, error) {
	return c.Platform.ListBreakpoints(ctx, workspaceID, workflowID)
}

func (c *Client) DeleteBreakpoint(ctx context.Context, breakpointID string, workspaceID string) (*DeleteBreakpointResponse, error) {
	return c.Platform.DeleteBreakpoint(ctx, breakpointID, workspaceID)
}

func (c *Client) StartDebugSession(ctx context.Context, req StartDebugSessionRequest) (*DebuggerSessionRecord, error) {
	return c.Platform.StartDebugSession(ctx, req)
}

func (c *Client) ListDebugSessions(ctx context.Context, workspaceID string, limit int) (*DebuggerSessionListResponse, error) {
	return c.Platform.ListDebugSessions(ctx, workspaceID, limit)
}

func (c *Client) StepDebugSession(ctx context.Context, sessionID string, req StepDebugSessionRequest) (*DebuggerSessionRecord, error) {
	return c.Platform.StepDebugSession(ctx, sessionID, req)
}

func (c *Client) GetDebuggerCodelens(ctx context.Context, workspaceID string, workflowID string, filePath string) (*DebuggerCodelensResponse, error) {
	return c.Platform.GetDebuggerCodelens(ctx, workspaceID, workflowID, filePath)
}
