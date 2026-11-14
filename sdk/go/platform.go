package keelway

import (
	"context"
	"net/http"
	"net/url"
	"strings"
)

type PlatformOverview struct {
	WorkspaceID          string           `json:"workspace_id"`
	ProjectName          string           `json:"project_name,omitempty"`
	Branch               string           `json:"branch,omitempty"`
	ActiveModelID        string           `json:"active_model_id,omitempty"`
	ExperienceMode       string           `json:"experience_mode,omitempty"`
	Views                []map[string]any `json:"views,omitempty"`
	LifecycleAgentsCount int              `json:"lifecycle_agents_count,omitempty"`
	Counts               map[string]int   `json:"counts,omitempty"`
	InstalledPackages    []map[string]any `json:"installed_packages,omitempty"`
}

type AgentsCatalog struct {
	Agents     []map[string]any `json:"agents"`
	Teams      []map[string]any `json:"teams,omitempty"`
	SDLCStages []map[string]any `json:"sdlc_stages,omitempty"`
	Runs       []map[string]any `json:"runs,omitempty"`
}

type TeamDispatchRequest struct {
	TeamID            string `json:"team_id"`
	Objective         string `json:"objective"`
	WorkspaceID       string `json:"workspace_id,omitempty"`
	SensitiveMutation bool   `json:"sensitive_mutation,omitempty"`
}

type TeamDispatchResult struct {
	RunID           string           `json:"run_id"`
	WorkspaceID     string           `json:"workspace_id,omitempty"`
	TeamID          string           `json:"team_id"`
	Objective       string           `json:"objective"`
	Status          string           `json:"status"`
	P10Checkpoint   map[string]any   `json:"p10_checkpoint,omitempty"`
	DelegationTrace []map[string]any `json:"delegation_trace,omitempty"`
}

type IssueCreateRequest struct {
	Title         string `json:"title"`
	WorkspaceID   string `json:"workspace_id,omitempty"`
	Priority      string `json:"priority,omitempty"`
	Status        string `json:"status,omitempty"`
	AssigneeAgent string `json:"assignee_agent,omitempty"`
	PRDID         string `json:"prd_id,omitempty"`
	SprintID      string `json:"sprint_id,omitempty"`
}

type Issue struct {
	ID            string `json:"id"`
	Title         string `json:"title"`
	Status        string `json:"status"`
	Priority      string `json:"priority,omitempty"`
	SprintID      string `json:"sprint_id,omitempty"`
	PRDID         string `json:"prd_id,omitempty"`
	AssigneeAgent string `json:"assignee_agent,omitempty"`
}

type IssueList struct {
	Issues []Issue `json:"issues"`
	Total  int     `json:"total"`
}

type MarketplacePackage struct {
	ID               string  `json:"id"`
	Name             string  `json:"name,omitempty"`
	Category         string  `json:"category,omitempty"`
	Kind             string  `json:"kind,omitempty"`
	Version          string  `json:"version,omitempty"`
	Publisher        string  `json:"publisher,omitempty"`
	PublisherTier    string  `json:"publisher_tier,omitempty"`
	PriceUSD         float64 `json:"price_usd,omitempty"`
	SecurityVerified bool    `json:"security_verified,omitempty"`
	ManifestSHA256   string  `json:"manifest_sha256,omitempty"`
	Status           string  `json:"status,omitempty"`
}

type MarketplacePackageList struct {
	Packages  []MarketplacePackage `json:"packages"`
	Total     int                  `json:"total"`
	Installed []map[string]any     `json:"installed,omitempty"`
}

type MarketplaceScanReport struct {
	Passed         bool             `json:"passed"`
	RiskGrade      string           `json:"risk_grade"`
	Findings       []map[string]any `json:"findings"`
	FindingsCount  int              `json:"findings_count,omitempty"`
	ManifestSHA256 string           `json:"manifest_sha256,omitempty"`
}

type MarketplaceInstallResult struct {
	PackageID   string `json:"package_id"`
	WorkspaceID string `json:"workspace_id,omitempty"`
	Status      string `json:"status"`
}

type BlueprintResult struct {
	WorkspaceID         string         `json:"workspace_id,omitempty"`
	ExperienceMode      string         `json:"experience_mode,omitempty"`
	Idea                string         `json:"idea,omitempty"`
	PRD                 map[string]any `json:"prd,omitempty"`
	SprintIssues        []Issue        `json:"sprint_issues,omitempty"`
	Workflow            map[string]any `json:"workflow,omitempty"`
	ArchitectureSummary map[string]any `json:"architecture_summary,omitempty"`
}

type EnterprisePolicy struct {
	TenantID                      string         `json:"tenant_id"`
	OrgDisplayName                string         `json:"org_display_name,omitempty"`
	RetentionMode                 string         `json:"retention_mode,omitempty"`
	AuditRetentionDays            int            `json:"audit_retention_days,omitempty"`
	PIIRedactionEnforced          bool           `json:"pii_redaction_enforced"`
	AllowPromptLogging            bool           `json:"allow_prompt_logging"`
	DeploymentTopology            string         `json:"deployment_topology,omitempty"`
	AllowedModelRegions           []string       `json:"allowed_model_regions,omitempty"`
	SSOSAMLRequired               bool           `json:"sso_saml_required"`
	RequireP10ForExternalWebhooks bool           `json:"require_p10_for_external_webhooks"`
	ResourceCaps                  map[string]any `json:"resource_caps,omitempty"`
}

type ComplianceEvaluation struct {
	TenantID     string           `json:"tenant_id"`
	Framework    string           `json:"framework,omitempty"`
	Frameworks   []string         `json:"frameworks,omitempty"`
	Passed       bool             `json:"passed"`
	Compliant    bool             `json:"compliant,omitempty"`
	ScorePct     float64          `json:"score_pct,omitempty"`
	Controls     []map[string]any `json:"controls,omitempty"`
	Remediations []string         `json:"remediations,omitempty"`
}

// PlatformService provides unified control-plane operations on /v1/platform/*.
type PlatformService struct{ client *Client }

func (p *PlatformService) GetOverview(ctx context.Context) (*PlatformOverview, error) {
	var out PlatformOverview
	if err := p.client.doJSON(ctx, http.MethodGet, "/v1/platform/overview", nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) ListAgents(ctx context.Context) (*AgentsCatalog, error) {
	var out AgentsCatalog
	if err := p.client.doJSON(ctx, http.MethodGet, "/v1/platform/agents", nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) DispatchTeam(ctx context.Context, req TeamDispatchRequest) (*TeamDispatchResult, error) {
	var out TeamDispatchResult
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/teams/dispatch", nil, req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) ListIssues(ctx context.Context) (*IssueList, error) {
	var out IssueList
	if err := p.client.doJSON(ctx, http.MethodGet, "/v1/platform/pm/issues", nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) CreateIssue(ctx context.Context, req IssueCreateRequest) (*Issue, error) {
	var out Issue
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/pm/issues", nil, req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) ListMarketplacePackages(ctx context.Context, category, query string) (*MarketplacePackageList, error) {
	q := url.Values{}
	if strings.TrimSpace(category) != "" {
		q.Set("category", category)
		q.Set("kind", category)
	}
	if strings.TrimSpace(query) != "" {
		q.Set("query", query)
	}
	var out MarketplacePackageList
	if err := p.client.doJSON(ctx, http.MethodGet, "/v1/platform/marketplace/packages", q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) ScanMarketplacePackage(ctx context.Context, pkg map[string]any) (*MarketplaceScanReport, error) {
	var out MarketplaceScanReport
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/marketplace/scan", nil, pkg, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) PublishMarketplacePackage(ctx context.Context, pkg map[string]any) (*MarketplacePackage, error) {
	var out MarketplacePackage
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/marketplace/publish", nil, pkg, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) InstallMarketplacePackage(ctx context.Context, packageID string) (*MarketplaceInstallResult, error) {
	var out MarketplaceInstallResult
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/marketplace/install", nil, map[string]any{"package_id": packageID}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) CompileBlueprint(ctx context.Context, idea, mode string) (*BlueprintResult, error) {
	if strings.TrimSpace(mode) == "" {
		mode = "non_coder"
	}
	body := map[string]any{"idea": idea, "experience_mode": mode, "mode": mode}
	var out BlueprintResult
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/nocode/blueprint", nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) GetEnterprisePolicy(ctx context.Context, tenantID string) (*EnterprisePolicy, error) {
	path := "/v1/platform/enterprise/policy/" + url.PathEscape(strings.TrimSpace(tenantID))
	var out EnterprisePolicy
	if err := p.client.doJSON(ctx, http.MethodGet, path, nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (p *PlatformService) EvaluateCompliance(ctx context.Context, tenantID string, frameworks []string) (*ComplianceEvaluation, error) {
	primary := "SOC2"
	if len(frameworks) > 0 && strings.TrimSpace(frameworks[0]) != "" {
		primary = strings.TrimSpace(frameworks[0])
	}
	body := map[string]any{"tenant_id": tenantID, "frameworks": frameworks, "framework": primary}
	var out ComplianceEvaluation
	if err := p.client.doJSON(ctx, http.MethodPost, "/v1/platform/enterprise/compliance-check", nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

type ClusterNode struct {
	NodeID         string   `json:"node_id"`
	Runtime        string   `json:"runtime,omitempty"`
	Region         string   `json:"region"`
	GPUModel       string   `json:"gpu_model,omitempty"`
	GPUCount       int      `json:"gpu_count,omitempty"`
	TotalVRAMGB    float64  `json:"total_vram_gb,omitempty"`
	FreeVRAMGB     float64  `json:"free_vram_gb,omitempty"`
	UtilizationPct float64  `json:"utilization_pct,omitempty"`
	Status         string   `json:"status"`
	LoadedModels   []string `json:"loaded_models,omitempty"`
}

type ClusterNodeList struct {
	Nodes []ClusterNode `json:"nodes"`
	Total int           `json:"total,omitempty"`
}

type ScheduleDecision struct {
	SelectedNodeID string  `json:"selected_node_id"`
	ModelID        string  `json:"model_id,omitempty"`
	Runtime        string  `json:"runtime,omitempty"`
	Region         string  `json:"region,omitempty"`
	PrivacyLevel   string  `json:"privacy_level,omitempty"`
	RequiredVRAMGB float64 `json:"required_vram_gb,omitempty"`
	Score          float64 `json:"score,omitempty"`
	ReceiptSHA256  string  `json:"receipt_sha256,omitempty"`
}

type ClusterLifecycle struct {
	Models      []map[string]any `json:"models,omitempty"`
	Deployments []map[string]any `json:"deployments,omitempty"`
	Stages      []string         `json:"stages,omitempty"`
	Total       int              `json:"total,omitempty"`
}

// ClusterService manages distributed GPU nodes, scheduling, and model lifecycle on /v1/cluster/*.
type ClusterService struct{ client *Client }

func (cs *ClusterService) ListNodes(ctx context.Context, region string) (*ClusterNodeList, error) {
	q := url.Values{}
	if strings.TrimSpace(region) != "" {
		q.Set("region", region)
	}
	var out ClusterNodeList
	if err := cs.client.doJSON(ctx, http.MethodGet, "/v1/cluster/nodes", q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (cs *ClusterService) Schedule(ctx context.Context, req map[string]any) (*ScheduleDecision, error) {
	var out ScheduleDecision
	if err := cs.client.doJSON(ctx, http.MethodPost, "/v1/cluster/schedule", nil, req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (cs *ClusterService) ListLifecycle(ctx context.Context) (*ClusterLifecycle, error) {
	var out ClusterLifecycle
	if err := cs.client.doJSON(ctx, http.MethodGet, "/v1/cluster/lifecycle", nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

type DocUpsertRequest struct {
	Title        string `json:"title"`
	DiataxisKind string `json:"diataxis_kind,omitempty"`
	Summary      string `json:"summary,omitempty"`
	Body         string `json:"body,omitempty"`
	LinkedPRDID  string `json:"linked_prd_id,omitempty"`
	WorkspaceID  string `json:"workspace_id,omitempty"`
}
type WorkspaceDoc struct {
	ID           string `json:"id"`
	Title        string `json:"title"`
	DiataxisKind string `json:"diataxis_kind"`
	Summary      string `json:"summary,omitempty"`
	Body         string `json:"body,omitempty"`
	LinkedPRDID  string `json:"linked_prd_id,omitempty"`
	UpdatedAt    string `json:"updated_at,omitempty"`
}
type DocList struct {
	WorkspaceID string         `json:"workspace_id"`
	Count       int            `json:"count"`
	Docs        []WorkspaceDoc `json:"docs"`
}
type IssuePatchRequest struct {
	WorkspaceID   string   `json:"workspace_id,omitempty"`
	Title         string   `json:"title,omitempty"`
	Status        string   `json:"status,omitempty"`
	Priority      string   `json:"priority,omitempty"`
	SprintID      string   `json:"sprint_id,omitempty"`
	PRDID         string   `json:"prd_id,omitempty"`
	AssigneeAgent string   `json:"assignee_agent,omitempty"`
	Description   string   `json:"description,omitempty"`
	Dependencies  []string `json:"dependencies,omitempty"`
}
type FeedbackCreateRequest struct {
	Persona     string  `json:"persona"`
	Quote       string  `json:"quote"`
	ImpactScore float64 `json:"impact_score,omitempty"`
	LinkedPRDID string  `json:"linked_prd_id,omitempty"`
	WorkspaceID string  `json:"workspace_id,omitempty"`
}
type FeedbackEntry struct {
	ID          string  `json:"id"`
	Persona     string  `json:"persona"`
	Quote       string  `json:"quote"`
	ImpactScore float64 `json:"impact_score"`
	LinkedPRDID string  `json:"linked_prd_id,omitempty"`
	CreatedAt   string  `json:"created_at,omitempty"`
}
type FeedbackList struct {
	WorkspaceID string          `json:"workspace_id"`
	Feedback    []FeedbackEntry `json:"feedback"`
	Count       int             `json:"count"`
	Total       int             `json:"total"`
}
type WorkspaceSecurityScanRequest struct {
	TargetName  string   `json:"target_name,omitempty"`
	TargetPath  string   `json:"target_path,omitempty"`
	Content     string   `json:"content,omitempty"`
	Snippet     string   `json:"snippet,omitempty"`
	WritePaths  []string `json:"write_paths,omitempty"`
	WorkspaceID string   `json:"workspace_id,omitempty"`
}
type WorkspaceSecurityScanReport struct {
	WorkspaceID string `json:"workspace_id"`
	TargetName  string `json:"target_name"`
	MarketplaceScanReport
}
type WorkspaceCreateRequest struct {
	ID            string `json:"id,omitempty"`
	Name          string `json:"name"`
	Branch        string `json:"branch,omitempty"`
	IsolationMode string `json:"isolation_mode,omitempty"`
	Description   string `json:"description,omitempty"`
}
type WorkspaceRecord struct {
	ID            string `json:"id"`
	Name          string `json:"name"`
	Branch        string `json:"branch,omitempty"`
	IsolationMode string `json:"isolation_mode,omitempty"`
	CreatedAt     string `json:"created_at,omitempty"`
}
type WorkspaceList struct {
	Workspaces []WorkspaceRecord `json:"workspaces"`
	Total      int               `json:"total"`
}
type RBACMemberUpsertRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	ActorID     string `json:"actor_id"`
	Role        string `json:"role"`
	DisplayName string `json:"display_name,omitempty"`
}
type RBACMember struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	ActorID     string `json:"actor_id"`
	Role        string `json:"role"`
	DisplayName string `json:"display_name,omitempty"`
	UpdatedAt   string `json:"updated_at,omitempty"`
}
type RBACMemberList struct {
	WorkspaceID string       `json:"workspace_id,omitempty"`
	Members     []RBACMember `json:"members"`
	Roles       []any        `json:"roles,omitempty"`
}
type RBACCheckRequest struct {
	WorkspaceID string `json:"workspace_id,omitempty"`
	ActorID     string `json:"actor_id,omitempty"`
	Role        string `json:"role,omitempty"`
	Permission  string `json:"permission"`
}
type RBACCheckResult struct {
	Allowed     bool   `json:"allowed"`
	Role        string `json:"role"`
	Permission  string `json:"permission"`
	Reason      string `json:"reason"`
	WorkspaceID string `json:"workspace_id,omitempty"`
}
