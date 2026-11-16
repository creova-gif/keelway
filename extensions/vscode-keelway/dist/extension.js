/**
 * Keelway Dev — Official VS Code & Cursor Extension Entrypoint (`activate` / `deactivate`).
 * Wires loopback Debugger Bridge, URI handler, 4D CodeLens, SecretStorage auth, and Studio Webview.
 */
import { KeelwayBridgeClient, parseAttachUri } from "./bridgeClient.js";
import { KeelwayCodeLensProvider, scanWorkflowSymbols } from "./codeLensProvider.js";
import { handleWebviewMessage, renderStudioWebviewHtml } from "./studioWebview.js";
let activePanel = null;
function isSessionPaused(session) {
    return Boolean(session && session.status.toUpperCase() === "PAUSED");
}
function resolveHostApi(injected) {
    if (injected)
        return injected;
    const globalApi = globalThis.__keelwayVscodeApi;
    if (!globalApi) {
        throw new Error("VsCodeHostApi is required when running outside an injected Extension Host.");
    }
    return globalApi;
}
export async function activate(context, options = {}) {
    const vscode = resolveHostApi(options.hostApi);
    const cfg = vscode.workspace.getConfiguration("keelway");
    const controlPlaneUrl = cfg.get("controlPlaneUrl", "http://127.0.0.1:7420");
    const defaultWorkspace = cfg.get("defaultWorkspace", "default");
    const bridgeClient = new KeelwayBridgeClient({
        baseUrl: controlPlaneUrl,
        workspaceId: defaultWorkspace,
        workflowId: "WF-STUDIO-01",
        getToken: () => context.secrets.get("keelway.apiToken"),
        fetchImpl: options.fetchImpl,
    });
    let activeSession = null;
    const syncPausedContext = async (session) => {
        activeSession = session;
        await vscode.commands.executeCommand("setContext", "keelwayDebugPaused", isSessionPaused(session));
    };
    const refreshPanelHtml = async () => {
        if (!activePanel)
            return;
        const target = bridgeClient.getTarget();
        const [sessionsRes, bpRes] = await Promise.all([
            bridgeClient.listDebugSessions({ workspace_id: target.workspaceId }),
            bridgeClient.listBreakpoints({ workspace_id: target.workspaceId, workflow_id: target.workflowId }),
        ]);
        const latest = activeSession ?? sessionsRes.sessions.find((s) => isSessionPaused(s)) ?? sessionsRes.sessions[0] ?? null;
        await syncPausedContext(latest);
        activePanel.webview.html = renderStudioWebviewHtml({
            workspaceId: target.workspaceId,
            workflowId: target.workflowId,
            controlPlaneUrl: target.baseUrl,
            activeSession: latest,
            sessions: sessionsRes.sessions,
            breakpoints: bpRes.breakpoints,
        });
    };
    const openOrRevealStudio = async () => {
        if (activePanel) {
            activePanel.reveal(2);
            await refreshPanelHtml();
            return activePanel;
        }
        const panel = vscode.window.createWebviewPanel("keelway.studioDebugger", "Keelway 4D Studio Debugger", 2, {
            enableScripts: true,
            retainContextWhenHidden: true,
        });
        activePanel = panel;
        const msgDisp = panel.webview.onDidReceiveMessage(async (rawMsg) => {
            const result = await handleWebviewMessage(rawMsg, bridgeClient);
            if (result.kind === "session") {
                await syncPausedContext(result.session);
            }
            else {
                await syncPausedContext(result.sessions.find((s) => isSessionPaused(s)) ?? result.sessions[0] ?? null);
            }
            await panel.webview.postMessage({ type: "debugger_state", result });
        });
        const closeDisp = panel.onDidDispose(() => {
            msgDisp.dispose();
            closeDisp.dispose();
            activePanel = null;
        });
        context.subscriptions.push(msgDisp, closeDisp);
        await refreshPanelHtml();
        return panel;
    };
    const attachFromUri = async (rawUri) => {
        const target = parseAttachUri(rawUri);
        bridgeClient.configureTarget({ baseUrl: target.baseUrl, workspaceId: target.workspaceId, workflowId: target.workflowId });
        const sessionsRes = await bridgeClient.listDebugSessions({ workspace_id: target.workspaceId });
        const chosen = (target.sessionId ? sessionsRes.sessions.find((s) => s.session_id === target.sessionId) : undefined) ??
            sessionsRes.sessions.find((s) => isSessionPaused(s)) ??
            sessionsRes.sessions[0] ??
            null;
        await syncPausedContext(chosen);
        await openOrRevealStudio();
        await vscode.window.showInformationMessage(`Attached Keelway 4D Bridge (${target.workspaceId} · ${target.workflowId})`);
    };
    const runStepCommand = async (action) => {
        if (!activeSession) {
            const listed = await bridgeClient.listDebugSessions();
            activeSession = listed.sessions.find((s) => isSessionPaused(s)) ?? listed.sessions[0] ?? null;
        }
        if (!activeSession)
            return null;
        const updated = await bridgeClient.stepDebugSession(activeSession.session_id, { action });
        await syncPausedContext(updated);
        if (activePanel)
            await activePanel.webview.postMessage({ type: "debugger_state", result: { kind: "session", session: updated } });
        return updated;
    };
    const codeLensProvider = new KeelwayCodeLensProvider(bridgeClient, () => bridgeClient.getTarget());
    context.subscriptions.push(vscode.languages.registerCodeLensProvider([{ language: "python" }, { language: "typescript" }], codeLensProvider), vscode.window.registerUriHandler({ handleUri: (uri) => attachFromUri(uri.toString()) }), vscode.commands.registerCommand("keelway.attachBridge", async (uriArg) => {
        const raw = typeof uriArg === "string" && uriArg.trim() ? uriArg : await vscode.window.showInputBox({ prompt: "Enter Keelway attach URI", placeHolder: "vscode://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01" });
        if (raw)
            await attachFromUri(raw);
    }), vscode.commands.registerCommand("keelway.toggleConditionalBreakpoint", async (arg) => {
        const opts = typeof arg === "object" && arg !== null ? arg : {};
        let nodeId = opts.nodeId;
        let lineNumber = opts.lineNumber;
        const editor = vscode.window.activeTextEditor;
        if (!nodeId && editor) {
            const curLine = editor.selection.active.line;
            const syms = scanWorkflowSymbols(editor.document.getText(), editor.document.languageId);
            const found = syms.find((s) => s.lineZeroBased === curLine) ?? syms[0];
            nodeId = found?.symbolId;
            lineNumber = found?.line_start ?? curLine + 1;
        }
        if (!nodeId)
            return null;
        const existing = await bridgeClient.listBreakpoints({ workflow_id: opts.workflowId ?? bridgeClient.getTarget().workflowId });
        const hit = existing.breakpoints.find((b) => b.node_id === nodeId);
        if (hit && opts.conditionType === undefined) {
            return bridgeClient.deleteBreakpoint(hit.breakpoint_id);
        }
        return bridgeClient.setBreakpoint({ node_id: nodeId, workflow_id: opts.workflowId, condition_type: opts.conditionType ?? "always", threshold: opts.threshold, line_number: lineNumber });
    }), vscode.commands.registerCommand("keelway.stepOverNode", () => runStepCommand("step_over")), vscode.commands.registerCommand("keelway.stepIntoAgent", () => runStepCommand("step_into")), vscode.commands.registerCommand("keelway.continueExecution", () => runStepCommand("continue")), vscode.commands.registerCommand("keelway.openStudioPanel", () => openOrRevealStudio()), vscode.commands.registerCommand("keelway.approvePendingHarnessTicket", async (arg) => {
        const opts = typeof arg === "string"
            ? { ticketId: arg }
            : typeof arg === "object" && arg !== null
                ? arg
                : {};
        const pendingRes = await bridgeClient.listPendingHarnessTickets(opts.workspaceId);
        const selectedId = (opts.ticketId && opts.ticketId.trim()
            ? (pendingRes.tickets.find((t) => t.ticket_id === opts.ticketId?.trim())?.ticket_id ?? opts.ticketId.trim())
            : undefined) ?? pendingRes.tickets[0]?.ticket_id;
        if (!selectedId) {
            await vscode.window.showInformationMessage("No pending Keelway Co-Harness tickets.");
            return null;
        }
        const decided = await bridgeClient.decideHarnessTicket(selectedId, "APPROVED", opts.workspaceId);
        await vscode.window.showInformationMessage(`Approved Keelway Co-Harness ticket ${decided.ticket_id} (${decided.scrubbed_command})`);
        return decided;
    }));
    return { bridgeClient, codeLensProvider, getActiveSession: () => activeSession };
}
export function deactivate() {
    if (activePanel) {
        activePanel.dispose();
        activePanel = null;
    }
}
//# sourceMappingURL=extension.js.map