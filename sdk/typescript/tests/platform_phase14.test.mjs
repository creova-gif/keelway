import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  PermissionDeniedError,
  PlatformClient,
  PlatformDebuggerClient,
  PlatformDebuggerDelegate,
  PolicyViolationError,
  TaskNotFoundError,
} from "../dist/index.js";

async function startPhase14MockServer() {
  const recorded = [];
  const breakpoints = [];
  const sessions = [];

  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const rawBody = Buffer.concat(chunks).toString("utf8");
    const parsedBody = rawBody ? JSON.parse(rawBody) : null;
    const reqUrl = new URL(req.url ?? "/", "http://127.0.0.1");
    const searchParams = Object.fromEntries(reqUrl.searchParams.entries());
    recorded.push({ method: req.method, pathname: reqUrl.pathname, searchParams, headers: req.headers, body: parsedBody });

    const sendJson = (status, payload) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(payload));
    };

    if (req.headers.authorization !== "Bearer kw_live_phase14_ts") return sendJson(401, { detail: "Invalid bearer token" });
    const p = reqUrl.pathname;
    const isViewer = req.headers["x-keelway-role"] === "viewer";

    if (req.method === "POST" && p === "/v1/platform/debugger/breakpoints") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied breakpoint mutation" });
      const bp = {
        breakpoint_id: `bp-p14-${breakpoints.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: parsedBody.workflow_id ?? "WF-STUDIO-01",
        node_id: parsedBody.node_id ?? null,
        file_path: parsedBody.file_path ?? "workflows/refund_agent.py",
        line_number: parsedBody.line_number ?? null,
        condition_type: parsedBody.condition_type ?? "always",
        threshold: parsedBody.threshold ?? null,
        enabled: parsedBody.enabled ?? true,
        label: parsedBody.label ?? parsedBody.condition_type ?? "always",
        created_at: "2026-11-15T22:00:00Z",
      };
      breakpoints.push(bp);
      return sendJson(200, bp);
    }
    if (req.method === "GET" && p === "/v1/platform/debugger/breakpoints") {
      const wsId = searchParams.workspace_id ?? "default";
      const wfId = searchParams.workflow_id;
      const matched = breakpoints.filter((b) => b.workspace_id === wsId && (!wfId || b.workflow_id === wfId));
      return sendJson(200, { workspace_id: wsId, count: matched.length, breakpoints: matched });
    }
    if (req.method === "DELETE" && p.startsWith("/v1/platform/debugger/breakpoints/")) {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied breakpoint deletion" });
      const bpId = decodeURIComponent(p.split("/").pop());
      const wsId = searchParams.workspace_id ?? "default";
      const idx = breakpoints.findIndex((b) => b.breakpoint_id === bpId && b.workspace_id === wsId);
      if (idx < 0) return sendJson(404, { detail: `Breakpoint '${bpId}' not found` });
      breakpoints.splice(idx, 1);
      return sendJson(200, { deleted: true, breakpoint_id: bpId, workspace_id: wsId });
    }
    if (req.method === "POST" && p === "/v1/platform/debugger/sessions") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied session start" });
      if (JSON.stringify(parsedBody.initial_state ?? {}).includes("sk-live-secret123456")) {
        return sendJson(422, { detail: "DLP policy violation: raw secret token detected", code: "policy_violation" });
      }
      const frame = { node_id: "triage_claim", agent_id: "intake-router", tool_name: "kbrain_query", line_number: 8 };
      const sess = {
        session_id: `dbg-p14-${sessions.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: parsedBody.workflow_id ?? "WF-STUDIO-01",
        status: "PAUSED",
        current_step_index: 0,
        step_depth: 0,
        total_steps: 2,
        hit_breakpoint_id: breakpoints[0]?.breakpoint_id ?? null,
        hit_reason: "always (step boundary)",
        active_step: frame,
        active_frame: frame,
        variables: { ...(parsedBody.initial_state ?? { dry_run: true }) },
        call_stack: [{ depth: 0, node_id: "triage_claim", agent_id: "intake-router", line_number: 8 }],
        mutation_count: 0,
        mutations: [],
        frame_sha256: "a".repeat(64),
        updated_at: "2026-11-15T22:01:00Z",
      };
      sessions.unshift(sess);
      return sendJson(200, sess);
    }
    if (req.method === "GET" && p === "/v1/platform/debugger/sessions") {
      const wsId = searchParams.workspace_id ?? "default";
      const limit = Number(searchParams.limit ?? 20);
      const matched = sessions.filter((s) => s.workspace_id === wsId).slice(0, limit);
      return sendJson(200, { workspace_id: wsId, count: matched.length, sessions: matched });
    }
    if (req.method === "POST" && p.endsWith("/step") && p.startsWith("/v1/platform/debugger/sessions/")) {
      const sessionId = decodeURIComponent(p.split("/").slice(-2, -1)[0]);
      const sess = sessions.find((s) => s.session_id === sessionId);
      if (!sess) return sendJson(404, { detail: `Session '${sessionId}' not found` });
      if (JSON.stringify(parsedBody.state_patch ?? {}).includes("sk-live-secret123456")) {
        return sendJson(422, { detail: "DLP policy violation in state_patch", code: "policy_violation" });
      }
      if (parsedBody.state_patch) {
        sess.variables = { ...sess.variables, ...parsedBody.state_patch };
        sess.mutation_count += 1;
      }
      if (parsedBody.action === "step_into") sess.step_depth = 1;
      if (parsedBody.action === "step_over") sess.current_step_index += 1;
      if (parsedBody.action === "continue") sess.status = "COMPLETED";
      return sendJson(200, { ...sess });
    }
    if (req.method === "GET" && p === "/v1/platform/debugger/codelens") {
      const wsId = searchParams.workspace_id ?? "default";
      const wfId = searchParams.workflow_id ?? "WF-STUDIO-01";
      const filePath = searchParams.file_path ?? "workflows/refund_agent.py";
      return sendJson(200, {
        workspace_id: wsId,
        workflow_id: wfId,
        file_path: filePath,
        vscode_attach_uri: `vscode://keelway.vscode-keelway/attach?port=7420&workspace=${wsId}&workflow=${wfId}`,
        cursor_attach_uri: `cursor://keelway.vscode-keelway/attach?port=7420&workspace=${wsId}&workflow=${wfId}`,
        bridge: { extension_id: "keelway.vscode-keelway", loopback_origin_policy: "extension-host-bearer-only" },
        lenses: [{ symbol: "triage_claim", file_path: filePath, line_start: 8, line: 8, model_checkpoint: "keelway-core:7b", p50_ms: 142, p50_latency_ms: 142, avg_cost_usd: 0, provenance_4d: "Apache-2.0 · Local Metal · Self-Operated · Zero-Egress", attached_breakpoints: breakpoints.length }],
      });
    }
    return sendJson(404, { detail: `Unhandled ${req.method} ${p}` });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    baseUrl: `http://127.0.0.1:${server.address().port}`,
    recorded,
    close: () => (server.closeAllConnections?.(), new Promise((resolve) => server.close(resolve))),
  };
}

describe("@keelway/sdk Phase 14 Step-Through Debugger, Conditional Breakpoints & 4D CodeLens", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase14MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase14_ts" });
  });
  after(async () => {
    await srv.close();
  });

  it("exports PlatformDebuggerClient, PlatformDebuggerDelegate, and mounts client.platform.debugger", () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(typeof PlatformDebuggerClient, "function");
    assert.equal(PlatformDebuggerClient, PlatformDebuggerDelegate);
    assert.ok(client.platform.debugger instanceof PlatformDebuggerClient);
  });

  it("manages conditional breakpoints, lists, CodeLens telemetry, and 403/404 mappings", async () => {
    assert.throws(() => client.platform.setBreakpoint({ workflow_id: "  " }), /workflow_id must be non-empty/);
    assert.throws(() => client.platform.setBreakpoint({ line_number: 0 }), /line_number must be >= 1/);

    const bp = await client.platform.setBreakpoint({
      workspace_id: "ws-p14",
      workflow_id: "WF-P14",
      node_id: "triage_claim",
      condition_type: "cost_usd_gt",
      threshold: 0.25,
      line_number: 8,
    });
    assert.equal(bp.condition_type, "cost_usd_gt");
    assert.equal(bp.threshold, 0.25);

    const listed = await client.platform.debugger.listBreakpoints({ workspace_id: "ws-p14", workflow_id: "WF-P14" });
    assert.equal(listed.count, 1);

    const codelens = await client.platform.getDebuggerCodelens({ workspace_id: "ws-p14", workflow_id: "WF-P14", file_path: "workflows/refund_agent.py" });
    assert.ok(codelens.vscode_attach_uri.startsWith("vscode://keelway.vscode-keelway/attach?"));
    assert.ok(codelens.cursor_attach_uri.startsWith("cursor://keelway.vscode-keelway/attach?"));
    assert.equal(codelens.lenses[0].attached_breakpoints, 1);

    await assert.rejects(
      () => client.platform.setBreakpoint({ workspace_id: "ws-p14" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );

    const del = await client.platform.deleteBreakpoint(bp.breakpoint_id, "ws-p14");
    assert.equal(del.deleted, true);
    await assert.rejects(
      () => client.platform.deleteBreakpoint("bp-missing", "ws-p14"),
      (err) => err instanceof TaskNotFoundError && err.status === 404,
    );
  });

  it("starts, lists, steps, mutates state with DLP enforcement, and completes debug sessions", async () => {
    const sess = await client.platform.startDebugSession({ workspace_id: "ws-p14", workflow_id: "WF-P14", initial_state: { claim_id: "CLM-14", approved: false } });
    assert.equal(sess.status, "PAUSED");
    assert.equal(sess.frame_sha256.length, 64);

    const into = await client.platform.stepDebugSession(sess.session_id, "step_into");
    assert.equal(into.step_depth, 1);

    const mutated = await client.platform.debugger.stepDebugSession(sess.session_id, { workspace_id: "ws-p14", action: "mutate_state", state_patch: { approved: true } });
    assert.equal(mutated.variables.approved, true);
    assert.equal(mutated.mutation_count, 1);

    await assert.rejects(
      () => client.platform.stepDebugSession(sess.session_id, { action: "mutate_state", state_patch: { secret: "sk-live-secret123456" } }),
      (err) => err instanceof PolicyViolationError && err.status === 422,
    );

    const completed = await client.platform.stepDebugSession(sess.session_id, { workspace_id: "ws-p14", action: "continue" });
    assert.equal(completed.status, "COMPLETED");

    const listed = await client.platform.listDebugSessions({ workspace_id: "ws-p14", limit: 5 });
    assert.equal(listed.count, 1);
    assert.throws(() => client.platform.listDebugSessions({ workspace_id: "ws-p14", limit: 0 }), /limit must be >= 1/);
  });
});
