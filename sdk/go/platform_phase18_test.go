package keelway

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func sha256String(v string) string {
	sum := sha256.Sum256([]byte(v))
	return hex.EncodeToString(sum[:])
}

func TestPlatformPhase18CoharnessAndWorktreeCiGate(t *testing.T) {
	t.Parallel()

	var mu sync.Mutex
	tickets := map[string]*ApprovalTicketRecord{}
	var gateRuns []WorktreeCiGateRunRecord

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer kw_live_go_p18" {
			t.Errorf("expected Bearer kw_live_go_p18, got %q", got)
		}
		var body map[string]any
		if r.Body != nil {
			_ = json.NewDecoder(r.Body).Decode(&body)
		}
		w.Header().Set("Content-Type", "application/json")
		p := r.URL.Path

		switch {
		case r.Method == http.MethodPost && p == "/v1/platform/harness/hooks/render":
			wsID, _ := body["workspace_id"].(string)
			host, _ := body["agent_host"].(string)
			mode, _ := body["mode"].(string)
			targets := map[string]string{"claude_code": ".claude/settings.json", "cursor": ".cursor/hooks.json", "codex_cli": ".codex/hooks.toml"}
			content := fmt.Sprintf(`{"hook":"PreToolUse","host":%q,"mode":%q}`, host, mode)
			_ = json.NewEncoder(w).Encode(HookManifestResponse{
				WorkspaceID: wsID, AgentHost: host, Mode: mode, TargetConfigPath: targets[host],
				HookEvent: "PreToolUse", ConfigContent: content, CLIInstallHint: "keelway harness install --host " + host, ConfigSHA256: sha256String(content),
			})

		case r.Method == http.MethodPost && p == "/v1/platform/harness/intercept":
			wsID, _ := body["workspace_id"].(string)
			host, _ := body["agent_host"].(string)
			toolName, _ := body["tool_name"].(string)
			cmd, _ := body["command"].(string)
			tktIDRaw, _ := body["ticket_id"].(string)
			cmdHash := sha256String(cmd)
			scrubbed := strings.ReplaceAll(cmd, "sk-live-secret99", "[REDACTED_SECRET]")
			dlpCount := 0
			if scrubbed != cmd {
				dlpCount = 1
			}
			verdict, reason := "ALLOW", "safe_readonly"
			var tktPtr *string
			if tktIDRaw != "" {
				tktPtr = StringPtr(tktIDRaw)
			}

			mu.Lock()
			if dlpCount > 0 || strings.Contains(cmd, "rm -rf /") {
				verdict, reason = "DENY", "dlp_or_destructive_block"
			} else if strings.Contains(cmd, "git push") {
				if tktIDRaw == "" {
					newID := fmt.Sprintf("tkt-go-%d", len(tickets)+1)
					tickets[newID] = &ApprovalTicketRecord{
						TicketID: newID, WorkspaceID: wsID, AgentHost: host, ToolName: toolName,
						ScrubbedCommand: scrubbed, CommandSHA256: cmdHash, Status: "PENDING",
						CreatedAt: "2026-11-16T01:00:00Z", TicketSHA256: sha256String(newID + cmdHash),
					}
					tktPtr, verdict, reason = StringPtr(newID), "HOLD_TICKET", "p10_ticket_required"
				} else if tkt, ok := tickets[tktIDRaw]; !ok {
					verdict, reason = "DENY", "ticket_not_found"
				} else if tkt.CommandSHA256 != cmdHash {
					verdict, reason = "DENY", "ticket_command_mismatch"
				} else if tkt.Status == "CONSUMED" {
					verdict, reason = "DENY", "ticket_already_consumed"
				} else if tkt.Status == "DENIED" {
					verdict, reason = "DENY", "ticket_denied"
				} else if tkt.Status == "PENDING" {
					verdict, reason = "HOLD_TICKET", "ticket_still_pending"
				} else {
					tkt.Status, tkt.ConsumedAt = "CONSUMED", StringPtr("2026-11-16T01:02:00Z")
					verdict, reason = "ALLOW_WITH_TICKET", "ticket_verified_consumed"
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(HarnessInterceptionRecord{
				InterceptionID: "int-go-1", WorkspaceID: wsID, AgentHost: host, ToolName: toolName,
				ScrubbedCommand: scrubbed, CommandSHA256: cmdHash, Verdict: verdict, ReasonCode: reason,
				Explanation: reason, TicketID: tktPtr, DLPRedactions: dlpCount, EventSHA256: sha256String(verdict + cmdHash), CreatedAt: "2026-11-16T01:00:00Z",
			})

		case r.Method == http.MethodGet && p == "/v1/platform/harness/tickets":
			wsID, st := r.URL.Query().Get("workspace_id"), r.URL.Query().Get("status")
			mu.Lock()
			matched := []ApprovalTicketRecord{}
			for _, tkt := range tickets {
				if tkt.WorkspaceID == wsID && (st == "" || tkt.Status == st) {
					matched = append(matched, *tkt)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(ApprovalTicketListResponse{WorkspaceID: wsID, Count: len(matched), Tickets: matched})

		case r.Method == http.MethodPost && strings.HasPrefix(p, "/v1/platform/harness/tickets/") && strings.HasSuffix(p, "/decide"):
			tktID := strings.TrimSuffix(strings.TrimPrefix(p, "/v1/platform/harness/tickets/"), "/decide")
			decision, _ := body["decision"].(string)
			rev, _ := body["reviewer"].(string)
			rsn, _ := body["reason"].(string)
			mu.Lock()
			tkt, ok := tickets[tktID]
			if !ok || tkt.Status == "CONSUMED" {
				mu.Unlock()
				code := http.StatusNotFound
				if ok {
					code = http.StatusConflict
				}
				w.WriteHeader(code)
				_ = json.NewEncoder(w).Encode(map[string]any{"detail": "ticket error"})
				return
			}
			tkt.Status, tkt.Reviewer, tkt.DecisionReason, tkt.DecidedAt = decision, StringPtr(rev), StringPtr(rsn), StringPtr("2026-11-16T01:01:00Z")
			cp := *tkt
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(cp)

		case r.Method == http.MethodPost && p == "/v1/platform/harness/ci-gate/evaluate":
			wsID, _ := body["workspace_id"].(string)
			wfName, _ := body["workflow_name"].(string)
			minScore, _ := body["min_eval_score"].(float64)
			status, winnerID, winnerModel := "PASS", StringPtr("cand-local"), StringPtr("keelway-core:7b")
			if rawBody, _ := json.Marshal(body); strings.Contains(string(rawBody), "sk-live-") {
				status, winnerID, winnerModel = "FAIL_SAFETY", nil, nil
			}
			mu.Lock()
			rec := WorktreeCiGateRunRecord{
				GateRunID: fmt.Sprintf("cigate-go-%d", len(gateRuns)+1), WorkspaceID: wsID, WorkflowName: wfName,
				Status: status, MinEvalScore: minScore, WinnerCandidateID: winnerID, WinnerModel: winnerModel, CostSavedUSD: 0.048,
				Candidates: []WorktreeCandidateInput{{CandidateID: "cand-local", WorktreeBranch: "wt/opencore-7b", ModelID: "keelway-core:7b", ProviderTier: "local_opencore", TestsPassed: true, EvalScore: 0.92}},
				GateSHA256: strings.Repeat("f", 64), CreatedAt: "2026-11-16T01:03:00Z",
			}
			gateRuns = append([]WorktreeCiGateRunRecord{rec}, gateRuns...)
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(rec)

		case r.Method == http.MethodGet && p == "/v1/platform/harness/ci-gate/runs":
			wsID := r.URL.Query().Get("workspace_id")
			mu.Lock()
			matched := []WorktreeCiGateRunRecord{}
			for _, g := range gateRuns {
				if g.WorkspaceID == wsID {
					matched = append(matched, g)
				}
			}
			mu.Unlock()
			_ = json.NewEncoder(w).Encode(WorktreeCiGateRunListResponse{WorkspaceID: wsID, Count: len(matched), Runs: matched})

		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL, WithAPIKey("kw_live_go_p18"))
	ctx := context.Background()

	if _, err := c.Platform.RenderAgentHookConfig(ctx, RenderAgentHookConfigRequest{AgentHost: "vim"}); err == nil {
		t.Fatal("expected invalid agent_host error")
	}
	if _, err := c.Platform.ListHarnessTickets(ctx, "ws-go-18", "UNKNOWN", 10); err == nil {
		t.Fatal("expected invalid status error")
	}
	if _, err := c.Platform.DecideHarnessTicket(ctx, "   ", DecideHarnessTicketRequest{Decision: "APPROVED"}); err == nil {
		t.Fatal("expected empty ticketID error")
	}

	manifest, err := c.RenderAgentHookConfig(ctx, RenderAgentHookConfigRequest{WorkspaceID: "ws-go-18", AgentHost: "codex_cli"})
	if err != nil || manifest.TargetConfigPath != ".codex/hooks.toml" {
		t.Fatalf("RenderAgentHookConfig failed: %+v, err=%v", manifest, err)
	}
	dlpBlock, err := c.Platform.InterceptAgentToolCall(ctx, InterceptAgentToolCallRequest{WorkspaceID: "ws-go-18", Command: "curl sk-live-secret99"})
	if err != nil || dlpBlock.Verdict != "DENY" || strings.Contains(dlpBlock.ScrubbedCommand, "sk-live-secret99") {
		t.Fatalf("DLP block failed: %+v, err=%v", dlpBlock, err)
	}
	held, err := c.InterceptAgentToolCall(ctx, InterceptAgentToolCallRequest{WorkspaceID: "ws-go-18", Command: "git push origin main"})
	if err != nil || held.Verdict != "HOLD_TICKET" || held.TicketID == nil {
		t.Fatalf("Intercept HOLD_TICKET failed: %+v, err=%v", held, err)
	}
	tktID := *held.TicketID

	if listed, err := c.ListHarnessTickets(ctx, "ws-go-18", "PENDING", 10); err != nil || listed.Count != 1 {
		t.Fatalf("ListHarnessTickets failed: %+v, err=%v", listed, err)
	}
	if decided, err := c.DecideHarnessTicket(ctx, tktID, DecideHarnessTicketRequest{WorkspaceID: "ws-go-18", Decision: "APPROVED"}); err != nil || decided.Status != "APPROVED" {
		t.Fatalf("DecideHarnessTicket failed: %+v, err=%v", decided, err)
	}
	if swapped, err := c.InterceptAgentToolCall(ctx, InterceptAgentToolCallRequest{WorkspaceID: "ws-go-18", Command: "git push --force origin main", TicketID: tktID}); err != nil || swapped.ReasonCode != "ticket_command_mismatch" {
		t.Fatalf("expected ticket_command_mismatch, got %+v, err=%v", swapped, err)
	}
	if consumed, err := c.InterceptAgentToolCall(ctx, InterceptAgentToolCallRequest{WorkspaceID: "ws-go-18", Command: "git push origin main", TicketID: tktID}); err != nil || consumed.Verdict != "ALLOW_WITH_TICKET" {
		t.Fatalf("expected ALLOW_WITH_TICKET, got %+v, err=%v", consumed, err)
	}
	if replayed, err := c.InterceptAgentToolCall(ctx, InterceptAgentToolCallRequest{WorkspaceID: "ws-go-18", Command: "git push origin main", TicketID: tktID}); err != nil || replayed.ReasonCode != "ticket_already_consumed" {
		t.Fatalf("expected ticket_already_consumed, got %+v, err=%v", replayed, err)
	}
	_, conflictErr := c.DecideHarnessTicket(ctx, tktID, DecideHarnessTicketRequest{WorkspaceID: "ws-go-18", Decision: "APPROVED"})
	var apiErr *APIError
	if !errors.As(conflictErr, &apiErr) || apiErr.StatusCode != http.StatusConflict {
		t.Fatalf("expected 409 APIError on consumed ticket, got %v", conflictErr)
	}
	if gatePass, err := c.EvaluateWorktreeCiGate(ctx, EvaluateWorktreeCiGateRequest{WorkspaceID: "ws-go-18"}); err != nil || gatePass.Status != "PASS" {
		t.Fatalf("EvaluateWorktreeCiGate PASS failed: %+v, err=%v", gatePass, err)
	}
	gateFail, err := c.EvaluateWorktreeCiGate(ctx, EvaluateWorktreeCiGateRequest{
		WorkspaceID: "ws-go-18", Candidates: []WorktreeCandidateInput{{CandidateID: "c1", WorktreeBranch: "wt/leak", ModelID: "m1", ProviderTier: "local_opencore", TestsPassed: true, EvalScore: 0.95, DiffExcerpt: "+ sk-live-leak"}},
	})
	if err != nil || gateFail.Status != "FAIL_SAFETY" {
		t.Fatalf("EvaluateWorktreeCiGate FAIL_SAFETY failed: %+v, err=%v", gateFail, err)
	}
	if runs, err := c.ListWorktreeCiGateRuns(ctx, "ws-go-18", 10); err != nil || runs.Count != 2 {
		t.Fatalf("ListWorktreeCiGateRuns failed: %+v, err=%v", runs, err)
	}
}
