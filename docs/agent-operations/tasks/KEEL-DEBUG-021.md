# Task Specification: KEEL-DEBUG-021

- **Title**: Phase 14 — Live Step-Through Debugger Breakpoints & Official VS Code / Cursor Extension Bridge
- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (`14A` Step-Debugger Engine & CLI Lead, `14B` VS Code/Cursor Extension & Tri-SDK Lead, `14C` Dev Tool Step-Debugger & CodeLens UI Lead)
- **Branch**: `main`

---

## 1. Scope & Strict File Ownership Boundaries

### Workstream 14A — SQLite WAL Step-Debugger Engine, FastAPI Routes & Sovereign CLI
- `core/platform/step_debugger.py` *(new, < 480 lines)*
- `core/api/platform_debugger_routes.py` *(new, < 280 lines — 7 OpenAPI 3.1 endpoints under `/v1/platform/debugger`)*
- `core/cli_debugger.py` *(new, < 240 lines — `keelway debug` subcommands)*
- `core/main.py` *(mount `platform_debugger_router`)*
- `core/cli_runtime.py` *(register & dispatch `core.cli_debugger`)*
- `tests/test_phase13_homepage_studio_and_release.py` *(relax `== 21` -> `>= 21` and `== 273` -> `>= 273`)*
- `tests/test_phase14_step_debugger_and_cli.py` *(new, < 380 lines)*

### Workstream 14B — Official VS Code / Cursor Extension (`extensions/vscode-keelway`) & Tri-Language SDK Parity
- `extensions/vscode-keelway/package.json` *(new)*
- `extensions/vscode-keelway/tsconfig.json` *(new)*
- `extensions/vscode-keelway/README.md` *(new)*
- `extensions/vscode-keelway/src/vscodeTypes.ts` *(new, < 120 lines)*
- `extensions/vscode-keelway/src/bridgeClient.ts` *(new, < 220 lines)*
- `extensions/vscode-keelway/src/codeLensProvider.ts` *(new, < 180 lines)*
- `extensions/vscode-keelway/src/studioWebview.ts` *(new, < 220 lines)*
- `extensions/vscode-keelway/src/extension.ts` *(new, < 180 lines)*
- `extensions/vscode-keelway/test/extension.test.mjs` *(new, < 260 lines)*
- `core/sdk/platform_debugger_client.py` *(new, < 280 lines)*
- `core/sdk/platform_runtime_client.py` *(inherit `AsyncPlatformDebuggerMixin` & `SyncPlatformDebuggerMixin`)*
- `sdk/typescript/src/platformDebugger.ts` *(new, < 320 lines)*
- `sdk/typescript/src/platform.ts`, `sdk/typescript/src/index.ts`, `sdk/typescript/package.json`
- `sdk/typescript/tests/platform_phase14.test.mjs` *(new, < 240 lines)*
- `sdk/go/platform_phase14.go` *(new, < 280 lines)* & `sdk/go/platform_phase14_test.go` *(new, < 280 lines)*

### Workstream 14C — `:7420/app` Live Step-Debugger, 4D CodeLens & IDE Bridge UI
- `dev-app/src/lib/platformDebuggerApi.ts` *(new, < 280 lines)*
- `dev-app/src/components/platform/StepDebuggerAndBridgePanel.tsx` *(new, < 460 lines)*
- `dev-app/src/components/platform/AgentsWorkspaceView.tsx` *(mount `<StepDebuggerAndBridgePanel />`)*
- `dev-app/src/__tests__/phase14-step-debugger-bridge.test.tsx` *(new, < 320 lines)*

### Lead Integration & Release Verification
- `website/openapi.json` & `website/public/openapi.json` (`280` paths)
- `website/product-facts.json` & `website/public/product-facts.json` (`22` features)
- `website/src/app/docs/page.tsx`, `website/src/components/layout/CommandPalette.tsx`, `website/src/app/api/search-index/route.ts`
- `tests/test_phase14_sdk_and_vscode_bridge.py` *(new, < 380 lines)*
- `scripts/verify_engineering_gates.sh` & `.github/workflows/ci.yml`
