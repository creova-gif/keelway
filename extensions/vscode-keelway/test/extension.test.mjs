import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { BridgeHttpError, KeelwayBridgeClient, parseAttachUri } from "../dist/bridgeClient.js";
import { formatCodeLensBadge, KeelwayCodeLensProvider, scanWorkflowSymbols } from "../dist/codeLensProvider.js";
import { activate, deactivate } from "../dist/extension.js";
import { handleWebviewMessage, renderStudioWebviewHtml } from "../dist/studioWebview.js";

function createMockDocument(uriPath, languageId, sourceText) {
  const lines = sourceText.split(/\r?\n/);
  return {
    uri: { fsPath: uriPath, path: uriPath, toString: () => `file://${uriPath}` },
    languageId,
    lineCount: lines.length,
    getText: () => sourceText,
    lineAt: (idx) => ({ lineNumber: idx, text: lines[idx] ?? "" }),
  };
}

function createMockFetch() {
  const calls = [];
  const breakpoints = [];
  const harnessTickets = [
    {
      ticket_id: "tkt-ext-01",
      workspace_id: "default",
      agent_host: "cursor",
      tool_name: "Bash",
      scrubbed_command: "git push origin main",
      command_sha256: "c".repeat(64),
      status: "PENDING",
      reviewer: null,
      decision_reason: null,
      created_at: "2026-11-16T02:00:00Z",
      decided_at: null,
      consumed_at: null,
      ticket_sha256: "d".repeat(64),
    },
  ];
  const sessions = [
    {
      session_id: "dbg-sess-01",
      workspace_id: "default",
      workflow_id: "WF-STUDIO-01",
      status: "PAUSED",
      current_step_index: 0,
      step_depth: 0,
      total_steps: 3,
      hit_reason: "always (step boundary)",
      active_step: { node_id: "plan", agent_id: "architect", tool_name: "kbrain_query", line_number: 2 },
      variables: { objective: "audit_release", approved: false },
      frame_sha256: "a".repeat(64),
    },
  ];
  const jsonRes = (status, payload) =>
    new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });

  const fetchImpl = async (urlStr, init = {}) => {
    const url = new URL(urlStr);
    const headers = { ...(init.headers ?? {}) };
    const body = init.body ? JSON.parse(String(init.body)) : null;
    calls.push({ method: init.method ?? "GET", pathname: url.pathname, query: Object.fromEntries(url.searchParams), headers, body });

    if (url.pathname === "/v1/platform/debugger/breakpoints" && init.method === "POST") {
      const bp = {
        breakpoint_id: `bp-${breakpoints.length + 1}`,
        workspace_id: body.workspace_id ?? "default",
        workflow_id: body.workflow_id ?? "WF-STUDIO-01",
        node_id: body.node_id ?? null,
        condition_type: body.condition_type ?? "always",
        threshold: body.threshold ?? null,
        enabled: body.enabled ?? true,
        line_number: body.line_number ?? 1,
      };
      breakpoints.push(bp);
      return jsonRes(200, bp);
    }
    if (url.pathname === "/v1/platform/debugger/breakpoints" && init.method === "GET") {
      const ws = url.searchParams.get("workspace_id") ?? "default";
      const wf = url.searchParams.get("workflow_id");
      const list = breakpoints.filter((b) => b.workspace_id === ws && (!wf || b.workflow_id === wf));
      return jsonRes(200, { workspace_id: ws, count: list.length, breakpoints: list });
    }
    if (url.pathname.startsWith("/v1/platform/debugger/breakpoints/") && init.method === "DELETE") {
      const bpId = decodeURIComponent(url.pathname.split("/").pop());
      const idx = breakpoints.findIndex((b) => b.breakpoint_id === bpId);
      if (idx >= 0) breakpoints.splice(idx, 1);
      return jsonRes(200, { deleted: idx >= 0, breakpoint_id: bpId, workspace_id: url.searchParams.get("workspace_id") ?? "default" });
    }
    if (url.pathname === "/v1/platform/debugger/sessions" && init.method === "POST") {
      if (body.initial_state && JSON.stringify(body.initial_state).includes("sk-live-secret123456")) {
        return jsonRes(422, { detail: "DLP policy violation: raw secret token detected" });
      }
      const created = {
        session_id: `dbg-sess-0${sessions.length + 1}`,
        workspace_id: body.workspace_id ?? "default",
        workflow_id: body.workflow_id ?? "WF-STUDIO-01",
        status: "PAUSED",
        current_step_index: 0,
        active_step: { node_id: "plan", agent_id: "architect", tool_name: "kbrain_query", line_number: 2 },
        variables: body.initial_state ?? {},
        frame_sha256: "b".repeat(64),
      };
      sessions.unshift(created);
      return jsonRes(200, created);
    }
    if (url.pathname === "/v1/platform/debugger/sessions" && init.method === "GET") {
      const ws = url.searchParams.get("workspace_id") ?? "default";
      const matched = sessions.filter((s) => s.workspace_id === ws || ws === "sec-ws");
      return jsonRes(200, { workspace_id: ws, count: matched.length, sessions: matched });
    }
    if (url.pathname.endsWith("/step") && init.method === "POST") {
      const sessionId = decodeURIComponent(url.pathname.split("/").slice(-2, -1)[0]);
      const sess = sessions.find((s) => s.session_id === sessionId) ?? sessions[0];
      if (body.state_patch && JSON.stringify(body.state_patch).includes("sk-live-secret123456")) {
        return jsonRes(422, { detail: "DLP policy violation: raw secret token detected in state_patch" });
      }
      sess.current_step_index += 1;
      if (body.state_patch) sess.variables = { ...sess.variables, ...body.state_patch };
      sess.status = body.action === "continue" ? "COMPLETED" : "PAUSED";
      return jsonRes(200, { ...sess });
    }
    if (url.pathname === "/v1/platform/debugger/codelens" && init.method === "GET") {
      return jsonRes(200, {
        workspace_id: url.searchParams.get("workspace_id") ?? "default",
        lenses: [
          { symbol: "plan", line_start: 2, model_checkpoint: "keelway-core:7b", p50_ms: 142, avg_cost_usd: 0, provenance_4d: "Apache-2.0 · Local Metal · Self-Operated · Zero-Egress", attached_breakpoints: 1 },
        ],
      });
    }
    if (url.pathname === "/v1/platform/harness/tickets" && init.method === "GET") {
      const ws = url.searchParams.get("workspace_id") ?? "default";
      const st = url.searchParams.get("status");
      const matched = harnessTickets.filter((t) => t.workspace_id === ws && (!st || t.status === st));
      return jsonRes(200, { workspace_id: ws, count: matched.length, tickets: matched });
    }
    const decideMatch = url.pathname.match(/^\/v1\/platform\/harness\/tickets\/([^/]+)\/decide$/);
    if (decideMatch && init.method === "POST") {
      const ticketId = decodeURIComponent(decideMatch[1]);
      const tkt = harnessTickets.find((t) => t.ticket_id === ticketId);
      if (!tkt) return jsonRes(404, { detail: "Ticket not found" });
      if (tkt.status === "CONSUMED") return jsonRes(409, { detail: "Ticket already consumed" });
      tkt.status = body.decision;
      tkt.reviewer = body.reviewer ?? "vscode-bridge";
      tkt.decision_reason = body.reason ?? "Approved via Keelway IDE Bridge";
      tkt.decided_at = "2026-11-16T02:01:00Z";
      return jsonRes(200, { ...tkt });
    }
    if (url.pathname === "/v1/platform/distill/promotion/evaluate" && init.method === "POST") {
      const ws = body.workspace_id ?? "default";
      const tag = body.task_tag ?? "code-patch";
      const minPairs = body.min_pairs ?? 3;
      const minAvg = body.min_avg_parity ?? 0.85;
      const vol = body.monthly_request_volume ?? 50000;
      const pairCount = tag === "low-sample" ? 1 : 6;
      const avgParity = tag === "low-parity" ? 0.68 : 0.94;
      const verdict = pairCount < minPairs ? "NEEDS_MORE_PAIRS" : avgParity < minAvg ? "HOLD_ON_FRONTIER" : "PROMOTE_TO_OPENCORE";
      const savings = verdict === "PROMOTE_TO_OPENCORE" ? Number((0.018 * vol).toFixed(2)) : 0;
      return jsonRes(200, {
        evaluation_id: "pgate-ext-19",
        workspace_id: ws,
        task_tag: tag,
        target_local_model: body.target_local_model ?? "keelway-core:7b",
        verdict,
        pair_count: pairCount,
        min_pairs: minPairs,
        avg_parity_score: avgParity,
        min_avg_parity: minAvg,
        avg_frontier_cost_usd: 0.018,
        monthly_request_volume: vol,
        projected_monthly_savings_usd: savings,
        recommendation: `Canary gate evaluated ${verdict}`,
        gate_sha256: "e".repeat(64),
        evaluated_at: "2026-11-16T03:05:00Z",
      });
    }
    return jsonRes(404, { detail: "Not found" });
  };

  return { calls, fetchImpl };
}

describe("vscode-keelway official VS Code & Cursor extension", () => {
  it("parses vscode:// and cursor:// attach URIs and rejects unsafe schemes or ports", () => {
    const vsTarget = parseAttachUri("vscode://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01");
    assert.equal(vsTarget.scheme, "vscode");
    assert.equal(vsTarget.baseUrl, "http://127.0.0.1:7420");
    assert.equal(vsTarget.workspaceId, "default");
    assert.equal(vsTarget.workflowId, "WF-STUDIO-01");

    const curTarget = parseAttachUri("cursor://keelway.vscode-keelway/attach?port=7455&workspace=sec-ws&workflow=WF-SEC-02&session=dbg-sess-01");
    assert.equal(curTarget.scheme, "cursor");
    assert.equal(curTarget.baseUrl, "http://127.0.0.1:7455");
    assert.equal(curTarget.workspaceId, "sec-ws");
    assert.equal(curTarget.sessionId, "dbg-sess-01");

    assert.throws(() => parseAttachUri("https://evil.example/attach?port=7420"), /Unsupported URI scheme/);
    assert.throws(() => parseAttachUri("vscode://other.ext/attach?port=7420"), /Unexpected extension authority/);
    assert.throws(() => parseAttachUri("vscode://keelway.vscode-keelway/open?port=7420"), /Unsupported attach path/);
    assert.throws(() => parseAttachUri("cursor://keelway.vscode-keelway/attach?port=99999"), /Invalid loopback port/);
  });

  it("enforces Bearer auth, zero Origin header hygiene, and 422 DLP error propagation", async () => {
    const { calls, fetchImpl } = createMockFetch();
    const bridge = new KeelwayBridgeClient({ baseUrl: "http://127.0.0.1:7420", apiToken: "kw_ext_token_14", fetchImpl });

    const bp = await bridge.setBreakpoint({ node_id: "plan", condition_type: "cost_usd_gt", threshold: 0.25, line_number: 2 });
    assert.equal(bp.breakpoint_id, "bp-1");
    assert.equal(calls[0].headers.Authorization, "Bearer kw_ext_token_14");
    assert.equal("Origin" in calls[0].headers, false);
    assert.equal("origin" in calls[0].headers, false);

    const started = await bridge.startDebugSession({ workflow_id: "WF-STUDIO-01", initial_state: { dry_run: true } });
    assert.equal(started.status, "PAUSED");

    await assert.rejects(
      () => bridge.stepDebugSession(started.session_id, { action: "mutate_state", state_patch: { api_key: "sk-live-secret123456" } }),
      (err) => err instanceof BridgeHttpError && err.status === 422 && err.detail.includes("DLP"),
    );
  });

  it("scans Python & TypeScript workflow symbols and renders 4D CodeLens badges", async () => {
    const { fetchImpl } = createMockFetch();
    const bridge = new KeelwayBridgeClient({ apiToken: "kw_ext_token_14", fetchImpl });
    const provider = new KeelwayCodeLensProvider(bridge);

    const pySource = ["# workflow", 'workflow.add_node("plan", role="architect")', 'studio.node("verify")', "@agent", "async def release_guard(state):", "    return state"].join("\n");
    const pySyms = scanWorkflowSymbols(pySource, "python");
    assert.deepEqual(pySyms.map((s) => ({ id: s.symbolId, line0: s.lineZeroBased, line1: s.line_start })), [
      { id: "plan", line0: 1, line1: 2 },
      { id: "verify", line0: 2, line1: 3 },
      { id: "release_guard", line0: 3, line1: 4 },
    ]);

    const pyLenses = await provider.provideCodeLenses(createMockDocument("/ws/flow.py", "python", pySource));
    assert.equal(pyLenses.length, 3);
    assert.equal(pyLenses[0].command.title, "▣ Keelway 4D · keelway-core:7b · P50 142ms · $0.000 · Zero-Egress · 1 Breakpoint");

    const tsSource = ['await client.platform.syncKflowStudio({ workflow_id: "WF-TS-14", nodes: [', '  { id: "ingest_span", label: "Ingest" },', "] });", 'studio.node("audit_gate");'].join("\n");
    const tsLenses = await provider.provideCodeLenses(createMockDocument("/ws/flow.ts", "typescript", tsSource));
    assert.equal(tsLenses.length, 3);
    assert.equal(formatCodeLensBadge({ symbol: "n", attached_breakpoints: 2 }), "▣ Keelway 4D · keelway-core:7b · P50 142ms · $0.000 · Zero-Egress · 2 Breakpoints");
  });

  it("renders strict default-src 'none' nonce CSP HTML with zero inline fetch()", () => {
    const html = renderStudioWebviewHtml(
      { workspaceId: "default<script>", workflowId: "WF-STUDIO-01", controlPlaneUrl: "http://127.0.0.1:7420", activeSession: null, breakpoints: [] },
      "NonceAlphaNumeric1234567890",
    );
    assert.ok(html.includes("default-src 'none'; style-src 'nonce-NonceAlphaNumeric1234567890'; script-src 'nonce-NonceAlphaNumeric1234567890';"));
    assert.equal(html.includes("fetch("), false);
    assert.equal(html.includes("<script>"), false);
    assert.ok(html.includes("acquireVsCodeApi()"));
  });

  it("activates commands, URI handler, SecretStorage token, Studio webview messages, and deactivates cleanly", async () => {
    const { calls, fetchImpl } = createMockFetch();
    const registeredCommands = new Map();
    const contextUpdates = [];
    let uriHandler = null;
    let webviewMsgListener = null;
    const postedMessages = [];

    const mockHost = {
      commands: {
        registerCommand: (id, cb) => (registeredCommands.set(id, cb), { dispose() {} }),
        executeCommand: async (cmd, key, val) => {
          if (cmd === "setContext") contextUpdates.push([key, val]);
        },
      },
      languages: { registerCodeLensProvider: () => ({ dispose() {} }) },
      window: {
        activeTextEditor: { document: createMockDocument("/ws/flow.py", "python", 'workflow.add_node("plan")'), selection: { active: { line: 0, character: 0 } } },
        registerUriHandler: (h) => ((uriHandler = h), { dispose() {} }),
        createWebviewPanel: () => ({
          webview: { html: "", onDidReceiveMessage: (fn) => ((webviewMsgListener = fn), { dispose() {} }), postMessage: async (msg) => (postedMessages.push(msg), true) },
          reveal() {},
          onDidDispose: () => ({ dispose() {} }),
          dispose() {},
        }),
        showInformationMessage: async () => undefined,
        showErrorMessage: async () => undefined,
        showInputBox: async () => undefined,
      },
      workspace: { getConfiguration: () => ({ get: (_k, defVal) => defVal }) },
    };
    const extCtx = {
      subscriptions: [],
      secrets: { get: async (k) => (k === "keelway.apiToken" ? "kw_secret_vault_14" : undefined), store: async () => {}, delete: async () => {} },
    };

    const handle = await activate(extCtx, { hostApi: mockHost, fetchImpl });
    await uriHandler.handleUri({ scheme: "cursor", authority: "keelway.vscode-keelway", path: "/attach", query: "port=7420&workspace=default&workflow=WF-STUDIO-01", toString: () => "cursor://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01" });
    assert.deepEqual(contextUpdates.at(-1), ["keelwayDebugPaused", true]);
    assert.equal(calls[0].headers.Authorization, "Bearer kw_secret_vault_14");

    const bpCreated = await registeredCommands.get("keelway.toggleConditionalBreakpoint")({ nodeId: "plan", conditionType: "before_p10_gate" });
    assert.equal(bpCreated.node_id, "plan");
    const bpDeleted = await registeredCommands.get("keelway.toggleConditionalBreakpoint")({ nodeId: "plan" });
    assert.equal(bpDeleted.deleted, true);

    await registeredCommands.get("keelway.stepOverNode")();
    await registeredCommands.get("keelway.stepIntoAgent")();
    await webviewMsgListener({ type: "mutate_state", sessionId: "dbg-sess-01", statePatch: { approved: true } });
    await webviewMsgListener({ type: "refresh_sessions", workspaceId: "default" });
    assert.equal(handle.getActiveSession().variables.approved, true);

    const completed = await registeredCommands.get("keelway.continueExecution")();
    assert.equal(completed.status, "COMPLETED");
    assert.deepEqual(contextUpdates.at(-1), ["keelwayDebugPaused", false]);
    assert.ok(postedMessages.length >= 3);

    const refreshRes = await handleWebviewMessage({ type: "refresh_sessions", workspaceId: "default" }, handle.bridgeClient);
    assert.equal(refreshRes.kind, "sessions");
    deactivate();
  });

  it("approves pending Co-Harness tickets end-to-end via keelway.approvePendingHarnessTicket", async () => {
    const { calls, fetchImpl } = createMockFetch();
    const registeredCommands = new Map();
    const infoMessages = [];
    const mockHost = {
      commands: {
        registerCommand: (id, cb) => (registeredCommands.set(id, cb), { dispose() {} }),
        executeCommand: async () => undefined,
      },
      languages: { registerCodeLensProvider: () => ({ dispose() {} }) },
      window: {
        registerUriHandler: () => ({ dispose() {} }),
        createWebviewPanel: () => ({ webview: { html: "", onDidReceiveMessage: () => ({ dispose() {} }), postMessage: async () => true }, reveal() {}, onDidDispose: () => ({ dispose() {} }), dispose() {} }),
        showInformationMessage: async (msg) => (infoMessages.push(msg), undefined),
        showErrorMessage: async () => undefined,
        showInputBox: async () => undefined,
      },
      workspace: { getConfiguration: () => ({ get: (_k, defVal) => defVal }) },
    };
    const extCtx = {
      subscriptions: [],
      secrets: { get: async (k) => (k === "keelway.apiToken" ? "kw_secret_vault_18" : undefined), store: async () => {}, delete: async () => {} },
    };

    const handle = await activate(extCtx, { hostApi: mockHost, fetchImpl });
    assert.ok(registeredCommands.has("keelway.approvePendingHarnessTicket"));

    const pendingBefore = await handle.bridgeClient.listPendingHarnessTickets("default");
    assert.equal(pendingBefore.count, 1);
    assert.equal(pendingBefore.tickets[0].ticket_id, "tkt-ext-01");

    const decided = await registeredCommands.get("keelway.approvePendingHarnessTicket")();
    assert.equal(decided.ticket_id, "tkt-ext-01");
    assert.equal(decided.status, "APPROVED");
    assert.equal(decided.reviewer, "vscode-bridge");
    assert.ok(infoMessages.some((m) => m.includes("Approved Keelway Co-Harness ticket tkt-ext-01")));

    const decideCall = calls.find((c) => c.pathname === "/v1/platform/harness/tickets/tkt-ext-01/decide");
    assert.ok(decideCall);
    assert.equal(decideCall.headers.Authorization, "Bearer kw_secret_vault_18");
    assert.equal("Origin" in decideCall.headers, false);
    assert.equal(decideCall.body.decision, "APPROVED");

    const noneRemaining = await registeredCommands.get("keelway.approvePendingHarnessTicket")();
    assert.equal(noneRemaining, null);
    assert.ok(infoMessages.some((m) => m.includes("No pending Keelway Co-Harness tickets")));
    deactivate();
  });

  it("inspects OpenCore distillation readiness end-to-end via keelway.inspectDistillationReadiness", async () => {
    const { calls, fetchImpl } = createMockFetch();
    const registeredCommands = new Map();
    const infoMessages = [];
    const mockHost = {
      commands: {
        registerCommand: (id, cb) => (registeredCommands.set(id, cb), { dispose() {} }),
        executeCommand: async () => undefined,
      },
      languages: { registerCodeLensProvider: () => ({ dispose() {} }) },
      window: {
        registerUriHandler: () => ({ dispose() {} }),
        createWebviewPanel: () => ({ webview: { html: "", onDidReceiveMessage: () => ({ dispose() {} }), postMessage: async () => true }, reveal() {}, onDidDispose: () => ({ dispose() {} }), dispose() {} }),
        showInformationMessage: async (msg) => (infoMessages.push(msg), undefined),
        showErrorMessage: async () => undefined,
        showInputBox: async () => undefined,
      },
      workspace: { getConfiguration: () => ({ get: (_k, defVal) => defVal }) },
    };
    const extCtx = {
      subscriptions: [],
      secrets: { get: async (k) => (k === "keelway.apiToken" ? "kw_secret_vault_19" : undefined), store: async () => {}, delete: async () => {} },
    };

    await activate(extCtx, { hostApi: mockHost, fetchImpl });
    assert.ok(registeredCommands.has("keelway.inspectDistillationReadiness"));

    const promoteEval = await registeredCommands.get("keelway.inspectDistillationReadiness")({
      workspaceId: "ws-ide-19",
      taskTag: "code-patch",
      targetLocalModel: "keelway-core:7b",
      minPairs: 3,
      minAvgParity: 0.85,
      monthlyRequestVolume: 50000,
    });
    assert.equal(promoteEval.verdict, "PROMOTE_TO_OPENCORE");
    assert.equal(promoteEval.avg_parity_score, 0.94);
    assert.equal(promoteEval.projected_monthly_savings_usd, 900);
    assert.ok(
      infoMessages.some(
        (m) => m.includes("PROMOTE_TO_OPENCORE") && m.includes("0.94") && m.includes("900.00"),
      ),
    );

    const promoCall = calls.find((c) => c.pathname === "/v1/platform/distill/promotion/evaluate");
    assert.ok(promoCall);
    assert.equal(promoCall.headers.Authorization, "Bearer kw_secret_vault_19");
    assert.equal("Origin" in promoCall.headers, false);
    assert.equal(promoCall.body.workspace_id, "ws-ide-19");
    assert.equal(promoCall.body.monthly_request_volume, 50000);

    const holdEval = await registeredCommands.get("keelway.inspectDistillationReadiness")("low-parity");
    assert.equal(holdEval.verdict, "HOLD_ON_FRONTIER");
    assert.equal(holdEval.projected_monthly_savings_usd, 0);
    deactivate();
  });
});
