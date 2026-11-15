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

func TestPlatformPhase14StepDebuggerBreakpointsAndCodeLens(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var breakpoints []DebuggerBreakpointRecord
	var sessions []DebuggerSessionRecord

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p14" {
			t.Errorf("expected Bearer kw_live_go_p14, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/debugger/breakpoints":
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			nodeID, _ := body["node_id"].(string)
			filePath, _ := body["file_path"].(string)
			condType, _ := body["condition_type"].(string)
			enabled, _ := body["enabled"].(bool)
			var linePtr *int
			if rawLine, ok := body["line_number"].(float64); ok {
				ln := int(rawLine)
				linePtr = &ln
			}
			var thrPtr *float64
			if rawThr, ok := body["threshold"].(float64); ok {
				thr := rawThr
				thrPtr = &thr
			}
			mu.Lock()
			rec := DebuggerBreakpointRecord{
				BreakpointID: fmt.Sprintf("bp-go-%d", len(breakpoints)+1), WorkspaceID: wsID, WorkflowID: wfID,
				NodeID: nodeID, FilePath: filePath, LineNumber: linePtr, ConditionType: condType,
				Threshold: thrPtr, Enabled: enabled, Label: condType, CreatedAt: "2026-11-15T22:00:00Z",
			}
			breakpoints = append(breakpoints, rec)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/debugger/breakpoints":
			wsID, wfID := r.URL.Query().Get("workspace_id"), r.URL.Query().Get("workflow_id")
			mu.Lock()
			matched := []DebuggerBreakpointRecord{}
			for _, bp := range breakpoints {
				if bp.WorkspaceID == wsID && (wfID == "" || bp.WorkflowID == wfID) {
					matched = append(matched, bp)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(DebuggerBreakpointListResponse{WorkspaceID: wsID, Count: len(matched), Breakpoints: matched})

		case r.Method == http.MethodDelete && strings.HasPrefix(p, "/v1/platform/debugger/breakpoints/"):
			bpID, wsID := strings.TrimPrefix(p, "/v1/platform/debugger/breakpoints/"), r.URL.Query().Get("workspace_id")
			mu.Lock()
			found := -1
			for idx, bp := range breakpoints {
				if bp.BreakpointID == bpID && bp.WorkspaceID == wsID {
					found = idx
					break
				}
			}
			if found >= 0 {
				breakpoints = append(breakpoints[:found], breakpoints[found+1:]...)
			}
			mu.Unlock()
			if found < 0 {
				w.WriteHeader(http.StatusNotFound)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Breakpoint not found"})
				return
			}
			_ = json.NewEncoder(w).Encode(DeleteBreakpointResponse{Deleted: true, BreakpointID: bpID, WorkspaceID: wsID})

		case r.Method == http.MethodPost && p == "/v1/platform/debugger/sessions":
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			initState, _ := body["initial_state"].(map[string]any)
			if initState == nil {
				initState = map[string]any{"dry_run": true}
			}
			mu.Lock()
			sess := DebuggerSessionRecord{
				SessionID: fmt.Sprintf("dbg-go-%d", len(sessions)+1), WorkspaceID: wsID, WorkflowID: wfID,
				Status: "PAUSED", CurrentStepIndex: 0, StepDepth: 0, TotalSteps: 3, HitReason: "always (step boundary)",
				ActiveStep: map[string]any{"node_id": "triage_claim", "line_number": 8},
				ActiveFrame: map[string]any{"node_id": "triage_claim", "line_number": 8},
				Variables: initState, CallStack: []map[string]any{{"depth": 0, "node_id": "triage_claim"}},
				Mutations: []map[string]any{}, FrameSHA256: strings.Repeat("d", 64), UpdatedAt: "2026-11-15T22:01:00Z",
			}
			sessions = append(sessions, sess)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(sess)

		case r.Method == http.MethodGet && p == "/v1/platform/debugger/sessions":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []DebuggerSessionRecord{}
			for _, s := range sessions {
				if s.WorkspaceID == wsID {
					matched = append(matched, s)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(DebuggerSessionListResponse{WorkspaceID: wsID, Count: len(matched), Sessions: matched})

		case r.Method == http.MethodPost && strings.HasPrefix(p, "/v1/platform/debugger/sessions/") && strings.HasSuffix(p, "/step"):
			sid := strings.TrimSuffix(strings.TrimPrefix(p, "/v1/platform/debugger/sessions/"), "/step")
			rawPatch, _ := json.Marshal(body["state_patch"])
			if strings.Contains(string(rawPatch), "sk-live-secret123456") {
				w.WriteHeader(http.StatusUnprocessableEntity)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "DLP secret rejected in state_patch"})
				return
			}
			action, _ := body["action"].(string)
			mu.Lock()
			var updated *DebuggerSessionRecord
			for i := range sessions {
				if sessions[i].SessionID == sid {
					if patch, ok := body["state_patch"].(map[string]any); ok {
						for k, v := range patch {
							sessions[i].Variables[k] = v
						}
						sessions[i].MutationCount++
					}
					if action == "step_into" {
						sessions[i].StepDepth = 1
					} else if action == "continue" {
						sessions[i].Status = "COMPLETED"
					} else if action == "step_over" {
						sessions[i].CurrentStepIndex++
					}
					cp := sessions[i]
					updated = &cp
					break
				}
			}
			mu.Unlock()
			if updated == nil {
				http.NotFound(w, r)
				return
			}
			_ = json.NewEncoder(w).Encode(updated)

		case r.Method == http.MethodGet && p == "/v1/platform/debugger/codelens":
			wsID := r.URL.Query().Get("workspace_id")
			wfID := firstString(r.URL.Query().Get("workflow_id"), "WF-STUDIO-01")
			fp := firstString(r.URL.Query().Get("file_path"), "workflows/refund_agent.py")
			_ = json.NewEncoder(w).Encode(DebuggerCodelensResponse{
				WorkspaceID: wsID, WorkflowID: wfID, FilePath: fp,
				VSCodeAttachURI: fmt.Sprintf("vscode://keelway.vscode-keelway/attach?port=7420&workspace=%s&workflow=%s", wsID, wfID),
				CursorAttachURI: fmt.Sprintf("cursor://keelway.vscode-keelway/attach?port=7420&workspace=%s&workflow=%s", wsID, wfID),
				Bridge:          map[string]any{"extension_id": "keelway.vscode-keelway"},
				Lenses:          []DebuggerCodelensItem{{Symbol: "triage_claim", FilePath: fp, LineStart: 8, Line: 8, ModelCheckpoint: "keelway-core:7b", P50MS: 142, P50LatencyMS: 142, Provenance4D: "Apache-2.0 · Local Metal · Self-Operated · Zero-Egress", AttachedBreakpoints: 1}},
			})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p14"))
	ctx := context.Background()

	if _, err := c.SetBreakpoint(ctx, SetBreakpointRequest{ConditionType: "bogus"}); err == nil {
		t.Fatal("expected invalid condition_type error")
	}
	if _, err := c.SetBreakpoint(ctx, SetBreakpointRequest{LineNumber: IntPtr(0)}); err == nil {
		t.Fatal("expected invalid line_number error")
	}

	bp, err := c.SetBreakpoint(ctx, SetBreakpointRequest{
		WorkspaceID: "ws-go-14", WorkflowID: "WF-GO-14", NodeID: "triage_claim",
		ConditionType: "cost_usd_gt", Threshold: Float64Ptr(0.25), LineNumber: IntPtr(8), Enabled: BoolPtr(true),
	})
	if err != nil || bp.ConditionType != "cost_usd_gt" || !bp.Enabled {
		t.Fatalf("SetBreakpoint failed: %+v, err=%v", bp, err)
	}
	if bpList, err := c.ListBreakpoints(ctx, "ws-go-14", "WF-GO-14"); err != nil || bpList.Count != 1 {
		t.Fatalf("ListBreakpoints failed: %+v, err=%v", bpList, err)
	}
	if lens, err := c.GetDebuggerCodelens(ctx, "ws-go-14", "WF-GO-14", "workflows/refund_agent.py"); err != nil || len(lens.Lenses) != 1 || !strings.HasPrefix(lens.CursorAttachURI, "cursor://") {
		t.Fatalf("GetDebuggerCodelens failed: %+v, err=%v", lens, err)
	}

	sess, err := c.StartDebugSession(ctx, StartDebugSessionRequest{
		WorkspaceID: "ws-go-14", WorkflowID: "WF-GO-14", InitialState: map[string]any{"claim_id": "CLM-14"},
	})
	if err != nil || sess.Status != "PAUSED" || len(sess.FrameSHA256) != 64 {
		t.Fatalf("StartDebugSession failed: %+v, err=%v", sess, err)
	}
	if _, err := c.StepDebugSession(ctx, sess.SessionID, StepDebugSessionRequest{Action: "invalid_step"}); err == nil {
		t.Fatal("expected invalid debugger action error")
	}
	mutated, err := c.StepDebugSession(ctx, sess.SessionID, StepDebugSessionRequest{
		WorkspaceID: "ws-go-14", Action: "mutate_state", StatePatch: map[string]any{"approved": true},
	})
	if err != nil || mutated.MutationCount != 1 {
		t.Fatalf("StepDebugSession mutate_state failed: %+v, err=%v", mutated, err)
	}

	_, dlpErr := c.Platform.StepDebugSession(ctx, sess.SessionID, StepDebugSessionRequest{
		WorkspaceID: "ws-go-14", Action: "mutate_state", StatePatch: map[string]any{"secret": "sk-live-secret123456"},
	})
	var apiErr *APIError
	if !errors.As(dlpErr, &apiErr) || apiErr.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422 APIError on DLP state_patch, got %v", dlpErr)
	}

	if done, err := c.StepDebugSession(ctx, sess.SessionID, StepDebugSessionRequest{WorkspaceID: "ws-go-14", Action: "continue"}); err != nil || done.Status != "COMPLETED" {
		t.Fatalf("StepDebugSession continue failed: %+v, err=%v", done, err)
	}
	if sessList, err := c.ListDebugSessions(ctx, "ws-go-14", 10); err != nil || sessList.Count != 1 {
		t.Fatalf("ListDebugSessions failed: %+v, err=%v", sessList, err)
	}
	if delRes, err := c.DeleteBreakpoint(ctx, bp.BreakpointID, "ws-go-14"); err != nil || !delRes.Deleted {
		t.Fatalf("DeleteBreakpoint failed: %+v, err=%v", delRes, err)
	}
}
