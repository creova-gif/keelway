# Universal Coding-Agent Co-Harness & Parallel Worktree CI Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local `<10ms` PreToolUse Coding-Agent Co-Harness (`Claude Code`, `Cursor`, `Codex CLI`) with single-use SHA-256 P-10 Approval Tickets plus a Parallel Worktree Arena & Deterministic `ci-gate` Evaluator across Keelway Core, CLI, Python/TS/Go SDKs, VS Code/Cursor Bridge, and `:7420/app` Operations Studio.

**Architecture:** `SQLiteAgentCoharnessEngine` (`core/platform/agent_coharness.py`) persists intercepted tool evaluations (`harness_interceptions`), single-use command-hash-bound approval tickets (`harness_approval_tickets`), and multi-candidate worktree CI gate evaluations (`worktree_ci_gate_runs`) in `platform_runtime.db` (`PRAGMA journal_mode=WAL`) with pre-storage DLP secret scrubbing. Zero files under `website/**` are touched.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite WAL, TypeScript (`@keelway/sdk` + VS Code/Cursor Extension + React 19 + Vitest + `axe-core`), Go 1.22+ (`keelway-go`).

**Spec:** `/Users/justinmafie/.gemini/antigravity/brain/4fc93daa-32c3-4fbe-a51e-f37db6591901/phase18_coharness_hooks_and_worktree_cigate_design.md`

## Global Constraints

- **STRICT ZERO `website/` TOUCH:** Never create, edit, or stage any file under `website/**` or `tests/test_website_facts.py` (owned exclusively by conversation `8fde1df8-a4b6-4789-bc4a-1e4c108741a3`).
- **STRICT ZERO BRAND-SHELL TOUCH:** Do not touch `DESIGN.md`, `web-console/index.html`, `dev-app/src/components/shell/DevAppShell.tsx`, `dev-app/src/components/platform/PlatformWorkspaceBar.tsx`, `dev-app/src/components/platform/BidirectionalKflowStudioPanel.tsx`, `dev-app/src/components/platform/FlightTapeScrubberAndRadar.tsx`, `dev-app/src/styles/tokens.css`, or `dev-app/src/components/ui/BrandMark.tsx`.
- **Module-Size Ratchets:** Every new file strictly `< 480` lines; `core/sdk/platform_runtime_client.py < 700` lines; `sdk/typescript/src/platform.ts < 700` lines; `sdk/typescript/src/index.ts < 700` lines.
- **Coding Rules:** Top-level imports only (zero inline imports inside function/method bodies); TypeScript exhaustive `never` check in `default:` case of `switch` over union/enum types; never run `uv run` (use `.venv/bin/pytest`, `.venv/bin/python`, `uvx ruff check`).

## Review Focus

1. **Ticket Replay & Command-Swap Attack:** An approved single-use `ticket_id` submitted a second time (after consumption) OR submitted with a modified `command` whose `command_sha256` differs from the ticket's `command_sha256` MUST fail closed (`DENY`, `reason_code: "ticket_already_consumed"` or `"ticket_command_mismatch"`).
2. **Denied or Unapproved Ticket Submission:** Submitting a `PENDING` or `DENIED` `ticket_id` to `/v1/platform/harness/intercept` must NOT grant execution (`HOLD_TICKET` if still pending, `DENY` if denied).
3. **Pre-Storage DLP Secret Scrubbing:** Intercepted commands containing inline secrets (`curl -H "Authorization: Bearer sk-live-..."`, `ghp_...`, `AKIA...`) must be both `DENY`-blocked AND scrubbed to `[REDACTED_SECRET]` before writing to `harness_interceptions` / `harness_approval_tickets` / `worktree_ci_gate_runs`.
4. **Worktree Diff Secret / Safety Failure:** `evaluate_worktree_ci_gate` receiving a candidate diff containing leaked credentials (`sk-live-`, `PRIVATE KEY`) or failing eval threshold (`eval_score < min_eval_score`) must deterministically return `FAIL_SAFETY` or `FAIL_REGRESSION` rather than `PASS`.
5. **Read-Only RBAC Enforcement:** Roles `auditor` and `viewer` can read hook manifests (`POST /hooks/render` or `GET`), tickets (`GET /tickets`), and CI gate runs (`GET /ci-gate/runs`), but receive `HTTP 403` on mutating endpoints (`/intercept`, `/tickets/{ticket_id}/decide`, `/ci-gate/evaluate`) and have disabled mutation buttons in `:7420/app`.

---

## Exact Wire Contract (`/v1/platform/harness/*` — 6 New OpenAPI Paths -> `304` Total)

1. `POST /v1/platform/harness/hooks/render` (`read:all`):
   - Request: `{ workspace_id?: string (default "default"), agent_host?: "claude_code" | "cursor" | "codex_cli" (default "claude_code"), mode?: "enforce" | "audit_only" (default "enforce") }`
   - Response (`HookManifestResponse`): `{ workspace_id, agent_host, mode, target_config_path: string, hook_event: "PreToolUse", config_content: string, cli_install_hint: string, config_sha256: string }`

2. `POST /v1/platform/harness/intercept` (`workflows:run`):
   - Request: `{ workspace_id?: string (default "default"), agent_host?: "claude_code" | "cursor" | "codex_cli" (default "claude_code"), tool_name?: string (default "Bash"), command?: string (default "git push origin main"), ticket_id?: string | null }`
   - Response (`HarnessInterceptionRecord`):
     `{ interception_id, workspace_id, agent_host, tool_name, scrubbed_command, command_sha256, verdict: "ALLOW" | "ALLOW_WITH_TICKET" | "HOLD_TICKET" | "DENY", reason_code: string, explanation: string, ticket_id: string | null, dlp_redactions: number, event_sha256: string, created_at: string }`
   - Classification rules:
     - Hard `DENY`: `rm -rf /`, `mkfs`, `dd if=`, `~/.ssh/id_`, `/etc/shadow`, raw secret exfiltration (`sk-live-`, `AKIA`, `ghp_`, `BEGIN PRIVATE KEY` paired with network/shell or raw secret leak in command).
     - `ALLOW`: read/test commands (`pytest`, `npm test`, `go test`, `git status`, `git diff`, `ls`, `cat `, `ruff check`) when no secrets/destructive flags present.
     - Sensitive mutation (`git push`, `DROP TABLE`, `DELETE FROM`, `kubectl apply`, `terraform apply`, `docker push`, `curl -X POST`, `chmod 777`):
       - Without `ticket_id`: creates `PENDING` `ApprovalTicketRecord` in `harness_approval_tickets` and returns `verdict: "HOLD_TICKET"`, `ticket_id`.
       - With `ticket_id`: verifies ticket exists in `workspace_id`, `command_sha256` matches exact command (`DENY` `"ticket_command_mismatch"` if tampered!), `status == "APPROVED"` and `consumed == False` (`DENY` `"ticket_already_consumed"` if already used, `"ticket_denied"` if `DENIED`, `"HOLD_TICKET"` if still `PENDING`). Marks ticket `CONSUMED` (`consumed_at`) and returns `verdict: "ALLOW_WITH_TICKET"`.

3. `GET /v1/platform/harness/tickets?workspace_id=default&status=&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, tickets: ApprovalTicketRecord[] }`
   - `ApprovalTicketRecord`: `{ ticket_id, workspace_id, agent_host, tool_name, scrubbed_command, command_sha256, status: "PENDING" | "APPROVED" | "DENIED" | "CONSUMED", reviewer: string | null, decision_reason: string | null, created_at: string, decided_at: string | null, consumed_at: string | null, ticket_sha256: string }`

4. `POST /v1/platform/harness/tickets/{ticket_id}/decide` (`workflows:run`):
   - Request: `{ workspace_id?: string (default "default"), decision: "APPROVED" | "DENIED", reviewer?: string (default "lead-engineer"), reason?: string (default "Verified safe workspace scope") }`
   - Response: `ApprovalTicketRecord` (`404` if `ticket_id` unknown, `409` if already `CONSUMED`).

5. `POST /v1/platform/harness/ci-gate/evaluate` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), workflow_name?: string (default "pr-worktree-arena"), diff_summary?: string (default "Refactor retry backoff & add unit test in core/platform/"), min_eval_score?: number (default 0.85), candidates?: Array<{ candidate_id: string, worktree_branch: string, model_id: string, provider_tier: "local_opencore" | "frontier_byom", tests_passed: boolean, eval_score: number, cost_usd: number, diff_excerpt?: string }> }`
     - Default 2-candidate worktree arena when `candidates` omitted:
       1. `{"candidate_id": "cand-local", "worktree_branch": "wt/opencore-7b", "model_id": "keelway-core:7b", "provider_tier": "local_opencore", "tests_passed": True, "eval_score": 0.92, "cost_usd": 0.0, "diff_excerpt": "+ assert retry_budget <= 3"}`
       2. `{"candidate_id": "cand-frontier", "worktree_branch": "wt/sonnet-byom", "model_id": "claude-3-7-sonnet", "provider_tier": "frontier_byom", "tests_passed": True, "eval_score": 0.93, "cost_usd": 0.048, "diff_excerpt": "+ assert retry_budget <= 3"}`
   - Response (`WorktreeCiGateRunRecord`):
     `{ gate_run_id, workspace_id, workflow_name, status: "PASS" | "FAIL_REGRESSION" | "FAIL_SAFETY", min_eval_score, winner_candidate_id: string | null, winner_model: string | null, cost_saved_usd: number, dlp_redactions: number, candidates: Array<...>, gate_sha256: string, created_at: string }`

6. `GET /v1/platform/harness/ci-gate/runs?workspace_id=default&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, runs: WorktreeCiGateRunRecord[] }`

---

## Parallel Tasks & Exclusive File Ownership

- [ ] **Task 1 (Workstream `18A` — Co-Harness & Worktree CI Gate Backend, FastAPI & CLI):**
  - Exclusive files:
    - `core/platform/agent_coharness.py` (`< 450` lines)
    - `core/api/platform_harness_routes.py` (`< 240` lines)
    - `core/cli_harness.py` (`< 220` lines)
    - `core/main.py` (`304` OpenAPI paths) & `core/cli_runtime.py`
    - `tests/test_phase18_coharness_and_cigate_cli.py` (`< 380` lines)

- [ ] **Task 2 (Workstream `18B` — Tri-Language SDK Parity + VS Code/Cursor Bridge):**
  - Exclusive files:
    - `core/sdk/platform_harness_client.py` (`< 240` lines) + `core/sdk/platform_runtime_client.py` (`< 700` lines)
    - `sdk/typescript/src/platformHarness.ts` (`< 290` lines) + `sdk/typescript/src/platform.ts` (`< 700` lines) + `sdk/typescript/src/index.ts` (`< 700` lines) + `sdk/typescript/package.json` + `sdk/typescript/tests/platform_phase18.test.mjs` (`< 240` lines)
    - `sdk/go/platform_phase18.go` (`< 260` lines) + `sdk/go/platform_phase18_test.go` (`< 240` lines)
    - `extensions/vscode-keelway/package.json`, `extensions/vscode-keelway/src/bridgeClient.ts`, `extensions/vscode-keelway/src/extension.ts`, `extensions/vscode-keelway/test/extension.test.mjs`

- [ ] **Task 3 (Workstream `18C` — `:7420/app` Operations Co-Harness & CI Gate Studio UI):**
  - Exclusive files:
    - `dev-app/src/lib/platformHarnessApi.ts` (`< 250` lines)
    - `dev-app/src/components/platform/AgentCoharnessAndCiGatePanel.tsx` (`< 430` lines)
    - `dev-app/src/components/platform/AutomationAndOpsViews.tsx` (`< 620` lines — mount inside `OperationsWorkspaceView`)
    - `dev-app/src/__tests__/phase18-coharness-and-cigate.test.tsx` (`< 310` lines)

- [ ] **Task 4 (Lead Integration, Cold Headless Chromium + SQLite WAL Proof & Selective CI Ship):**
  - Create `tests/test_phase18_sdk_and_vscode_coharness.py` (`< 340` lines) & wire Phase 18 suites into `scripts/verify_engineering_gates.sh`.
  - Run `uvx ruff check .` & `./scripts/verify_engineering_gates.sh` (`8/8` stages).
  - Run cold headless Chromium + CLI + SQLite WAL proof (`verify-keelway-phase18-proof/`).
  - Selectively stage ONLY Phase 18 files (zero `website/**` or brand-touched files), commit, push, and verify `5/5` GitHub Actions CI green.
