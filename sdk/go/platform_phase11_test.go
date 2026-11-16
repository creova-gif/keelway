package keelway

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestPlatformPhase11DevxFlightTapesEvalAndMigration(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var recorded []map[string]any
	tapes := make(map[string]FlightTapeRecord)
	cases := make(map[string]EvalDatasetCase)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p11" {
			t.Errorf("expected Bearer kw_live_go_p11, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		mu.Lock()
		recorded = append(recorded, map[string]any{
			"method": r.Method,
			"path":   r.URL.Path,
			"query":  r.URL.Query(),
			"body":   body,
		})
		mu.Unlock()

		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/traces/ingest":
			wsID, _ := body["workspace_id"].(string)
			wfName, _ := body["workflow_name"].(string)
			srcFw, _ := body["source_framework"].(string)
			tid, _ := body["trace_id"].(string)
			rawSpans, _ := body["spans"].([]any)
			mu.Lock()
			if tid == "" {
				tid = "ft_go_" + strings.Repeat("1", len(tapes)+1)
			}
			var steps []FlightTapeStep
			for idx, item := range rawSpans {
				m, _ := item.(map[string]any)
				name, _ := m["name"].(string)
				steps = append(steps, FlightTapeStep{
					StepIndex:  idx,
					Name:       name,
					Model:      "keelway-core:7b",
					Prompt:     "Analyze node health",
					Output:     "All nodes healthy.",
					StepSHA256: strings.Repeat("a", 64),
				})
			}
			rec := FlightTapeRecord{
				TraceID:         tid,
				WorkspaceID:     wsID,
				WorkflowName:    wfName,
				SourceFramework: srcFw,
				SpanCount:       len(rawSpans),
				StepCount:       len(steps),
				Steps:           steps,
				TapeSHA256:      strings.Repeat("b", 64),
				Status:          "recorded",
			}
			tapes[tid] = rec
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/traces":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			var list []FlightTapeRecord
			for _, rec := range tapes {
				if rec.WorkspaceID == wsID {
					list = append(list, rec)
				}
			}
			mu.Unlock()
			if list == nil {
				list = []FlightTapeRecord{}
			}
			_ = json.NewEncoder(w).Encode(FlightTapeListResponse{
				WorkspaceID: wsID,
				Total:       len(list),
				Tapes:       list,
			})

		case r.Method == http.MethodPost && strings.HasPrefix(p, "/v1/platform/traces/") && strings.HasSuffix(p, "/replay"):
			tid := strings.TrimSuffix(strings.TrimPrefix(p, "/v1/platform/traces/"), "/replay")
			mu.Lock()
			orig, ok := tapes[tid]
			if !ok {
				mu.Unlock()
				http.NotFound(w, r)
				return
			}
			fromIdx := 0
			if rawIdx, ok := body["from_step_index"].(float64); ok {
				fromIdx = int(rawIdx)
			}
			forkID := tid + "_fork"
			stepsCopy := append([]FlightTapeStep(nil), orig.Steps...)
			if len(stepsCopy) > fromIdx {
				if ovModel, ok := body["override_model"].(string); ok && ovModel != "" {
					stepsCopy[fromIdx].Model = ovModel
				}
				if ovPrompt, ok := body["override_prompt"].(string); ok && ovPrompt != "" {
					stepsCopy[fromIdx].Prompt = ovPrompt
				}
			}
			forked := FlightTapeRecord{
				TraceID:             forkID,
				WorkspaceID:         orig.WorkspaceID,
				WorkflowName:        orig.WorkflowName,
				SourceFramework:     orig.SourceFramework,
				ForkedFromTraceID:   tid,
				ForkedFromStepIndex: &fromIdx,
				SpanCount:           orig.SpanCount,
				StepCount:           len(stepsCopy),
				Steps:               stepsCopy,
				TapeSHA256:          strings.Repeat("c", 64),
				Status:              "replayed_fork",
			}
			tapes[forkID] = forked
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(forked)

		case r.Method == http.MethodPost && p == "/v1/platform/eval/dataset/promote":
			tid, _ := body["trace_id"].(string)
			wsID, _ := body["workspace_id"].(string)
			title, _ := body["title"].(string)
			mu.Lock()
			if _, ok := tapes[tid]; !ok {
				mu.Unlock()
				http.NotFound(w, r)
				return
			}
			cid := "case_go_1"
			item := EvalDatasetCase{
				CaseID:              cid,
				ID:                  cid,
				WorkspaceID:         wsID,
				SourceTraceID:       tid,
				Title:               title,
				ExpectedSubstrings:  []string{"healthy"},
				ForbiddenSubstrings: []string{"panic"},
				CaseSHA256:          strings.Repeat("d", 64),
			}
			cases[cid] = item
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(item)

		case r.Method == http.MethodGet && p == "/v1/platform/eval/dataset":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			var list []EvalDatasetCase
			for _, c := range cases {
				if c.WorkspaceID == wsID {
					list = append(list, c)
				}
			}
			mu.Unlock()
			if list == nil {
				list = []EvalDatasetCase{}
			}
			_ = json.NewEncoder(w).Encode(EvalDatasetListResponse{
				WorkspaceID: wsID,
				Total:       len(list),
				Cases:       list,
			})

		case r.Method == http.MethodPost && p == "/v1/platform/migrate/langgraph":
			src, _ := body["source_code"].(string)
			if strings.Contains(src, "eval(") {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Dynamic eval rejected by static AST importer"})
				return
			}
			wsID, _ := body["workspace_id"].(string)
			wfName, _ := body["workflow_name"].(string)
			lang, _ := body["source_language"].(string)
			_ = json.NewEncoder(w).Encode(LanggraphMigrationResult{
				WorkspaceID:      wsID,
				WorkflowID:       "wf_go_migrated",
				WorkflowName:     wfName,
				SourceFramework:  "langgraph",
				SourceLanguage:   lang,
				Nodes:            []map[string]any{{"id": "triage", "requires_p10": false}, {"id": "mutate", "requires_p10": true}},
				Edges:            []map[string]any{{"from": "triage", "to": "mutate"}},
				P10GatesInjected: 1,
				ASTDigestSHA256:  strings.Repeat("e", 64),
			})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p11"))
	ctx := context.Background()

	tape, err := c.IngestOtelTraces(ctx, IngestOtelTracesRequest{
		WorkspaceID:     "ws-go-11",
		WorkflowName:    "cluster-check",
		SourceFramework: "opentelemetry_genai",
		TraceID:         "trace_go_01",
		Spans: []map[string]any{
			{"span_id": "sp_1", "name": "gen_ai.chat"},
		},
	})
	if err != nil || tape.TraceID != "trace_go_01" || len(tape.TapeSHA256) != 64 {
		t.Fatalf("IngestOtelTraces failed: %+v, err=%v", tape, err)
	}

	listed, err := c.Platform.ListFlightTapes(ctx, "ws-go-11", 15)
	if err != nil || listed.Total != 1 || len(listed.Tapes) != 1 {
		t.Fatalf("ListFlightTapes failed: %+v, err=%v", listed, err)
	}

	if _, err := c.ReplayFlightTape(ctx, "   ", ReplayFlightTapeRequest{}); err == nil {
		t.Fatal("expected non-empty traceID error")
	}

	forked, err := c.ReplayFlightTape(ctx, "trace_go_01", ReplayFlightTapeRequest{
		WorkspaceID:    "ws-go-11",
		FromStepIndex:  0,
		OverrideModel:  "keelway-coder:7b",
		OverridePrompt: "Verify cluster health strictly",
		OverrideState:  map[string]any{"strict": true},
	})
	if err != nil || forked.ForkedFromTraceID != "trace_go_01" || forked.Steps[0].Model != "keelway-coder:7b" {
		t.Fatalf("ReplayFlightTape failed: %+v, err=%v", forked, err)
	}

	if _, err := c.PromoteTraceToEval(ctx, PromoteTraceToEvalRequest{TraceID: ""}); err == nil {
		t.Fatal("expected non-empty trace_id error")
	}

	promoted, err := c.PromoteTraceToEval(ctx, PromoteTraceToEvalRequest{
		WorkspaceID:         "ws-go-11",
		TraceID:             "trace_go_01",
		Title:               "Cluster health baseline",
		ExpectedSubstrings:  []string{"healthy"},
		ForbiddenSubstrings: []string{"panic"},
	})
	if err != nil || promoted.SourceTraceID != "trace_go_01" || len(promoted.CaseSHA256) != 64 {
		t.Fatalf("PromoteTraceToEval failed: %+v, err=%v", promoted, err)
	}

	ds, err := c.ListEvalDatasetCases(ctx, "ws-go-11")
	if err != nil || ds.Total != 1 || len(ds.Cases) != 1 {
		t.Fatalf("ListEvalDatasetCases failed: %+v, err=%v", ds, err)
	}

	if _, err := c.MigrateLanggraphSource(ctx, MigrateLanggraphRequest{SourceCode: "   "}); err == nil {
		t.Fatal("expected non-empty source_code error")
	}

	migrated, err := c.MigrateLanggraphSource(ctx, MigrateLanggraphRequest{
		WorkspaceID:    "ws-go-11",
		SourceCode:     "from langgraph.graph import StateGraph\ng = StateGraph(dict)\n",
		SourceLanguage: "python",
		WorkflowName:   "go-migrated-dag",
	})
	if err != nil || migrated.WorkflowName != "go-migrated-dag" || migrated.P10GatesInjected != 1 {
		t.Fatalf("MigrateLanggraphSource failed: %+v, err=%v", migrated, err)
	}

	_, badMigrateErr := c.Platform.MigrateLanggraphSource(ctx, MigrateLanggraphRequest{
		WorkspaceID: "ws-go-11",
		SourceCode:  "eval('bad')",
	})
	var apiErr *APIError
	if !errors.As(badMigrateErr, &apiErr) || apiErr.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 APIError for unsafe LangGraph source, got %v", badMigrateErr)
	}
}
