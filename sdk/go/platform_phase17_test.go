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

func TestPlatformPhase17FormalSafetyAndEdgeMesh(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	var verifications []SafetyVerificationRecord
	nodes := []MeshNodeRecord{
		{
			NodeID: "edge-mac-m3-max", WorkspaceID: "ws-go-17", Name: "edge-mac-m3-max",
			Tier: "edge_local", HardwareHAL: "apple_metal_secure_enclave", Region: "local-loopback",
			VRAMGB: 64, Status: "ONLINE", AttestationSHA256: "sha256:" + strings.Repeat("a", 64), RegisteredAt: "2026-11-16T00:00:00Z",
		},
		{
			NodeID: "cluster-h100-us-east", WorkspaceID: "ws-go-17", Name: "cluster-h100-us-east",
			Tier: "cluster_burst", HardwareHAL: "nvidia_h100_cc", Region: "us-east-1",
			VRAMGB: 80, Status: "ONLINE", AttestationSHA256: "sha256:" + strings.Repeat("b", 64), RegisteredAt: "2026-11-16T00:00:00Z",
		},
	}
	var handoffs []MeshHandoffRecord

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p17" {
			t.Errorf("expected Bearer kw_live_go_p17, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/safety/verify":
			wsID, _ := body["workspace_id"].(string)
			wfID, _ := body["workflow_id"].(string)
			wfName, _ := body["workflow_name"].(string)
			inject, _ := body["inject_p10_guards"].(bool)
			status := "VIOLATION_FOUND"
			injected := []string{}
			violations := []SafetyViolation{{
				InvariantID: "no_unguarded_destructive_tool", Severity: "CRITICAL",
				OffendingNode: "wire_exec", CounterexamplePath: []string{"intake", "wire_exec"}, Remediation: "Require P-10 approval",
			}}
			if inject {
				status = "VERIFIED_SAFE"
				injected = []string{"wire_exec"}
				violations = []SafetyViolation{}
			}
			mu.Lock()
			rec := SafetyVerificationRecord{
				VerificationID: fmt.Sprintf("sver-go-%d", len(verifications)+1), WorkspaceID: wsID,
				WorkflowID: wfID, WorkflowName: wfName, Status: status, StatesExplored: 6,
				InvariantsChecked: []SafetyInvariantCheck{{InvariantID: "no_unguarded_destructive_tool", Passed: inject, Description: "Destructive tools require P-10"}},
				Violations: violations, P10GuardsInjected: injected, DLPRedactions: 0,
				ProofSHA256: "sha256:" + strings.Repeat("c", 64), CreatedAt: "2026-11-16T00:01:00Z",
			}
			verifications = append([]SafetyVerificationRecord{rec}, verifications...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/safety/verifications":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []SafetyVerificationRecord{}
			for _, v := range verifications {
				if v.WorkspaceID == wsID {
					matched = append(matched, v)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(SafetyVerificationListResponse{WorkspaceID: wsID, Count: len(matched), Verifications: matched})

		case r.Method == http.MethodPost && p == "/v1/platform/mesh/nodes":
			wsID, _ := body["workspace_id"].(string)
			name, _ := body["name"].(string)
			tier, _ := body["tier"].(string)
			hal, _ := body["hardware_hal"].(string)
			region, _ := body["region"].(string)
			vram, _ := body["vram_gb"].(float64)
			status, _ := body["status"].(string)
			mu.Lock()
			rec := MeshNodeRecord{
				NodeID: fmt.Sprintf("mesh-go-%d", len(nodes)+1), WorkspaceID: wsID, Name: name,
				Tier: tier, HardwareHAL: hal, Region: region, VRAMGB: int(vram), Status: status,
				AttestationSHA256: "sha256:" + strings.Repeat("d", 64), RegisteredAt: "2026-11-16T00:02:00Z",
			}
			nodes = append(nodes, rec)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/mesh/nodes":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []MeshNodeRecord{}
			for _, n := range nodes {
				if n.WorkspaceID == wsID {
					matched = append(matched, n)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(MeshNodeListResponse{WorkspaceID: wsID, Count: len(matched), Nodes: matched})

		case r.Method == http.MethodPost && p == "/v1/platform/mesh/dispatch":
			wsID, _ := body["workspace_id"].(string)
			wfName, _ := body["workflow_name"].(string)
			cls, _ := body["data_classification"].(string)
			allowBurst, _ := body["allow_sanitized_burst"].(bool)
			forceRaw, _ := body["force_raw_cloud_burst"].(bool)
			if forceRaw && cls == "restricted_pii" {
				w.WriteHeader(http.StatusUnprocessableEntity)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "Raw PII burst forbidden", "code": "mesh_sovereignty_violation"})
				return
			}
			status := "PINNED_EDGE_ONLY"
			var burstID *string
			cost := 0.0
			if allowBurst {
				status = "ATTESTED_COMPLETE"
				burstID = StringPtr("cluster-h100-us-east")
				cost = 0.0042
			}
			mu.Lock()
			rec := MeshHandoffRecord{
				HandoffID: fmt.Sprintf("mhand-go-%d", len(handoffs)+1), WorkspaceID: wsID, WorkflowName: wfName,
				DataClassification: cls, Status: status, EdgeNodeID: "edge-mac-m3-max", BurstNodeID: burstID,
				Stages: []MeshStageExecution{{
					StageName: "local_dlp_scrub", TargetTier: "edge_local", NodeID: "edge-mac-m3-max",
					ModelID: "keelway-core:7b", HardwareHAL: "apple_metal_secure_enclave", ZeroRawPIIEgress: true, CostUSD: 0.0,
				}},
				TotalCostUSD: cost, DLPRedactions: 2, AttestationSHA256: "sha256:" + strings.Repeat("e", 64), CreatedAt: "2026-11-16T00:03:00Z",
			}
			handoffs = append([]MeshHandoffRecord{rec}, handoffs...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/mesh/handoffs":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []MeshHandoffRecord{}
			for _, h := range handoffs {
				if h.WorkspaceID == wsID {
					matched = append(matched, h)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(MeshHandoffListResponse{WorkspaceID: wsID, Count: len(matched), Handoffs: matched})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p17"))
	ctx := context.Background()

	if _, err := c.Platform.ListSafetyVerifications(ctx, "ws-go-17", -1); err == nil {
		t.Fatal("expected negative limit error")
	}
	if _, err := c.Platform.RegisterMeshNode(ctx, RegisterMeshNodeRequest{Name: "   "}); err == nil {
		t.Fatal("expected empty name error")
	}
	if _, err := c.Platform.RegisterMeshNode(ctx, RegisterMeshNodeRequest{Name: "n1", Tier: "bad_tier"}); err == nil {
		t.Fatal("expected invalid tier error")
	}
	if _, err := c.Platform.DispatchMeshHandoff(ctx, DispatchMeshHandoffRequest{DataClassification: "secret_alien"}); err == nil {
		t.Fatal("expected invalid data_classification error")
	}

	unsafe, err := c.Platform.VerifyWorkflowSafety(ctx, VerifyWorkflowSafetyRequest{
		WorkspaceID: "ws-go-17",
		Nodes:       []SafetyWorkflowNodeInput{{NodeID: "wire_exec", ToolKind: "external_transfer", RequiresP10: BoolPtr(false)}},
	})
	if err != nil || unsafe.Status != "VIOLATION_FOUND" || len(unsafe.Violations) != 1 {
		t.Fatalf("VerifyWorkflowSafety unsafe failed: %+v, err=%v", unsafe, err)
	}

	safe, err := c.VerifyWorkflowSafety(ctx, VerifyWorkflowSafetyRequest{WorkspaceID: "ws-go-17", InjectP10Guards: true})
	if err != nil || safe.Status != "VERIFIED_SAFE" || len(safe.P10GuardsInjected) != 1 {
		t.Fatalf("VerifyWorkflowSafety safe failed: %+v, err=%v", safe, err)
	}

	if verList, err := c.Platform.ListSafetyVerifications(ctx, "ws-go-17", 10); err != nil || verList.Count != 2 {
		t.Fatalf("ListSafetyVerifications failed: %+v, err=%v", verList, err)
	}

	regNode, err := c.Platform.RegisterMeshNode(ctx, RegisterMeshNodeRequest{
		WorkspaceID: "ws-go-17", Name: "edge-tpm2", Tier: "edge_local", HardwareHAL: "linux_tpm2", VRAMGB: 24,
	})
	if err != nil || regNode.HardwareHAL != "linux_tpm2" {
		t.Fatalf("RegisterMeshNode failed: %+v, err=%v", regNode, err)
	}
	if nodeList, err := c.Platform.ListMeshNodes(ctx, "ws-go-17"); err != nil || nodeList.Count != 3 {
		t.Fatalf("ListMeshNodes failed: %+v, err=%v", nodeList, err)
	}

	attested, err := c.Platform.DispatchMeshHandoff(ctx, DispatchMeshHandoffRequest{WorkspaceID: "ws-go-17"})
	if err != nil || attested.Status != "ATTESTED_COMPLETE" || attested.BurstNodeID == nil {
		t.Fatalf("DispatchMeshHandoff attested failed: %+v, err=%v", attested, err)
	}
	pinned, err := c.DispatchMeshHandoff(ctx, DispatchMeshHandoffRequest{WorkspaceID: "ws-go-17", AllowSanitizedBurst: BoolPtr(false)})
	if err != nil || pinned.Status != "PINNED_EDGE_ONLY" || pinned.BurstNodeID != nil {
		t.Fatalf("DispatchMeshHandoff pinned failed: %+v, err=%v", pinned, err)
	}

	_, sovErr := c.Platform.DispatchMeshHandoff(ctx, DispatchMeshHandoffRequest{
		WorkspaceID: "ws-go-17", DataClassification: "restricted_pii", ForceRawCloudBurst: true,
	})
	var apiErr *APIError
	if !errors.As(sovErr, &apiErr) || apiErr.StatusCode != http.StatusUnprocessableEntity {
		t.Fatalf("expected 422 APIError on sovereignty violation, got %v", sovErr)
	}
	if handoffList, err := c.Platform.ListMeshHandoffs(ctx, "ws-go-17", 10); err != nil || handoffList.Count != 2 {
		t.Fatalf("ListMeshHandoffs failed: %+v, err=%v", handoffList, err)
	}
}
