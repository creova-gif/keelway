package keelway

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestPlatformPhase19ShadowCacheAndDistillation(t *testing.T) {
	t.Parallel()

	type cacheItem struct {
		id, wsID, taskTag, prompt, response string
		parity, costSaved, msSaved          float64
		hits, redactions                    int
	}
	var mu sync.Mutex
	var cache []*cacheItem
	var pairs []ShadowDistillPairRecord
	var datasets []DistillationDatasetRecord
	lookups := map[string]int{}

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p19" {
			t.Errorf("expected Bearer kw_live_go_p19, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/distill/shadow/evaluate":
			if r.Header.Get("X-Keelway-Role") == "auditor" {
				w.WriteHeader(http.StatusForbidden)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Auditor role denied shadow evaluate"})
				return
			}
			wsID, tag := body["workspace_id"].(string), body["task_tag"].(string)
			rawPrompt, fResp, lResp := body["prompt"].(string), body["frontier_response"].(string), body["local_response"].(string)
			fModel, lModel := body["frontier_model"].(string), body["local_model"].(string)
			fCost, bypass := body["frontier_cost_usd"].(float64), body["bypass_cache"].(bool)
			scrubbed := strings.ReplaceAll(rawPrompt, "sk-live-secret19", "[REDACTED_SECRET]")
			dlp := 0
			if scrubbed != rawPrompt {
				dlp = 1
			}

			mu.Lock()
			lookups[wsID]++
			if !bypass {
				for _, entry := range cache {
					if entry.wsID == wsID && entry.taskTag == tag && strings.EqualFold(strings.TrimSuffix(entry.prompt, "!"), strings.TrimSuffix(scrubbed, "!")) {
						entry.hits, entry.costSaved, entry.msSaved = entry.hits+1, entry.costSaved+fCost, entry.msSaved+745
						matchType := "semantic_shingle"
						if entry.prompt == scrubbed {
							matchType = "exact_sha256"
						}
						rec := ShadowEvaluationRecord{
							EvaluationID: "seval-hit", CacheEntryID: entry.id, WorkspaceID: wsID, TaskTag: tag,
							Verdict: "CACHE_HIT", MatchType: matchType, SimilarityScore: 0.96, ParityScore: entry.parity,
							FrontierModel: fModel, LocalModel: lModel, ScrubbedPrompt: scrubbed, CachedResponse: entry.response,
							CostSavedUSD: fCost, LatencySavedMS: 745, DLPRedactions: dlp, EventSHA256: sha256String("hit:" + entry.id), CreatedAt: "2026-11-16T03:00:00Z",
						}
						mu.Unlock()
						_ = json.NewEncoder(w).Encode(rec)
						return
					}
				}
			}
			parity, verdict := 0.94, "LOCAL_PARITY_READY"
			if fResp != lResp {
				parity, verdict = 0.72, "SHADOW_CAPTURED"
			}
			pairID, cacheID := fmt.Sprintf("spair-go-%d", len(pairs)+1), fmt.Sprintf("scache-go-%d", len(cache)+1)
			pairs = append([]ShadowDistillPairRecord{{
				PairID: pairID, WorkspaceID: wsID, TaskTag: tag, ScrubbedPrompt: scrubbed,
				ScrubbedFrontierResponse: fResp, ScrubbedLocalResponse: lResp, FrontierModel: fModel, LocalModel: lModel,
				ParityScore: parity, FrontierCostUSD: fCost, DLPRedactions: dlp, PairSHA256: sha256String(pairID), CreatedAt: "2026-11-16T03:00:00Z",
			}}, pairs...)
			cache = append(cache, &cacheItem{id: cacheID, wsID: wsID, taskTag: tag, prompt: scrubbed, response: fResp, parity: parity, redactions: dlp})
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(ShadowEvaluationRecord{
				EvaluationID: "seval-miss", PairID: StringPtr(pairID), CacheEntryID: cacheID, WorkspaceID: wsID, TaskTag: tag,
				Verdict: verdict, MatchType: "cache_miss", ParityScore: parity, FrontierModel: fModel, LocalModel: lModel,
				ScrubbedPrompt: scrubbed, CachedResponse: fResp, DLPRedactions: dlp, EventSHA256: sha256String(pairID), CreatedAt: "2026-11-16T03:00:00Z",
			})

		case r.Method == http.MethodGet && p == "/v1/platform/distill/shadow/pairs":
			wsID, tag := r.URL.Query().Get("workspace_id"), r.URL.Query().Get("task_tag")
			mu.Lock()
			matched := []ShadowDistillPairRecord{}
			for _, pr := range pairs {
				if pr.WorkspaceID == wsID && (tag == "" || pr.TaskTag == tag) {
					matched = append(matched, pr)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(ShadowPairListResponse{WorkspaceID: wsID, Count: len(matched), Pairs: matched})

		case r.Method == http.MethodGet && p == "/v1/platform/distill/cache/stats":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			entries, hits, cost, ms, dlp, tot := 0, 0, 0.0, 0.0, 0, lookups[wsID]
			for _, c := range cache {
				if c.wsID == wsID {
					entries, hits, cost, ms, dlp = entries+1, hits+c.hits, cost+c.costSaved, ms+c.msSaved, dlp+c.redactions
				}
			}
			mu.Unlock()
			rate := 0.0
			if tot > 0 {
				rate = float64(hits) / float64(tot)
			}
			_ = json.NewEncoder(w).Encode(SemanticCacheStatsResponse{
				WorkspaceID: wsID, EntryCount: entries, TotalHits: hits, TotalLookups: tot,
				HitRate: rate, TotalCostSavedUSD: cost, TotalLatencySavedMS: ms, TotalDLPRedactions: dlp,
			})

		case r.Method == http.MethodPost && p == "/v1/platform/distill/datasets/compile":
			wsID, tag := body["workspace_id"].(string), body["task_tag"].(string)
			fmtKind, baseModel := body["export_format"].(string), body["target_base_model"].(string)
			mu.Lock()
			cnt := 0
			for _, pr := range pairs {
				if pr.WorkspaceID == wsID && (tag == "" || pr.TaskTag == tag) {
					cnt++
				}
			}
			preview := fmt.Sprintf(`{"format":%q,"records":%d}`, fmtKind, cnt)
			ds := DistillationDatasetRecord{
				DatasetID: fmt.Sprintf("qds-go-%d", len(datasets)+1), WorkspaceID: wsID, TaskTag: tag,
				ExportFormat: fmtKind, TargetBaseModel: baseModel, RecordCount: cnt, AvgParityScore: 0.94,
				LoraRank: 16, LoraAlpha: 32, JSONLPreview: preview, DatasetSHA256: sha256String(preview), CreatedAt: "2026-11-16T03:01:00Z",
			}
			datasets = append([]DistillationDatasetRecord{ds}, datasets...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(ds)

		case r.Method == http.MethodGet && p == "/v1/platform/distill/datasets":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []DistillationDatasetRecord{}
			for _, d := range datasets {
				if d.WorkspaceID == wsID {
					matched = append(matched, d)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(DistillationDatasetListResponse{WorkspaceID: wsID, Count: len(matched), Datasets: matched})

		case r.Method == http.MethodPost && p == "/v1/platform/distill/promotion/evaluate":
			wsID, tag, model := body["workspace_id"].(string), body["task_tag"].(string), body["target_local_model"].(string)
			minP, minAvg, vol := int(body["min_pairs"].(float64)), body["min_avg_parity"].(float64), int(body["monthly_request_volume"].(float64))
			mu.Lock()
			cnt := 0
			for _, pr := range pairs {
				if pr.WorkspaceID == wsID && pr.TaskTag == tag {
					cnt++
				}
			}
			mu.Unlock()
			verdict, savings := "PROMOTE_TO_OPENCORE", float64(vol)*0.018
			if cnt < minP {
				verdict, savings = "NEEDS_MORE_PAIRS", 0
			}
			_ = json.NewEncoder(w).Encode(DistillationPromotionEvaluation{
				EvaluationID: "pgate-go-1", WorkspaceID: wsID, TaskTag: tag, TargetLocalModel: model,
				Verdict: verdict, PairCount: cnt, MinPairs: minP, AvgParityScore: 0.94, MinAvgParity: minAvg,
				AvgFrontierCostUSD: 0.018, MonthlyRequestVolume: vol, ProjectedMonthlySavingsUSD: savings,
				Recommendation: verdict, GateSHA256: sha256String(verdict), EvaluatedAt: "2026-11-16T03:02:00Z",
			})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c, ctx := NewClient(srv.URL, WithAPIKey("kw_live_go_p19")), context.Background()

	if _, err := c.Platform.CompileDistillationDataset(ctx, CompileDistillationDatasetRequest{ExportFormat: "parquet"}); err == nil {
		t.Fatal("expected invalid export_format error")
	}
	if _, err := c.Platform.ListShadowPairs(ctx, "ws-go-19", "", -1); err == nil {
		t.Fatal("expected negative limit error")
	}
	if _, err := c.Platform.EvaluateShadowPrompt(ctx, EvaluateShadowPromptRequest{SimilarityThreshold: 1.5}); err == nil {
		t.Fatal("expected invalid similarity_threshold error")
	}

	miss, err := c.EvaluateShadowPrompt(ctx, EvaluateShadowPromptRequest{WorkspaceID: "ws-go-19", TaskTag: "sql-gen", Prompt: "Build SQL report with sk-live-secret19"})
	if err != nil || miss.Verdict != "LOCAL_PARITY_READY" || strings.Contains(miss.ScrubbedPrompt, "sk-live-secret19") {
		t.Fatalf("EvaluateShadowPrompt miss failed: %+v, err=%v", miss, err)
	}
	if otherWs, err := c.EvaluateShadowPrompt(ctx, EvaluateShadowPromptRequest{WorkspaceID: "ws-other", TaskTag: "sql-gen", Prompt: "Build SQL report with sk-live-secret19"}); err != nil || otherWs.Verdict == "CACHE_HIT" {
		t.Fatalf("expected cross-workspace cache isolation, got %+v, err=%v", otherWs, err)
	}
	if hit, err := c.EvaluateShadowPrompt(ctx, EvaluateShadowPromptRequest{WorkspaceID: "ws-go-19", TaskTag: "sql-gen", Prompt: "build sql report with sk-live-secret19!"}); err != nil || hit.Verdict != "CACHE_HIT" {
		t.Fatalf("expected semantic shingle CACHE_HIT, got %+v, err=%v", hit, err)
	}
	if stats, err := c.GetSemanticCacheStats(ctx, "ws-go-19"); err != nil || stats.TotalHits != 1 {
		t.Fatalf("GetSemanticCacheStats failed: %+v, err=%v", stats, err)
	}
	if needsMore, err := c.EvaluateDistillationPromotion(ctx, EvaluateDistillationPromotionRequest{WorkspaceID: "ws-go-19", TaskTag: "sql-gen", MinPairs: 2}); err != nil || needsMore.Verdict != "NEEDS_MORE_PAIRS" {
		t.Fatalf("expected NEEDS_MORE_PAIRS, got %+v, err=%v", needsMore, err)
	}
	if _, err := c.EvaluateShadowPrompt(ctx, EvaluateShadowPromptRequest{WorkspaceID: "ws-go-19", TaskTag: "sql-gen", Prompt: "Aggregate cohort retention SQL", BypassCache: true}); err != nil {
		t.Fatalf("second shadow prompt failed: %v", err)
	}
	if listedPairs, err := c.ListShadowPairs(ctx, "ws-go-19", "sql-gen", 10); err != nil || listedPairs.Count != 2 {
		t.Fatalf("ListShadowPairs failed: %+v, err=%v", listedPairs, err)
	}
	if ds, err := c.CompileDistillationDataset(ctx, CompileDistillationDatasetRequest{WorkspaceID: "ws-go-19", TaskTag: "sql-gen", ExportFormat: "sft_jsonl"}); err != nil || ds.RecordCount != 2 {
		t.Fatalf("CompileDistillationDataset failed: %+v, err=%v", ds, err)
	}
	if dsList, err := c.ListDistillationDatasets(ctx, "ws-go-19", 10); err != nil || dsList.Count != 1 {
		t.Fatalf("ListDistillationDatasets failed: %+v, err=%v", dsList, err)
	}
	if promo, err := c.EvaluateDistillationPromotion(ctx, EvaluateDistillationPromotionRequest{WorkspaceID: "ws-go-19", TaskTag: "sql-gen", MinPairs: 2}); err != nil || promo.Verdict != "PROMOTE_TO_OPENCORE" || promo.ProjectedMonthlySavingsUSD <= 0 {
		t.Fatalf("EvaluateDistillationPromotion failed: %+v, err=%v", promo, err)
	}

	auditorClient := NewClient(srv.URL, WithAPIKey("kw_live_go_p19"), WithHeader("X-Keelway-Role", "auditor"))
	_, denyErr := auditorClient.EvaluateShadowPrompt(ctx, EvaluateShadowPromptRequest{WorkspaceID: "ws-go-19"})
	var apiErr *APIError
	if !errors.As(denyErr, &apiErr) || apiErr.StatusCode != http.StatusForbidden {
		t.Fatalf("expected 403 APIError for auditor role, got %v", denyErr)
	}
}
