package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

func StringPtr(v string) *string {
	return &v
}

type SafetyWorkflowNodeInput struct {
	NodeID             string `json:"node_id"`
	Role               string `json:"role,omitempty"`
	ToolKind           string `json:"tool_kind,omitempty"`
	RequiresP10        *bool  `json:"requires_p10,omitempty"`
	MaxIterations      *int   `json:"max_iterations,omitempty"`
	DataClassification string `json:"data_classification,omitempty"`
}

type SafetyWorkflowEdgeInput struct {
	FromNode  string `json:"from_node"`
	ToNode    string `json:"to_node"`
	Condition string `json:"condition,omitempty"`
}

type VerifyWorkflowSafetyRequest struct {
	WorkspaceID     string                    `json:"workspace_id,omitempty"`
	WorkflowID      string                    `json:"workflow_id,omitempty"`
	WorkflowName    string                    `json:"workflow_name,omitempty"`
	Nodes           []SafetyWorkflowNodeInput `json:"nodes,omitempty"`
	Edges           []SafetyWorkflowEdgeInput `json:"edges,omitempty"`
	AirgapMode      bool                      `json:"airgap_mode"`
	InjectP10Guards bool                      `json:"inject_p10_guards"`
}

type SafetyInvariantCheck struct {
	InvariantID string `json:"invariant_id"`
	Passed      bool   `json:"passed"`
	Description string `json:"description"`
}

type SafetyViolation struct {
	InvariantID        string   `json:"invariant_id"`
	Severity           string   `json:"severity"`
	OffendingNode      string   `json:"offending_node"`
	CounterexamplePath []string `json:"counterexample_path"`
	Remediation        string   `json:"remediation"`
}

type SafetyVerificationRecord struct {
	VerificationID    string                 `json:"verification_id"`
	WorkspaceID       string                 `json:"workspace_id"`
	WorkflowID        string                 `json:"workflow_id"`
	WorkflowName      string                 `json:"workflow_name"`
	Status            string                 `json:"status"`
	StatesExplored    int                    `json:"states_explored"`
	InvariantsChecked []SafetyInvariantCheck `json:"invariants_checked"`
	Violations        []SafetyViolation      `json:"violations"`
	P10GuardsInjected []string               `json:"p10_guards_injected"`
	DLPRedactions     int                    `json:"dlp_redactions"`
	ProofSHA256       string                 `json:"proof_sha256"`
	CreatedAt         string                 `json:"created_at"`
}

type SafetyVerificationListResponse struct {
	WorkspaceID   string                     `json:"workspace_id"`
	Count         int                        `json:"count"`
	Verifications []SafetyVerificationRecord `json:"verifications"`
}

type RegisterMeshNodeRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	NodeID      string `json:"node_id,omitempty"`
	Name        string `json:"name"`
	Tier        string `json:"tier,omitempty"`
	HardwareHAL string `json:"hardware_hal,omitempty"`
	Region      string `json:"region,omitempty"`
	VRAMGB      int    `json:"vram_gb,omitempty"`
	Status      string `json:"status,omitempty"`
}

type MeshNodeRecord struct {
	NodeID            string `json:"node_id"`
	WorkspaceID       string `json:"workspace_id"`
	Name              string `json:"name"`
	Tier              string `json:"tier"`
	HardwareHAL       string `json:"hardware_hal"`
	Region            string `json:"region"`
	VRAMGB            int    `json:"vram_gb"`
	Status            string `json:"status"`
	AttestationSHA256 string `json:"attestation_sha256"`
	RegisteredAt      string `json:"registered_at"`
}

type MeshNodeListResponse struct {
	WorkspaceID string           `json:"workspace_id"`
	Count       int              `json:"count"`
	Nodes       []MeshNodeRecord `json:"nodes"`
}

type DispatchMeshHandoffRequest struct {
	WorkspaceID         string `json:"workspace_id,omitempty"`
	WorkflowName        string `json:"workflow_name,omitempty"`
	TaskSummary         string `json:"task_summary,omitempty"`
	DataClassification  string `json:"data_classification,omitempty"`
	AllowSanitizedBurst *bool  `json:"allow_sanitized_burst,omitempty"`
	ForceRawCloudBurst  bool   `json:"force_raw_cloud_burst"`
}

type MeshStageExecution struct {
	StageName        string  `json:"stage_name"`
	TargetTier       string  `json:"target_tier"`
	NodeID           string  `json:"node_id"`
	ModelID          string  `json:"model_id"`
	HardwareHAL      string  `json:"hardware_hal"`
	ZeroRawPIIEgress bool    `json:"zero_raw_pii_egress"`
	CostUSD          float64 `json:"cost_usd"`
}

type MeshHandoffRecord struct {
	HandoffID          string               `json:"handoff_id"`
	WorkspaceID        string               `json:"workspace_id"`
	WorkflowName       string               `json:"workflow_name"`
	DataClassification string               `json:"data_classification"`
	Status             string               `json:"status"`
	EdgeNodeID         string               `json:"edge_node_id"`
	BurstNodeID        *string              `json:"burst_node_id"`
	Stages             []MeshStageExecution `json:"stages"`
	TotalCostUSD       float64              `json:"total_cost_usd"`
	DLPRedactions      int                  `json:"dlp_redactions"`
	AttestationSHA256  string               `json:"attestation_sha256"`
	CreatedAt          string               `json:"created_at"`
}

type MeshHandoffListResponse struct {
	WorkspaceID string              `json:"workspace_id"`
	Count       int                 `json:"count"`
	Handoffs    []MeshHandoffRecord `json:"handoffs"`
}

func buildSafetyMeshListQuery(wsID string, limit int) (url.Values, error) {
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

func (p *PlatformService) VerifyWorkflowSafety(ctx context.Context, req VerifyWorkflowSafetyRequest) (*SafetyVerificationRecord, error) {
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.WorkflowID = firstString(strings.TrimSpace(req.WorkflowID), "WF-TREASURY-01")
	req.WorkflowName = firstString(strings.TrimSpace(req.WorkflowName), "treasury-wire-approver")
	return doPlatformJSON[SafetyVerificationRecord](ctx, p.client, http.MethodPost, "/v1/platform/safety/verify", nil, req)
}

func (p *PlatformService) ListSafetyVerifications(ctx context.Context, workspaceID string, limit int) (*SafetyVerificationListResponse, error) {
	q, err := buildSafetyMeshListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[SafetyVerificationListResponse](ctx, p.client, http.MethodGet, "/v1/platform/safety/verifications", q, nil)
}

func (p *PlatformService) RegisterMeshNode(ctx context.Context, req RegisterMeshNodeRequest) (*MeshNodeRecord, error) {
	cleanName := strings.TrimSpace(req.Name)
	if cleanName == "" {
		return nil, fmt.Errorf("keelway: name must be non-empty")
	}
	tier := firstString(strings.TrimSpace(req.Tier), "edge_local")
	if tier != "edge_local" && tier != "cluster_burst" {
		return nil, fmt.Errorf("keelway: invalid tier %q", tier)
	}
	hal := firstString(strings.TrimSpace(req.HardwareHAL), "apple_metal_secure_enclave")
	if hal != "apple_metal_secure_enclave" && hal != "nvidia_h100_cc" && hal != "linux_tpm2" {
		return nil, fmt.Errorf("keelway: invalid hardware_hal %q", hal)
	}
	status := firstString(strings.TrimSpace(req.Status), "ONLINE")
	if status != "ONLINE" && status != "DRAINING" {
		return nil, fmt.Errorf("keelway: invalid status %q", status)
	}
	if req.VRAMGB < 0 {
		return nil, fmt.Errorf("keelway: vram_gb must be >= 1")
	}
	if req.VRAMGB == 0 {
		req.VRAMGB = 32
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.NodeID = strings.TrimSpace(req.NodeID)
	req.Name = cleanName
	req.Tier = tier
	req.HardwareHAL = hal
	req.Region = firstString(strings.TrimSpace(req.Region), "local-loopback")
	req.Status = status
	return doPlatformJSON[MeshNodeRecord](ctx, p.client, http.MethodPost, "/v1/platform/mesh/nodes", nil, req)
}

func (p *PlatformService) ListMeshNodes(ctx context.Context, workspaceID string) (*MeshNodeListResponse, error) {
	return doPlatformJSON[MeshNodeListResponse](ctx, p.client, http.MethodGet, "/v1/platform/mesh/nodes", wsQuery(workspaceID), nil)
}

func (p *PlatformService) DispatchMeshHandoff(ctx context.Context, req DispatchMeshHandoffRequest) (*MeshHandoffRecord, error) {
	cls := firstString(strings.TrimSpace(req.DataClassification), "restricted_pii")
	if cls != "public" && cls != "internal" && cls != "restricted_pii" {
		return nil, fmt.Errorf("keelway: invalid data_classification %q", cls)
	}
	allowBurst := true
	if req.AllowSanitizedBurst != nil {
		allowBurst = *req.AllowSanitizedBurst
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.WorkflowName = firstString(strings.TrimSpace(req.WorkflowName), "clinical-synthesis-pipeline")
	req.TaskSummary = firstString(strings.TrimSpace(req.TaskSummary), "Ingest patient intake & synthesize anonymized cohort summary")
	req.DataClassification = cls
	req.AllowSanitizedBurst = &allowBurst
	return doPlatformJSON[MeshHandoffRecord](ctx, p.client, http.MethodPost, "/v1/platform/mesh/dispatch", nil, req)
}

func (p *PlatformService) ListMeshHandoffs(ctx context.Context, workspaceID string, limit int) (*MeshHandoffListResponse, error) {
	q, err := buildSafetyMeshListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[MeshHandoffListResponse](ctx, p.client, http.MethodGet, "/v1/platform/mesh/handoffs", q, nil)
}

func (c *Client) VerifyWorkflowSafety(ctx context.Context, req VerifyWorkflowSafetyRequest) (*SafetyVerificationRecord, error) {
	return c.Platform.VerifyWorkflowSafety(ctx, req)
}
func (c *Client) ListSafetyVerifications(ctx context.Context, workspaceID string, limit int) (*SafetyVerificationListResponse, error) {
	return c.Platform.ListSafetyVerifications(ctx, workspaceID, limit)
}
func (c *Client) RegisterMeshNode(ctx context.Context, req RegisterMeshNodeRequest) (*MeshNodeRecord, error) {
	return c.Platform.RegisterMeshNode(ctx, req)
}
func (c *Client) ListMeshNodes(ctx context.Context, workspaceID string) (*MeshNodeListResponse, error) {
	return c.Platform.ListMeshNodes(ctx, workspaceID)
}
func (c *Client) DispatchMeshHandoff(ctx context.Context, req DispatchMeshHandoffRequest) (*MeshHandoffRecord, error) {
	return c.Platform.DispatchMeshHandoff(ctx, req)
}
func (c *Client) ListMeshHandoffs(ctx context.Context, workspaceID string, limit int) (*MeshHandoffListResponse, error) {
	return c.Platform.ListMeshHandoffs(ctx, workspaceID, limit)
}
