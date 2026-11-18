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

func TestPlatformPhase15CyclicKFlowAndAutopilot(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var runs []CyclicKFlowRunRecord
	var sims []AutopilotSimulationRecord

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p15" {
			t.Errorf("expected Bearer kw_live_go_p15, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/kflow/cyclic/validate":
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			_ = json.NewEncoder(w).Encode(CyclicKFlowValidationResponse{
				WorkspaceID: wsID, WorkflowID: wfID, Valid: true, NodeCount: 3, LoopEdgeCount: 1,
				MaxWorstCaseSteps: 7, TopologicalSpine: []string{"draft_patch", "critic_verify", "publish_release"},
				CompensationHandlers: []string{"revert_worktree", "discard_candidate", "rollback_tag"},
				SpecSHA256:           strings.Repeat("a", 64),
			})

		case r.Method == http.MethodPost && p == "/v1/platform/kflow/cyclic/execute":
			rawState, _ := json.Marshal(body["initial_state"])
			if strings.Contains(string(rawState), "sk-live-secret123456") {
				w.WriteHeader(http.StatusUnprocessableEntity)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "DLP secret rejected in initial_state", "code": "policy_violation"})
				return
			}
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			timedOut, _ := body["simulate_timeout"].(bool)
			thr, _ := body["critic_threshold"].(float64)
			shards := 3
			if rawShards, ok := body["fan_out_shards"].(float64); ok {
				shards = int(rawShards)
			}
			maxIter := 3
			if rawMax, ok := body["max_iterations_override"].(float64); ok {
				maxIter = int(rawMax)
			}
			status := "CONVERGED"
			var compLog []CyclicCompensationLogEntry
			if timedOut {
				status = "COMPENSATED"
				compLog = []CyclicCompensationLogEntry{{NodeID: "draft_patch", Handler: "revert_worktree", Reason: "timeout_exceeded", Status: "ROLLED_BACK"}}
			}
			mu.Lock()
			rec := CyclicKFlowRunRecord{
				RunID: fmt.Sprintf("cyc-go-%d", len(runs)+1), WorkspaceID: wsID, WorkflowID: wfID,
				Status: status, IterationsExecuted: 2, MaxIterations: maxIter, Converged: !timedOut,
				FinalCriticScore: 0.90, CriticThreshold: thr, FanOutShards: shards,
				TotalCostUSD: 0.16, TotalLatencyMS: 1260,
				IterationTrace:  []CyclicIterationTraceEntry{{Iteration: 1, NodeID: "draft_patch", AgentID: "code-synthesizer", Model: "claude-3-7-sonnet", CriticScore: 0.74, ShardCount: shards, Status: "COMPLETED", CostUSD: 0.045, LatencyMS: 340}},
				CompensationLog: compLog, RunSHA256: strings.Repeat("b", 64), CreatedAt: "2026-11-15T23:00:00Z",
			}
			runs = append([]CyclicKFlowRunRecord{rec}, runs...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/kflow/cyclic/runs":
			wsID, wfID := r.URL.Query().Get("workspace_id"), r.URL.Query().Get("workflow_id")
			mu.Lock()
			matched := []CyclicKFlowRunRecord{}
			for _, rRec := range runs {
				if rRec.WorkspaceID == wsID && (wfID == "" || rRec.WorkflowID == wfID) {
					matched = append(matched, rRec)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(CyclicKFlowRunListResponse{WorkspaceID: wsID, Count: len(matched), Runs: matched})

		case r.Method == http.MethodGet && strings.HasPrefix(p, "/v1/platform/kflow/cyclic/runs/"):
			runID, wsID := strings.TrimPrefix(p, "/v1/platform/kflow/cyclic/runs/"), r.URL.Query().Get("workspace_id")
			mu.Lock()
			var found *CyclicKFlowRunRecord
			for i := range runs {
				if runs[i].RunID == runID && runs[i].WorkspaceID == wsID {
					cp := runs[i]
					found = &cp
					break
				}
			}
			mu.Unlock()
			if found == nil {
				w.WriteHeader(http.StatusNotFound)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Cyclic KFlow run not found"})
				return
			}
			_ = json.NewEncoder(w).Encode(found)

		case r.Method == http.MethodPost && p == "/v1/platform/kflow/autopilot/simulate":
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			policy, _ := body["privacy_policy"].(string)
			budgetCap, _ := body["budget_cap_usd"].(float64)
			mult := int(body["expected_loop_multiplier"].(float64))
			mu.Lock()
			sim := AutopilotSimulationRecord{
				SimulationID: fmt.Sprintf("apsim-go-%d", len(sims)+1), WorkspaceID: wsID, WorkflowID: wfID,
				PrivacyPolicy: policy, BudgetCapUSD: budgetCap, ExpectedLoopMultiplier: mult,
				BaselineP50USD: 0.08, BaselineP95USD: 0.16, BaselineTTFTMS: 765,
				OptimizedP50USD: 0.0, OptimizedP95USD: 0.0, SavingsPct: 100.0, OptimizedTTFTMS: 405,
				PrivacyCompliant: true, ViolationsResolved: 2,
				NodePlan:         []AutopilotNodePlanEntry{{NodeID: "draft_patch", OriginalModel: "claude-3-7-sonnet", SelectedModel: "qwen2.5-coder:7b", Rewritten: true, Reason: "airgap_strict", DataBoundary: "local_metal_zero_egress"}},
				SimulationSHA256: strings.Repeat("c", 64), CreatedAt: "2026-11-15T23:01:00Z",
			}
			sims = append([]AutopilotSimulationRecord{sim}, sims...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(sim)

		case r.Method == http.MethodGet && p == "/v1/platform/kflow/autopilot/simulations":
			wsID, wfID := r.URL.Query().Get("workspace_id"), r.URL.Query().Get("workflow_id")
			mu.Lock()
			matched := []AutopilotSimulationRecord{}
			for _, s := range sims {
				if s.WorkspaceID == wsID && (wfID == "" || s.WorkflowID == wfID) {
					matched = append(matched, s)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(AutopilotSimulationListResponse{WorkspaceID: wsID, Count: len(matched), Simulations: matched})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p15"))
	ctx := context.Background()

	if _, err := c.Platform.ExecuteCyclicKFlow(ctx, ExecuteCyclicKFlowRequest{MaxIterationsOverride: IntPtr(0)}); err == nil {
		t.Fatal("expected invalid max_iterations_override error")
	}
	if _, err := c.Platform.ExecuteCyclicKFlow(ctx, ExecuteCyclicKFlowRequest{FanOutShards: IntPtr(99)}); err == nil {
		t.Fatal("expected invalid fan_out_shards error")
	}
	if _, err := c.Platform.SimulateKFlowAutopilot(ctx, SimulateKFlowAutopilotRequest{PrivacyPolicy: "invalid_policy"}); err == nil {
		t.Fatal("expected invalid privacy_policy error")
	}
	if _, err := c.Platform.GetCyclicKFlowRun(ctx, "   ", "ws-go-15"); err == nil {
		t.Fatal("expected empty runID error")
	}

	val, err := c.Platform.ValidateCyclicKFlow(ctx, ValidateCyclicKFlowRequest{WorkspaceID: "ws-go-15", WorkflowID: "WF-GO-15"})
	if err != nil || !val.Valid || len(val.SpecSHA256) != 64 {
		t.Fatalf("ValidateCyclicKFlow failed: %+v, err=%v", val, err)
	}

	runOK, err := c.Platform.ExecuteCyclicKFlow(ctx, ExecuteCyclicKFlowRequest{
		WorkspaceID: "ws-go-15", WorkflowID: "WF-GO-15", CriticThreshold: Float64Ptr(0.85), FanOutShards: IntPtr(4),
	})
	if err != nil || runOK.Status != "CONVERGED" || !runOK.Converged || runOK.FanOutShards != 4 {
		t.Fatalf("ExecuteCyclicKFlow converged failed: %+v, err=%v", runOK, err)
	}

	runComp, err := c.Platform.ExecuteCyclicKFlow(ctx, ExecuteCyclicKFlowRequest{
		WorkspaceID: "ws-go-15", WorkflowID: "WF-GO-15", SimulateTimeout: true,
	})
	if err != nil || runComp.Status != "COMPENSATED" || len(runComp.CompensationLog) != 1 {
		t.Fatalf("ExecuteCyclicKFlow compensated failed: %+v, err=%v", runComp, err)
	}

	if gotRun, err := c.Platform.GetCyclicKFlowRun(ctx, runOK.RunID, "ws-go-15"); err != nil || gotRun.RunID != runOK.RunID {
		t.Fatalf("GetCyclicKFlowRun failed: %+v, err=%v", gotRun, err)
	}

	_, notFoundErr := c.Platform.GetCyclicKFlowRun(ctx, "cyc-missing", "ws-go-15")
	var apiErr *APIError
	if !errors.As(notFoundErr, &apiErr) || apiErr.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 APIError on missing run, got %v", notFoundErr)
	}

	_, dlpErr := c.Platform.ExecuteCyclicKFlow(ctx, ExecuteCyclicKFlowRequest{
		WorkspaceID: "ws-go-15", InitialState: map[string]any{"token": "sk-live-secret123456"},
	})
	if !errors.As(dlpErr, &apiErr) || apiErr.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422 APIError on DLP initial_state, got %v", dlpErr)
	}

	if listed, err := c.Platform.ListCyclicKFlowRuns(ctx, ListCyclicKFlowRunsParams{WorkspaceID: "ws-go-15", WorkflowID: "WF-GO-15", Limit: 10}); err != nil || listed.Count != 2 {
		t.Fatalf("ListCyclicKFlowRuns failed: %+v, err=%v", listed, err)
	}

	sim, err := c.Platform.SimulateKFlowAutopilot(ctx, SimulateKFlowAutopilotRequest{
		WorkspaceID: "ws-go-15", WorkflowID: "WF-GO-15", BudgetCapUSD: Float64Ptr(0.10), PrivacyPolicy: "airgap_strict", ExpectedLoopMultiplier: 3,
	})
	if err != nil || !sim.PrivacyCompliant || sim.OptimizedP95USD != 0.0 || len(sim.SimulationSHA256) != 64 {
		t.Fatalf("SimulateKFlowAutopilot failed: %+v, err=%v", sim, err)
	}

	if simList, err := c.Platform.ListKFlowAutopilotSimulations(ctx, ListAutopilotSimulationsParams{WorkspaceID: "ws-go-15", WorkflowID: "WF-GO-15", Limit: 5}); err != nil || simList.Count != 1 {
		t.Fatalf("ListKFlowAutopilotSimulations failed: %+v, err=%v", simList, err)
	}
}
