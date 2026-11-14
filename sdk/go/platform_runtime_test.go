package keelway

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestPlatformPhase4DocsIssuesFeedbackAndSecurityScan(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p5" {
			t.Errorf("expected Bearer kw_live_go_p5, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodGet && p == "/v1/platform/docs":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"count":        1,
				"docs":         []map[string]any{{"id": "DOC-01", "title": "Architecture", "diataxis_kind": "explanation", "body": "# Arch"}},
			})
		case r.Method == http.MethodPost && p == "/v1/platform/docs":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": "DOC-02", "title": req["title"], "diataxis_kind": req["diataxis_kind"], "summary": req["summary"], "body": req["body"]})
		case r.Method == http.MethodPut && strings.HasPrefix(p, "/v1/platform/docs/"):
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": strings.TrimPrefix(p, "/v1/platform/docs/"), "title": req["title"], "diataxis_kind": req["diataxis_kind"], "body": req["body"]})
		case r.Method == http.MethodPatch && strings.HasPrefix(p, "/v1/platform/pm/issues/"):
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": strings.TrimPrefix(p, "/v1/platform/pm/issues/"), "title": "Updated Issue", "status": req["status"], "priority": req["priority"]})
		case r.Method == http.MethodGet && p == "/v1/platform/product/feedback":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"), "count": 1, "total": 1,
				"feedback": []map[string]any{{"id": "FB-01", "persona": "SecOps", "quote": "Great audit trail", "impact_score": 9.1}},
			})
		case r.Method == http.MethodPost && p == "/v1/platform/product/feedback":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": "FB-02", "persona": req["persona"], "quote": req["quote"], "impact_score": req["impact_score"]})
		case r.Method == http.MethodPost && p == "/v1/platform/security/scan":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			content, _ := req["content"].(string)
			passed := !strings.Contains(content, "sk-live-")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": req["workspace_id"], "target_name": req["target_name"], "passed": passed,
				"risk_grade": map[bool]string{true: "A", false: "BLOCKED"}[passed], "findings_count": map[bool]int{true: 0, false: 1}[passed], "findings": []map[string]any{},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p5"))
	ctx := context.Background()

	if docs, err := c.Platform.ListDocs(ctx, "ws-go"); err != nil || docs.Count != 1 || docs.Docs[0].ID != "DOC-01" {
		t.Fatalf("ListDocs failed: %+v, err=%v", docs, err)
	}
	if createdDoc, err := c.Platform.CreateDoc(ctx, DocUpsertRequest{Title: "Go SDK Guide", DiataxisKind: "tutorial", Summary: "Zero-dep", Body: "package main", WorkspaceID: "ws-go"}); err != nil || createdDoc.ID != "DOC-02" {
		t.Fatalf("CreateDoc failed: %+v, err=%v", createdDoc, err)
	}
	if updatedDoc, err := c.Platform.UpdateDoc(ctx, "DOC-02", DocUpsertRequest{Title: "Go SDK Guide v2", DiataxisKind: "tutorial", Body: "package keelway", WorkspaceID: "ws-go"}); err != nil || updatedDoc.Title != "Go SDK Guide v2" {
		t.Fatalf("UpdateDoc failed: %+v, err=%v", updatedDoc, err)
	}
	if updatedIssue, err := c.Platform.UpdateIssue(ctx, "ISS-42", IssuePatchRequest{WorkspaceID: "ws-go", Status: "done", Priority: "high"}); err != nil || updatedIssue.ID != "ISS-42" || updatedIssue.Status != "done" {
		t.Fatalf("UpdateIssue failed: %+v, err=%v", updatedIssue, err)
	}
	if fb, err := c.Platform.ListFeedback(ctx, "ws-go"); err != nil || fb.Total != 1 {
		t.Fatalf("ListFeedback failed: %+v, err=%v", fb, err)
	}
	if newFb, err := c.Platform.CreateFeedback(ctx, FeedbackCreateRequest{Persona: "Platform Lead", Quote: "Fast local WAL", ImpactScore: 9.4, WorkspaceID: "ws-go"}); err != nil || newFb.ID != "FB-02" {
		t.Fatalf("CreateFeedback failed: %+v, err=%v", newFb, err)
	}
	if scan, err := c.Platform.ScanWorkspaceSecurity(ctx, WorkspaceSecurityScanRequest{TargetName: "secrets.env", Content: "OPENAI_KEY=sk-live-leak123", WorkspaceID: "ws-go"}); err != nil || scan.Passed || scan.RiskGrade != "BLOCKED" {
		t.Fatalf("ScanWorkspaceSecurity failed: %+v, err=%v", scan, err)
	}
}

func TestPlatformPhase5WorkspacesRBACVaultWebhooksAndExecutionSSE(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		if r.Method == http.MethodGet && strings.HasSuffix(p, "/events") {
			if got := r.Header.Get("Accept"); got != "text/event-stream" {
				t.Errorf("expected Accept text/event-stream, got %q", got)
			}
			if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p5" {
				t.Errorf("expected Authorization header on SSE, got %q", got)
			}
			w.Header().Set("Content-Type", "text/event-stream")
			flusher, ok := w.(http.Flusher)
			if !ok {
				t.Fatal("ResponseWriter missing Flusher")
			}
			chunks := []string{
				": keep-alive\r\nevent: run.started\r\nda",
				"ta: {\"type\":\"run.started\",\"run_id\":\"run_go_1\",\"seq\":1}\r\n\r\n",
				"data: {\"type\":\"p10.he",
				"ld\",\"run_id\":\"run_go_1\",\"seq\":2,\"status\":\"awaiting_p10_approval\"}\n\n",
				"data: {\"type\":\"run.completed\",\"run_id\":\"run_go_1\",\"seq\":3,\"status\":\"completed\"}\n",
				"\ndata: [DO",
				"NE]\n\ndata: {\"type\":\"ignored\",\"seq\":99}\n\n",
			}
			for _, ch := range chunks {
				_, _ = w.Write([]byte(ch))
				flusher.Flush()
			}
			return
		}

		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && p == "/v1/platform/workspaces":
			_ = json.NewEncoder(w).Encode(map[string]any{"workspaces": []map[string]any{{"id": "default", "name": "Default", "branch": "main"}}, "total": 1})
		case r.Method == http.MethodPost && p == "/v1/platform/workspaces":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": req["id"], "name": req["name"], "branch": req["branch"], "isolation_mode": req["isolation_mode"]})
		case r.Method == http.MethodGet && p == "/v1/platform/rbac/members":
			_ = json.NewEncoder(w).Encode(map[string]any{"members": []map[string]any{{"actor_id": "usr_1", "role": "owner"}}, "roles": []string{"owner", "admin", "builder", "operator", "viewer"}})
		case r.Method == http.MethodPost && p == "/v1/platform/rbac/members":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			_ = json.NewEncoder(w).Encode(map[string]any{"actor_id": req["actor_id"], "role": req["role"], "workspace_id": req["workspace_id"]})
		case r.Method == http.MethodPost && p == "/v1/platform/rbac/check":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			allowed := req["role"] == "owner" || req["role"] == "admin"
			_ = json.NewEncoder(w).Encode(map[string]any{"allowed": allowed, "role": req["role"], "permission": req["permission"], "reason": "matrix_evaluated"})
		case r.Method == http.MethodGet && p == "/v1/platform/vault/secrets":
			_ = json.NewEncoder(w).Encode(map[string]any{"secrets": []map[string]any{{"name": "ANTHROPIC_KEY", "namespace": "byom", "masked_preview": "sk-a****7890", "fingerprint_sha256": "deadbeef", "version": 1}}, "total": 1})
		case r.Method == http.MethodPost && p == "/v1/platform/vault/secrets":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"name": req["name"], "namespace": req["namespace"], "masked_preview": "sk-a****7890", "fingerprint_sha256": "deadbeef", "version": 1})
		case r.Method == http.MethodPost && strings.HasSuffix(p, "/rotate"):
			_ = json.NewEncoder(w).Encode(map[string]any{"name": "ANTHROPIC_KEY", "namespace": "byom", "masked_preview": "sk-r****1111", "fingerprint_sha256": "cafebabe", "version": 2})
		case r.Method == http.MethodDelete && strings.HasPrefix(p, "/v1/platform/vault/secrets/"):
			_ = json.NewEncoder(w).Encode(map[string]any{"deleted": true, "name": "ANTHROPIC_KEY"})
		case r.Method == http.MethodGet && p == "/v1/platform/webhooks":
			_ = json.NewEncoder(w).Encode(map[string]any{"webhooks": []map[string]any{{"id": "wh_go_1", "url": "https://hooks.example.com/events", "events": []string{"*"}}}, "total": 1})
		case r.Method == http.MethodPost && p == "/v1/platform/webhooks":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			u, _ := req["url"].(string)
			if strings.Contains(u, "169.254.169.254") {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "SSRF blocked"})
				return
			}
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"id": "wh_go_2", "url": u, "events": req["events"]})
		case r.Method == http.MethodPost && strings.HasSuffix(p, "/test") && strings.HasPrefix(p, "/v1/platform/webhooks/"):
			_ = json.NewEncoder(w).Encode(map[string]any{"webhook_id": "wh_go_2", "signature": "sha256=abcdef", "delivered": true})
		case r.Method == http.MethodPost && p == "/v1/platform/webhooks/verify":
			_ = json.NewEncoder(w).Encode(map[string]any{"valid": true, "reason": "ok"})
		case r.Method == http.MethodDelete && strings.HasPrefix(p, "/v1/platform/webhooks/"):
			_ = json.NewEncoder(w).Encode(map[string]any{"deleted": true, "webhook_id": "wh_go_2"})
		case r.Method == http.MethodPost && p == "/v1/platform/execution/runs":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			if req["stream"] != false {
				t.Errorf("StartExecutionRun must send stream=false, got %v", req["stream"])
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"run_id": "run_go_1", "kind": req["kind"], "target_id": req["target_id"], "objective": req["objective"], "status": "awaiting_p10_approval", "requires_p10": true})
		case r.Method == http.MethodPost && strings.HasSuffix(p, "/p10"):
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			_ = json.NewEncoder(w).Encode(map[string]any{"run_id": "run_go_1", "status": map[bool]string{true: "completed", false: "aborted_by_p10"}[req["decision"] == "approve"]})
		case r.Method == http.MethodPost && p == "/v1/platform/pricing/simulate":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"schedule":              req["schedule"],
				"seats":                 req["seats"],
				"monthly_api_spend_usd": req["monthly_api_spend_usd"],
				"run_swarm":             req["run_swarm"],
				"calibrated":            map[string]any{"pro_annual_usd": 29.0, "byom_annual_usd": 15.0, "pricing_health_score": 96.5},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p5"))
	ctx := context.Background()

	if ws, err := c.Platform.ListWorkspaces(ctx); err != nil || ws.Total != 1 {
		t.Fatalf("ListWorkspaces failed: %+v, err=%v", ws, err)
	}
	if createdWS, err := c.Platform.CreateWorkspace(ctx, WorkspaceCreateRequest{ID: "hipaa", Name: "HIPAA", Branch: "main", IsolationMode: "air_gap"}); err != nil || createdWS.ID != "hipaa" {
		t.Fatalf("CreateWorkspace failed: %+v, err=%v", createdWS, err)
	}
	if members, err := c.Platform.ListRBACMembers(ctx, "hipaa"); err != nil || len(members.Members) != 1 {
		t.Fatalf("ListRBACMembers failed: %+v, err=%v", members, err)
	}
	if mem, err := c.Platform.UpsertRBACMember(ctx, RBACMemberUpsertRequest{WorkspaceID: "hipaa", ActorID: "usr_viewer", Role: "viewer"}); err != nil || mem.Role != "viewer" {
		t.Fatalf("UpsertRBACMember failed: %+v, err=%v", mem, err)
	}
	if chk, err := c.Platform.CheckRBAC(ctx, RBACCheckRequest{WorkspaceID: "hipaa", Role: "viewer", Permission: "secrets:write"}); err != nil || chk.Allowed {
		t.Fatalf("CheckRBAC viewer expected false: %+v, err=%v", chk, err)
	}

	sec, err := c.Platform.PutSecret(ctx, SecretPutRequest{WorkspaceID: "hipaa", Name: "ANTHROPIC_KEY", Namespace: "byom", SecretValue: "sk-ant-secret"})
	if err != nil || sec.MaskedPreview != "sk-a****7890" {
		t.Fatalf("PutSecret failed: %+v, err=%v", sec, err)
	}
	if listSec, err := c.Platform.ListSecrets(ctx, "hipaa"); err != nil || len(listSec.Secrets) != 1 {
		t.Fatalf("ListSecrets failed: %+v, err=%v", listSec, err)
	}
	if rot, err := c.Platform.RotateSecret(ctx, "ANTHROPIC_KEY", SecretRotateRequest{WorkspaceID: "hipaa", SecretValue: "sk-rot-1111"}); err != nil || rot.Version != 2 {
		t.Fatalf("RotateSecret failed: %+v, err=%v", rot, err)
	}
	if delSec, err := c.Platform.DeleteSecret(ctx, "hipaa", "ANTHROPIC_KEY"); err != nil || !delSec.Deleted {
		t.Fatalf("DeleteSecret failed: %+v, err=%v", delSec, err)
	}

	_, ssrfErr := c.Platform.CreateWebhook(ctx, WebhookCreateRequest{URL: "http://169.254.169.254/latest/meta-data", Events: []string{"*"}})
	var apiErr *APIError
	if !errors.As(ssrfErr, &apiErr) || apiErr.StatusCode != 400 {
		t.Fatalf("expected HTTP 400 APIError on SSRF webhook, got %v", ssrfErr)
	}
	wh, err := c.Platform.CreateWebhook(ctx, WebhookCreateRequest{URL: "https://hooks.example.com/events", Events: []string{"run.completed"}})
	if err != nil || wh.ID != "wh_go_2" {
		t.Fatalf("CreateWebhook failed: %+v, err=%v", wh, err)
	}
	if whList, err := c.Platform.ListWebhooks(ctx, "hipaa"); err != nil || len(whList.Webhooks) != 1 {
		t.Fatalf("ListWebhooks failed: %+v, err=%v", whList, err)
	}
	if testRec, err := c.Platform.TestWebhook(ctx, "wh_go_2"); err != nil || testRec.Signature != "sha256=abcdef" {
		t.Fatalf("TestWebhook failed: %+v, err=%v", testRec, err)
	}
	if ver, err := c.Platform.VerifyWebhook(ctx, WebhookVerifyRequest{Payload: `{"ok":true}`, Signature: "sha256=abcdef", Secret: "sec"}); err != nil || !ver.Valid {
		t.Fatalf("VerifyWebhook failed: %+v, err=%v", ver, err)
	}
	if delWH, err := c.Platform.DeleteWebhook(ctx, "wh_go_2"); err != nil || !delWH.Deleted {
		t.Fatalf("DeleteWebhook failed: %+v, err=%v", delWH, err)
	}

	snap, err := c.Platform.StartExecutionRun(ctx, ExecutionRunStartRequest{Kind: "agent", TargetID: "feature-coder", Objective: "Ship vault", WorkspaceID: "hipaa", RequiresP10: true})
	if err != nil || snap.RunID != "run_go_1" || snap.Status != "awaiting_p10_approval" {
		t.Fatalf("StartExecutionRun failed: %+v, err=%v", snap, err)
	}

	stream, err := c.Platform.StreamExecutionEvents(ctx, "run_go_1")
	if err != nil {
		t.Fatalf("StreamExecutionEvents failed: %v", err)
	}
	defer stream.Close()

	var events []ExecutionEvent
	for stream.Next() {
		events = append(events, stream.Event())
	}
	if err := stream.Err(); err != nil {
		t.Fatalf("unexpected stream error: %v", err)
	}
	if len(events) != 3 || events[0].Type != "run.started" || events[1].Type != "p10.held" || events[2].Type != "run.completed" {
		t.Fatalf("unexpected streamed events: %+v", events)
	}

	resolved, err := c.Platform.ResolveExecutionP10(ctx, "run_go_1", ExecutionP10Request{Decision: "approve", Approver: "usr_1", Role: "owner"})
	if err != nil || resolved.Status != "completed" {
		t.Fatalf("ResolveExecutionP10 failed: %+v, err=%v", resolved, err)
	}

	simDefault, err := c.Platform.SimulatePricing(ctx, PricingSimulationRequest{})
	if err != nil || simDefault["schedule"] != "compare" || simDefault["run_swarm"] != true {
		t.Fatalf("SimulatePricing default failed: %+v, err=%v", simDefault, err)
	}
	simCustom, err := c.Platform.SimulatePricing(ctx, PricingSimulationRequest{Schedule: "calibrated", Seats: 12, MonthlyAPISpendUSD: 2400, RunSwarm: true})
	if err != nil || simCustom["schedule"] != "calibrated" || simCustom["seats"] != float64(12) {
		t.Fatalf("SimulatePricing custom failed: %+v, err=%v", simCustom, err)
	}
}
