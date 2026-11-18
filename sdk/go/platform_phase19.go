package keelway

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

const (
	defaultShadowPrompt   = "Refactor retry loop with bounded exponential backoff in Python"
	defaultShadowResponse = "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))"
)

type EvaluateShadowPromptRequest struct {
	WorkspaceID         string  `json:"workspace_id,omitempty"`
	TaskTag             string  `json:"task_tag,omitempty"`
	Prompt              string  `json:"prompt,omitempty"`
	FrontierModel       string  `json:"frontier_model,omitempty"`
	LocalModel          string  `json:"local_model,omitempty"`
	FrontierResponse    string  `json:"frontier_response,omitempty"`
	LocalResponse       string  `json:"local_response,omitempty"`
	FrontierCostUSD     float64 `json:"frontier_cost_usd,omitempty"`
	FrontierLatencyMS   int     `json:"frontier_latency_ms,omitempty"`
	LocalLatencyMS      int     `json:"local_latency_ms,omitempty"`
	SimilarityThreshold float64 `json:"similarity_threshold,omitempty"`
	BypassCache         bool    `json:"bypass_cache"`
}

type ShadowEvaluationRecord struct {
	EvaluationID    string  `json:"evaluation_id"`
	PairID          *string `json:"pair_id"`
	CacheEntryID    string  `json:"cache_entry_id"`
	WorkspaceID     string  `json:"workspace_id"`
	TaskTag         string  `json:"task_tag"`
	Verdict         string  `json:"verdict"`
	MatchType       string  `json:"match_type"`
	SimilarityScore float64 `json:"similarity_score"`
	ParityScore     float64 `json:"parity_score"`
	FrontierModel   string  `json:"frontier_model"`
	LocalModel      string  `json:"local_model"`
	ScrubbedPrompt  string  `json:"scrubbed_prompt"`
	CachedResponse  string  `json:"cached_response"`
	CostSavedUSD    float64 `json:"cost_saved_usd"`
	LatencySavedMS  float64 `json:"latency_saved_ms"`
	DLPRedactions   int     `json:"dlp_redactions"`
	EventSHA256     string  `json:"event_sha256"`
	CreatedAt       string  `json:"created_at"`
}

type ShadowDistillPairRecord struct {
	PairID                   string  `json:"pair_id"`
	WorkspaceID              string  `json:"workspace_id"`
	TaskTag                  string  `json:"task_tag"`
	ScrubbedPrompt           string  `json:"scrubbed_prompt"`
	ScrubbedFrontierResponse string  `json:"scrubbed_frontier_response"`
	ScrubbedLocalResponse    string  `json:"scrubbed_local_response"`
	FrontierModel            string  `json:"frontier_model"`
	LocalModel               string  `json:"local_model"`
	ParityScore              float64 `json:"parity_score"`
	FrontierCostUSD          float64 `json:"frontier_cost_usd"`
	DLPRedactions            int     `json:"dlp_redactions"`
	PairSHA256               string  `json:"pair_sha256"`
	CreatedAt                string  `json:"created_at"`
}

type ShadowPairListResponse struct {
	WorkspaceID string                    `json:"workspace_id"`
	Count       int                       `json:"count"`
	Pairs       []ShadowDistillPairRecord `json:"pairs"`
}

type SemanticCacheStatsResponse struct {
	WorkspaceID         string  `json:"workspace_id"`
	EntryCount          int     `json:"entry_count"`
	TotalHits           int     `json:"total_hits"`
	TotalLookups        int     `json:"total_lookups"`
	HitRate             float64 `json:"hit_rate"`
	TotalCostSavedUSD   float64 `json:"total_cost_saved_usd"`
	TotalLatencySavedMS float64 `json:"total_latency_saved_ms"`
	TotalDLPRedactions  int     `json:"total_dlp_redactions"`
}

type CompileDistillationDatasetRequest struct {
	WorkspaceID     string  `json:"workspace_id,omitempty"`
	TaskTag         string  `json:"task_tag"`
	ExportFormat    string  `json:"export_format,omitempty"`
	TargetBaseModel string  `json:"target_base_model,omitempty"`
	MinParityScore  float64 `json:"min_parity_score"`
}

type DistillationDatasetRecord struct {
	DatasetID       string  `json:"dataset_id"`
	WorkspaceID     string  `json:"workspace_id"`
	TaskTag         string  `json:"task_tag"`
	ExportFormat    string  `json:"export_format"`
	TargetBaseModel string  `json:"target_base_model"`
	RecordCount     int     `json:"record_count"`
	AvgParityScore  float64 `json:"avg_parity_score"`
	LoraRank        int     `json:"lora_rank"`
	LoraAlpha       int     `json:"lora_alpha"`
	DLPRedactions   int     `json:"dlp_redactions"`
	JSONLPreview    string  `json:"jsonl_preview"`
	DatasetSHA256   string  `json:"dataset_sha256"`
	CreatedAt       string  `json:"created_at"`
}

type DistillationDatasetListResponse struct {
	WorkspaceID string                      `json:"workspace_id"`
	Count       int                         `json:"count"`
	Datasets    []DistillationDatasetRecord `json:"datasets"`
}

type EvaluateDistillationPromotionRequest struct {
	WorkspaceID          string  `json:"workspace_id,omitempty"`
	TaskTag              string  `json:"task_tag,omitempty"`
	TargetLocalModel     string  `json:"target_local_model,omitempty"`
	MinPairs             int     `json:"min_pairs,omitempty"`
	MinAvgParity         float64 `json:"min_avg_parity,omitempty"`
	MonthlyRequestVolume int     `json:"monthly_request_volume,omitempty"`
}

type DistillationPromotionEvaluation struct {
	EvaluationID               string  `json:"evaluation_id"`
	WorkspaceID                string  `json:"workspace_id"`
	TaskTag                    string  `json:"task_tag"`
	TargetLocalModel           string  `json:"target_local_model"`
	Verdict                    string  `json:"verdict"`
	PairCount                  int     `json:"pair_count"`
	MinPairs                   int     `json:"min_pairs"`
	AvgParityScore             float64 `json:"avg_parity_score"`
	MinAvgParity               float64 `json:"min_avg_parity"`
	AvgFrontierCostUSD         float64 `json:"avg_frontier_cost_usd"`
	MonthlyRequestVolume       int     `json:"monthly_request_volume"`
	ProjectedMonthlySavingsUSD float64 `json:"projected_monthly_savings_usd"`
	Recommendation             string  `json:"recommendation"`
	GateSHA256                 string  `json:"gate_sha256"`
	EvaluatedAt                string  `json:"evaluated_at"`
}

func buildDistillListQuery(wsID string, limit int) (url.Values, error) {
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

func (p *PlatformService) EvaluateShadowPrompt(ctx context.Context, req EvaluateShadowPromptRequest) (*ShadowEvaluationRecord, error) {
	if req.FrontierCostUSD < 0.0 || req.FrontierLatencyMS < 0 || req.LocalLatencyMS < 0 {
		return nil, fmt.Errorf("keelway: cost and latency values must be >= 0")
	}
	if req.SimilarityThreshold < 0.0 || req.SimilarityThreshold > 1.0 {
		return nil, fmt.Errorf("keelway: similarity_threshold must be between 0.0 and 1.0")
	}
	if req.FrontierCostUSD == 0.0 {
		req.FrontierCostUSD = 0.018
	}
	if req.FrontierLatencyMS == 0 {
		req.FrontierLatencyMS = 840
	}
	if req.LocalLatencyMS == 0 {
		req.LocalLatencyMS = 95
	}
	if req.SimilarityThreshold == 0.0 {
		req.SimilarityThreshold = 0.82
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.TaskTag = firstString(strings.TrimSpace(req.TaskTag), "code-patch")
	req.Prompt = firstString(strings.TrimSpace(req.Prompt), defaultShadowPrompt)
	req.FrontierModel = firstString(strings.TrimSpace(req.FrontierModel), "claude-3-7-sonnet")
	req.LocalModel = firstString(strings.TrimSpace(req.LocalModel), "keelway-core:7b")
	req.FrontierResponse = firstString(strings.TrimSpace(req.FrontierResponse), defaultShadowResponse)
	req.LocalResponse = firstString(strings.TrimSpace(req.LocalResponse), defaultShadowResponse)
	return doPlatformJSON[ShadowEvaluationRecord](ctx, p.client, http.MethodPost, "/v1/platform/distill/shadow/evaluate", nil, req)
}

func (p *PlatformService) ListShadowPairs(ctx context.Context, workspaceID string, taskTag string, limit int) (*ShadowPairListResponse, error) {
	q, err := buildDistillListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	if cleanTag := strings.TrimSpace(taskTag); cleanTag != "" {
		q.Set("task_tag", cleanTag)
	}
	return doPlatformJSON[ShadowPairListResponse](ctx, p.client, http.MethodGet, "/v1/platform/distill/shadow/pairs", q, nil)
}

func (p *PlatformService) GetSemanticCacheStats(ctx context.Context, workspaceID string) (*SemanticCacheStatsResponse, error) {
	return doPlatformJSON[SemanticCacheStatsResponse](ctx, p.client, http.MethodGet, "/v1/platform/distill/cache/stats", wsQuery(workspaceID), nil)
}

func (p *PlatformService) CompileDistillationDataset(ctx context.Context, req CompileDistillationDatasetRequest) (*DistillationDatasetRecord, error) {
	format := firstString(strings.TrimSpace(req.ExportFormat), "dpo_preference")
	if format != "sft_jsonl" && format != "dpo_preference" {
		return nil, fmt.Errorf("keelway: invalid export_format %q", format)
	}
	if req.MinParityScore < 0.0 || req.MinParityScore > 1.0 {
		return nil, fmt.Errorf("keelway: min_parity_score must be between 0.0 and 1.0")
	}
	req.WorkspaceID, req.TaskTag = firstString(strings.TrimSpace(req.WorkspaceID), "default"), strings.TrimSpace(req.TaskTag)
	req.ExportFormat, req.TargetBaseModel = format, firstString(strings.TrimSpace(req.TargetBaseModel), "keelway-core:7b")
	return doPlatformJSON[DistillationDatasetRecord](ctx, p.client, http.MethodPost, "/v1/platform/distill/datasets/compile", nil, req)
}

func (p *PlatformService) ListDistillationDatasets(ctx context.Context, workspaceID string, limit int) (*DistillationDatasetListResponse, error) {
	q, err := buildDistillListQuery(workspaceID, limit)
	if err != nil {
		return nil, err
	}
	return doPlatformJSON[DistillationDatasetListResponse](ctx, p.client, http.MethodGet, "/v1/platform/distill/datasets", q, nil)
}

func (p *PlatformService) EvaluateDistillationPromotion(ctx context.Context, req EvaluateDistillationPromotionRequest) (*DistillationPromotionEvaluation, error) {
	if req.MinPairs < 0 || req.MonthlyRequestVolume < 0 || req.MinAvgParity < 0.0 || req.MinAvgParity > 1.0 {
		return nil, fmt.Errorf("keelway: invalid promotion gate thresholds")
	}
	if req.MinPairs == 0 {
		req.MinPairs = 3
	}
	if req.MinAvgParity == 0.0 {
		req.MinAvgParity = 0.85
	}
	if req.MonthlyRequestVolume == 0 {
		req.MonthlyRequestVolume = 50000
	}
	req.WorkspaceID = firstString(strings.TrimSpace(req.WorkspaceID), "default")
	req.TaskTag = firstString(strings.TrimSpace(req.TaskTag), "code-patch")
	req.TargetLocalModel = firstString(strings.TrimSpace(req.TargetLocalModel), "keelway-core:7b")
	return doPlatformJSON[DistillationPromotionEvaluation](ctx, p.client, http.MethodPost, "/v1/platform/distill/promotion/evaluate", nil, req)
}

func (c *Client) EvaluateShadowPrompt(ctx context.Context, req EvaluateShadowPromptRequest) (*ShadowEvaluationRecord, error) {
	return c.Platform.EvaluateShadowPrompt(ctx, req)
}
func (c *Client) ListShadowPairs(ctx context.Context, workspaceID string, taskTag string, limit int) (*ShadowPairListResponse, error) {
	return c.Platform.ListShadowPairs(ctx, workspaceID, taskTag, limit)
}
func (c *Client) GetSemanticCacheStats(ctx context.Context, workspaceID string) (*SemanticCacheStatsResponse, error) {
	return c.Platform.GetSemanticCacheStats(ctx, workspaceID)
}
func (c *Client) CompileDistillationDataset(ctx context.Context, req CompileDistillationDatasetRequest) (*DistillationDatasetRecord, error) {
	return c.Platform.CompileDistillationDataset(ctx, req)
}
func (c *Client) ListDistillationDatasets(ctx context.Context, workspaceID string, limit int) (*DistillationDatasetListResponse, error) {
	return c.Platform.ListDistillationDatasets(ctx, workspaceID, limit)
}
func (c *Client) EvaluateDistillationPromotion(ctx context.Context, req EvaluateDistillationPromotionRequest) (*DistillationPromotionEvaluation, error) {
	return c.Platform.EvaluateDistillationPromotion(ctx, req)
}
