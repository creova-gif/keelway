package keelway

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
)

func TestPlatformPhase16StructuredOutputAndSelfHealing(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var runs []StructuredOutputRunRecord
	var diagnoses []SelfHealingDiagnosisRecord
	var escapedApplyPaths []string

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p16" {
			t.Errorf("expected Bearer kw_live_go_p16, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path
		rawPath := r.URL.EscapedPath()

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/healing/content-blocks/normalize":
			wsID, _ := body["workspace_id"].(string)
			prov, _ := body["provider_format"].(string)
			mod, _ := body["model_id"].(string)
			rawBytes, _ := json.Marshal(body["raw_payload"])
			redactions := 0
			if strings.Contains(string(rawBytes), "sk-live-secret") {
				redactions = 1
			}
			_ = json.NewEncoder(w).Encode(NormalizedContentEnvelope{
				WorkspaceID: wsID, ProviderFormat: prov, ModelID: mod, BlockCount: 2,
				ContentBlocks: []NormalizedContentBlock{
					{Index: 0, Kind: "reasoning", Content: "Analyzing invoice"},
					{Index: 1, Kind: "text", Content: "Token [REDACTED_SECRET]"},
				},
				DLPRedactions: redactions, EnvelopeSHA256: strings.Repeat("a", 64),
			})

		case r.Method == http.MethodPost && p == "/v1/platform/healing/structured/enforce":
			wsID, _ := body["workspace_id"].(string)
			schemaName, _ := body["schema_name"].(string)
			prov, _ := body["provider_format"].(string)
			mod, _ := body["model_id"].(string)
			strict, _ := body["strict_mode"].(bool)
			failClosed, _ := body["fail_closed"].(bool)
			rawOut := fmt.Sprint(body["raw_output"])
			invalid := strings.Contains(rawOut, "INVALID")
			repaired := !invalid && !strict && strings.Contains(rawOut, "<think>")
			status := "VALID"
			if invalid {
				status = "SCHEMA_REJECTED"
			} else if repaired {
				status = "REPAIRED_VALID"
			}
			mu.Lock()
			rec := StructuredOutputRunRecord{
				RunID: fmt.Sprintf("srun-go-%d", len(runs)+1), WorkspaceID: wsID, SchemaName: schemaName,
				ProviderFormat: prov, ModelID: mod, Status: status, RepairApplied: repaired,
				RepairActions: []string{"strip_think_tags"}, ValidatedData: map[string]any{"approved": true, "score": 42},
				ValidationErrors: []string{}, DLPRedactions: 0, RunSHA256: strings.Repeat("b", 64), CreatedAt: "2026-11-16T00:00:00Z",
			}
			runs = append([]StructuredOutputRunRecord{rec}, runs...)
			mu.Unlock()
			if invalid && failClosed {
				w.WriteHeader(http.StatusUnprocessableEntity)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Schema rejected", "code": "structured_schema_rejected", "run": rec})
				return
			}
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/healing/structured/runs":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []StructuredOutputRunRecord{}
			for _, rec := range runs {
				if rec.WorkspaceID == wsID {
					matched = append(matched, rec)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(StructuredOutputRunListResponse{WorkspaceID: wsID, Count: len(matched), Runs: matched})

		case r.Method == http.MethodPost && p == "/v1/platform/healing/root-cause/diagnose":
			wsID, _ := body["workspace_id"].(string)
			wfName, _ := body["workflow_name"].(string)
			mu.Lock()
			diagID := "diag/slash#go"
			if len(diagnoses) > 0 {
				diagID = fmt.Sprintf("diag-go-%d", len(diagnoses)+1)
			}
			diag := SelfHealingDiagnosisRecord{
				DiagnosisID: diagID, WorkspaceID: wsID, TraceID: "trace-go-16", WorkflowName: wfName,
				FailureClass: "schema_mismatch", Status: "DIAGNOSED", Confidence: 0.93, FailedNode: "extract_invoice",
				DiagnosticModel: "keelway-core:7b", Summary: "Scalar mismatch", RootCauseEvidence: []string{"$.amount string"},
				ProposedPatch:   ProposedSelfHealingPatch{TargetSurface: "json_schema", RecommendedModel: "keelway-core:7b", UnifiedDiff: "--- a\n+++ b", PatchedPrompt: "Strict JSON"},
				DiagnosisSHA256: strings.Repeat("c", 64), CreatedAt: "2026-11-16T00:01:00Z",
			}
			diagnoses = append([]SelfHealingDiagnosisRecord{diag}, diagnoses...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(diag)

		case r.Method == http.MethodPost && strings.HasPrefix(rawPath, "/v1/platform/healing/root-cause/") && strings.HasSuffix(rawPath, "/apply"):
			encSeg := strings.TrimSuffix(strings.TrimPrefix(rawPath, "/v1/platform/healing/root-cause/"), "/apply")
			diagID, _ := url.PathUnescape(encSeg)
			wsID, _ := body["workspace_id"].(string)
			title, _ := body["eval_title"].(string)
			if title == "" {
				title = "Regression Case"
			}
			mu.Lock()
			escapedApplyPaths = append(escapedApplyPaths, rawPath)
			var found *SelfHealingDiagnosisRecord
			for i := range diagnoses {
				if diagnoses[i].DiagnosisID == diagID && diagnoses[i].WorkspaceID == wsID {
					diagnoses[i].Status = "VERIFIED_HEALED"
					diagnoses[i].VerificationReplayTraceID = "replay-go-16"
					diagnoses[i].PromotedEvalCaseID = "eval-go-16"
					cp := diagnoses[i]
					found = &cp
					break
				}
			}
			mu.Unlock()
			if found == nil {
				w.WriteHeader(http.StatusNotFound)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Diagnosis not found"})
				return
			}
			_ = json.NewEncoder(w).Encode(ApplySelfHealingResponse{
				Diagnosis: *found, VerifiedHealed: true, CachedStepsReused: 3, ReplayCostUSD: 0.0012,
				PromotedEvalCase: &PromotedEvalCaseSummary{CaseID: "eval-go-16", Title: title, CaseSHA256: strings.Repeat("d", 64)},
			})

		case r.Method == http.MethodGet && p == "/v1/platform/healing/root-cause/diagnoses":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []SelfHealingDiagnosisRecord{}
			for _, d := range diagnoses {
				if d.WorkspaceID == wsID {
					matched = append(matched, d)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(SelfHealingDiagnosisListResponse{WorkspaceID: wsID, Count: len(matched), Diagnoses: matched})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p16"))
	ctx := context.Background()

	if _, err := c.Platform.NormalizeContentBlocks(ctx, NormalizeContentBlocksRequest{ProviderFormat: "bad_fmt", RawPayload: "hi"}); err == nil {
		t.Fatal("expected invalid provider_format error")
	}
	if _, err := c.Platform.EnforceStructuredOutput(ctx, EnforceStructuredOutputRequest{RawOutput: "{}"}); err == nil {
		t.Fatal("expected nil json_schema error")
	}
	if _, err := c.Platform.ApplySelfHealingPatch(ctx, "   ", ApplySelfHealingPatchRequest{}); err == nil {
		t.Fatal("expected empty diagnosisID error")
	}
	if _, err := c.Platform.ListStructuredOutputRuns(ctx, ListStructuredOutputRunsParams{Limit: -1}); err == nil {
		t.Fatal("expected negative limit error")
	}

	norm, err := c.Platform.NormalizeContentBlocks(ctx, NormalizeContentBlocksRequest{
		WorkspaceID: "ws-go-16", ProviderFormat: "deepseek_opencore", RawPayload: "<think>x</think>sk-live-secret123",
	})
	if err != nil || norm.BlockCount != 2 || norm.DLPRedactions != 1 || len(norm.EnvelopeSHA256) != 64 {
		t.Fatalf("NormalizeContentBlocks failed: %+v, err=%v", norm, err)
	}

	repaired, err := c.Platform.EnforceStructuredOutput(ctx, EnforceStructuredOutputRequest{
		WorkspaceID: "ws-go-16", SchemaName: "InvoiceDecision",
		JSONSchema: map[string]any{"type": "object"}, RawOutput: `<think>ok</think>{"approved": "true"}`, StrictMode: BoolPtr(false),
	})
	if err != nil || repaired.Status != "REPAIRED_VALID" || !repaired.RepairApplied {
		t.Fatalf("EnforceStructuredOutput repaired failed: %+v, err=%v", repaired, err)
	}

	_, failClosedErr := c.Platform.EnforceStructuredOutput(ctx, EnforceStructuredOutputRequest{
		WorkspaceID: "ws-go-16", JSONSchema: map[string]any{"type": "object"}, RawOutput: "INVALID", FailClosed: BoolPtr(true),
	})
	var apiErr *APIError
	if !errors.As(failClosedErr, &apiErr) || apiErr.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422 APIError on fail_closed schema rejection, got %v", failClosedErr)
	}

	softFail, err := c.EnforceStructuredOutput(ctx, EnforceStructuredOutputRequest{
		WorkspaceID: "ws-go-16", JSONSchema: map[string]any{"type": "object"}, RawOutput: "INVALID", FailClosed: BoolPtr(false),
	})
	if err != nil || softFail.Status != "SCHEMA_REJECTED" {
		t.Fatalf("EnforceStructuredOutput soft-fail failed: %+v, err=%v", softFail, err)
	}

	if runList, err := c.Platform.ListStructuredOutputRuns(ctx, ListStructuredOutputRunsParams{WorkspaceID: "ws-go-16", Limit: 10}); err != nil || runList.Count != 3 {
		t.Fatalf("ListStructuredOutputRuns failed: %+v, err=%v", runList, err)
	}

	diag, err := c.Platform.DiagnoseFailureRootCause(ctx, DiagnoseFailureRootCauseRequest{
		WorkspaceID: "ws-go-16", WorkflowName: "invoice-triage-agent",
		FailedStep: &FailedStepInput{NodeName: "extract_invoice", ErrorMessage: "schema mismatch"},
	})
	if err != nil || diag.DiagnosisID != "diag/slash#go" || diag.Status != "DIAGNOSED" {
		t.Fatalf("DiagnoseFailureRootCause failed: %+v, err=%v", diag, err)
	}

	applied, err := c.Platform.ApplySelfHealingPatch(ctx, diag.DiagnosisID, ApplySelfHealingPatchRequest{
		WorkspaceID: "ws-go-16", PromoteToEval: BoolPtr(true), EvalTitle: "Go Healing Eval",
	})
	if err != nil || !applied.VerifiedHealed || applied.Diagnosis.Status != "VERIFIED_HEALED" || applied.PromotedEvalCase == nil {
		t.Fatalf("ApplySelfHealingPatch failed: %+v, err=%v", applied, err)
	}
	if len(escapedApplyPaths) == 0 || escapedApplyPaths[0] != "/v1/platform/healing/root-cause/diag%2Fslash%23go/apply" {
		t.Fatalf("expected URL-escaped diagnosisID path, got %v", escapedApplyPaths)
	}

	if _, missingErr := c.Platform.ApplySelfHealingPatch(ctx, "diag-missing", ApplySelfHealingPatchRequest{WorkspaceID: "ws-go-16"}); !errors.As(missingErr, &apiErr) || apiErr.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 APIError on missing diagnosis, got %v", missingErr)
	}

	if diagList, err := c.Platform.ListSelfHealingDiagnoses(ctx, ListSelfHealingDiagnosesParams{WorkspaceID: "ws-go-16", Limit: 5}); err != nil || diagList.Count != 1 {
		t.Fatalf("ListSelfHealingDiagnoses failed: %+v, err=%v", diagList, err)
	}
}
