# Phase 17 Implementation Plan (`KEEL-SAFETY-024`): Tier 3 `:7420/app` Dev-Tool Moats + Minimalist YC / Investor Website Curation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete 100% of the Competitive Strategy Tier 3 Moats inside the local `:7420/app` Dev Tool, CLI, and Python/TS/Go SDKs (**Formal Safety State-Machine Verifier** + **Federated Edge-to-Cluster Agent Mesh**), while simultaneously using a dedicated Website Curation Subagent (`17D`) to remove unnecessary internal technical clutter from the public website and sharpen YC / investor signal.

**Architecture:** `SQLiteSafetyAndMeshEngine` (`core/platform/safety_and_mesh.py`) persists bounded state-machine safety verifications (`safety_verifications`) and hardware-attested edge-to-cluster workload handoffs (`mesh_nodes`, `mesh_handoffs`) in `platform_runtime.db` (`PRAGMA journal_mode=WAL`) with DLP secret scrubbing. Public website routes (`/`, `/docs`, `/governance`, `/models`, `/api-reference`) are slimmed to high-conviction YC/investor proof without adding new public feature bloat.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite WAL, TypeScript (`@keelway/sdk` + React 19 + Next.js 15 + Vitest + `axe-core`), Go 1.22+ (`keelway-go`).

---

## Exact Wire Contract (`/v1/platform/safety/*` & `/v1/platform/mesh/*`)

All 6 new routes live in `core/api/platform_safety_mesh_routes.py`, mounted in `core/main.py` (`298` total OpenAPI 3.1 paths):

1. `POST /v1/platform/safety/verify` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), workflow_id?: string (default "WF-TREASURY-01"), workflow_name?: string (default "treasury-wire-approver"), nodes?: Array<{ node_id: string, role?: string (default "agent"), tool_kind?: "read_only" | "write" | "destructive_shell" | "external_transfer" | "cloud_egress", requires_p10?: boolean, max_iterations?: number, data_classification?: "public" | "internal" | "restricted_pii" }>, edges?: Array<{ from_node: string, to_node: string, condition?: string }>, airgap_mode?: boolean (default false), inject_p10_guards?: boolean (default false) }`
   - Response (`SafetyVerificationRecord`):
     `{ verification_id, workspace_id, workflow_id, workflow_name, status: "VERIFIED_SAFE" | "VIOLATION_FOUND", states_explored: number, invariants_checked: Array<{ invariant_id: "no_unguarded_destructive_tool" | "no_privilege_escalation" | "bounded_termination" | "airgap_zero_egress", passed: boolean, description: string }>, violations: Array<{ invariant_id: string, severity: "CRITICAL" | "HIGH", offending_node: string, counterexample_path: string[], remediation: string }>, p10_guards_injected: string[], dlp_redactions: number, proof_sha256: string, created_at: string }`
   - Behavior:
     - Checks all 4 formal invariants deterministically across reachable state paths:
       1. `no_unguarded_destructive_tool`: any node with `tool_kind` in `{"destructive_shell", "external_transfer"}` MUST have `requires_p10=true` (unless `inject_p10_guards=true`, which auto-injects `requires_p10=true` and records `node_id` in `p10_guards_injected`).
       2. `no_privilege_escalation`: a `"viewer"` or `"untrusted_tool"` role node cannot transition directly into a `"destructive_shell"` / `"external_transfer"` node without an intervening P-10 gate.
       3. `bounded_termination`: any cycle or `max_iterations` must satisfy `1 <= max_iterations <= 10` (no unbounded cycle).
       4. `airgap_zero_egress`: when `airgap_mode=true` or node `data_classification == "restricted_pii"`, `tool_kind == "cloud_egress"` is forbidden unless scrubbed/local.
     - Persists every verification into `safety_verifications` with `proof_sha256` (`sha256:...`).

2. `GET /v1/platform/safety/verifications?workspace_id=default&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, verifications: SafetyVerificationRecord[] }`

3. `POST /v1/platform/mesh/nodes` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), node_id?: string, name: string, tier: "edge_local" | "cluster_burst", hardware_hal: "apple_metal_secure_enclave" | "nvidia_h100_cc" | "linux_tpm2", region?: string (default "local-loopback"), vram_gb?: number (default 32), status?: "ONLINE" | "DRAINING" (default "ONLINE") }`
   - Response (`MeshNodeRecord`):
     `{ node_id, workspace_id, name, tier, hardware_hal, region, vram_gb, status, attestation_sha256, registered_at }`
   - Note: Each workspace auto-seeds 2 default attested nodes (`edge-mac-m3-max` on `edge_local` / `apple_metal_secure_enclave` and `cluster-h100-us-east` on `cluster_burst` / `nvidia_h100_cc`) on first list/dispatch if empty.

4. `GET /v1/platform/mesh/nodes?workspace_id=default` (`read:all`):
   - Response: `{ workspace_id, count, nodes: MeshNodeRecord[] }`

5. `POST /v1/platform/mesh/dispatch` (`workflows:run`):
   - Request:
     `{ workspace_id?: string (default "default"), workflow_name?: string (default "clinical-synthesis-pipeline"), task_summary?: string (default "Ingest patient intake & synthesize anonymized cohort summary"), data_classification?: "public" | "internal" | "restricted_pii" (default "restricted_pii"), allow_sanitized_burst?: boolean (default true), force_raw_cloud_burst?: boolean (default false) }`
   - Response (`MeshHandoffRecord`):
     `{ handoff_id, workspace_id, workflow_name, data_classification, status: "ATTESTED_COMPLETE" | "PINNED_EDGE_ONLY", edge_node_id, burst_node_id: string | null, stages: Array<{ stage_name: string, target_tier: "edge_local" | "cluster_burst", node_id: string, model_id: string, hardware_hal: string, zero_raw_pii_egress: boolean, cost_usd: number }>, total_cost_usd: number, dlp_redactions: number, attestation_sha256: string, created_at: string }`
   - Rejects (`HTTP 422` fail-closed, `code: "mesh_sovereignty_violation"`): `force_raw_cloud_burst=true` when `data_classification == "restricted_pii"` (raw PII can NEVER burst off `edge_local` without local sanitization!).

6. `GET /v1/platform/mesh/handoffs?workspace_id=default&limit=25` (`read:all`):
   - Response: `{ workspace_id, count, handoffs: MeshHandoffRecord[] }`

---

## Parallel Workstreams & Strict File Ownership

- [ ] **Task 1 (Workstream 17A — Backend Safety Verifier & Edge Mesh Engine, FastAPI & CLI):**
  - Own exclusively:
    - `core/platform/safety_and_mesh.py` (`< 480` lines)
    - `core/api/platform_safety_mesh_routes.py` (`< 250` lines)
    - `core/cli_safety_mesh.py` (`< 230` lines)
    - `core/main.py` & `core/cli_runtime.py`
    - `tests/test_phase17_safety_verifier_and_mesh_cli.py` (`< 380` lines)

- [ ] **Task 2 (Workstream 17B — Tri-Language SDK Parity: Python, TypeScript, Go):**
  - Own exclusively:
    - `core/sdk/platform_safety_mesh_client.py` (`< 250` lines) + `core/sdk/platform_runtime_client.py` (`< 700` lines)
    - `sdk/typescript/src/platformSafetyMesh.ts` (`< 300` lines) + `sdk/typescript/src/platform.ts` (`< 700` lines) + `sdk/typescript/src/index.ts` (`< 700` lines) + `sdk/typescript/package.json` + `sdk/typescript/tests/platform_phase17.test.mjs` (`< 240` lines)
    - `sdk/go/platform_phase17.go` (`< 270` lines) + `sdk/go/platform_phase17_test.go` (`< 250` lines)

- [ ] **Task 3 (Workstream 17C — `:7420/app` Security Studio UI):**
  - Own exclusively:
    - `dev-app/src/lib/platformSafetyMeshApi.ts` (`< 280` lines)
    - `dev-app/src/components/platform/FormalSafetyAndEdgeMeshPanel.tsx` (`< 440` lines)
    - `dev-app/src/components/platform/SecurityWorkspaceView.tsx` (`< 420` lines)
    - `dev-app/src/__tests__/phase17-safety-and-edge-mesh.test.tsx` (`< 320` lines)

- [ ] **Task 4 (Workstream 17D — Dedicated Website Minimalist & YC/Investor Curation Agent):**
  - Own exclusively:
    - `website/src/app/page.tsx`
    - `website/src/components/docs/DocsHub.tsx` (`< 360` lines — slimmed from `486` lines while preserving all required test tokens!)
    - `website/src/app/governance/page.tsx`
    - `website/src/app/models/page.tsx`
    - `website/src/app/api-reference/page.tsx`

- [ ] **Task 5 (Lead Integration, OpenAPI Sync, Cold Headless Chromium E2E & Release Gates):**
  - Export `website/openapi.json` & `website/public/openapi.json` (`298` paths).
  - Create `tests/test_phase17_sdk_and_yc_website.py` (`< 340` lines) & wire Phase 17 suites into `scripts/verify_engineering_gates.sh`.
  - Rebuild `core/dev_app_dist/`, run `uvx ruff check .`, `./scripts/verify_engineering_gates.sh` (`8/8` green), `npm --prefix website run typecheck && npm --prefix website run build`, execute cold headless Chromium + SQLite WAL proof (`verify-keelway-phase17-proof/`), commit, push to `origin/main`, and verify GitHub Actions + Vercel.
