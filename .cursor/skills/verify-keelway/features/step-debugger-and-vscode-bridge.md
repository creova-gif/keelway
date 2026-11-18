# Feature Verification: Live Step-Through Debugger & VS Code / Cursor Bridge (`KEEL-DEBUG-021`)

## Overview
Verifies Keelway Dev's Chrome-DevTools-style Live Conditional Step-Through Debugger (`/v1/platform/debugger/*`), in-place DLP-guarded state mutation, 4D Routing CodeLens, and Official VS Code / Cursor Extension Bridge (`extensions/vscode-keelway`) inside `:7420/app` (`Agents` view) and Sovereign CLI (`keelway debug`).

## Preconditions
- Cold-launch Keelway Dev via `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --artifact-dir <dir>` or bind uvicorn against a fresh SQLite database (`DATABASE_URL` + `KEELWAY_PLATFORM_DB_PATH`).

## Cold Browser E2E Verification Steps
1. Navigate to `http://127.0.0.1:<port>/app?token=<launch_token>` and switch to the **Agents** workspace tab.
2. Scroll to **Live Step-Through Debugger & VS Code / Cursor Bridge** (`#step-debugger-bridge-panel`).
3. Create a conditional breakpoint (`condition_type = "cost_usd_gt"`, `threshold = 0.25` or `"before_shell_tool"`), then click **Start Debug Session**.
4. Assert session transitions to `PAUSED`, displays the triggered `hit_breakpoint_id`, `hit_reason`, active call-stack frame, and deterministic `frame_sha256` receipt.
5. Enter a clean variable override in **Mutate Frame State (DLP-Guarded)** and click **Apply State Patch**; verify `mutation_count >= 1` and updated `frame_sha256`.
6. Click **Step Into (F11)** and **Step Over (F10)**; verify active step index/depth advances cleanly with zero console or page errors.
7. Verify **4D Routing CodeLens & IDE Attach** displays `vscode://keelway.vscode-keelway/attach` and `cursor://keelway.vscode-keelway/attach` URIs.
8. Confirm SQLite persistence via `keelway debug session list --db-path <db> --json` and `keelway debug breakpoint list --db-path <db> --json`.
