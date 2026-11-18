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

func TestPlatformPhase8KflowKspacesAndSbom(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var recorded []map[string]any

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p8" {
			t.Errorf("expected Bearer kw_live_go_p8, got %q", got)
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
		case r.Method == http.MethodPost && p == "/v1/platform/automation/workflows/execute":
			wfID, _ := body["workflow_id"].(string)
			if wfID == "WF-CYCLE" {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Cycle detected in KFlow DAG"})
				return
			}
			approved, _ := body["approved_node_ids"].([]any)
			status := "awaiting_p10"
			held := "deploy_prod"
			if len(approved) > 0 {
				status = "completed"
				held = ""
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"run_id":            "kflow-go-01",
				"workspace_id":      body["workspace_id"],
				"workflow_id":       wfID,
				"trigger":           body["trigger"],
				"status":            status,
				"held_node_id":      held,
				"topological_order": []string{"lint", "deploy_prod"},
				"waves":             [][]string{{"lint"}, {"deploy_prod"}},
				"tokens_used":       320,
				"token_budget":      body["token_budget"],
				"receipt_sha256":    "sha256:" + strings.Repeat("a", 64),
			})
		case r.Method == http.MethodGet && p == "/v1/platform/automation/runs":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"count":        1,
				"runs": []map[string]any{
					{"run_id": "kflow-go-01", "workflow_id": "WF-GO-01", "status": "completed"},
				},
			})
		case r.Method == http.MethodPost && p == "/v1/platform/kspaces/sync":
			ops, _ := body["operations"].([]any)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":        body["workspace_id"],
				"peer_id":             body["peer_id"],
				"applied_count":       len(ops),
				"vector_clock":        map[string]int64{"peer-1": 9},
				"active_keys_count":   len(ops),
				"state_digest_sha256": "sha256:" + strings.Repeat("b", 64),
				"entries": []map[string]any{
					{"namespace": "presence", "key": "peer-1", "value": "online", "lamport_ts": 9, "peer_id": "peer-1", "tombstone": false},
				},
			})
		case r.Method == http.MethodGet && p == "/v1/platform/kspaces/state":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":        r.URL.Query().Get("workspace_id"),
				"vector_clock":        map[string]int64{"peer-1": 9},
				"active_keys_count":   1,
				"state_digest_sha256": "sha256:" + strings.Repeat("b", 64),
				"entries": []map[string]any{
					{"namespace": "presence", "key": "peer-1", "value": "online", "lamport_ts": 9, "peer_id": "peer-1", "tombstone": false},
				},
			})
		case r.Method == http.MethodGet && p == "/v1/platform/security/sbom":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":         r.URL.Query().Get("workspace_id"),
				"verified":             true,
				"verification_status":  "VERIFIED",
				"bom_format":           "CycloneDX",
				"spec_version":         "1.5",
				"component_count":      2,
				"root_digest_sha256":   strings.Repeat("c", 64),
				"provenance_signature": strings.Repeat("d", 64),
				"manifest":             map[string]any{"bom_format": "CycloneDX"},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p8"))
	ctx := context.Background()

	_, cycleErr := c.Platform.ExecuteKflowDag(ctx, KflowDagExecuteRequest{WorkflowID: "WF-CYCLE"})
	var apiErr *APIError
	if !errors.As(cycleErr, &apiErr) || apiErr.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 APIError for cyclic DAG, got %v", cycleErr)
	}

	gated, err := c.Platform.ExecuteKflowDag(ctx, KflowDagExecuteRequest{
		WorkflowID: "WF-GO-01",
		Nodes: []map[string]any{
			{"id": "lint", "kind": "agent"},
			{"id": "deploy_prod", "kind": "p10_gate", "depends_on": []string{"lint"}, "requires_p10": true},
		},
	})
	if err != nil || gated.Status != "awaiting_p10" || gated.TokenBudget != 25000 || gated.HeldNodeID != "deploy_prod" {
		t.Fatalf("ExecuteKflowDag gated failed: %+v, err=%v", gated, err)
	}

	done, err := c.Platform.ExecuteKflowDag(ctx, KflowDagExecuteRequest{
		WorkflowID:      "WF-GO-01",
		WorkspaceID:     "ws-go-8",
		Trigger:         "schedule",
		TokenBudget:     4096,
		ApprovedNodeIDs: []string{"deploy_prod"},
	})
	if err != nil || done.Status != "completed" || done.WorkspaceID != "ws-go-8" {
		t.Fatalf("ExecuteKflowDag approved failed: %+v, err=%v", done, err)
	}

	runs, err := c.Platform.ListKflowRuns(ctx, KflowRunListParams{WorkspaceID: "ws-go-8", WorkflowID: "WF-GO-01", Limit: 5})
	if err != nil || runs.Count != 1 || runs.Runs[0].RunID != "kflow-go-01" {
		t.Fatalf("ListKflowRuns failed: %+v, err=%v", runs, err)
	}

	syncRes, err := c.Platform.SyncKspacesCrdt(ctx, KspacesCrdtSyncRequest{
		WorkspaceID: "ws-go-8",
		PeerID:      "peer-1",
		Operations:  []KspacesCrdtOperation{{Namespace: "presence", Key: "peer-1", Value: "online", LamportTS: 9}},
	})
	if err != nil || syncRes.AppliedCount != 1 || syncRes.ActiveKeysCount != 1 {
		t.Fatalf("SyncKspacesCrdt failed: %+v, err=%v", syncRes, err)
	}

	state, err := c.Platform.GetKspacesState(ctx, "ws-go-8", "presence")
	if err != nil || len(state.Entries) != 1 || state.Entries[0].Value != "online" {
		t.Fatalf("GetKspacesState failed: %+v, err=%v", state, err)
	}

	sbom, err := c.Platform.GetPlatformSbom(ctx, "")
	if err != nil || !sbom.Verified || sbom.BomFormat != "CycloneDX" || sbom.WorkspaceID != "default" {
		t.Fatalf("GetPlatformSbom failed: %+v, err=%v", sbom, err)
	}

	mu.Lock()
	defer mu.Unlock()
	execBody := recorded[1]["body"].(map[string]any)
	if approvedSlice, ok := execBody["approved_node_ids"].([]any); !ok || len(approvedSlice) != 0 {
		t.Fatalf("expected non-nil empty approved_node_ids slice, got %#v", execBody["approved_node_ids"])
	}
}
