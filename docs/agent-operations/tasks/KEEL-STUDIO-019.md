# Task Specification: KEEL-STUDIO-019

- **Title**: Phase 12 — Golden-Thread 4-Stage Journey Bar, Bidirectional KFlow ↔ Code Split Studio, Interactive Flight-Tape Waterfall Scrubber, Sandbox Blast-Radius Radar & Prompt Regression Gate
- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (3-Agent Parallel Wave: `12A` Backend/CLI, `12B` Tri-SDK/Website, `12C` Dev-App Creative Studio UI)
- **Branch**: `main`

---

## 1. Scope & File Ownership Boundaries

### Workstream 12A — Backend SQLite WAL, Bidirectional AST Sync, Sandbox Blast-Radius, Prompt Gate & Sovereign CLI
- `core/platform/kflow_bidirectional_sync.py` *(new, < 500 lines)*
- `core/platform/sandbox_blast_radius.py` *(new, < 550 lines)*
- `core/api/platform_studio_routes.py` *(new, < 250 lines)*
- `core/main.py` *(wire `platform_studio_router`)*
- `core/cli_studio.py` *(new, < 280 lines)*
- `core/cli_runtime.py` *(wire `register_studio_cli_subparsers` & `dispatch_studio_cli`)*
- `tests/test_phase12_bidirectional_studio_and_blast_radius.py` *(new, < 700 lines)*

### Workstream 12B — 5-Method Tri-SDK Parity (`Python`, `@keelway/sdk`, `keelway-go`) & Website Sync
- `core/sdk/platform_studio_client.py` *(new, < 360 lines)*
- `core/sdk/platform_runtime_client.py` *(inherit `AsyncPlatformStudioMixin` & `SyncPlatformStudioMixin`)*
- `sdk/typescript/src/platformStudio.ts` *(new, < 340 lines)*
- `sdk/typescript/src/platform.ts`, `sdk/typescript/src/types.ts`, `sdk/typescript/src/index.ts`, `sdk/typescript/dist/*`
- `sdk/typescript/tests/platform_phase12.test.mjs` *(new, < 360 lines)*
- `sdk/go/platform_phase12.go` & `sdk/go/platform_phase12_test.go` *(new, < 340 lines each)*
- `website/src/components/docs/DocsHub.tsx` *(< 500 lines, zero internal tokens)* & `website/src/components/home/CustomerJourneyGrid.tsx` *(`$39/seat` -> `$29/seat` calibration fix)*
- `tests/test_phase12_sdk_parity.py` *(new, < 520 lines)*

### Workstream 12C — Creative Dev-App UI/UX (`:7420/app`)
- `dev-app/src/lib/platformStudioApi.ts` *(new, < 550 lines)*
- `dev-app/src/components/platform/GoldenThreadJourneyBar.tsx` *(new, < 220 lines)* & `dev-app/src/components/platform/PlatformWorkspaceBar.tsx`
- `dev-app/src/components/platform/BidirectionalKflowStudioPanel.tsx` *(new, < 380 lines)* & `dev-app/src/components/platform/AutomationAndOpsViews.tsx`
- `dev-app/src/components/platform/FlightTapeScrubberAndRadar.tsx` *(new, < 380 lines)* & `dev-app/src/components/platform/FlightTapeDebuggerPanel.tsx`
- `dev-app/src/__tests__/phase12-golden-thread-studio.test.tsx` *(new, < 360 lines)*

---

## 2. Canonical API Contract (`/v1/platform/studio/*`)

1. `POST /v1/platform/studio/kflow/sync`
2. `POST /v1/platform/studio/blast-radius/record`
3. `GET /v1/platform/studio/blast-radius`
4. `POST /v1/platform/studio/prompt-gate/evaluate`
5. `GET /v1/platform/studio/prompt-gate/runs`
