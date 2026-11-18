import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  PermissionDeniedError,
  PlatformClient,
  PlatformStudioClient,
  PlatformStudioDelegate,
  PolicyViolationError,
} from "../dist/index.js";

async function startPhase12MockServer() {
  const recorded = [];
  const audits = [];
  const gateRuns = [];

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

    if (req.headers.authorization !== "Bearer kw_live_phase12_ts") {
      return sendJson(401, { detail: "Invalid bearer token" });
    }

    const p = reqUrl.pathname;
    const isViewer = req.headers["x-keelway-role"] === "viewer";

    if (req.method === "POST" && p === "/v1/platform/studio/kflow/sync") {
      if (isViewer && (parsedBody.direction === "graph_to_code" || parsedBody.persist)) {
        return sendJson(403, { detail: "Viewer role denied studio persistence" });
      }
      const src = String(parsedBody.source_code ?? "");
      if (src.length > 262144) return sendJson(413, { detail: "source_code exceeds 262144 bytes" });
      if (src.includes("def broken(:")) return sendJson(422, { detail: "Malformed syntax rejected without eval/exec" });
      const defaultNodes = [
        { id: "plan", label: "Plan Sprint", agent_id: "architect", depends_on: [], requires_p10: false },
        { id: "ship", label: "Ship Release", agent_id: "release-engineer", depends_on: ["plan"], requires_p10: true },
      ];
      const nodes = (parsedBody.nodes ?? defaultNodes).map((n, idx) => ({
        id: n.id,
        label: n.label ?? n.id,
        agent_id: n.agent_id ?? "feature-coder",
        depends_on: n.depends_on ?? [],
        requires_p10: Boolean(n.requires_p10),
        line_start: n.line_start ?? idx * 8 + 1,
        line_end: n.line_end ?? idx * 8 + 6,
        wave: n.wave ?? idx,
        x: n.x ?? idx * 220 + 80,
        y: n.y ?? 120,
      }));
      return sendJson(200, {
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: parsedBody.workflow_id ?? "WF-STUDIO-01",
        direction: parsedBody.direction ?? "code_to_graph",
        language: parsedBody.language ?? "python",
        nodes,
        edges: nodes.length > 1 ? [{ from: nodes[0].id, to: nodes[1].id, is_cycle: false }] : [],
        cycle_back_edges: [],
        p10_locked_nodes: nodes.filter((n) => n.requires_p10).map((n) => n.id),
        source_code: src || "# generated kflow source\n",
        persisted: Boolean(parsedBody.persist),
        sync_sha256: "a".repeat(64),
      });
    }

    if (req.method === "POST" && p === "/v1/platform/studio/blast-radius/record") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied blast-radius recording" });
      const blockedPaths = parsedBody.blocked_paths ?? [];
      const blockedHosts = parsedBody.blocked_egress_hosts ?? [];
      const egressAttempts = parsedBody.egress_attempts ?? 0;
      const fsReads = parsedBody.fs_reads ?? [];
      const fsWrites = parsedBody.fs_writes ?? [];
      const rec = {
        audit_id: `blast-${audits.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        trace_id: parsedBody.trace_id ?? null,
        workflow_id: parsedBody.workflow_id ?? null,
        fs_reads: fsReads,
        fs_writes: fsWrites,
        blocked_paths: blockedPaths,
        egress_attempts: egressAttempts,
        blocked_egress_hosts: blockedHosts,
        p10_gates_triggered: parsedBody.p10_gates_triggered ?? 0,
        seatbelted: parsedBody.seatbelted ?? true,
        zero_unapproved_egress: egressAttempts === blockedHosts.length,
        syscalls_audited: fsReads.length + fsWrites.length + blockedPaths.length + egressAttempts + 4,
        risk_tier: blockedPaths.length > 0 || egressAttempts > 0 ? "elevated" : "contained",
        audit_sha256: "b".repeat(64),
        recorded_at: "2026-11-15T19:00:00Z",
      };
      audits.push(rec);
      return sendJson(200, rec);
    }

    if (req.method === "GET" && p === "/v1/platform/studio/blast-radius") {
      const wsId = searchParams.workspace_id ?? "default";
      const traceId = searchParams.trace_id;
      const limit = Number(searchParams.limit ?? 25);
      const matched = audits.filter((a) => a.workspace_id === wsId && (!traceId || a.trace_id === traceId)).slice(0, limit);
      return sendJson(200, { workspace_id: wsId, count: matched.length, audits: matched });
    }

    if (req.method === "POST" && p === "/v1/platform/studio/prompt-gate/evaluate") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied prompt gate evaluation" });
      const hasDlpLeak = String(parsedBody.candidate_prompt_text ?? "").includes("sk-live-secret");
      const minPassRate = parsedBody.min_pass_rate ?? 0.9;
      const passRate = hasDlpLeak ? 0.5 : 1.0;
      const run = {
        gate_run_id: `pgate-${gateRuns.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        candidate_prompt_version: parsedBody.candidate_prompt_version,
        candidate_model_id: parsedBody.candidate_model_id,
        verdict: !hasDlpLeak && passRate >= minPassRate ? "PASS" : "BLOCK",
        cases_evaluated: 4,
        passed_cases: hasDlpLeak ? 2 : 4,
        pass_rate: passRate,
        min_pass_rate: minPassRate,
        schema_valid_count: 4,
        dlp_violations: hasDlpLeak ? 1 : 0,
        cost_delta_usd: -0.0012,
        dataset_source: "golden_eval_suite",
        gate_sha256: "c".repeat(64),
        evaluated_at: "2026-11-15T19:01:00Z",
      };
      gateRuns.push(run);
      return sendJson(200, run);
    }

    if (req.method === "GET" && p === "/v1/platform/studio/prompt-gate/runs") {
      const wsId = searchParams.workspace_id ?? "default";
      const limit = Number(searchParams.limit ?? 20);
      const matched = gateRuns.filter((r) => r.workspace_id === wsId).slice(0, limit);
      return sendJson(200, { workspace_id: wsId, count: matched.length, runs: matched });
    }

    return sendJson(404, { detail: `Unhandled ${req.method} ${p}` });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    baseUrl: `http://127.0.0.1:${server.address().port}`,
    recorded,
    close: () => {
      server.closeAllConnections?.();
      return new Promise((resolve) => server.close(resolve));
    },
  };
}

describe("@keelway/sdk Phase 12 Bidirectional KFlow Studio, Blast-Radius & Prompt Gate", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase12MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase12_ts" });
  });

  after(async () => {
    await srv.close();
  });

  it("exports PlatformStudioClient, PlatformStudioDelegate, and mounts client.platform.studio", () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(typeof PlatformStudioClient, "function");
    assert.equal(PlatformStudioClient, PlatformStudioDelegate);
    assert.ok(client.platform.studio instanceof PlatformStudioClient);
  });

  it("synchronizes KFlow topology bidirectionally across Python and TypeScript ASTs", async () => {
    const syncedGraph = await client.platform.syncKflowStudio({
      workspace_id: "ws-p12",
      direction: "code_to_graph",
      language: "python",
      workflow_id: "WF-STUDIO-12",
      source_code: "# @kflow_node id=plan\n# @kflow_node id=ship depends_on=plan requires_p10=true\n",
    });
    assert.equal(syncedGraph.workspace_id, "ws-p12");
    assert.deepEqual(syncedGraph.p10_locked_nodes, ["ship"]);
    assert.equal(syncedGraph.sync_sha256.length, 64);

    const syncedCode = await client.platform.studio.syncKflowStudio({
      workspace_id: "ws-p12",
      direction: "graph_to_code",
      language: "typescript",
      workflow_id: "WF-STUDIO-12",
      nodes: [
        { id: "audit", label: "Audit Diff", agent_id: "reviewer", depends_on: [], requires_p10: false },
        { id: "deploy", label: "Deploy Prod", agent_id: "deployer", depends_on: ["audit"], requires_p10: true },
      ],
      persist: true,
    });
    assert.equal(syncedCode.language, "typescript");
    assert.equal(syncedCode.persisted, true);
    assert.deepEqual(syncedCode.p10_locked_nodes, ["deploy"]);

    assert.throws(() => client.platform.syncKflowStudio({ workflow_id: "   " }), /workflow_id must be non-empty/);
    await assert.rejects(
      () => client.platform.syncKflowStudio({ source_code: "def broken(:" }),
      (err) => err instanceof PolicyViolationError && err.status === 422,
    );
  });

  it("records and lists Seatbelt sandbox blast-radius audits with trace filtering", async () => {
    assert.throws(() => client.platform.recordBlastRadius({ egress_attempts: -1 }), /egress_attempts must be >= 0/);
    const audit = await client.platform.recordBlastRadius({
      workspace_id: "ws-p12",
      trace_id: "trace_p12_01",
      workflow_id: "WF-STUDIO-12",
      fs_reads: ["core/main.py", "core/platform/flight_tape.py"],
      fs_writes: ["artifacts/report.json"],
      blocked_paths: ["/etc/passwd"],
      egress_attempts: 1,
      blocked_egress_hosts: ["evil.example.invalid"],
      p10_gates_triggered: 1,
      seatbelted: true,
    });
    assert.equal(audit.zero_unapproved_egress, true);
    assert.equal(audit.audit_sha256.length, 64);

    const listFiltered = await client.platform.listBlastRadiusAudits({
      workspace_id: "ws-p12",
      trace_id: "trace_p12_01",
      limit: 10,
    });
    assert.equal(listFiltered.count, 1);
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p12", trace_id: "trace_p12_01", limit: "10" });

    const listByString = await client.platform.studio.listBlastRadiusAudits("ws-p12");
    assert.equal(listByString.count, 1);
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p12", limit: "25" });
  });

  it("evaluates inline prompt regression gates, lists runs, and maps 403 viewer RBAC errors", async () => {
    assert.throws(
      () => client.platform.evaluatePromptGate({ candidate_prompt_version: "  ", candidate_model_id: "keelway-coder:7b" }),
      /candidate_prompt_version must be non-empty/,
    );
    assert.throws(
      () => client.platform.evaluatePromptGate({ candidate_prompt_version: "p-15", candidate_model_id: "keelway-coder:7b", min_pass_rate: 1.5 }),
      /min_pass_rate must be between 0.0 and 1.0/,
    );

    const passed = await client.platform.evaluatePromptGate({
      workspace_id: "ws-p12",
      candidate_prompt_version: "p-15",
      candidate_model_id: "keelway-coder:7b",
      candidate_prompt_text: "Return JSON summary with findings and status keys.",
      required_json_keys: ["findings", "status"],
      min_pass_rate: 0.9,
    });
    assert.equal(passed.verdict, "PASS");
    assert.equal(passed.gate_sha256.length, 64);

    const blocked = await client.platform.studio.evaluatePromptGate({
      workspace_id: "ws-p12",
      candidate_prompt_version: "p-16-bad",
      candidate_model_id: "keelway-coder:7b",
      candidate_prompt_text: "Debug token sk-live-secret",
      min_pass_rate: 0.9,
    });
    assert.equal(blocked.verdict, "BLOCK");
    assert.equal(blocked.dlp_violations, 1);

    const runs = await client.platform.listPromptGateRuns({ workspace_id: "ws-p12", limit: 5 });
    assert.equal(runs.count, 2);
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p12", limit: "5" });

    await assert.rejects(
      () => client.platform.recordBlastRadius({ workspace_id: "ws-p12" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );
  });
});
