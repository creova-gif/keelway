# Task Specification: KEEL-KFLOW-022

- **Title**: Phase 15 — Bounded Cyclic & Conditional KFlow Sub-Graphs + Pre-Run Cost/Privacy Autopilot
- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (`15A` Cyclic KFlow & Autopilot Engine/CLI Lead, `15B` Tri-SDK Parity Lead, `15C` Dev Tool Cyclic Studio & Autopilot UI Lead)
- **Branch**: `main`

---

## 1. Scope & Strict File Ownership Boundaries

### Workstream 15A — SQLite WAL Cyclic KFlow Engine, Pre-Run Autopilot, FastAPI Routes & CLI
- `core/platform/kflow_cyclic_autopilot.py` *(new, < 480 lines)*
- `core/api/platform_cyclic_routes.py` *(new, < 260 lines — 6 OpenAPI 3.1 endpoints under `/v1/platform/kflow`)*
- `core/cli_cyclic.py` *(new, < 240 lines — `keelway kflow-cyclic` & `keelway autopilot` subcommands)*
- `core/main.py` *(mount `platform_cyclic_router`)*
- `core/cli_runtime.py` *(register & dispatch `core.cli_cyclic`)*
- `tests/test_phase14_step_debugger_and_cli.py` & `tests/test_phase14_sdk_and_vscode_bridge.py` *(relax `== 280` -> `>= 280` and `== 22` -> `>= 22`)*
- `tests/test_phase15_cyclic_kflow_and_cli.py` *(new, < 380 lines)*

### Workstream 15B — Tri-Language SDK Parity (`Python`, `TypeScript`, `Go`)
- `core/sdk/platform_cyclic_client.py` *(new, < 260 lines)*
- `core/sdk/platform_runtime_client.py` *(inherit `AsyncPlatformCyclicMixin` & `SyncPlatformCyclicMixin`)*
- `sdk/typescript/src/platformCyclic.ts` *(new, < 310 lines)*
- `sdk/typescript/src/platform.ts`, `sdk/typescript/src/index.ts`, `sdk/typescript/package.json`
- `sdk/typescript/tests/platform_phase15.test.mjs` *(new, < 240 lines)*
- `sdk/go/platform_phase15.go` *(new, < 270 lines)* & `sdk/go/platform_phase15_test.go` *(new, < 250 lines)*

### Workstream 15C — `:7420/app` Cyclic KFlow & Cost/Privacy Autopilot Studio UI
- `dev-app/src/lib/platformCyclicApi.ts` *(new, < 280 lines)*
- `dev-app/src/components/platform/CyclicKflowAndAutopilotPanel.tsx` *(new, < 450 lines)*
- `dev-app/src/components/platform/AutomationAndOpsViews.tsx` *(mount `<CyclicKflowAndAutopilotPanel />`)*
- `dev-app/src/__tests__/phase15-cyclic-kflow-autopilot.test.tsx` *(new, < 320 lines)*

### Lead Integration & Release Verification
- `website/openapi.json` & `website/public/openapi.json` (`286` paths)
- `website/product-facts.json` & `website/public/product-facts.json` (`23` features)
- `website/src/components/docs/DocsHub.tsx`, `website/src/components/layout/CommandPalette.tsx`, `website/src/app/api/search-index/route.ts`
- `tests/test_phase15_sdk_and_website_sync.py` *(new, < 360 lines)*
- `scripts/verify_engineering_gates.sh`
