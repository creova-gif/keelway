package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

const defaultToolSchemaJSON = `{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}`

type McpLockToolSpec struct {
	ServerID        string `json:"server_id"`
	ToolName        string `json:"tool_name"`
	Version         string `json:"version,omitempty"`
	Description     string `json:"description"`
	InputSchemaJSON string `json:"input_schema_json,omitempty"`
}

type McpPinnedToolEntry struct {
	ServerID        string `json:"server_id"`
	ToolName        string `json:"tool_name"`
	Version         string `json:"version"`
	Description     string `json:"description"`
	InputSchemaJSON string `json:"input_schema_json"`
	ToolSHA256      string `json:"tool_sha256"`
}

type PinMcpLockfileRequest struct {
	WorkspaceID  string            `json:"workspace_id,omitempty"`
	LockfileName string            `json:"lockfile_name,omitempty"`
	Tools        []McpLockToolSpec `json:"tools,omitempty"`
}

type McpLockfileRecord struct {
	LockfileID       *string              `json:"lockfile_id"`
	WorkspaceID      string               `json:"workspace_id"`
	LockfileName     string               `json:"lockfile_name"`
	SchemaVersion    string               `json:"schema_version"`
	Status           string               `json:"status"`
	ToolCount        int                  `json:"tool_count"`
	MerkleRootSHA256 string               `json:"merkle_root_sha256"`
	Tools            []McpPinnedToolEntry `json:"tools"`
	Findings         []string             `json:"findings"`
	DLPRedactions    int                  `json:"dlp_redactions"`
	LockfileJSON     string               `json:"lockfile_json"`
	CreatedAt        string               `json:"created_at"`
}

type McpLockfileListResponse struct {
	WorkspaceID string              `json:"workspace_id"`
	Count       int                 `json:"count"`
	Lockfiles   []McpLockfileRecord `json:"lockfiles"`
}

type VerifyMcpLockfileRequest struct {
	WorkspaceID  string            `json:"workspace_id,omitempty"`
	LockfileID   *string           `json:"lockfile_id,omitempty"`
	LiveTools    []McpLockToolSpec `json:"live_tools,omitempty"`
	SimulateMode string            `json:"simulate_mode,omitempty"`
}

type McpLockVerificationRecord struct {
	VerificationID           string   `json:"verification_id"`
	LockfileID               string   `json:"lockfile_id"`
	WorkspaceID              string   `json:"workspace_id"`
	Verdict                  string   `json:"verdict"`
	ExpectedMerkleRootSHA256 string   `json:"expected_merkle_root_sha256"`
	ObservedMerkleRootSHA256 string   `json:"observed_merkle_root_sha256"`
	DriftedTools             []string `json:"drifted_tools"`
	PoisoningFindings        []string `json:"poisoning_findings"`
	DLPRedactions            int      `json:"dlp_redactions"`
	VerificationSHA256       string   `json:"verification_sha256"`
	VerifiedAt               string   `json:"verified_at"`
}

type McpLockVerificationListResponse struct {
	WorkspaceID   string                      `json:"workspace_id"`
	Count         int                         `json:"count"`
	Verifications []McpLockVerificationRecord `json:"verifications"`
}

type ConformanceScenarioInput struct {
	ScenarioID         string  `json:"scenario_id"`
	SchemaValid        bool    `json:"schema_valid"`
	DeterministicMatch bool    `json:"deterministic_match"`
	LatencyMS          int     `json:"latency_ms"`
	FrontierCostUSD    float64 `json:"frontier_cost_usd,omitempty"`
}

type RunConformanceBenchmarkRequest struct {
	WorkspaceID         string                     `json:"workspace_id,omitempty"`
	TargetID            string                     `json:"target_id,omitempty"`
	TargetKind          string                     `json:"target_kind,omitempty"`
	ModelID             string                     `json:"model_id,omitempty"`
	LatencyBudgetMS     int                        `json:"latency_budget_ms,omitempty"`
	MinConformanceScore float64                    `json:"min_conformance_score,omitempty"`
	Scenarios           []ConformanceScenarioInput `json:"scenarios,omitempty"`
}

type ConformanceBenchmarkRecord struct {
	BenchmarkID          string  `json:"benchmark_id"`
	WorkspaceID          string  `json:"workspace_id"`
	TargetID             string  `json:"target_id"`
	TargetKind           string  `json:"target_kind"`
	ModelID              string  `json:"model_id"`
	Verdict              string  `json:"verdict"`
	ScenarioCount        int     `json:"scenario_count"`
	ConformanceScore     float64 `json:"conformance_score"`
	MinConformanceScore  float64 `json:"min_conformance_score"`
	P95LatencyMS         int     `json:"p95_latency_ms"`
	LatencyBudgetMS      int     `json:"latency_budget_ms"`
	FrontierCostSavedUSD float64 `json:"frontier_cost_saved_usd"`
	CertSHA256           string  `json:"cert_sha256"`
	CreatedAt            string  `json:"created_at"`
}

type ConformanceBenchmarkListResponse struct {
	WorkspaceID string                       `json:"workspace_id"`
	Count       int                          `json:"count"`
	Runs        []ConformanceBenchmarkRecord `json:"runs"`
}

func buildSupplyChainListQuery(wsID string, limit int) (url.Values, error) {
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

func normalizeGoTools(tools []McpLockToolSpec) ([]McpLockToolSpec, error) {
	if len(tools) == 0 {
		return nil, nil
	}
	out := make([]McpLockToolSpec, len(tools))
	for i, t := range tools {
		srv, name := strings.TrimSpace(t.ServerID), strings.TrimSpace(t.ToolName)
		if srv == "" || name == "" || t.Description == "" {
			return nil, fmt.Errorf("keelway: tool server_id, tool_name, and description must be non-empty")
		}
		schema := t.InputSchemaJSON
		if schema == "" {
			schema = defaultToolSchemaJSON
		}
		out[i] = McpLockToolSpec{
			ServerID: srv, ToolName: name, Version: firstString(strings.TrimSpace(t.Version), "1.0.0"),
			Description: t.Description, InputSchemaJSON: schema,
		}
	}
	return out, nil
}

func (p *PlatformService) PinMcpLockfile(ctx context.Context, req PinMcpLockfileRequest) (*McpLockfileRecord, error) {
	tools, err := normalizeGoTools(req.Tools)
	if err != nil {
		return nil, err
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.LockfileName = firstString(strings.TrimSpace(req.LockfileName), "keelway.lock.json")
	req.Tools = tools
	return doPlatformJSON[McpLockfileRecord](ctx, p.client, http.MethodPost, "/v1/platform/supply-chain/lock/pin", nil, req)
}

func (p *PlatformService) ListMcpLockfiles(ctx context.Context, workspaceID string, limit int) (*McpLockfileListResponse, error) {
	q, err := buildSupplyChainListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[McpLockfileListResponse](ctx, p.client, http.MethodGet, "/v1/platform/supply-chain/lock/snapshots", q, nil)
}

func (p *PlatformService) VerifyMcpLockfile(ctx context.Context, req VerifyMcpLockfileRequest) (*McpLockVerificationRecord, error) {
	mode := firstString(strings.TrimSpace(req.SimulateMode), "clean")
	if mode != "clean" && mode != "rug_pull" && mode != "poisoning" {
		return nil, fmt.Errorf("keelway: invalid simulate_mode %q", mode)
	}
	live, err := normalizeGoTools(req.LiveTools)
	if err != nil {
		return nil, err
	}
	req.WorkspaceID, req.SimulateMode, req.LiveTools = firstString(strings.TrimSpace(req.WorkspaceID), "default"), mode, live
	return doPlatformJSON[McpLockVerificationRecord](ctx, p.client, http.MethodPost, "/v1/platform/supply-chain/lock/verify", nil, req)
}

func (p *PlatformService) ListMcpLockVerifications(ctx context.Context, workspaceID string, limit int) (*McpLockVerificationListResponse, error) {
	q, err := buildSupplyChainListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[McpLockVerificationListResponse](ctx, p.client, http.MethodGet, "/v1/platform/supply-chain/lock/verifications", q, nil)
}

func (p *PlatformService) RunConformanceBenchmark(ctx context.Context, req RunConformanceBenchmarkRequest) (*ConformanceBenchmarkRecord, error) {
	kind := firstString(strings.TrimSpace(req.TargetKind), "mcp_server")
	if kind != "mcp_server" && kind != "skill_package" && kind != "opencore_model" {
		return nil, fmt.Errorf("keelway: invalid target_kind %q", kind)
	}
	if req.LatencyBudgetMS < 0 || req.MinConformanceScore < 0.0 || req.MinConformanceScore > 1.0 {
		return nil, fmt.Errorf("keelway: invalid benchmark budget or conformance score threshold")
	}
	if req.LatencyBudgetMS == 0 {
		req.LatencyBudgetMS = 250
	}
	if req.MinConformanceScore == 0.0 {
		req.MinConformanceScore = 0.90
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.TargetID = firstString(strings.TrimSpace(req.TargetID), "mcp-git-local")
	req.TargetKind, req.ModelID = kind, firstString(strings.TrimSpace(req.ModelID), "keelway-core:7b")
	return doPlatformJSON[ConformanceBenchmarkRecord](ctx, p.client, http.MethodPost, "/v1/platform/supply-chain/bench/run", nil, req)
}

func (p *PlatformService) ListConformanceBenchmarks(ctx context.Context, workspaceID string, limit int) (*ConformanceBenchmarkListResponse, error) {
	q, err := buildSupplyChainListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[ConformanceBenchmarkListResponse](ctx, p.client, http.MethodGet, "/v1/platform/supply-chain/bench/runs", q, nil)
}

func (c *Client) PinMcpLockfile(ctx context.Context, req PinMcpLockfileRequest) (*McpLockfileRecord, error) {
	return c.Platform.PinMcpLockfile(ctx, req)
}
func (c *Client) ListMcpLockfiles(ctx context.Context, workspaceID string, limit int) (*McpLockfileListResponse, error) {
	return c.Platform.ListMcpLockfiles(ctx, workspaceID, limit)
}
func (c *Client) VerifyMcpLockfile(ctx context.Context, req VerifyMcpLockfileRequest) (*McpLockVerificationRecord, error) {
	return c.Platform.VerifyMcpLockfile(ctx, req)
}
func (c *Client) ListMcpLockVerifications(ctx context.Context, workspaceID string, limit int) (*McpLockVerificationListResponse, error) {
	return c.Platform.ListMcpLockVerifications(ctx, workspaceID, limit)
}
func (c *Client) RunConformanceBenchmark(ctx context.Context, req RunConformanceBenchmarkRequest) (*ConformanceBenchmarkRecord, error) {
	return c.Platform.RunConformanceBenchmark(ctx, req)
}
func (c *Client) ListConformanceBenchmarks(ctx context.Context, workspaceID string, limit int) (*ConformanceBenchmarkListResponse, error) {
	return c.Platform.ListConformanceBenchmarks(ctx, workspaceID, limit)
}
