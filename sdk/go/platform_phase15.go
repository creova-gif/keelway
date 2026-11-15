package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

type CyclicKFlowNodeInput struct {
	ID                  string   `json:"id"`
	AgentID             string   `json:"agent_id,omitempty"`
	Model               string   `json:"model,omitempty"`
	DependsOn           []string `json:"depends_on,omitempty"`
	FanOutItems         int      `json:"fan_out_items,omitempty"`
	TimeoutMS           int      `json:"timeout_ms,omitempty"`
	CompensationHandler string   `json:"compensation_handler,omitempty"`
	BaseCostUSD         *float64 `json:"base_cost_usd,omitempty"`
	TTFTMS              int      `json:"ttft_ms,omitempty"`
	RequiresP10         bool     `json:"requires_p10,omitempty"`
}
type CyclicLoopEdgeInput struct {
	FromNode      string   `json:"from_node"`
	ToNode        string   `json:"to_node"`
	Condition     string   `json:"condition,omitempty"`
	Threshold     *float64 `json:"threshold,omitempty"`
	MaxIterations int      `json:"max_iterations,omitempty"`
}
type ValidateCyclicKFlowRequest struct {
	WorkspaceID string                 `json:"workspace_id,omitempty"`
	WorkflowID  string                 `json:"workflow_id,omitempty"`
	Nodes       []CyclicKFlowNodeInput `json:"nodes,omitempty"`
	LoopEdges   []CyclicLoopEdgeInput  `json:"loop_edges,omitempty"`
}
type CyclicKFlowValidationResponse struct {
	WorkspaceID          string   `json:"workspace_id"`
	WorkflowID           string   `json:"workflow_id"`
	Valid                bool     `json:"valid"`
	NodeCount            int      `json:"node_count"`
	LoopEdgeCount        int      `json:"loop_edge_count"`
	MaxWorstCaseSteps    int      `json:"max_worst_case_steps"`
	TopologicalSpine     []string `json:"topological_spine"`
	CompensationHandlers []string `json:"compensation_handlers"`
	SpecSHA256           string   `json:"spec_sha256"`
}
type ExecuteCyclicKFlowRequest struct {
	WorkspaceID           string                 `json:"workspace_id,omitempty"`
	WorkflowID            string                 `json:"workflow_id,omitempty"`
	Nodes                 []CyclicKFlowNodeInput `json:"nodes,omitempty"`
	LoopEdges             []CyclicLoopEdgeInput  `json:"loop_edges,omitempty"`
	MaxIterationsOverride *int                   `json:"max_iterations_override,omitempty"`
	CriticThreshold       *float64               `json:"critic_threshold,omitempty"`
	FanOutShards          *int                   `json:"fan_out_shards,omitempty"`
	SimulateTimeout       bool                   `json:"simulate_timeout"`
	InitialState          map[string]any         `json:"initial_state,omitempty"`
	ApprovedNodeIDs       []string               `json:"approved_node_ids,omitempty"`
}
type CyclicIterationTraceEntry struct {
	Iteration   int     `json:"iteration"`
	NodeID      string  `json:"node_id"`
	AgentID     string  `json:"agent_id"`
	Model       string  `json:"model"`
	CriticScore float64 `json:"critic_score"`
	ShardCount  int     `json:"shard_count"`
	Status      string  `json:"status"`
	CostUSD     float64 `json:"cost_usd"`
	LatencyMS   int     `json:"latency_ms"`
}
type CyclicCompensationLogEntry struct {
	NodeID  string `json:"node_id"`
	Handler string `json:"handler"`
	Reason  string `json:"reason"`
	Status  string `json:"status"`
}
type CyclicKFlowRunRecord struct {
	RunID              string                       `json:"run_id"`
	WorkspaceID        string                       `json:"workspace_id"`
	WorkflowID         string                       `json:"workflow_id"`
	Status             string                       `json:"status"`
	IterationsExecuted int                          `json:"iterations_executed"`
	MaxIterations      int                          `json:"max_iterations"`
	Converged          bool                         `json:"converged"`
	FinalCriticScore   float64                      `json:"final_critic_score"`
	CriticThreshold    float64                      `json:"critic_threshold"`
	FanOutShards       int                          `json:"fan_out_shards"`
	TotalCostUSD       float64                      `json:"total_cost_usd"`
	TotalLatencyMS     int                          `json:"total_latency_ms"`
	IterationTrace     []CyclicIterationTraceEntry  `json:"iteration_trace"`
	CompensationLog    []CyclicCompensationLogEntry `json:"compensation_log"`
	HeldNodeID         string                       `json:"held_node_id,omitempty"`
	RunSHA256          string                       `json:"run_sha256"`
	CreatedAt          string                       `json:"created_at"`
}
type ListCyclicKFlowRunsParams struct {
	WorkspaceID string
	WorkflowID  string
	Limit       int
}
type CyclicKFlowRunListResponse struct {
	WorkspaceID string                 `json:"workspace_id"`
	Count       int                    `json:"count"`
	Runs        []CyclicKFlowRunRecord `json:"runs"`
}
type SimulateKFlowAutopilotRequest struct {
	WorkspaceID            string                 `json:"workspace_id,omitempty"`
	WorkflowID             string                 `json:"workflow_id,omitempty"`
	Nodes                  []CyclicKFlowNodeInput `json:"nodes,omitempty"`
	LoopEdges              []CyclicLoopEdgeInput  `json:"loop_edges,omitempty"`
	BudgetCapUSD           *float64               `json:"budget_cap_usd,omitempty"`
	PrivacyPolicy          string                 `json:"privacy_policy,omitempty"`
	ExpectedLoopMultiplier int                    `json:"expected_loop_multiplier,omitempty"`
}
type AutopilotNodePlanEntry struct {
	NodeID        string  `json:"node_id"`
	OriginalModel string  `json:"original_model"`
	SelectedModel string  `json:"selected_model"`
	Rewritten     bool    `json:"rewritten"`
	Reason        string  `json:"reason"`
	P50CostUSD    float64 `json:"p50_cost_usd"`
	P95CostUSD    float64 `json:"p95_cost_usd"`
	DataBoundary  string  `json:"data_boundary"`
}
type AutopilotSimulationRecord struct {
	SimulationID           string                   `json:"simulation_id"`
	WorkspaceID            string                   `json:"workspace_id"`
	WorkflowID             string                   `json:"workflow_id"`
	PrivacyPolicy          string                   `json:"privacy_policy"`
	BudgetCapUSD           float64                  `json:"budget_cap_usd"`
	ExpectedLoopMultiplier int                      `json:"expected_loop_multiplier"`
	BaselineP50USD         float64                  `json:"baseline_p50_usd"`
	BaselineP95USD         float64                  `json:"baseline_p95_usd"`
	BaselineTTFTMS         int                      `json:"baseline_ttft_ms"`
	OptimizedP50USD        float64                  `json:"optimized_p50_usd"`
	OptimizedP95USD        float64                  `json:"optimized_p95_usd"`
	SavingsPct             float64                  `json:"savings_pct"`
	OptimizedTTFTMS        int                      `json:"optimized_ttft_ms"`
	PrivacyCompliant       bool                     `json:"privacy_compliant"`
	ViolationsResolved     int                      `json:"violations_resolved"`
	NodePlan               []AutopilotNodePlanEntry `json:"node_plan"`
	SimulationSHA256       string                   `json:"simulation_sha256"`
	CreatedAt              string                   `json:"created_at"`
}
type ListAutopilotSimulationsParams = ListCyclicKFlowRunsParams
type AutopilotSimulationListResponse struct {
	WorkspaceID string                      `json:"workspace_id"`
	Count       int                         `json:"count"`
	Simulations []AutopilotSimulationRecord `json:"simulations"`
}

func optFloat(v *float64, fallback float64) float64 {
	if v != nil {
		return *v
	}
	return fallback
}

func buildCyclicListQuery(wsID, wfID string, limit int) (url.Values, error) {
	if limit < 0 {
		return nil, fmt.Errorf("keelway: limit must be >= 1")
	}
	if limit == 0 {
		limit = 25
	}
	q := wsQuery(wsID)
	if cleanWF := strings.TrimSpace(wfID); cleanWF != "" {
		q.Set("workflow_id", cleanWF)
	}
	q.Set("limit", strconv.Itoa(limit))
	return q, nil
}

func (p *PlatformService) ValidateCyclicKFlow(ctx context.Context, req ValidateCyclicKFlowRequest) (*CyclicKFlowValidationResponse, error) {
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	req.WorkflowID = firstString(strings.TrimSpace(req.WorkflowID), "WF-CYCLIC-01")
	return doPlatformJSON[CyclicKFlowValidationResponse](ctx, p.client, http.MethodPost, "/v1/platform/kflow/cyclic/validate", nil, req)
}

func (p *PlatformService) ExecuteCyclicKFlow(ctx context.Context, req ExecuteCyclicKFlowRequest) (*CyclicKFlowRunRecord, error) {
	thr := optFloat(req.CriticThreshold, 0.85)
	if thr < 0.0 || thr > 1.0 {
		return nil, fmt.Errorf("keelway: critic_threshold must be between 0.0 and 1.0")
	}
	if req.MaxIterationsOverride != nil && (*req.MaxIterationsOverride < 1 || *req.MaxIterationsOverride > 10) {
		return nil, fmt.Errorf("keelway: max_iterations_override must be between 1 and 10")
	}
	if req.FanOutShards != nil && (*req.FanOutShards < 1 || *req.FanOutShards > 16) {
		return nil, fmt.Errorf("keelway: fan_out_shards must be between 1 and 16")
	}
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	req.WorkflowID = firstString(strings.TrimSpace(req.WorkflowID), "WF-CYCLIC-01")
	req.CriticThreshold = &thr
	return doPlatformJSON[CyclicKFlowRunRecord](ctx, p.client, http.MethodPost, "/v1/platform/kflow/cyclic/execute", nil, req)
}

func (p *PlatformService) ListCyclicKFlowRuns(ctx context.Context, params ListCyclicKFlowRunsParams) (*CyclicKFlowRunListResponse, error) {
	q, err := buildCyclicListQuery(params.WorkspaceID, params.WorkflowID, params.Limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[CyclicKFlowRunListResponse](ctx, p.client, http.MethodGet, "/v1/platform/kflow/cyclic/runs", q, nil)
}

func (p *PlatformService) GetCyclicKFlowRun(ctx context.Context, runID string, workspaceID string) (*CyclicKFlowRunRecord, error) {
	return doSegJSON[CyclicKFlowRunRecord](ctx, p.client, http.MethodGet, "/v1/platform/kflow/cyclic/runs/", runID, "runID", "", wsQuery(workspaceID), nil)
}

func (p *PlatformService) SimulateKFlowAutopilot(ctx context.Context, req SimulateKFlowAutopilotRequest) (*AutopilotSimulationRecord, error) {
	policy := firstString(strings.TrimSpace(req.PrivacyPolicy), "hybrid_balanced")
	if policy != "hybrid_balanced" && policy != "airgap_strict" && policy != "eu_residency" {
		return nil, fmt.Errorf("keelway: invalid privacy_policy %q", policy)
	}
	budgetCap := optFloat(req.BudgetCapUSD, 0.15)
	if budgetCap < 0.0 || req.ExpectedLoopMultiplier < 0 {
		return nil, fmt.Errorf("keelway: budget_cap_usd must be >= 0.0 and expected_loop_multiplier >= 1")
	}
	if req.ExpectedLoopMultiplier == 0 {
		req.ExpectedLoopMultiplier = 2
	}
	req.WorkspaceID = firstString(req.WorkspaceID, "default")
	req.WorkflowID = firstString(strings.TrimSpace(req.WorkflowID), "WF-CYCLIC-01")
	req.PrivacyPolicy, req.BudgetCapUSD = policy, &budgetCap
	return doPlatformJSON[AutopilotSimulationRecord](ctx, p.client, http.MethodPost, "/v1/platform/kflow/autopilot/simulate", nil, req)
}

func (p *PlatformService) ListKFlowAutopilotSimulations(ctx context.Context, params ListAutopilotSimulationsParams) (*AutopilotSimulationListResponse, error) {
	q, err := buildCyclicListQuery(params.WorkspaceID, params.WorkflowID, params.Limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[AutopilotSimulationListResponse](ctx, p.client, http.MethodGet, "/v1/platform/kflow/autopilot/simulations", q, nil)
}

func (c *Client) ValidateCyclicKFlow(ctx context.Context, req ValidateCyclicKFlowRequest) (*CyclicKFlowValidationResponse, error) {
	return c.Platform.ValidateCyclicKFlow(ctx, req)
}
func (c *Client) ExecuteCyclicKFlow(ctx context.Context, req ExecuteCyclicKFlowRequest) (*CyclicKFlowRunRecord, error) {
	return c.Platform.ExecuteCyclicKFlow(ctx, req)
}
func (c *Client) ListCyclicKFlowRuns(ctx context.Context, params ListCyclicKFlowRunsParams) (*CyclicKFlowRunListResponse, error) {
	return c.Platform.ListCyclicKFlowRuns(ctx, params)
}
func (c *Client) GetCyclicKFlowRun(ctx context.Context, runID string, workspaceID string) (*CyclicKFlowRunRecord, error) {
	return c.Platform.GetCyclicKFlowRun(ctx, runID, workspaceID)
}
func (c *Client) SimulateKFlowAutopilot(ctx context.Context, req SimulateKFlowAutopilotRequest) (*AutopilotSimulationRecord, error) {
	return c.Platform.SimulateKFlowAutopilot(ctx, req)
}
func (c *Client) ListKFlowAutopilotSimulations(ctx context.Context, params ListAutopilotSimulationsParams) (*AutopilotSimulationListResponse, error) {
	return c.Platform.ListKFlowAutopilotSimulations(ctx, params)
}
