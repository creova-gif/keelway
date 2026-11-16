package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

type RenderAgentHookConfigRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	AgentHost   string `json:"agent_host,omitempty"`
	Mode        string `json:"mode,omitempty"`
}

type HookManifestResponse struct {
	WorkspaceID      string `json:"workspace_id"`
	AgentHost        string `json:"agent_host"`
	Mode             string `json:"mode"`
	TargetConfigPath string `json:"target_config_path"`
	HookEvent        string `json:"hook_event"`
	ConfigContent    string `json:"config_content"`
	CLIInstallHint   string `json:"cli_install_hint"`
	ConfigSHA256     string `json:"config_sha256"`
}

type InterceptAgentToolCallRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	AgentHost   string `json:"agent_host,omitempty"`
	ToolName    string `json:"tool_name,omitempty"`
	Command     string `json:"command,omitempty"`
	TicketID    string `json:"ticket_id,omitempty"`
}

type HarnessInterceptionRecord struct {
	InterceptionID  string  `json:"interception_id"`
	WorkspaceID     string  `json:"workspace_id"`
	AgentHost       string  `json:"agent_host"`
	ToolName        string  `json:"tool_name"`
	ScrubbedCommand string  `json:"scrubbed_command"`
	CommandSHA256   string  `json:"command_sha256"`
	Verdict         string  `json:"verdict"`
	ReasonCode      string  `json:"reason_code"`
	Explanation     string  `json:"explanation"`
	TicketID        *string `json:"ticket_id"`
	DLPRedactions   int     `json:"dlp_redactions"`
	EventSHA256     string  `json:"event_sha256"`
	CreatedAt       string  `json:"created_at"`
}

type ApprovalTicketRecord struct {
	TicketID        string  `json:"ticket_id"`
	WorkspaceID     string  `json:"workspace_id"`
	AgentHost       string  `json:"agent_host"`
	ToolName        string  `json:"tool_name"`
	ScrubbedCommand string  `json:"scrubbed_command"`
	CommandSHA256   string  `json:"command_sha256"`
	Status          string  `json:"status"`
	Reviewer        *string `json:"reviewer"`
	DecisionReason  *string `json:"decision_reason"`
	CreatedAt       string  `json:"created_at"`
	DecidedAt       *string `json:"decided_at"`
	ConsumedAt      *string `json:"consumed_at"`
	TicketSHA256    string  `json:"ticket_sha256"`
}

type ApprovalTicketListResponse struct {
	WorkspaceID string                 `json:"workspace_id"`
	Count       int                    `json:"count"`
	Tickets     []ApprovalTicketRecord `json:"tickets"`
}

type DecideHarnessTicketRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	Decision    string `json:"decision"`
	Reviewer    string `json:"reviewer,omitempty"`
	Reason      string `json:"reason,omitempty"`
}

type WorktreeCandidateInput struct {
	CandidateID    string  `json:"candidate_id"`
	WorktreeBranch string  `json:"worktree_branch"`
	ModelID        string  `json:"model_id"`
	ProviderTier   string  `json:"provider_tier"`
	TestsPassed    bool    `json:"tests_passed"`
	EvalScore      float64 `json:"eval_score"`
	CostUSD        float64 `json:"cost_usd"`
	DiffExcerpt    string  `json:"diff_excerpt,omitempty"`
}

type EvaluateWorktreeCiGateRequest struct {
	WorkspaceID  string                   `json:"workspace_id,omitempty"`
	WorkflowName string                   `json:"workflow_name,omitempty"`
	DiffSummary  string                   `json:"diff_summary,omitempty"`
	MinEvalScore float64                  `json:"min_eval_score,omitempty"`
	Candidates   []WorktreeCandidateInput `json:"candidates,omitempty"`
}

type WorktreeCiGateRunRecord struct {
	GateRunID         string                   `json:"gate_run_id"`
	WorkspaceID       string                   `json:"workspace_id"`
	WorkflowName      string                   `json:"workflow_name"`
	Status            string                   `json:"status"`
	MinEvalScore      float64                  `json:"min_eval_score"`
	WinnerCandidateID *string                  `json:"winner_candidate_id"`
	WinnerModel       *string                  `json:"winner_model"`
	CostSavedUSD      float64                  `json:"cost_saved_usd"`
	DLPRedactions     int                      `json:"dlp_redactions"`
	Candidates        []WorktreeCandidateInput `json:"candidates"`
	GateSHA256        string                   `json:"gate_sha256"`
	CreatedAt         string                   `json:"created_at"`
}

type WorktreeCiGateRunListResponse struct {
	WorkspaceID string                    `json:"workspace_id"`
	Count       int                       `json:"count"`
	Runs        []WorktreeCiGateRunRecord `json:"runs"`
}

func validateHarnessAgentHost(raw string) (string, error) {
	host := firstString(strings.TrimSpace(raw), "claude_code")
	if host != "claude_code" && host != "cursor" && host != "codex_cli" {
		return "", fmt.Errorf("keelway: invalid agent_host %q", host)
	}
	return host, nil
}

func buildHarnessListQuery(wsID string, limit int) (url.Values, error) {
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

func (p *PlatformService) RenderAgentHookConfig(ctx context.Context, req RenderAgentHookConfigRequest) (*HookManifestResponse, error) {
	host, err := validateHarnessAgentHost(req.AgentHost)
	if err != nil {
		return nil, err
	}
	mode := firstString(strings.TrimSpace(req.Mode), "enforce")
	if mode != "enforce" && mode != "audit_only" {
		return nil, fmt.Errorf("keelway: invalid mode %q", mode)
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.AgentHost = host
	req.Mode = mode
	return doPlatformJSON[HookManifestResponse](ctx, p.client, http.MethodPost, "/v1/platform/harness/hooks/render", nil, req)
}

func (p *PlatformService) InterceptAgentToolCall(ctx context.Context, req InterceptAgentToolCallRequest) (*HarnessInterceptionRecord, error) {
	host, err := validateHarnessAgentHost(req.AgentHost)
	if err != nil {
		return nil, err
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.AgentHost = host
	req.ToolName = firstString(strings.TrimSpace(req.ToolName), "Bash")
	req.Command = firstString(strings.TrimSpace(req.Command), "git push origin main")
	req.TicketID = strings.TrimSpace(req.TicketID)
	return doPlatformJSON[HarnessInterceptionRecord](ctx, p.client, http.MethodPost, "/v1/platform/harness/intercept", nil, req)
}

func (p *PlatformService) ListHarnessTickets(ctx context.Context, workspaceID string, status string, limit int) (*ApprovalTicketListResponse, error) {
	q, err := buildHarnessListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	if cleanStatus := strings.TrimSpace(status); cleanStatus != "" {
		if cleanStatus != "PENDING" && cleanStatus != "APPROVED" && cleanStatus != "DENIED" && cleanStatus != "CONSUMED" {
			return nil, fmt.Errorf("keelway: invalid ticket status %q", cleanStatus)
		}
		q.Set("status", cleanStatus)
	}
	return doPlatformJSON[ApprovalTicketListResponse](ctx, p.client, http.MethodGet, "/v1/platform/harness/tickets", q, nil)
}

func (p *PlatformService) DecideHarnessTicket(ctx context.Context, ticketID string, req DecideHarnessTicketRequest) (*ApprovalTicketRecord, error) {
	decision := firstString(strings.TrimSpace(req.Decision), "APPROVED")
	if decision != "APPROVED" && decision != "DENIED" {
		return nil, fmt.Errorf("keelway: invalid ticket decision %q", decision)
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.Decision = decision
	req.Reviewer = firstString(strings.TrimSpace(req.Reviewer), "lead-engineer")
	req.Reason = firstString(strings.TrimSpace(req.Reason), "Verified safe workspace scope")
	return doSegJSON[ApprovalTicketRecord](ctx, p.client, http.MethodPost, "/v1/platform/harness/tickets/", ticketID, "ticketID", "/decide", nil, req)
}

func (p *PlatformService) EvaluateWorktreeCiGate(ctx context.Context, req EvaluateWorktreeCiGateRequest) (*WorktreeCiGateRunRecord, error) {
	if req.MinEvalScore < 0.0 || req.MinEvalScore > 1.0 {
		return nil, fmt.Errorf("keelway: min_eval_score must be between 0.0 and 1.0")
	}
	if req.MinEvalScore == 0.0 {
		req.MinEvalScore = 0.85
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.WorkflowName = firstString(strings.TrimSpace(req.WorkflowName), "pr-worktree-arena")
	req.DiffSummary = firstString(strings.TrimSpace(req.DiffSummary), "Refactor retry backoff & add unit test in core/platform/")
	return doPlatformJSON[WorktreeCiGateRunRecord](ctx, p.client, http.MethodPost, "/v1/platform/harness/ci-gate/evaluate", nil, req)
}

func (p *PlatformService) ListWorktreeCiGateRuns(ctx context.Context, workspaceID string, limit int) (*WorktreeCiGateRunListResponse, error) {
	q, err := buildHarnessListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[WorktreeCiGateRunListResponse](ctx, p.client, http.MethodGet, "/v1/platform/harness/ci-gate/runs", q, nil)
}

func (c *Client) RenderAgentHookConfig(ctx context.Context, req RenderAgentHookConfigRequest) (*HookManifestResponse, error) {
	return c.Platform.RenderAgentHookConfig(ctx, req)
}
func (c *Client) InterceptAgentToolCall(ctx context.Context, req InterceptAgentToolCallRequest) (*HarnessInterceptionRecord, error) {
	return c.Platform.InterceptAgentToolCall(ctx, req)
}
func (c *Client) ListHarnessTickets(ctx context.Context, workspaceID string, status string, limit int) (*ApprovalTicketListResponse, error) {
	return c.Platform.ListHarnessTickets(ctx, workspaceID, status, limit)
}
func (c *Client) DecideHarnessTicket(ctx context.Context, ticketID string, req DecideHarnessTicketRequest) (*ApprovalTicketRecord, error) {
	return c.Platform.DecideHarnessTicket(ctx, ticketID, req)
}
func (c *Client) EvaluateWorktreeCiGate(ctx context.Context, req EvaluateWorktreeCiGateRequest) (*WorktreeCiGateRunRecord, error) {
	return c.Platform.EvaluateWorktreeCiGate(ctx, req)
}
func (c *Client) ListWorktreeCiGateRuns(ctx context.Context, workspaceID string, limit int) (*WorktreeCiGateRunListResponse, error) {
	return c.Platform.ListWorktreeCiGateRuns(ctx, workspaceID, limit)
}
