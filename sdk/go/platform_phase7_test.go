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

func TestPlatformPhase7McpAndGoldenEvals(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var recorded []map[string]any

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p7" {
			t.Errorf("expected Bearer kw_live_go_p7, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		mu.Lock()
		recorded = append(recorded, map[string]any{
			"method":       r.Method,
			"escaped_path": r.URL.EscapedPath(),
			"workspace_id": r.URL.Query().Get("workspace_id"),
			"body":         body,
		})
		mu.Unlock()

		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodGet && p == "/v1/platform/mcp/servers":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"servers": []map[string]any{
					{"id": "keelway-core-mcp", "name": "Keelway Core MCP", "transport": "builtin", "builtin": true, "status": "active"},
				},
				"total": 1,
			})
		case r.Method == http.MethodPost && p == "/v1/platform/mcp/servers":
			ep, _ := body["endpoint"].(string)
			if strings.Contains(ep, "169.254.169.254") {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "SSRF blocked"})
				return
			}
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"id":            body["id"],
				"name":          body["name"],
				"transport":     body["transport"],
				"endpoint":      ep,
				"workspace_id":  body["workspace_id"],
				"allowed_tools": body["allowed_tools"],
				"status":        "registered",
			})
		case r.Method == http.MethodDelete && strings.HasPrefix(p, "/v1/platform/mcp/servers/"):
			serverID := strings.TrimPrefix(p, "/v1/platform/mcp/servers/")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"deleted":      true,
				"server_id":    serverID,
				"workspace_id": r.URL.Query().Get("workspace_id"),
			})
		case r.Method == http.MethodGet && p == "/v1/platform/mcp/tools":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"tools": []map[string]any{
					{"name": "workspace.list_files", "server_id": "keelway-core-mcp", "builtin": true, "mutating": false},
				},
				"count": 1,
				"total": 1,
			})
		case r.Method == http.MethodPost && p == "/v1/platform/mcp/call":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":   body["workspace_id"],
				"tool_name":      body["tool_name"],
				"ok":             true,
				"redacted":       true,
				"result":         map[string]any{"files": []string{"pyproject.toml"}},
				"receipt_sha256": strings.Repeat("b", 64),
			})
		case r.Method == http.MethodPost && p == "/v1/platform/evals/golden":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"eval_run_id":  "eval-go-01",
				"workspace_id": body["workspace_id"],
				"category":     body["category"],
				"total_cases":  16,
				"passed_cases": 16,
				"failed_cases": 0,
				"pass_rate":    1.0,
				"cases":        []map[string]any{{"id": "gov-p10-self-approval", "category": "governance_p10", "passed": true}},
			})
		case r.Method == http.MethodGet && p == "/v1/platform/evals/latest":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"has_run":      true,
				"latest": map[string]any{
					"eval_run_id":  "eval-go-01",
					"workspace_id": r.URL.Query().Get("workspace_id"),
					"category":     "all",
					"total_cases":  16,
					"passed_cases": 16,
					"failed_cases": 0,
					"pass_rate":    1.0,
				},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p7"))
	ctx := context.Background()

	srvList, err := c.Platform.ListMcpServers(ctx, "")
	if err != nil || srvList.WorkspaceID != "default" || len(srvList.Servers) != 1 {
		t.Fatalf("ListMcpServers failed: %+v, err=%v", srvList, err)
	}

	_, ssrfErr := c.Platform.RegisterMcpServer(ctx, McpServerRegisterRequest{
		ID:        "bad-ssrf",
		Name:      "SSRF",
		Transport: "sse",
		Endpoint:  "http://169.254.169.254/latest/meta-data",
	})
	var apiErr *APIError
	if !errors.As(ssrfErr, &apiErr) || apiErr.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 APIError for SSRF endpoint, got %v", ssrfErr)
	}

	reg, err := c.Platform.RegisterMcpServer(ctx, McpServerRegisterRequest{
		ID:           "local/docs-mcp",
		Name:         "Local Docs MCP",
		Transport:    "sse",
		Endpoint:     "http://127.0.0.1:8910/sse",
		WorkspaceID:  "ws-go-7",
		AllowedTools: []string{"docs.search"},
	})
	if err != nil || reg.ID != "local/docs-mcp" || reg.Status != "registered" {
		t.Fatalf("RegisterMcpServer failed: %+v, err=%v", reg, err)
	}

	tools, err := c.Platform.ListMcpTools(ctx, "ws-go-7")
	if err != nil || tools.Total != 1 || tools.Tools[0].Name != "workspace.list_files" {
		t.Fatalf("ListMcpTools failed: %+v, err=%v", tools, err)
	}

	callRes, err := c.Platform.CallMcpTool(ctx, McpToolCallRequest{ToolName: "workspace.list_files"})
	if err != nil || !callRes.OK || !callRes.Redacted {
		t.Fatalf("CallMcpTool failed: %+v, err=%v", callRes, err)
	}

	evalDefault, err := c.Platform.RunGoldenEvals(ctx, GoldenEvalRunRequest{})
	if err != nil || evalDefault.Category != "all" || evalDefault.PassedCases != 16 || evalDefault.TotalCases != 16 {
		t.Fatalf("RunGoldenEvals default failed: %+v, err=%v", evalDefault, err)
	}

	latest, err := c.Platform.GetLatestGoldenEvals(ctx, "ws-go-7")
	if err != nil || !latest.HasRun || latest.Latest == nil || latest.Latest.EvalRunID != "eval-go-01" || latest.WorkspaceID != "ws-go-7" {
		t.Fatalf("GetLatestGoldenEvals failed: %+v, err=%v", latest, err)
	}

	delRes, err := c.Platform.DeleteMcpServer(ctx, "local/docs-mcp", "ws-go-7")
	if err != nil || !delRes.Deleted {
		t.Fatalf("DeleteMcpServer failed: %+v, err=%v", delRes, err)
	}
	if _, emptyErr := c.Platform.DeleteMcpServer(ctx, "   ", "ws-go-7"); emptyErr == nil {
		t.Fatal("expected error on empty serverID")
	}

	mu.Lock()
	defer mu.Unlock()
	last := recorded[len(recorded)-1]
	if last["escaped_path"] != "/v1/platform/mcp/servers/local%2Fdocs-mcp" {
		t.Fatalf("expected URL-escaped serverID path, got %v", last["escaped_path"])
	}
	callBody := recorded[4]["body"].(map[string]any)
	if argsMap, ok := callBody["arguments"].(map[string]any); !ok || len(argsMap) != 0 {
		t.Fatalf("expected empty arguments map on nil Arguments, got %#v", callBody["arguments"])
	}
}
