# Keelway Dev — Sovereign Agent Debugger & 4D Studio Bridge

Official zero-dependency VS Code and Cursor extension (`v1.1.0`) for **Keelway Dev** sovereign AI engineering workflows.

## Capabilities

- **4D Inline CodeLens (`Python` & `TypeScript`)**: Displays live model provenance, P50 latency, token cost, zero-egress posture, and active breakpoint counts directly above `add_node(...)`, `studio.node(...)`, `@agent`, and `syncKflowStudio(...)` symbols:
  `▣ Keelway 4D · keelway-core:7b · P50 142ms · $0.000 · Zero-Egress · 1 Breakpoint`
- **Interactive Step-Through Agent Debugger**:
  - `F10` (`keelway.stepOverNode`) — Step over the current workflow node when `keelwayDebugPaused` is active.
  - `F11` (`keelway.stepIntoAgent`) — Step into agent prompt, tool invocation, and P10 approval state.
  - `F5` (`keelway.continueExecution`) — Continue workflow execution until the next conditional breakpoint or completion.
  - `keelway.toggleConditionalBreakpoint` — Attach AST-safe conditional breakpoints on workflow nodes.
- **One-Click URI Deep-Link Bridge**:
  Supports `vscode://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01` and `cursor://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01`.
- **Zero-CSRF Loopback & Strict Nonce CSP Security**:
  - Extension Host HTTP requests authenticate with `SecretStorage` (`keelway.apiToken`) via `Authorization: Bearer <token>` and strip any `Origin` header to preserve local loopback origin enforcement.
  - The 4D Studio Webview enforces `default-src 'none'; style-src 'nonce-…'; script-src 'nonce-…';` with zero external CDN assets and zero browser `fetch()` calls, communicating exclusively via `acquireVsCodeApi().postMessage(...)`.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `keelway.controlPlaneUrl` | `http://127.0.0.1:7420` | Local loopback URL for the Keelway Sovereign Control Plane. |
| `keelway.defaultWorkspace` | `default` | Default workspace ID for debugging sessions and CodeLens telemetry. |

## Build & Offline Verification

```bash
npm run build
npm test
```
