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

func TestPlatformPhase12StudioSyncBlastRadiusAndPromptGate(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var audits []BlastRadiusAuditRecord
	var gateRuns []PromptGateEvaluationResult

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p12" {
			t.Errorf("expected Bearer kw_live_go_p12, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/studio/kflow/sync":
			src, _ := body["source_code"].(string)
			if strings.Contains(src, "syntax_error(") {
				w.WriteHeader(http.StatusUnprocessableEntity)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Malformed syntax rejected by static AST parser"})
				return
			}
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			dir, _ := body["direction"].(string)
			lang, _ := body["language"].(string)
			persisted, _ := body["persist"].(bool)
			nodes := []StudioKflowNode{
				{
					ID: "plan", Label: "Plan", AgentID: "architect", DependsOn: []string{},
					RequiresP10: false, LineStart: 1, LineEnd: 5, Wave: 0, X: 80, Y: 120,
				},
				{
					ID: "deploy", Label: "Deploy", AgentID: "release-engineer", DependsOn: []string{"plan"},
					RequiresP10: true, LineStart: 7, LineEnd: 14, Wave: 1, X: 300, Y: 120,
				},
			}
			_ = json.NewEncoder(w).Encode(StudioKflowSyncResult{
				WorkspaceID:    wsID,
				WorkflowID:     wfID,
				Direction:      dir,
				Language:       lang,
				Nodes:          nodes,
				Edges:          []StudioKflowEdge{{From: "plan", To: "deploy", IsCycle: false}},
				CycleBackEdges: []StudioKflowCycleEdge{},
				P10LockedNodes: []string{"deploy"},
				SourceCode:     src,
				Persisted:      persisted,
				SyncSHA256:     strings.Repeat("a", 64),
			})

		case r.Method == http.MethodPost && p == "/v1/platform/studio/blast-radius/record":
			wsID, _ := body["workspace_id"].(string)
			tid, _ := body["trace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			seatbelted := true
			if sb, ok := body["seatbelted"].(bool); ok {
				seatbelted = sb
			}
			egress := 0
			if rawEg, ok := body["egress_attempts"].(float64); ok {
				egress = int(rawEg)
			}
			mu.Lock()
			rec := BlastRadiusAuditRecord{
				AuditID:              fmt.Sprintf("blast-go-%d", len(audits)+1),
				WorkspaceID:          wsID,
				TraceID:              tid,
				WorkflowID:           wfID,
				FSReads:              []string{"core/main.py"},
				FSWrites:             []string{"artifacts/out.json"},
				BlockedPaths:         []string{"/etc/shadow"},
				EgressAttempts:       egress,
				BlockedEgressHosts:   []string{"telemetry.invalid"},
				P10GatesTriggered:    1,
				Seatbelted:           seatbelted,
				ZeroUnapprovedEgress: true,
				SyscallsAudited:      9,
				RiskTier:             "contained",
				AuditSHA256:          strings.Repeat("b", 64),
				RecordedAt:           "2026-11-15T19:00:00Z",
			}
			audits = append(audits, rec)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/studio/blast-radius":
			wsID := r.URL.Query().Get("workspace_id")
			tid := r.URL.Query().Get("trace_id")
			mu.Lock()
			var matched []BlastRadiusAuditRecord
			for _, a := range audits {
				if a.WorkspaceID == wsID && (tid == "" || a.TraceID == tid) {
					matched = append(matched, a)
				}
			}
			mu.Unlock()
			if matched == nil {
				matched = []BlastRadiusAuditRecord{}
			}
			_ = json.NewEncoder(w).Encode(BlastRadiusAuditListResponse{
				WorkspaceID: wsID,
				Count:       len(matched),
				Audits:      matched,
			})

		case r.Method == http.MethodPost && p == "/v1/platform/studio/prompt-gate/evaluate":
			wsID, _ := body["workspace_id"].(string)
			ver, _ := body["candidate_prompt_version"].(string)
			modelID, _ := body["candidate_model_id"].(string)
			txt, _ := body["candidate_prompt_text"].(string)
			minRate := 0.9
			if rawMin, ok := body["min_pass_rate"].(float64); ok {
				minRate = rawMin
			}
			verdict := "PASS"
			dlp := 0
			passRate := 1.0
			if strings.Contains(txt, "AKIA_SECRET") {
				verdict = "BLOCK"
				dlp = 1
				passRate = 0.5
			}
			mu.Lock()
			run := PromptGateEvaluationResult{
				GateRunID:              fmt.Sprintf("pgate-go-%d", len(gateRuns)+1),
				WorkspaceID:            wsID,
				CandidatePromptVersion: ver,
				CandidateModelID:       modelID,
				Verdict:                verdict,
				CasesEvaluated:         4,
				PassedCases:            4 - dlp*2,
				PassRate:               passRate,
				MinPassRate:            minRate,
				SchemaValidCount:       4,
				DLPViolations:          dlp,
				CostDeltaUSD:           -0.001,
				DatasetSource:          "golden_eval_suite",
				GateSHA256:             strings.Repeat("c", 64),
				EvaluatedAt:            "2026-11-15T19:02:00Z",
			}
			gateRuns = append(gateRuns, run)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(run)

		case r.Method == http.MethodGet && p == "/v1/platform/studio/prompt-gate/runs":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			var matched []PromptGateEvaluationResult
			for _, run := range gateRuns {
				if run.WorkspaceID == wsID {
					matched = append(matched, run)
				}
			}
			mu.Unlock()
			if matched == nil {
				matched = []PromptGateEvaluationResult{}
			}
			_ = json.NewEncoder(w).Encode(PromptGateRunListResponse{
				WorkspaceID: wsID,
				Count:       len(matched),
				Runs:        matched,
			})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p12"))
	ctx := context.Background()

	if _, err := c.SyncKflowStudio(ctx, SyncKflowStudioRequest{Direction: "invalid"}); err == nil {
		t.Fatal("expected invalid direction error")
	}
	if _, err := c.SyncKflowStudio(ctx, SyncKflowStudioRequest{Language: "ruby"}); err == nil {
		t.Fatal("expected invalid language error")
	}

	syncRes, err := c.SyncKflowStudio(ctx, SyncKflowStudioRequest{
		WorkspaceID: "ws-go-12",
		Direction:   "graph_to_code",
		Language:    "typescript",
		WorkflowID:  "WF-GO-12",
		Nodes: []StudioKflowNodeInput{
			{ID: "plan", Label: "Plan", AgentID: "architect", RequiresP10: false},
			{ID: "deploy", Label: "Deploy", AgentID: "release-engineer", DependsOn: []string{"plan"}, RequiresP10: true},
		},
		Persist: BoolPtr(true),
	})
	if err != nil || !syncRes.Persisted || len(syncRes.SyncSHA256) != 64 || len(syncRes.P10LockedNodes) != 1 {
		t.Fatalf("SyncKflowStudio failed: %+v, err=%v", syncRes, err)
	}

	_, badSyncErr := c.Platform.SyncKflowStudio(ctx, SyncKflowStudioRequest{
		WorkspaceID: "ws-go-12",
		SourceCode:  "syntax_error(",
	})
	var apiErr *APIError
	if !errors.As(badSyncErr, &apiErr) || apiErr.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422 APIError for malformed studio source, got %v", badSyncErr)
	}

	if _, err := c.RecordBlastRadius(ctx, RecordBlastRadiusRequest{EgressAttempts: -1}); err == nil {
		t.Fatal("expected negative egress_attempts error")
	}

	audit, err := c.RecordBlastRadius(ctx, RecordBlastRadiusRequest{
		WorkspaceID:        "ws-go-12",
		TraceID:            "trace_go_12",
		WorkflowID:         "WF-GO-12",
		FSReads:            []string{"core/main.py"},
		FSWrites:           []string{"artifacts/out.json"},
		BlockedPaths:       []string{"/etc/shadow"},
		EgressAttempts:     1,
		BlockedEgressHosts: []string{"telemetry.invalid"},
		P10GatesTriggered:  1,
		Seatbelted:         BoolPtr(true),
	})
	if err != nil || !audit.ZeroUnapprovedEgress || len(audit.AuditSHA256) != 64 {
		t.Fatalf("RecordBlastRadius failed: %+v, err=%v", audit, err)
	}

	auditList, err := c.ListBlastRadiusAudits(ctx, "ws-go-12", "trace_go_12", 10)
	if err != nil || auditList.Count != 1 || len(auditList.Audits) != 1 {
		t.Fatalf("ListBlastRadiusAudits failed: %+v, err=%v", auditList, err)
	}

	if _, err := c.EvaluatePromptGate(ctx, EvaluatePromptGateRequest{CandidatePromptVersion: "", CandidateModelID: "m"}); err == nil {
		t.Fatal("expected empty candidate_prompt_version error")
	}
	if _, err := c.EvaluatePromptGate(ctx, EvaluatePromptGateRequest{CandidatePromptVersion: "p1", CandidateModelID: "m", MinPassRate: Float64Ptr(1.2)}); err == nil {
		t.Fatal("expected out-of-range min_pass_rate error")
	}

	gatePass, err := c.EvaluatePromptGate(ctx, EvaluatePromptGateRequest{
		WorkspaceID:            "ws-go-12",
		CandidatePromptVersion: "p-15",
		CandidateModelID:       "keelway-coder:7b",
		CandidatePromptText:    "Produce strict JSON summary.",
		RequiredJSONKeys:       []string{"summary", "status"},
		MinPassRate:            Float64Ptr(0.95),
	})
	if err != nil || gatePass.Verdict != "PASS" || len(gatePass.GateSHA256) != 64 {
		t.Fatalf("EvaluatePromptGate PASS failed: %+v, err=%v", gatePass, err)
	}

	gateBlock, err := c.Platform.EvaluatePromptGate(ctx, EvaluatePromptGateRequest{
		WorkspaceID:            "ws-go-12",
		CandidatePromptVersion: "p-16",
		CandidateModelID:       "keelway-coder:7b",
		CandidatePromptText:    "Leak AKIA_SECRET",
	})
	if err != nil || gateBlock.Verdict != "BLOCK" || gateBlock.DLPViolations != 1 {
		t.Fatalf("EvaluatePromptGate BLOCK failed: %+v, err=%v", gateBlock, err)
	}

	runs, err := c.ListPromptGateRuns(ctx, "ws-go-12", 10)
	if err != nil || runs.Count != 2 || len(runs.Runs) != 2 {
		t.Fatalf("ListPromptGateRuns failed: %+v, err=%v", runs, err)
	}
}
