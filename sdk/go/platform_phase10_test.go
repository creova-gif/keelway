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

func TestPlatformPhase10KBrainAndKHub(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var recorded []map[string]any
	facts := make(map[string]KBrainFactRecord)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p10" {
			t.Errorf("expected Bearer kw_live_go_p10, got %q", got)
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
		case r.Method == http.MethodPost && p == "/v1/platform/kbrain/facts":
			stmt, _ := body["statement"].(string)
			if strings.Contains(stmt, "sk-ant-leak") {
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "DLP secret leak blocked"})
				return
			}
			wsID, _ := body["workspace_id"].(string)
			key, _ := body["key"].(string)
			scope, _ := body["scope"].(string)
			prov, _ := body["provenance_uri"].(string)
			autoApprove, _ := body["auto_approve"].(bool)
			var tags []string
			if rawTags, ok := body["tags"].([]any); ok {
				for _, tItem := range rawTags {
					if s, ok := tItem.(string); ok {
						tags = append(tags, s)
					}
				}
			}
			if tags == nil {
				tags = []string{}
			}

			mu.Lock()
			conflictID := ""
			for _, existing := range facts {
				if existing.WorkspaceID == wsID && existing.Key == key && existing.Scope == scope && existing.Statement != stmt {
					conflictID = existing.ID
					break
				}
			}
			id := "kb_go_" + strings.Repeat("1", len(facts)+1)
			status := "proposed"
			if conflictID != "" {
				status = "conflict"
			} else if autoApprove {
				status = "approved"
			}
			rec := KBrainFactRecord{
				ID:                 id,
				WorkspaceID:        wsID,
				Key:                key,
				Statement:          stmt,
				Scope:              scope,
				Status:             status,
				ConflictWithFactID: conflictID,
				ProvenanceURI:      prov,
				Tags:               tags,
				CreatedBy:          "go-operator",
				FactSHA256:         strings.Repeat("a", 64),
				CreatedAt:          "2026-11-15T00:00:00Z",
			}
			facts[id] = rec
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/kbrain/search":
			wsID := r.URL.Query().Get("workspace_id")
			q := strings.ToLower(r.URL.Query().Get("query"))
			maxScope := r.URL.Query().Get("max_scope")
			includeConflicts := r.URL.Query().Get("include_conflicts") == "true"
			mu.Lock()
			var results []KBrainSearchResultItem
			for _, f := range facts {
				if f.WorkspaceID != wsID || f.Status == "rejected" {
					continue
				}
				if !includeConflicts && f.Status == "conflict" {
					continue
				}
				if q != "" && !strings.Contains(strings.ToLower(f.Statement), q) && !strings.Contains(strings.ToLower(f.Key), q) {
					continue
				}
				results = append(results, KBrainSearchResultItem{
					KBrainFactRecord: f,
					Score:            0.95,
					BM25Score:        0.92,
					NGramScore:       0.89,
				})
			}
			mu.Unlock()
			if results == nil {
				results = []KBrainSearchResultItem{}
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":  wsID,
				"query":         r.URL.Query().Get("query"),
				"max_scope":     maxScope,
				"total_matches": len(results),
				"results":       results,
			})

		case r.Method == http.MethodPost && strings.HasPrefix(p, "/v1/platform/kbrain/facts/") && strings.HasSuffix(p, "/resolve"):
			factID := strings.TrimSuffix(strings.TrimPrefix(p, "/v1/platform/kbrain/facts/"), "/resolve")
			resAction, _ := body["resolution"].(string)
			mu.Lock()
			rec, ok := facts[factID]
			if !ok {
				mu.Unlock()
				http.NotFound(w, r)
				return
			}
			if resAction == "approve" {
				rec.Status = "approved"
			} else {
				rec.Status = "rejected"
			}
			rec.ConflictWithFactID = ""
			facts[factID] = rec
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/khub/skills":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":          r.URL.Query().Get("workspace_id"),
				"total_skills":          2,
				"air_gap_compliant":     true,
				"catalog_digest_sha256": strings.Repeat("b", 64),
				"skills": []map[string]any{
					{"id": "skill-01", "name": "AST Guard", "digest_sha256": strings.Repeat("c", 64), "air_gap_ready": true},
					{"id": "skill-02", "name": "SBOM Verifier", "digest_sha256": strings.Repeat("d", 64), "air_gap_ready": true},
				},
			})

		case r.Method == http.MethodPost && p == "/v1/platform/khub/mirror/verify":
			ids, _ := body["skill_ids"].([]any)
			count := len(ids)
			if count == 0 {
				count = 2
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":          body["workspace_id"],
				"verified":              true,
				"mirror_format":         "khub-skill-bundle-v1",
				"skills_verified":       count,
				"catalog_digest_sha256": strings.Repeat("b", 64),
				"verified_at":           "2026-11-15T00:00:05Z",
			})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p10"))
	ctx := context.Background()

	if _, err := c.Platform.RecordKBrainFact(ctx, KBrainFactRecordRequest{Key: "", Statement: "bad"}); err == nil {
		t.Fatal("expected non-empty key error")
	}

	f1, err := c.Platform.RecordKBrainFact(ctx, KBrainFactRecordRequest{
		WorkspaceID:   "ws-go-10",
		Key:           "routing.residency",
		Statement:     "Zero-egress workspaces pin inference to local OpenCore weights.",
		Scope:         "project",
		ProvenanceURI: "file://core/models/router.py",
		Tags:          []string{"routing", "zero-egress"},
		AutoApprove:   true,
	})
	if err != nil || f1.Status != "approved" || len(f1.FactSHA256) != 64 {
		t.Fatalf("RecordKBrainFact #1 failed: %+v, err=%v", f1, err)
	}

	_, dlpErr := c.Platform.RecordKBrainFact(ctx, KBrainFactRecordRequest{
		WorkspaceID: "ws-go-10",
		Key:         "secret.test",
		Statement:   "Contains sk-ant-leak-1234567890",
	})
	var apiErr *APIError
	if !errors.As(dlpErr, &apiErr) || apiErr.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 APIError for DLP secret leak, got %v", dlpErr)
	}

	f2, err := c.Platform.RecordKBrainFact(ctx, KBrainFactRecordRequest{
		WorkspaceID: "ws-go-10",
		Key:         "routing.residency",
		Statement:   "Conflicting cloud egress rule.",
		Scope:       "project",
	})
	if err != nil || f2.Status != "conflict" || f2.ConflictWithFactID != f1.ID {
		t.Fatalf("RecordKBrainFact conflict check failed: %+v, err=%v", f2, err)
	}

	cleanSearch, err := c.Platform.SearchKBrainFacts(ctx, KBrainSearchParams{
		WorkspaceID:      "ws-go-10",
		Query:            "Zero-egress",
		MaxScope:         "org",
		IncludeConflicts: false,
		Limit:            10,
	})
	if err != nil || cleanSearch.TotalMatches != 1 {
		t.Fatalf("SearchKBrainFacts clean failed: %+v, err=%v", cleanSearch, err)
	}

	resolved, err := c.Platform.ResolveKBrainFact(ctx, f2.ID, KBrainFactResolveRequest{
		WorkspaceID: "ws-go-10",
		Resolution:  "reject",
	})
	if err != nil || resolved.Status != "rejected" {
		t.Fatalf("ResolveKBrainFact failed: %+v, err=%v", resolved, err)
	}

	skills, err := c.Platform.ListKHubSkills(ctx, "ws-go-10")
	if err != nil || skills.TotalSkills != 2 || !skills.AirGapCompliant {
		t.Fatalf("ListKHubSkills failed: %+v, err=%v", skills, err)
	}

	mirror, err := c.Platform.VerifyKHubMirror(ctx, KHubMirrorVerifyRequest{
		WorkspaceID: "ws-go-10",
		SkillIDs:    []string{"skill-01"},
	})
	if err != nil || !mirror.Verified || mirror.SkillsVerified != 1 {
		t.Fatalf("VerifyKHubMirror failed: %+v, err=%v", mirror, err)
	}
}
