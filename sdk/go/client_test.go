package keelway

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestAuthResponsesCreateAndRoutingExplain(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_test_token" {
			t.Errorf("unexpected Authorization header: %q", got)
		}
		if got := r.Header.Get("X-Tenant-Env"); got != "sovereign-prod" {
			t.Errorf("unexpected custom header: %q", got)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}

		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/responses":
			if r.Method != http.MethodPost {
				t.Errorf("expected POST, got %s", r.Method)
			}
			if body["stream"] != false {
				t.Errorf("expected stream=false, got %v", body["stream"])
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":          "resp_01",
				"object":      "response",
				"model":       "keelway-core:7b",
				"output_text": "Sovereign inference verified.",
				"usage":       map[string]any{"input_tokens": 12, "output_tokens": 6, "total_tokens": 18},
			})
		case "/v1/routing/explain":
			if body["privacy_level"] != "private" {
				t.Errorf("expected privacy_level=private, got %v", body["privacy_level"])
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"decision_id":       "rt_99",
				"selected_model":    "keelway-core:7b",
				"selected_provider": "ollama_metal",
				"fallback_chain":    []string{"qwen2.5-coder:7b"},
				"privacy_compliant": true,
				"provenance":        map[string]any{"data_boundary": "airgap_local"},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	client := NewClient(
		srv.URL+"/",
		WithAPIKey("kw_live_test_token"),
		WithHTTPClient(srv.Client()),
		WithTimeout(5*time.Second),
		WithHeader("X-Tenant-Env", "sovereign-prod"),
	)

	res, err := client.Responses.Create(context.Background(), ResponseCreateRequest{
		Model:        "keelway-core:7b",
		Input:        "Verify zero-egress execution",
		PrivacyLevel: "private",
	})
	if err != nil {
		t.Fatalf("Responses.Create failed: %v", err)
	}
	if res.ID != "resp_01" || res.OutputText != "Sovereign inference verified." || res.Usage.TotalTokens != 18 {
		t.Fatalf("unexpected ResponseResult: %+v", res)
	}

	explain, err := client.Routing.Explain(context.Background(), RoutingExplainRequest{
		Prompt:       "Classify regulated payroll document",
		PrivacyLevel: "private",
	})
	if err != nil {
		t.Fatalf("Routing.Explain failed: %v", err)
	}
	if explain.SelectedModel != "keelway-core:7b" || !explain.PrivacyCompliant {
		t.Fatalf("unexpected RoutingExplanation: %+v", explain)
	}
}

func TestResponsesStreamChunkSplitSSE(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Accept"); got != "text/event-stream" {
			t.Errorf("expected Accept text/event-stream, got %q", got)
		}
		var payload map[string]any
		_ = json.NewDecoder(r.Body).Decode(&payload)
		if payload["stream"] != true {
			t.Errorf("expected stream=true, got %v", payload["stream"])
		}

		w.Header().Set("Content-Type", "text/event-stream")
		flusher, ok := w.(http.Flusher)
		if !ok {
			t.Fatal("ResponseWriter does not implement http.Flusher")
		}

		chunks := []string{
			": keep-alive\r\nevent: response.created\r\ndata: {\"type\":\"response.",
			"created\",\"response_id\":\"resp_sse_1\"}\r\n\r\n",
			"data: {\"type\":\"response.output_text.del",
			"ta\",\"delta\":\"Zero-\"}\n\ndata: {\"type\":\"response.output_text.delta\",\"delta\":\"egress OK\"}\n",
			"\ndata: [DO",
			"NE]\n\n",
		}
		for _, part := range chunks {
			_, _ = io.WriteString(w, part)
			flusher.Flush()
		}
	}))
	defer srv.Close()

	client := NewClient(srv.URL, WithAPIKey("kw_live_stream"))
	stream, err := client.Responses.Stream(context.Background(), ResponseCreateRequest{
		Model: "keelway-core:7b",
		Input: "Stream test",
	})
	if err != nil {
		t.Fatalf("Responses.Stream failed: %v", err)
	}
	defer stream.Close()

	var events []*StreamEvent
	var combined strings.Builder
	for {
		ev, err := stream.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			t.Fatalf("stream.Next unexpected error: %v", err)
		}
		events = append(events, ev)
		combined.WriteString(ev.Delta)
	}

	if len(events) != 3 {
		t.Fatalf("expected 3 SSE events before [DONE], got %d", len(events))
	}
	if events[0].Type != "response.created" || events[0].ResponseID != "resp_sse_1" {
		t.Fatalf("unexpected first event: %+v", events[0])
	}
	if got := combined.String(); got != "Zero-egress OK" {
		t.Fatalf("expected assembled delta %q, got %q", "Zero-egress OK", got)
	}
	if ev, err := stream.Next(); !errors.Is(err, io.EOF) || ev != nil {
		t.Fatalf("subsequent Next() should return io.EOF, got ev=%v err=%v", ev, err)
	}
}

func TestTypedHTTPErrorMappings(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/401":
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = io.WriteString(w, `{"detail":"Invalid bearer API key"}`)
		case "/402":
			w.WriteHeader(http.StatusPaymentRequired)
			_, _ = io.WriteString(w, `{"detail":"Tenant daily spend limit exceeded"}`)
		case "/403":
			w.WriteHeader(http.StatusForbidden)
			_, _ = io.WriteString(w, `{"detail":"Air-Gap zero-egress policy blocked cloud call"}`)
		case "/404":
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, `{"detail":"Package pkg_missing not found"}`)
		case "/422":
			w.WriteHeader(http.StatusUnprocessableEntity)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"detail": map[string]any{
					"passed":     false,
					"risk_grade": "C",
					"message":    "Pre-publish Marketplace security scan failed",
					"findings": []map[string]any{
						{
							"code":     "DANGEROUS_EXECUTION_HOOK",
							"severity": "critical",
							"message":  "Unsandboxed shell execution detected",
						},
					},
				},
			})
		case "/429":
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = io.WriteString(w, `{"detail":"RPM quota exceeded"}`)
		case "/503":
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = io.WriteString(w, `{"detail":"Upstream inference worker unavailable"}`)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL)
	ctx := context.Background()

	err := c.doJSON(ctx, http.MethodGet, "/401", nil, nil, nil)
	var authErr *AuthenticationError
	if !errors.As(err, &authErr) || authErr.StatusCode != 401 {
		t.Fatalf("expected AuthenticationError(401), got %T (%v)", err, err)
	}

	err = c.doJSON(ctx, http.MethodGet, "/402", nil, nil, nil)
	var budgetErr *BudgetExceededError
	if !errors.As(err, &budgetErr) || budgetErr.StatusCode != 402 {
		t.Fatalf("expected BudgetExceededError(402), got %T (%v)", err, err)
	}

	err = c.doJSON(ctx, http.MethodGet, "/403", nil, nil, nil)
	var airGapErr *AirGapEgressError
	if !errors.As(err, &airGapErr) || airGapErr.StatusCode != 403 {
		t.Fatalf("expected AirGapEgressError(403), got %T (%v)", err, err)
	}

	err = c.doJSON(ctx, http.MethodGet, "/404", nil, nil, nil)
	var notFoundErr *NotFoundError
	if !errors.As(err, &notFoundErr) || notFoundErr.StatusCode != 404 {
		t.Fatalf("expected NotFoundError(404), got %T (%v)", err, err)
	}

	err = c.doJSON(ctx, http.MethodPost, "/422", nil, map[string]any{}, nil)
	var polErr *PolicyViolationError
	var baseAPIErr *APIError
	if !errors.As(err, &polErr) || !errors.As(err, &baseAPIErr) {
		t.Fatalf("expected PolicyViolationError & APIError, got %T (%v)", err, err)
	}
	if polErr.RiskGrade != "C" || len(polErr.Findings) != 1 || polErr.Findings[0]["code"] != "DANGEROUS_EXECUTION_HOOK" {
		t.Fatalf("expected preserved RiskGrade=C and Findings, got grade=%q findings=%+v", polErr.RiskGrade, polErr.Findings)
	}

	err = c.doJSON(ctx, http.MethodGet, "/429", nil, nil, nil)
	var rateErr *RateLimitError
	if !errors.As(err, &rateErr) || rateErr.StatusCode != 429 {
		t.Fatalf("expected RateLimitError(429), got %T (%v)", err, err)
	}

	err = c.doJSON(ctx, http.MethodGet, "/503", nil, nil, nil)
	var upErr *UpstreamProviderError
	if !errors.As(err, &upErr) || upErr.StatusCode != 503 {
		t.Fatalf("expected UpstreamProviderError(503), got %T (%v)", err, err)
	}
}

func TestPlatformAndClusterServices(t *testing.T) {
	t.Parallel()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/v1/platform/overview":
			_ = json.NewEncoder(w).Encode(map[string]any{"workspace_id": "default", "lifecycle_agents_count": 12})
		case r.Method == http.MethodGet && r.URL.Path == "/v1/platform/agents":
			_ = json.NewEncoder(w).Encode(map[string]any{"agents": []map[string]any{{"id": "feature-coder"}}})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/teams/dispatch":
			_ = json.NewEncoder(w).Encode(map[string]any{"run_id": "run_01", "team_id": "squad-core", "objective": "Ship", "status": "gated_p10"})
		case r.Method == http.MethodGet && r.URL.Path == "/v1/platform/pm/issues":
			_ = json.NewEncoder(w).Encode(map[string]any{"issues": []map[string]any{{"id": "ISS-1", "title": "Audit", "status": "todo"}}, "total": 1})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/pm/issues":
			_ = json.NewEncoder(w).Encode(map[string]any{"id": "ISS-2", "title": "Add policy", "status": "todo"})
		case r.Method == http.MethodGet && r.URL.Path == "/v1/platform/marketplace/packages":
			if r.URL.Query().Get("category") != "agent" || r.URL.Query().Get("query") != "sec" {
				t.Errorf("unexpected marketplace query: %s", r.URL.RawQuery)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"packages": []map[string]any{{"id": "pkg_1", "name": "SecScanner"}}, "total": 1})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/marketplace/scan":
			_ = json.NewEncoder(w).Encode(map[string]any{"passed": true, "risk_grade": "A", "findings": []map[string]any{}})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/marketplace/publish":
			_ = json.NewEncoder(w).Encode(map[string]any{"id": "pkg_pub_1", "name": "VerifiedSkill", "security_verified": true})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/marketplace/install":
			_ = json.NewEncoder(w).Encode(map[string]any{"package_id": "pkg_pub_1", "status": "installed"})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/nocode/blueprint":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":    "default",
				"experience_mode": "non_coder",
				"idea":            "Vendor approval portal",
				"prd":             map[string]any{"id": "PRD-1"},
			})
		case r.Method == http.MethodGet && r.URL.Path == "/v1/platform/enterprise/policy/acme-fin":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"tenant_id":              "acme-fin",
				"retention_mode":         "worm_7y",
				"pii_redaction_enforced": true,
			})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/platform/enterprise/compliance-check":
			var req map[string]any
			_ = json.NewDecoder(r.Body).Decode(&req)
			if req["tenant_id"] != "acme-fin" || req["framework"] != "SOC2" {
				t.Errorf("unexpected compliance request: %+v", req)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"tenant_id": "acme-fin",
				"framework": "SOC2",
				"passed":    true,
				"score_pct": 100.0,
			})
		case r.Method == http.MethodGet && r.URL.Path == "/v1/cluster/nodes":
			if r.URL.Query().Get("region") != "eu" {
				t.Errorf("expected region=eu, got %q", r.URL.Query().Get("region"))
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"nodes": []map[string]any{{"node_id": "node-vllm-eu-01", "region": "eu", "status": "healthy"}},
				"total": 1,
			})
		case r.Method == http.MethodPost && r.URL.Path == "/v1/cluster/schedule":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"selected_node_id": "node-vllm-eu-01",
				"model_id":         "qwen2.5-coder:7b",
				"region":           "eu",
				"receipt_sha256":   "abc123sha",
			})
		case r.Method == http.MethodGet && r.URL.Path == "/v1/cluster/lifecycle":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"deployments": []map[string]any{{"model_id": "keelway-core:7b", "stage": "production"}},
				"total":       1,
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_platform"))
	ctx := context.Background()

	ov, err := c.Platform.GetOverview(ctx)
	if err != nil || ov.LifecycleAgentsCount != 12 {
		t.Fatalf("GetOverview failed: %+v, err=%v", ov, err)
	}
	if agents, err := c.Platform.ListAgents(ctx); err != nil || len(agents.Agents) != 1 {
		t.Fatalf("ListAgents failed: %+v, err=%v", agents, err)
	}
	if run, err := c.Platform.DispatchTeam(ctx, TeamDispatchRequest{TeamID: "squad-core", Objective: "Ship"}); err != nil || run.RunID != "run_01" {
		t.Fatalf("DispatchTeam failed: %+v, err=%v", run, err)
	}
	if issues, err := c.Platform.ListIssues(ctx); err != nil || issues.Total != 1 {
		t.Fatalf("ListIssues failed: %+v, err=%v", issues, err)
	}
	if created, err := c.Platform.CreateIssue(ctx, IssueCreateRequest{Title: "Add policy"}); err != nil || created.ID != "ISS-2" {
		t.Fatalf("CreateIssue failed: %+v, err=%v", created, err)
	}
	if pkgs, err := c.Platform.ListMarketplacePackages(ctx, "agent", "sec"); err != nil || pkgs.Total != 1 {
		t.Fatalf("ListMarketplacePackages failed: %+v, err=%v", pkgs, err)
	}
	if scan, err := c.Platform.ScanMarketplacePackage(ctx, map[string]any{"name": "Skill"}); err != nil || !scan.Passed || scan.RiskGrade != "A" {
		t.Fatalf("ScanMarketplacePackage failed: %+v, err=%v", scan, err)
	}
	if pub, err := c.Platform.PublishMarketplacePackage(ctx, map[string]any{"name": "VerifiedSkill"}); err != nil || !pub.SecurityVerified {
		t.Fatalf("PublishMarketplacePackage failed: %+v, err=%v", pub, err)
	}
	if inst, err := c.Platform.InstallMarketplacePackage(ctx, "pkg_pub_1"); err != nil || inst.Status != "installed" {
		t.Fatalf("InstallMarketplacePackage failed: %+v, err=%v", inst, err)
	}
	if bp, err := c.Platform.CompileBlueprint(ctx, "Vendor approval portal", "non_coder"); err != nil || bp.Idea != "Vendor approval portal" {
		t.Fatalf("CompileBlueprint failed: %+v, err=%v", bp, err)
	}
	if pol, err := c.Platform.GetEnterprisePolicy(ctx, "acme-fin"); err != nil || !pol.PIIRedactionEnforced {
		t.Fatalf("GetEnterprisePolicy failed: %+v, err=%v", pol, err)
	}
	if comp, err := c.Platform.EvaluateCompliance(ctx, "acme-fin", []string{"SOC2", "HIPAA"}); err != nil || !comp.Passed || comp.ScorePct != 100.0 {
		t.Fatalf("EvaluateCompliance failed: %+v, err=%v", comp, err)
	}

	nodes, err := c.Cluster.ListNodes(ctx, "eu")
	if err != nil || len(nodes.Nodes) != 1 || nodes.Nodes[0].NodeID != "node-vllm-eu-01" {
		t.Fatalf("Cluster.ListNodes failed: %+v, err=%v", nodes, err)
	}
	sched, err := c.Cluster.Schedule(ctx, map[string]any{"model_id": "qwen2.5-coder:7b", "region_residency": "eu"})
	if err != nil || sched.SelectedNodeID != "node-vllm-eu-01" {
		t.Fatalf("Cluster.Schedule failed: %+v, err=%v", sched, err)
	}
	lc, err := c.Cluster.ListLifecycle(ctx)
	if err != nil || len(lc.Deployments) != 1 {
		t.Fatalf("Cluster.ListLifecycle failed: %+v, err=%v", lc, err)
	}
}

func TestContextCancellation(t *testing.T) {
	t.Parallel()

	started := make(chan struct{})
	release := make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		close(started)
		select {
		case <-r.Context().Done():
		case <-release:
		}
	}))
	defer func() {
		close(release)
		srv.Close()
	}()

	client := NewClient(srv.URL)
	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		<-started
		cancel()
	}()

	_, err := client.Responses.Create(ctx, ResponseCreateRequest{Input: "Blocked call"})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}
