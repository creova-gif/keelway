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

func TestPlatformPhase9EnterpriseAndObservability(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var recorded []map[string]any
	approvals := make(map[string][]P10QuorumApprovalEntry)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p9" {
			t.Errorf("expected Bearer kw_live_go_p9, got %q", got)
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
		case r.Method == http.MethodPut && p == "/v1/platform/enterprise/oidc":
			secret, _ := body["signing_secret"].(string)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":               body["workspace_id"],
				"issuer_url":                 body["issuer_url"],
				"client_id":                  body["client_id"],
				"enabled":                    body["enabled"],
				"signing_secret_configured":  secret != "",
				"signing_secret_fingerprint": "sha256:" + strings.Repeat("1", 64),
				"group_role_mapping":         body["group_role_mapping"],
				"updated_at":                 "2026-11-15T00:00:00Z",
			})
		case r.Method == http.MethodPost && p == "/v1/platform/enterprise/scim/v2/Users":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"schemas":     []string{"urn:ietf:params:scim:schemas:core:2.0:User"},
				"id":          "scim-u-01",
				"userName":    body["userName"],
				"displayName": body["displayName"],
				"active":      body["active"],
				"groups":      body["groups"],
				"mapped_role": "admin",
				"updated_at":  "2026-11-15T00:00:01Z",
			})
		case r.Method == http.MethodGet && p == "/v1/platform/enterprise/scim/v2/Users":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"schemas":      []string{"urn:ietf:params:scim:api:messages:2.0:ListResponse"},
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"totalResults": 1,
				"Resources": []map[string]any{
					{
						"schemas":     []string{"urn:ietf:params:scim:schemas:core:2.0:User"},
						"id":          "scim-u-01",
						"userName":    "sre@keelway.dev",
						"displayName": "SRE Lead",
						"active":      true,
						"groups":      []string{"okta:admins"},
						"mapped_role": "admin",
					},
				},
			})
		case r.Method == http.MethodPost && p == "/v1/platform/enterprise/p10-quorum/approve":
			initiator, _ := body["initiator_id"].(string)
			approver, _ := body["approver_id"].(string)
			propID, _ := body["proposal_id"].(string)
			reason, _ := body["reason"].(string)
			if initiator != "" && initiator == approver {
				w.WriteHeader(http.StatusForbidden)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Self-approval forbidden under P-10 quorum"})
				return
			}
			mu.Lock()
			list := append(approvals[propID], P10QuorumApprovalEntry{ApproverID: approver, Reason: reason})
			approvals[propID] = list
			mu.Unlock()
			status := "awaiting_quorum"
			receipt := ""
			if len(list) >= 2 {
				status = "quorum_approved"
				receipt = strings.Repeat("2", 64)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":          body["workspace_id"],
				"proposal_id":           propID,
				"initiator_id":          initiator,
				"required_approvals":    body["required_approvals"],
				"approval_count":        len(list),
				"status":                status,
				"approvals":             list,
				"quorum_receipt_sha256": receipt,
			})
		case r.Method == http.MethodGet && p == "/v1/platform/enterprise/siem/export":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id": r.URL.Query().Get("workspace_id"),
				"format":       r.URL.Query().Get("format"),
				"record_count": 2,
				"batch_sha256": strings.Repeat("3", 64),
				"exported_at":  "2026-11-15T00:00:02Z",
				"records":      []any{map[string]any{"class_uid": 3002}, map[string]any{"class_uid": 6003}},
			})
		case r.Method == http.MethodGet && p == "/v1/platform/observability/metrics":
			fmtParam := r.URL.Query().Get("format")
			promText := ""
			if fmtParam == "prometheus" {
				promText = "keelway_audit_entries_total 12\n"
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"workspace_id":    r.URL.Query().Get("workspace_id"),
				"format":          fmtParam,
				"generated_at":    "2026-11-15T00:00:03Z",
				"counters":        map[string]any{"audit_entries_total": 12},
				"prometheus_text": promText,
				"otlp_resource_metrics": map[string]any{
					"resourceMetrics": []any{},
				},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p9"))
	ctx := context.Background()

	oidc, err := c.Platform.ConfigureOIDCProvider(ctx, OIDCProviderConfigRequest{
		WorkspaceID:      "ws-go-9",
		IssuerURL:        "https://login.keelway.dev",
		ClientID:         "keelway-go-sso",
		SigningSecret:    "sec-go-9",
		GroupRoleMapping: map[string]string{"okta:admins": "admin"},
		Enabled:          true,
	})
	if err != nil || !oidc.SigningSecretConfigured || oidc.GroupRoleMapping["okta:admins"] != "admin" {
		t.Fatalf("ConfigureOIDCProvider failed: %+v, err=%v", oidc, err)
	}

	user, err := c.Platform.ProvisionSCIMUser(ctx, SCIMUserProvisionRequest{
		WorkspaceID: "ws-go-9",
		UserName:    "sre@keelway.dev",
		DisplayName: "SRE Lead",
		Groups:      []string{"okta:admins"},
		Active:      true,
	})
	if err != nil || user.MappedRole != "admin" || !user.Active {
		t.Fatalf("ProvisionSCIMUser failed: %+v, err=%v", user, err)
	}

	users, err := c.Platform.ListSCIMUsers(ctx, "ws-go-9")
	if err != nil || users.TotalResults != 1 || users.Resources[0].UserName != "sre@keelway.dev" {
		t.Fatalf("ListSCIMUsers failed: %+v, err=%v", users, err)
	}

	_, selfErr := c.Platform.ApproveP10Quorum(ctx, P10QuorumApproveRequest{
		WorkspaceID: "ws-go-9",
		ProposalID:  "PROP-GO-01",
		InitiatorID: "alice",
		ApproverID:  "alice",
	})
	var apiErr *APIError
	if !errors.As(selfErr, &apiErr) || apiErr.StatusCode != http.StatusForbidden {
		t.Fatalf("expected 403 APIError for self-approval, got %v", selfErr)
	}

	q1, err := c.Platform.ApproveP10Quorum(ctx, P10QuorumApproveRequest{
		WorkspaceID: "ws-go-9",
		ProposalID:  "PROP-GO-01",
		InitiatorID: "alice",
		ApproverID:  "bob",
		Reason:      "First sign-off",
	})
	if err != nil || q1.Status != "awaiting_quorum" || q1.RequiredApprovals != 2 {
		t.Fatalf("ApproveP10Quorum #1 failed: %+v, err=%v", q1, err)
	}

	q2, err := c.Platform.ApproveP10Quorum(ctx, P10QuorumApproveRequest{
		WorkspaceID: "ws-go-9",
		ProposalID:  "PROP-GO-01",
		InitiatorID: "alice",
		ApproverID:  "carol",
		Reason:      "Second sign-off",
	})
	if err != nil || q2.Status != "quorum_approved" || len(q2.QuorumReceiptSHA256) != 64 {
		t.Fatalf("ApproveP10Quorum #2 failed: %+v, err=%v", q2, err)
	}

	siem, err := c.Platform.ExportSIEMAudit(ctx, SIEMAuditExportParams{
		WorkspaceID: "ws-go-9",
		Format:      "jsonl",
		Limit:       50,
	})
	if err != nil || siem.Format != "jsonl" || siem.RecordCount != 2 {
		t.Fatalf("ExportSIEMAudit failed: %+v, err=%v", siem, err)
	}

	metrics, err := c.Platform.GetObservabilityMetrics(ctx, ObservabilityMetricsParams{
		WorkspaceID: "ws-go-9",
		Format:      "prometheus",
	})
	if err != nil || metrics.Format != "prometheus" || !strings.Contains(metrics.PrometheusText, "keelway_audit_entries_total") {
		t.Fatalf("GetObservabilityMetrics failed: %+v, err=%v", metrics, err)
	}
}
