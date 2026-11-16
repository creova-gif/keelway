package keelway

import (
	"context"
	"net/http"
	"strconv"
)

type OIDCProviderConfigRequest struct {
	WorkspaceID      string            `json:"workspace_id,omitempty"`
	IssuerURL        string            `json:"issuer_url"`
	ClientID         string            `json:"client_id"`
	SigningSecret    string            `json:"signing_secret,omitempty"`
	GroupRoleMapping map[string]string `json:"group_role_mapping,omitempty"`
	Enabled          bool              `json:"enabled"`
}

type OIDCProviderConfigResponse struct {
	WorkspaceID              string            `json:"workspace_id"`
	IssuerURL                string            `json:"issuer_url"`
	ClientID                 string            `json:"client_id"`
	Enabled                  bool              `json:"enabled"`
	SigningSecretConfigured  bool              `json:"signing_secret_configured"`
	SigningSecretFingerprint string            `json:"signing_secret_fingerprint,omitempty"`
	GroupRoleMapping         map[string]string `json:"group_role_mapping"`
	UpdatedAt                string            `json:"updated_at,omitempty"`
}

type SCIMUserResource struct {
	Schemas     []string `json:"schemas"`
	ID          string   `json:"id"`
	UserName    string   `json:"userName"`
	DisplayName string   `json:"displayName,omitempty"`
	Active      bool     `json:"active"`
	Groups      []string `json:"groups"`
	MappedRole  string   `json:"mapped_role"`
	UpdatedAt   string   `json:"updated_at,omitempty"`
}

type SCIMUserListResponse struct {
	Schemas      []string           `json:"schemas"`
	WorkspaceID  string             `json:"workspace_id"`
	TotalResults int                `json:"totalResults"`
	Resources    []SCIMUserResource `json:"Resources"`
}

type SCIMUserProvisionRequest struct {
	WorkspaceID string   `json:"workspace_id,omitempty"`
	UserName    string   `json:"userName"`
	DisplayName string   `json:"displayName,omitempty"`
	Groups      []string `json:"groups,omitempty"`
	Active      bool     `json:"active"`
}

type P10QuorumApproveRequest struct {
	WorkspaceID       string `json:"workspace_id,omitempty"`
	ProposalID        string `json:"proposal_id"`
	ApproverID        string `json:"approver_id"`
	InitiatorID       string `json:"initiator_id,omitempty"`
	RequiredApprovals int    `json:"required_approvals,omitempty"`
	Reason            string `json:"reason,omitempty"`
}

type P10QuorumApprovalEntry struct {
	ApproverID string `json:"approver_id"`
	Reason     string `json:"reason,omitempty"`
	ApprovedAt string `json:"approved_at,omitempty"`
}

type P10QuorumStatusResponse struct {
	WorkspaceID         string                   `json:"workspace_id"`
	ProposalID          string                   `json:"proposal_id"`
	InitiatorID         string                   `json:"initiator_id"`
	RequiredApprovals   int                      `json:"required_approvals"`
	ApprovalCount       int                      `json:"approval_count"`
	Status              string                   `json:"status"`
	Approvals           []P10QuorumApprovalEntry `json:"approvals"`
	QuorumReceiptSHA256 string                   `json:"quorum_receipt_sha256,omitempty"`
}

type SIEMAuditExportParams struct {
	WorkspaceID string
	Format      string
	Limit       int
}

type SIEMAuditExportResponse struct {
	WorkspaceID string `json:"workspace_id"`
	Format      string `json:"format"`
	RecordCount int    `json:"record_count"`
	BatchSHA256 string `json:"batch_sha256"`
	ExportedAt  string `json:"exported_at"`
	Records     []any  `json:"records"`
}

type ObservabilityMetricsParams struct {
	WorkspaceID string
	Format      string
}

type ObservabilityMetricsResponse struct {
	WorkspaceID         string         `json:"workspace_id"`
	Format              string         `json:"format"`
	GeneratedAt         string         `json:"generated_at"`
	Counters            map[string]any `json:"counters"`
	PrometheusText      string         `json:"prometheus_text,omitempty"`
	OTLPResourceMetrics any            `json:"otlp_resource_metrics,omitempty"`
}

func (p *PlatformService) ConfigureOIDCProvider(ctx context.Context, req OIDCProviderConfigRequest) (*OIDCProviderConfigResponse, error) {
	mapping := req.GroupRoleMapping
	if mapping == nil {
		mapping = map[string]string{}
	}
	body := map[string]any{
		"workspace_id":       firstString(req.WorkspaceID, "default"),
		"issuer_url":         req.IssuerURL,
		"client_id":          req.ClientID,
		"signing_secret":     req.SigningSecret,
		"group_role_mapping": mapping,
		"enabled":            req.Enabled,
	}
	return doPlatformJSON[OIDCProviderConfigResponse](ctx, p.client, http.MethodPut, "/v1/platform/enterprise/oidc", nil, body)
}

func (p *PlatformService) ListSCIMUsers(ctx context.Context, workspaceID string) (*SCIMUserListResponse, error) {
	return doPlatformJSON[SCIMUserListResponse](ctx, p.client, http.MethodGet, "/v1/platform/enterprise/scim/v2/Users", wsQuery(workspaceID), nil)
}

func (p *PlatformService) ProvisionSCIMUser(ctx context.Context, req SCIMUserProvisionRequest) (*SCIMUserResource, error) {
	groups := req.Groups
	if groups == nil {
		groups = []string{}
	}
	body := map[string]any{
		"workspace_id": firstString(req.WorkspaceID, "default"),
		"userName":     req.UserName,
		"displayName":  req.DisplayName,
		"groups":       groups,
		"active":       req.Active,
	}
	return doPlatformJSON[SCIMUserResource](ctx, p.client, http.MethodPost, "/v1/platform/enterprise/scim/v2/Users", nil, body)
}

func (p *PlatformService) ApproveP10Quorum(ctx context.Context, req P10QuorumApproveRequest) (*P10QuorumStatusResponse, error) {
	required := req.RequiredApprovals
	if required <= 0 {
		required = 2
	}
	body := map[string]any{
		"workspace_id":       firstString(req.WorkspaceID, "default"),
		"proposal_id":        req.ProposalID,
		"approver_id":        req.ApproverID,
		"initiator_id":       req.InitiatorID,
		"required_approvals": required,
		"reason":             req.Reason,
	}
	return doPlatformJSON[P10QuorumStatusResponse](ctx, p.client, http.MethodPost, "/v1/platform/enterprise/p10-quorum/approve", nil, body)
}

func (p *PlatformService) ExportSIEMAudit(ctx context.Context, params SIEMAuditExportParams) (*SIEMAuditExportResponse, error) {
	q := wsQuery(params.WorkspaceID)
	q.Set("format", firstString(params.Format, "ocsf"))
	limit := params.Limit
	if limit <= 0 {
		limit = 100
	}
	q.Set("limit", strconv.Itoa(limit))
	return doPlatformJSON[SIEMAuditExportResponse](ctx, p.client, http.MethodGet, "/v1/platform/enterprise/siem/export", q, nil)
}

func (p *PlatformService) GetObservabilityMetrics(ctx context.Context, params ObservabilityMetricsParams) (*ObservabilityMetricsResponse, error) {
	q := wsQuery(params.WorkspaceID)
	q.Set("format", firstString(params.Format, "otlp_json"))
	return doPlatformJSON[ObservabilityMetricsResponse](ctx, p.client, http.MethodGet, "/v1/platform/observability/metrics", q, nil)
}
