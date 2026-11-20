package keelway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
)

func TestKStackExecuteAndAgentsRegistry(t *testing.T) {
	t.Parallel()

	var recorded []map[string]any

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p21" {
			t.Errorf("expected Bearer kw_live_go_p21, got %q", got)
		}
		var body map[string]any
		if r.Body != nil && r.ContentLength != 0 {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		recorded = append(recorded, map[string]any{
			"method": r.Method,
			"path":   r.URL.Path,
			"query":  r.URL.Query(),
			"body":   body,
		})

		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/kstack/execute":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"proof": map[string]any{
					"execution_id":        "exec-1",
					"skill_name":          body["name"],
					"skill_digest_sha256": "abc123",
					"actor":               "go-client",
					"inputs":              body["inputs"],
					"outputs":             map[string]any{"pass_rate_pct": 90.0},
					"permissions_used":    []string{"execute_restricted"},
					"success":             true,
					"duration_ms":         12.5,
					"timestamp_utc":       "2026-11-19T00:00:00Z",
					"signature_sha256":    "deadbeef",
				},
			})
		case r.Method == http.MethodGet && p == "/v1/agents/registry":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"manifests": []map[string]any{
					{"id": 1, "name": "devops-sre", "version": "1.0.0", "owner": "system", "digest": "d1", "enabled": true},
					{"id": 2, "name": "pr-reviewer", "version": "1.0.0", "owner": "system", "digest": "d2", "enabled": false},
				},
			})
		case r.Method == http.MethodPost && p == "/v1/agents/registry/devops-sre/1.0.0/toggle":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":         1,
				"enabled":    body["enabled"],
				"updated_at": "2026-11-19T00:00:00Z",
			})
		default:
			w.WriteHeader(http.StatusNotFound)
			_ = json.NewEncoder(w).Encode(map[string]any{"detail": "not found"})
		}
	}))
	defer srv.Close()

	client := NewClient(srv.URL, WithAPIKey("kw_live_go_p21"))
	ctx := context.Background()

	proof, err := client.KStack.Execute(ctx, KStackExecuteRequest{
		Name:   "kstack/golden-eval",
		Inputs: map[string]any{"model_name": "m1", "compare_to": "latest"},
	})
	if err != nil {
		t.Fatalf("KStack.Execute: %v", err)
	}
	if !proof.Success || proof.SkillName != "kstack/golden-eval" || proof.Outputs["pass_rate_pct"] != 90.0 {
		t.Fatalf("unexpected proof: %+v", proof)
	}

	registry, err := client.Agents.ListRegistry(ctx, true)
	if err != nil {
		t.Fatalf("Agents.ListRegistry: %v", err)
	}
	if len(registry.Manifests) != 2 || registry.Manifests[0].Name != "devops-sre" {
		t.Fatalf("unexpected registry: %+v", registry)
	}

	toggled, err := client.Agents.ToggleManifest(ctx, "devops-sre", "1.0.0", false)
	if err != nil {
		t.Fatalf("Agents.ToggleManifest: %v", err)
	}
	if toggled.Enabled != false || toggled.ID != 1 {
		t.Fatalf("unexpected toggle response: %+v", toggled)
	}

	if len(recorded) != 3 {
		t.Fatalf("expected 3 requests, got %d", len(recorded))
	}
	if recorded[0]["body"].(map[string]any)["inputs"].(map[string]any)["compare_to"] != "latest" {
		t.Fatalf("execute inputs not transmitted: %+v", recorded[0])
	}
	if q := recorded[1]["query"].(url.Values); q.Get("enabled_only") != "true" {
		t.Fatalf("enabled_only query not transmitted: %+v", q)
	}
	if recorded[2]["body"].(map[string]any)["enabled"] != false {
		t.Fatalf("toggle body not transmitted: %+v", recorded[2])
	}
}
