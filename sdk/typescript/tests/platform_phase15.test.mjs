import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  PermissionDeniedError,
  PlatformClient,
  PlatformCyclicClient,
  PlatformCyclicDelegate,
  PolicyViolationError,
  TaskNotFoundError,
} from "../dist/index.js";

async function startPhase15MockServer() {
  const recorded = [];
  const runs = [];
  const simulations = [];

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

    if (req.headers.authorization !== "Bearer kw_live_phase15_ts") return sendJson(401, { detail: "Invalid bearer token" });
    const p = reqUrl.pathname;
    const isViewer = req.headers["x-keelway-role"] === "viewer";

    if (req.method === "POST" && p === "/v1/platform/kflow/cyclic/validate") {
      return sendJson(200, {
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: parsedBody.workflow_id ?? "WF-CYCLIC-01",
        valid: true,
        node_count: parsedBody.nodes?.length ?? 3,
        loop_edge_count: parsedBody.loop_edges?.length ?? 1,
        max_worst_case_steps: 7,
        topological_spine: ["draft_patch", "critic_verify", "publish_release"],
        compensation_handlers: ["revert_worktree", "discard_candidate", "rollback_tag"],
        spec_sha256: "a".repeat(64),
      });
    }

    if (req.method === "POST" && p === "/v1/platform/kflow/cyclic/execute") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied cyclic execution" });
      if (JSON.stringify(parsedBody.initial_state ?? {}).includes("sk-live-secret123456")) {
        return sendJson(422, { detail: "DLP policy violation in initial_state", code: "policy_violation" });
      }
      const timedOut = Boolean(parsedBody.simulate_timeout);
      const status = timedOut ? "COMPENSATED" : "CONVERGED";
      const run = {
        run_id: `cyc-p15-${runs.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: parsedBody.workflow_id ?? "WF-CYCLIC-01",
        status,
        iterations_executed: timedOut ? 1 : 2,
        max_iterations: parsedBody.max_iterations_override ?? 3,
        converged: !timedOut,
        final_critic_score: timedOut ? 0 : 0.9,
        critic_threshold: parsedBody.critic_threshold ?? 0.85,
        fan_out_shards: parsedBody.fan_out_shards ?? 3,
        total_cost_usd: 0.16,
        total_latency_ms: 1260,
        iteration_trace: [{ iteration: 1, node_id: "draft_patch", agent_id: "code-synthesizer", model: "claude-3-7-sonnet", critic_score: 0.74, shard_count: 3, status: "COMPLETED", cost_usd: 0.045, latency_ms: 340 }],
        compensation_log: timedOut ? [{ node_id: "draft_patch", handler: "revert_worktree", reason: "timeout_exceeded", status: "ROLLED_BACK" }] : [],
        held_node_id: null,
        run_sha256: "b".repeat(64),
        created_at: "2026-11-15T23:00:00Z",
      };
      runs.unshift(run);
      return sendJson(200, run);
    }

    if (req.method === "GET" && p === "/v1/platform/kflow/cyclic/runs") {
      const wsId = searchParams.workspace_id ?? "default";
      const wfId = searchParams.workflow_id;
      const limit = Number(searchParams.limit ?? 25);
      const matched = runs.filter((r) => r.workspace_id === wsId && (!wfId || r.workflow_id === wfId)).slice(0, limit);
      return sendJson(200, { workspace_id: wsId, count: matched.length, runs: matched });
    }

    if (req.method === "GET" && p.startsWith("/v1/platform/kflow/cyclic/runs/")) {
      const runId = decodeURIComponent(p.slice("/v1/platform/kflow/cyclic/runs/".length));
      const wsId = searchParams.workspace_id ?? "default";
      const found = runs.find((r) => r.run_id === runId && r.workspace_id === wsId);
      if (!found) return sendJson(404, { detail: `Cyclic KFlow run '${runId}' not found` });
      return sendJson(200, found);
    }

    if (req.method === "POST" && p === "/v1/platform/kflow/autopilot/simulate") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied autopilot simulation" });
      const policy = parsedBody.privacy_policy ?? "hybrid_balanced";
      const sim = {
        simulation_id: `apsim-p15-${simulations.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: parsedBody.workflow_id ?? "WF-CYCLIC-01",
        privacy_policy: policy,
        budget_cap_usd: parsedBody.budget_cap_usd ?? 0.15,
        expected_loop_multiplier: parsedBody.expected_loop_multiplier ?? 2,
        baseline_p50_usd: 0.08,
        baseline_p95_usd: 0.16,
        baseline_ttft_ms: 765,
        optimized_p50_usd: policy === "airgap_strict" ? 0 : 0.035,
        optimized_p95_usd: policy === "airgap_strict" ? 0 : 0.07,
        savings_pct: policy === "airgap_strict" ? 100 : 56.25,
        optimized_ttft_ms: 405,
        privacy_compliant: true,
        violations_resolved: 2,
        node_plan: [{ node_id: "draft_patch", original_model: "claude-3-7-sonnet", selected_model: "qwen2.5-coder:7b", rewritten: true, reason: "policy rewrite", p50_cost_usd: 0, p95_cost_usd: 0, data_boundary: "local_metal_zero_egress" }],
        simulation_sha256: "c".repeat(64),
        created_at: "2026-11-15T23:01:00Z",
      };
      simulations.unshift(sim);
      return sendJson(200, sim);
    }

    if (req.method === "GET" && p === "/v1/platform/kflow/autopilot/simulations") {
      const wsId = searchParams.workspace_id ?? "default";
      const wfId = searchParams.workflow_id;
      const limit = Number(searchParams.limit ?? 25);
      const matched = simulations.filter((s) => s.workspace_id === wsId && (!wfId || s.workflow_id === wfId)).slice(0, limit);
      return sendJson(200, { workspace_id: wsId, count: matched.length, simulations: matched });
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

describe("@keelway/sdk Phase 15 Cyclic KFlow Sub-Graphs & Cost/Privacy Autopilot", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase15MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase15_ts" });
  });
  after(async () => {
    await srv.close();
  });

  it("exports PlatformCyclicClient, PlatformCyclicDelegate, and mounts client.platform.cyclic", () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(typeof PlatformCyclicClient, "function");
    assert.equal(PlatformCyclicClient, PlatformCyclicDelegate);
    assert.ok(client.platform.cyclic instanceof PlatformCyclicClient);
  });

  it("validates cyclic graphs, executes reflection loops, handles saga compensation, DLP 422, and 403/404 errors", async () => {
    assert.throws(() => client.platform.validateCyclicKflow({ workflow_id: "   " }), /workflow_id must be non-empty/);
    assert.throws(() => client.platform.executeCyclicKflow({ max_iterations_override: 0 }), /max_iterations_override must be between 1 and 10/);
    assert.throws(() => client.platform.executeCyclicKflow({ fan_out_shards: 20 }), /fan_out_shards must be between 1 and 16/);
    assert.throws(() => client.platform.getCyclicKflowRun("  ", "ws-p15"), /run_id must be non-empty/);

    const validated = await client.platform.validateCyclicKflow({ workspace_id: "ws-p15", workflow_id: "WF-P15" });
    assert.equal(validated.valid, true);
    assert.equal(validated.spec_sha256.length, 64);

    const converged = await client.platform.executeCyclicKflow({
      workspace_id: "ws-p15",
      workflow_id: "WF-P15",
      critic_threshold: 0.85,
      fan_out_shards: 4,
    });
    assert.equal(converged.status, "CONVERGED");
    assert.equal(converged.converged, true);
    assert.equal(converged.fan_out_shards, 4);

    const compensated = await client.platform.cyclic.executeCyclicKflow({
      workspace_id: "ws-p15",
      workflow_id: "WF-P15",
      simulate_timeout: true,
    });
    assert.equal(compensated.status, "COMPENSATED");
    assert.equal(compensated.compensation_log.length, 1);

    const fetched = await client.platform.getCyclicKflowRun(converged.run_id, "ws-p15");
    assert.equal(fetched.run_id, converged.run_id);

    const listed = await client.platform.listCyclicKflowRuns({ workspace_id: "ws-p15", workflow_id: "WF-P15", limit: 10 });
    assert.equal(listed.count, 2);

    await assert.rejects(
      () => client.platform.executeCyclicKflow({ workspace_id: "ws-p15", initial_state: { token: "sk-live-secret123456" } }),
      (err) => err instanceof PolicyViolationError && err.status === 422,
    );
    await assert.rejects(
      () => client.platform.executeCyclicKflow({ workspace_id: "ws-p15" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );
    await assert.rejects(
      () => client.platform.getCyclicKflowRun("cyc-missing", "ws-p15"),
      (err) => err instanceof TaskNotFoundError && err.status === 404,
    );
  });

  it("simulates pre-run cost/privacy autopilot plans and lists persisted simulations", async () => {
    assert.throws(() => client.platform.simulateKflowAutopilot({ budget_cap_usd: -0.01 }), /budget_cap_usd must be >= 0.0/);
    assert.throws(() => client.platform.listKflowAutopilotSimulations({ limit: 0 }), /limit must be >= 1/);

    const sim = await client.platform.simulateKflowAutopilot({
      workspace_id: "ws-p15",
      workflow_id: "WF-P15",
      budget_cap_usd: 0.1,
      privacy_policy: "airgap_strict",
      expected_loop_multiplier: 3,
    });
    assert.equal(sim.privacy_compliant, true);
    assert.equal(sim.optimized_p95_usd, 0);
    assert.equal(sim.simulation_sha256.length, 64);

    const sims = await client.platform.listKflowAutopilotSimulations({ workspace_id: "ws-p15", workflow_id: "WF-P15", limit: 5 });
    assert.equal(sims.count, 1);
    assert.equal(sims.simulations[0].simulation_id, sim.simulation_id);
  });
});
