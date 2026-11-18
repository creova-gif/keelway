package keelway

import (
	"context"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

type KflowDagExecuteRequest struct {
	WorkflowID      string           `json:"workflow_id"`
	Nodes           []map[string]any `json:"nodes,omitempty"`
	Trigger         string           `json:"trigger,omitempty"`
	TokenBudget     int              `json:"token_budget,omitempty"`
	ApprovedNodeIDs []string         `json:"approved_node_ids,omitempty"`
	WorkspaceID     string           `json:"workspace_id,omitempty"`
}

type KflowNodeResult struct {
	ID              string   `json:"id"`
	Label           string   `json:"label,omitempty"`
	AgentID         string   `json:"agent_id,omitempty"`
	DependsOn       []string `json:"depends_on,omitempty"`
	RequiresP10     bool     `json:"requires_p10,omitempty"`
	Wave            int      `json:"wave,omitempty"`
	Status          string   `json:"status"`
	Tokens          int      `json:"tokens,omitempty"`
	UpstreamDigests []string `json:"upstream_digests,omitempty"`
	OutputDigest    string   `json:"output_digest,omitempty"`
	ErrorDetail     string   `json:"error_detail,omitempty"`
}

type KflowRunReceipt struct {
	RunID            string            `json:"run_id"`
	WorkspaceID      string            `json:"workspace_id,omitempty"`
	WorkflowID       string            `json:"workflow_id"`
	Trigger          string            `json:"trigger,omitempty"`
	Status           string            `json:"status"`
	HeldNodeID       string            `json:"held_node_id,omitempty"`
	TopologicalOrder []string          `json:"topological_order,omitempty"`
	Waves            [][]string        `json:"waves,omitempty"`
	Nodes            []KflowNodeResult `json:"nodes,omitempty"`
	TokensUsed       int               `json:"tokens_used,omitempty"`
	TokenBudget      int               `json:"token_budget,omitempty"`
	ReceiptSHA256    string            `json:"receipt_sha256,omitempty"`
	CreatedAt        string            `json:"created_at,omitempty"`
}

type KflowRunListParams struct {
	WorkspaceID string
	WorkflowID  string
	Limit       int
}

type KflowRunList struct {
	WorkspaceID string            `json:"workspace_id,omitempty"`
	Count       int               `json:"count,omitempty"`
	Runs        []KflowRunReceipt `json:"runs"`
}

type KspacesCrdtOperation struct {
	Namespace string `json:"namespace,omitempty"`
	Key       string `json:"key"`
	Value     any    `json:"value,omitempty"`
	Op        string `json:"op,omitempty"`
	LamportTS int64  `json:"lamport_ts,omitempty"`
}

type KspacesCrdtEntry struct {
	Namespace string `json:"namespace"`
	Key       string `json:"key"`
	Value     any    `json:"value"`
	LamportTS int64  `json:"lamport_ts"`
	PeerID    string `json:"peer_id"`
	Tombstone bool   `json:"tombstone"`
}

type KspacesCrdtSyncRequest struct {
	WorkspaceID string                 `json:"workspace_id,omitempty"`
	PeerID      string                 `json:"peer_id"`
	Operations  []KspacesCrdtOperation `json:"operations"`
}

type KspacesStateResponse struct {
	WorkspaceID       string             `json:"workspace_id"`
	VectorClock       map[string]int64   `json:"vector_clock,omitempty"`
	StateDigestSHA256 string             `json:"state_digest_sha256"`
	ActiveKeysCount   int                `json:"active_keys_count"`
	Entries           []KspacesCrdtEntry `json:"entries"`
}

type KspacesSyncResult struct {
	KspacesStateResponse
	PeerID       string `json:"peer_id"`
	AppliedCount int    `json:"applied_count"`
}

type PlatformSbomResponse struct {
	WorkspaceID         string         `json:"workspace_id,omitempty"`
	Verified            bool           `json:"verified"`
	VerificationStatus  string         `json:"verification_status,omitempty"`
	SerialNumber        string         `json:"serial_number,omitempty"`
	BomFormat           string         `json:"bom_format"`
	SpecVersion         string         `json:"spec_version"`
	ComponentCount      int            `json:"component_count,omitempty"`
	RootDigestSHA256    string         `json:"root_digest_sha256"`
	ProvenanceSignature string         `json:"provenance_signature"`
	Manifest            map[string]any `json:"manifest,omitempty"`
}

func (p *PlatformService) ExecuteKflowDag(ctx context.Context, req KflowDagExecuteRequest) (*KflowRunReceipt, error) {
	nodes := req.Nodes
	if nodes == nil {
		nodes = []map[string]any{}
	}
	approved := req.ApprovedNodeIDs
	if approved == nil {
		approved = []string{}
	}
	budget := req.TokenBudget
	if budget <= 0 {
		budget = 25000
	}
	body := map[string]any{
		"workspace_id":      firstString(req.WorkspaceID, "default"),
		"workflow_id":       req.WorkflowID,
		"nodes":             nodes,
		"trigger":           firstString(req.Trigger, "manual"),
		"token_budget":      budget,
		"approved_node_ids": approved,
	}
	return doPlatformJSON[KflowRunReceipt](ctx, p.client, http.MethodPost, "/v1/platform/automation/workflows/execute", nil, body)
}

func (p *PlatformService) ListKflowRuns(ctx context.Context, params KflowRunListParams) (*KflowRunList, error) {
	q := wsQuery(params.WorkspaceID)
	if wf := strings.TrimSpace(params.WorkflowID); wf != "" {
		q.Set("workflow_id", wf)
	}
	if params.Limit > 0 {
		q.Set("limit", strconv.Itoa(params.Limit))
	}
	return doPlatformJSON[KflowRunList](ctx, p.client, http.MethodGet, "/v1/platform/automation/runs", q, nil)
}

func (p *PlatformService) SyncKspacesCrdt(ctx context.Context, req KspacesCrdtSyncRequest) (*KspacesSyncResult, error) {
	ops := req.Operations
	if ops == nil {
		ops = []KspacesCrdtOperation{}
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"peer_id":      req.PeerID,
		"operations":   ops,
	}
	return doPlatformJSON[KspacesSyncResult](ctx, p.client, http.MethodPost, "/v1/platform/kspaces/sync", nil, body)
}

func (p *PlatformService) GetKspacesState(ctx context.Context, workspaceID, namespace string) (*KspacesStateResponse, error) {
	q := wsQuery(workspaceID)
	if ns := strings.TrimSpace(namespace); ns != "" {
		q.Set("namespace", ns)
	}
	return doPlatformJSON[KspacesStateResponse](ctx, p.client, http.MethodGet, "/v1/platform/kspaces/state", q, nil)
}

func (p *PlatformService) GetPlatformSbom(ctx context.Context, workspaceID string) (*PlatformSbomResponse, error) {
	q := url.Values{"workspace_id": {firstString(workspaceID, "default")}}
	return doPlatformJSON[PlatformSbomResponse](ctx, p.client, http.MethodGet, "/v1/platform/security/sbom", q, nil)
}
