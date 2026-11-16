/**
 * Keelway 4D Studio Step-Debugger Webview Renderer & Message Dispatcher.
 * Strict `default-src 'none'` nonce CSP, zero external CDNs, zero inline browser `fetch()`.
 */
const NONCE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
export function createCspNonce(length = 32) {
    const bytes = new Uint8Array(length);
    globalThis.crypto.getRandomValues(bytes);
    let out = "";
    for (const byte of bytes) {
        out += NONCE_ALPHABET[byte % NONCE_ALPHABET.length];
    }
    return out;
}
function escapeHtml(raw) {
    return raw
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}
function sanitizeNonce(nonce) {
    const candidate = (nonce ?? "").replace(/[^A-Za-z0-9]/g, "");
    return candidate.length >= 16 ? candidate : createCspNonce(32);
}
export function renderStudioWebviewHtml(state, nonce) {
    const safeNonce = sanitizeNonce(nonce);
    const active = state.activeSession ?? state.sessions?.[0] ?? null;
    const sessionId = escapeHtml(active?.session_id ?? "");
    const statusText = escapeHtml(active?.status ?? "IDLE");
    const currentNode = escapeHtml(active?.active_step?.node_id ?? active?.current_node_id ?? "none");
    const stepIndex = active ? String(active.current_step_index ?? active.step_index ?? 0) : "0";
    const stateJson = escapeHtml(JSON.stringify(active?.variables ?? active?.state ?? {}, null, 2));
    const bpItems = (state.breakpoints ?? [])
        .map((bp) => `<li><code>${escapeHtml(bp.node_id ?? "*")}</code> — ${escapeHtml(bp.label ?? bp.condition_type ?? bp.condition ?? "always")} (${bp.enabled ? "enabled" : "muted"})</li>`)
        .join("");
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${safeNonce}'; script-src 'nonce-${safeNonce}';">
  <title>Keelway 4D Studio Debugger</title>
  <style nonce="${safeNonce}">
    body { font-family: system-ui, -apple-system, sans-serif; background: #0b0f17; color: #e2e8f0; margin: 0; padding: 16px; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 12px; }
    .badge { background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 4px 8px; font-size: 12px; }
    .toolbar { display: flex; gap: 8px; margin: 14px 0; flex-wrap: wrap; }
    button { background: #2563eb; color: #ffffff; border: none; border-radius: 6px; padding: 6px 12px; cursor: pointer; font-weight: 600; }
    button.secondary { background: #334155; }
    textarea { width: 100%; min-height: 120px; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; padding: 8px; font-family: monospace; box-sizing: border-box; }
    .panel { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
  </style>
</head>
<body data-session-id="${sessionId}" data-workspace-id="${escapeHtml(state.workspaceId)}">
  <div class="header">
    <div>
      <strong>▣ Keelway 4D Sovereign Agent Debugger</strong>
      <div>Workspace: <code>${escapeHtml(state.workspaceId)}</code> · Workflow: <code>${escapeHtml(state.workflowId)}</code></div>
    </div>
    <span class="badge" id="session-status">Status: ${statusText} · Node: ${currentNode} · Step #${stepIndex}</span>
  </div>
  <div class="toolbar">
    <button id="btn-step-over" type="button">Step Over (F10)</button>
    <button id="btn-step-into" type="button">Step Into (F11)</button>
    <button id="btn-continue" type="button">Continue (F5)</button>
    <button id="btn-refresh" class="secondary" type="button">Refresh Sessions</button>
  </div>
  <div class="panel">
    <label for="state-editor"><strong>Live Agent Variables (JSON)</strong></label>
    <textarea id="state-editor">${stateJson}</textarea>
    <div class="toolbar">
      <button id="btn-mutate" class="secondary" type="button">Mutate State</button>
    </div>
  </div>
  <div class="panel">
    <strong>Conditional Breakpoints</strong>
    <ul>${bpItems || "<li>No conditional breakpoints registered.</li>"}</ul>
  </div>
  <script nonce="${safeNonce}">
    (function () {
      const vscode = acquireVsCodeApi();
      const root = document.body;
      const getSessionId = () => root.getAttribute("data-session-id") || "";
      const getWorkspaceId = () => root.getAttribute("data-workspace-id") || "default";

      document.getElementById("btn-step-over")?.addEventListener("click", () => {
        vscode.postMessage({ type: "step_over", sessionId: getSessionId(), workspaceId: getWorkspaceId() });
      });
      document.getElementById("btn-step-into")?.addEventListener("click", () => {
        vscode.postMessage({ type: "step_into", sessionId: getSessionId(), workspaceId: getWorkspaceId() });
      });
      document.getElementById("btn-continue")?.addEventListener("click", () => {
        vscode.postMessage({ type: "continue", sessionId: getSessionId(), workspaceId: getWorkspaceId() });
      });
      document.getElementById("btn-refresh")?.addEventListener("click", () => {
        vscode.postMessage({ type: "refresh_sessions", workspaceId: getWorkspaceId() });
      });
      document.getElementById("btn-mutate")?.addEventListener("click", () => {
        const editor = document.getElementById("state-editor");
        const parsed = JSON.parse(editor ? editor.value : "{}");
        vscode.postMessage({ type: "mutate_state", sessionId: getSessionId(), workspaceId: getWorkspaceId(), statePatch: parsed });
      });
    })();
  </script>
</body>
</html>`;
}
export async function handleWebviewMessage(msg, bridgeClient) {
    switch (msg.type) {
        case "step_over": {
            const session = await bridgeClient.stepDebugSession(msg.sessionId, {
                action: "step_over",
                workspace_id: msg.workspaceId,
            });
            return { kind: "session", session };
        }
        case "step_into": {
            const session = await bridgeClient.stepDebugSession(msg.sessionId, {
                action: "step_into",
                workspace_id: msg.workspaceId,
            });
            return { kind: "session", session };
        }
        case "continue": {
            const session = await bridgeClient.stepDebugSession(msg.sessionId, {
                action: "continue",
                workspace_id: msg.workspaceId,
            });
            return { kind: "session", session };
        }
        case "mutate_state": {
            const session = await bridgeClient.stepDebugSession(msg.sessionId, {
                action: "mutate_state",
                workspace_id: msg.workspaceId,
                state_patch: msg.statePatch,
            });
            return { kind: "session", session };
        }
        case "refresh_sessions": {
            const list = await bridgeClient.listDebugSessions({ workspace_id: msg.workspaceId });
            return { kind: "sessions", sessions: list.sessions };
        }
        default: {
            const _exhaustive = msg;
            throw new Error(`Unhandled Studio webview message: ${JSON.stringify(_exhaustive)}`);
        }
    }
}
//# sourceMappingURL=studioWebview.js.map