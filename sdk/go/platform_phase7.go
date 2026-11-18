package keelway

import (
	"context"
	"net/http"
)

type McpServerRegisterRequest struct {
	ID           string   `json:"id"`
	Name         string   `json:"name"`
	Transport    string   `json:"transport"`
	Endpoint     string   `json:"endpoint"`
	WorkspaceID  string   `json:"workspace_id,omitempty"`
	AllowedTools []string `json:"allowed_tools,omitempty"`
}

type McpServerRecord struct {
	ID              string   `json:"id"`
	Name            string   `json:"name"`
	Transport       string   `json:"transport"`
	Endpoint        string   `json:"endpoint,omitempty"`
	WorkspaceID     string   `json:"workspace_id,omitempty"`
	Builtin         bool     `json:"builtin,omitempty"`
	Status          string   `json:"status,omitempty"`
	ToolsCount      int      `json:"tools_count,omitempty"`
	AllowedTools    []string `json:"allowed_tools,omitempty"`
	ProtocolVersion string   `json:"protocol_version,omitempty"`
	CreatedAt       string   `json:"created_at,omitempty"`
}

type McpServerList struct {
	WorkspaceID     string            `json:"workspace_id,omitempty"`
	ProtocolVersion string            `json:"protocol_version,omitempty"`
	Count           int               `json:"count,omitempty"`
	Total           int               `json:"total,omitempty"`
	Servers         []McpServerRecord `json:"servers"`
}

type McpServerDeleteResult struct {
	Deleted     bool   `json:"deleted"`
	ID          string `json:"id,omitempty"`
	ServerID    string `json:"server_id,omitempty"`
	WorkspaceID string `json:"workspace_id,omitempty"`
}

type McpToolDescriptor struct {
	Name        string         `json:"name"`
	ServerID    string         `json:"server_id,omitempty"`
	Description string         `json:"description,omitempty"`
	InputSchema map[string]any `json:"inputSchema,omitempty"`
	Mutating    bool           `json:"mutating,omitempty"`
	Builtin     bool           `json:"builtin,omitempty"`
}

type McpToolList struct {
	WorkspaceID     string              `json:"workspace_id,omitempty"`
	ProtocolVersion string              `json:"protocol_version,omitempty"`
	Count           int                 `json:"count,omitempty"`
	Total           int                 `json:"total,omitempty"`
	Tools           []McpToolDescriptor `json:"tools"`
}

type McpToolCallRequest struct {
	ToolName    string         `json:"tool_name"`
	Arguments   map[string]any `json:"arguments,omitempty"`
	WorkspaceID string         `json:"workspace_id,omitempty"`
}

type McpToolCallResult struct {
	OK              bool    `json:"ok"`
	WorkspaceID     string  `json:"workspace_id,omitempty"`
	ToolName        string  `json:"tool_name"`
	ProtocolVersion string  `json:"protocol_version,omitempty"`
	Redacted        bool    `json:"redacted,omitempty"`
	DurationMS      float64 `json:"duration_ms,omitempty"`
	Result          any     `json:"result,omitempty"`
	ReceiptSHA256   string  `json:"receipt_sha256,omitempty"`
}

type GoldenEvalRunRequest struct {
	Category    string `json:"category,omitempty"`
	WorkspaceID string `json:"workspace_id,omitempty"`
}

type GoldenEvalCaseResult struct {
	ID         string  `json:"id"`
	Category   string  `json:"category"`
	Title      string  `json:"title,omitempty"`
	Passed     bool    `json:"passed"`
	DurationMS float64 `json:"duration_ms,omitempty"`
	Evidence   string  `json:"evidence,omitempty"`
}

type GoldenEvalCategorySummary struct {
	Total    int     `json:"total"`
	Passed   int     `json:"passed"`
	Failed   int     `json:"failed"`
	PassRate float64 `json:"pass_rate"`
}

type GoldenEvalReport struct {
	EvalRunID     string                               `json:"eval_run_id"`
	WorkspaceID   string                               `json:"workspace_id,omitempty"`
	Category      string                               `json:"category"`
	TotalCases    int                                  `json:"total_cases"`
	PassedCases   int                                  `json:"passed_cases"`
	FailedCases   int                                  `json:"failed_cases"`
	PassRate      float64                              `json:"pass_rate"`
	DurationMS    float64                              `json:"duration_ms,omitempty"`
	Categories    map[string]GoldenEvalCategorySummary `json:"categories,omitempty"`
	Cases         []GoldenEvalCaseResult               `json:"cases,omitempty"`
	ReceiptSHA256 string                               `json:"receipt_sha256,omitempty"`
	CreatedAt     string                               `json:"created_at,omitempty"`
}

type LatestGoldenEvalsResponse struct {
	WorkspaceID string            `json:"workspace_id"`
	HasRun      bool              `json:"has_run"`
	Latest      *GoldenEvalReport `json:"latest"`
}

func (p *PlatformService) ListMcpServers(ctx context.Context, workspaceID string) (*McpServerList, error) {
	return doPlatformJSON[McpServerList](ctx, p.client, http.MethodGet, "/v1/platform/mcp/servers", wsQuery(workspaceID), nil)
}

func (p *PlatformService) RegisterMcpServer(ctx context.Context, req McpServerRegisterRequest) (*McpServerRecord, error) {
	body := map[string]any{
		"id":           req.ID,
		"name":         req.Name,
		"transport":    req.Transport,
		"endpoint":     req.Endpoint,
		"workspace_id": firstString(req.WorkspaceID, "default"),
	}
	if req.AllowedTools != nil {
		body["allowed_tools"] = req.AllowedTools
	}
	return doPlatformJSON[McpServerRecord](ctx, p.client, http.MethodPost, "/v1/platform/mcp/servers", nil, body)
}

func (p *PlatformService) DeleteMcpServer(ctx context.Context, serverID, workspaceID string) (*McpServerDeleteResult, error) {
	return doSegJSON[McpServerDeleteResult](ctx, p.client, http.MethodDelete, "/v1/platform/mcp/servers/", serverID, "serverID", "", wsQuery(workspaceID), nil)
}

func (p *PlatformService) ListMcpTools(ctx context.Context, workspaceID string) (*McpToolList, error) {
	return doPlatformJSON[McpToolList](ctx, p.client, http.MethodGet, "/v1/platform/mcp/tools", wsQuery(workspaceID), nil)
}

func (p *PlatformService) CallMcpTool(ctx context.Context, req McpToolCallRequest) (*McpToolCallResult, error) {
	args := req.Arguments
	if args == nil {
		args = map[string]any{}
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"tool_name":    req.ToolName,
		"arguments":    args,
	}
	return doPlatformJSON[McpToolCallResult](ctx, p.client, http.MethodPost, "/v1/platform/mcp/call", nil, body)
}

func (p *PlatformService) RunGoldenEvals(ctx context.Context, req GoldenEvalRunRequest) (*GoldenEvalReport, error) {
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"category":     firstString(req.Category, "all"),
	}
	return doPlatformJSON[GoldenEvalReport](ctx, p.client, http.MethodPost, "/v1/platform/evals/golden", nil, body)
}

func (p *PlatformService) GetLatestGoldenEvals(ctx context.Context, workspaceID string) (*LatestGoldenEvalsResponse, error) {
	return doPlatformJSON[LatestGoldenEvalsResponse](ctx, p.client, http.MethodGet, "/v1/platform/evals/latest", wsQuery(workspaceID), nil)
}
