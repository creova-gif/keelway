import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  KeelwayError,
  PermissionDeniedError,
  PlatformClient,
  PlatformDevxDelegate,
} from "../dist/index.js";

async function startPhase11MockServer() {
  const recorded = [];
  const tapes = new Map();
  const evalCases = new Map();

  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const rawBody = Buffer.concat(chunks).toString("utf8");
    const parsedBody = rawBody ? JSON.parse(rawBody) : null;
    const reqUrl = new URL(req.url ?? "/", "http://127.0.0.1");
    const searchParams = Object.fromEntries(reqUrl.searchParams.entries());
    recorded.push({
      method: req.method,
      pathname: reqUrl.pathname,
      searchParams,
      headers: req.headers,
      body: parsedBody,
    });

    const sendJson = (status, payload) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(payload));
    };

    if (req.headers.authorization !== "Bearer kw_live_phase11_ts") {
      return sendJson(401, { detail: "Invalid bearer token" });
    }
    if (req.headers["x-keelway-role"] === "viewer" && req.method === "POST") {
      return sendJson(403, { detail: "Viewer role denied Phase 11 mutation" });
    }

    const p = reqUrl.pathname;

    if (req.method === "POST" && p === "/v1/platform/traces/ingest") {
      const wsId = parsedBody.workspace_id ?? "default";
      const spans = parsedBody.spans ?? [];
      const resourceSpans = parsedBody.resourceSpans ?? parsedBody.resource_spans ?? [];
      if (spans.length === 0 && resourceSpans.length === 0) {
        return sendJson(400, { detail: "At least one span or resourceSpan is required" });
      }
      const traceId = parsedBody.trace_id ?? `ft_trace_${tapes.size + 1}`;
      const steps = spans.map((sp, idx) => ({
        step_index: idx,
        span_id: sp.span_id ?? `sp_${idx + 1}`,
        name: sp.name ?? `step_${idx}`,
        model: sp.attributes?.["gen_ai.request.model"] ?? "keelway-core:7b",
        prompt: sp.attributes?.["gen_ai.prompt"] ?? "",
        output: sp.attributes?.["gen_ai.completion"] ?? "",
        step_sha256: "a".repeat(64),
      }));
      const tape = {
        trace_id: traceId,
        workspace_id: wsId,
        workflow_name: parsedBody.workflow_name ?? "agent-trace",
        source_framework: parsedBody.source_framework ?? "opentelemetry_genai",
        span_count: spans.length || resourceSpans.length,
        step_count: steps.length || 1,
        steps,
        tape_sha256: "b".repeat(64),
        status: "recorded",
        created_at: "2026-11-15T12:00:00Z",
      };
      tapes.set(traceId, tape);
      return sendJson(200, tape);
    }

    if (req.method === "GET" && p === "/v1/platform/traces") {
      const wsId = searchParams.workspace_id ?? "default";
      const limit = Number(searchParams.limit ?? 20);
      const matched = [...tapes.values()]
        .filter((t) => t.workspace_id === wsId)
        .slice(0, limit);
      return sendJson(200, {
        workspace_id: wsId,
        total: matched.length,
        tapes: matched,
      });
    }

    const replayMatch = p.match(/^\/v1\/platform\/traces\/([^/]+)\/replay$/);
    if (req.method === "POST" && replayMatch) {
      const parentId = decodeURIComponent(replayMatch[1]);
      const parentTape = tapes.get(parentId);
      if (!parentTape) {
        return sendJson(404, { detail: `Trace ${parentId} not found` });
      }
      const forkId = `${parentId}_fork_${tapes.size + 1}`;
      const fromIdx = parsedBody.from_step_index ?? 0;
      const forkedSteps = (parentTape.steps ?? []).map((st) =>
        st.step_index === fromIdx
          ? {
              ...st,
              prompt: parsedBody.override_prompt ?? st.prompt,
              model: parsedBody.override_model ?? st.model,
              state: parsedBody.override_state ?? st.state ?? {},
            }
          : st,
      );
      const forked = {
        ...parentTape,
        trace_id: forkId,
        parent_trace_id: parentId,
        forked_from_trace_id: parentId,
        forked_from_step_index: fromIdx,
        steps: forkedSteps,
        tape_sha256: "c".repeat(64),
        status: "replayed_fork",
      };
      tapes.set(forkId, forked);
      return sendJson(200, forked);
    }

    if (req.method === "POST" && p === "/v1/platform/eval/dataset/promote") {
      const traceId = parsedBody.trace_id;
      const sourceTape = tapes.get(traceId);
      if (!sourceTape) {
        return sendJson(404, { detail: `Trace ${traceId} not found` });
      }
      const caseId = `eval_case_${evalCases.size + 1}`;
      const item = {
        case_id: caseId,
        id: caseId,
        workspace_id: parsedBody.workspace_id ?? "default",
        source_trace_id: traceId,
        title: parsedBody.title ?? `Golden case from ${traceId}`,
        expected_substrings: parsedBody.expected_substrings ?? [],
        forbidden_substrings: parsedBody.forbidden_substrings ?? [],
        case_sha256: "d".repeat(64),
        created_at: "2026-11-15T12:01:00Z",
      };
      evalCases.set(caseId, item);
      return sendJson(200, item);
    }

    if (req.method === "GET" && p === "/v1/platform/eval/dataset") {
      const wsId = searchParams.workspace_id ?? "default";
      const items = [...evalCases.values()].filter((c) => c.workspace_id === wsId);
      return sendJson(200, {
        workspace_id: wsId,
        total: items.length,
        cases: items,
      });
    }

    if (req.method === "POST" && p === "/v1/platform/migrate/langgraph") {
      const code = String(parsedBody.source_code ?? "");
      if (code.includes("os.system(")) {
        return sendJson(400, { detail: "Unsafe shell invocation rejected by static AST importer" });
      }
      return sendJson(200, {
        workspace_id: parsedBody.workspace_id ?? "default",
        workflow_id: "wf_migrated_01",
        workflow_name: parsedBody.workflow_name ?? "migrated-langgraph",
        source_framework: "langgraph",
        source_language: parsedBody.source_language ?? "python",
        nodes: [
          { id: "planner", agent_id: "architect", requires_p10: false },
          { id: "deployer", agent_id: "release-engineer", requires_p10: true },
        ],
        edges: [{ from: "planner", to: "deployer" }],
        p10_gates_injected: 1,
        ast_digest_sha256: "e".repeat(64),
      });
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

describe("@keelway/sdk Phase 11 Flight-Tape Time-Travel, Trace-to-Eval & LangGraph AST Migration", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase11MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase11_ts" });
  });

  after(async () => {
    await srv.close();
  });

  it("exports PlatformClient alias and PlatformDevxDelegate", () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(typeof PlatformDevxDelegate, "function");
    assert.ok(client.platform instanceof PlatformClient);
  });

  it("ingests OTel GenAI spans, lists flight tapes, and replays counterfactual forks", async () => {
    const ingested = await client.platform.ingestOtelTraces({
      workspace_id: "ws-p11",
      workflow_name: "triage-pipeline",
      source_framework: "opentelemetry_genai",
      trace_id: "trace_alpha_01",
      spans: [
        {
          span_id: "sp_01",
          name: "gen_ai.chat",
          attributes: {
            "gen_ai.request.model": "keelway-core:7b",
            "gen_ai.prompt": "Summarize incident #42",
            "gen_ai.completion": "Root cause: expired webhook secret.",
          },
        },
      ],
    });
    assert.equal(ingested.trace_id, "trace_alpha_01");
    assert.equal(ingested.span_count, 1);
    assert.equal(ingested.tape_sha256.length, 64);
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p11",
      workflow_name: "triage-pipeline",
      source_framework: "opentelemetry_genai",
      trace_id: "trace_alpha_01",
      spans: [
        {
          span_id: "sp_01",
          name: "gen_ai.chat",
          attributes: {
            "gen_ai.request.model": "keelway-core:7b",
            "gen_ai.prompt": "Summarize incident #42",
            "gen_ai.completion": "Root cause: expired webhook secret.",
          },
        },
      ],
    });

    const listed = await client.platform.listFlightTapes("ws-p11", 10);
    assert.equal(listed.workspace_id, "ws-p11");
    assert.equal(listed.total, 1);
    assert.deepEqual(srv.recorded.at(-1).searchParams, {
      workspace_id: "ws-p11",
      limit: "10",
    });

    const replayed = await client.platform.replayFlightTape("trace_alpha_01", {
      workspace_id: "ws-p11",
      from_step_index: 0,
      override_prompt: "Summarize incident #42 with remediation steps",
      override_model: "keelway-coder:7b",
      override_state: { strict_mode: true },
    });
    assert.equal(replayed.forked_from_trace_id, "trace_alpha_01");
    assert.equal(replayed.forked_from_step_index, 0);
    assert.equal(replayed.steps[0].model, "keelway-coder:7b");
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p11",
      from_step_index: 0,
      override_prompt: "Summarize incident #42 with remediation steps",
      override_model: "keelway-coder:7b",
      override_state: { strict_mode: true },
    });
  });

  it("promotes traces to golden eval dataset cases, lists cases, and migrates LangGraph AST", async () => {
    assert.throws(
      () => client.platform.promoteTraceToEval({ trace_id: "   " }),
      /trace_id must be non-empty/,
    );

    const promoted = await client.platform.promoteTraceToEval({
      workspace_id: "ws-p11",
      trace_id: "trace_alpha_01",
      title: "Webhook secret incident regression",
      expected_substrings: ["webhook secret"],
      forbidden_substrings: ["stacktrace_internal"],
    });
    assert.equal(promoted.source_trace_id, "trace_alpha_01");
    assert.equal(promoted.case_sha256.length, 64);
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p11",
      trace_id: "trace_alpha_01",
      title: "Webhook secret incident regression",
      expected_substrings: ["webhook secret"],
      forbidden_substrings: ["stacktrace_internal"],
    });

    const dataset = await client.platform.listEvalDatasetCases("ws-p11");
    assert.equal(dataset.total, 1);
    assert.equal(dataset.cases[0].title, "Webhook secret incident regression");
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p11" });

    const migrated = await client.platform.migrateLanggraphSource({
      workspace_id: "ws-p11",
      source_code:
        "from langgraph.graph import StateGraph\ng = StateGraph(dict)\ng.add_node('planner', plan_fn)\ng.add_node('deployer', deploy_fn)\ng.add_edge('planner', 'deployer')\n",
      source_language: "python",
      workflow_name: "prod-release-flow",
    });
    assert.equal(migrated.workflow_name, "prod-release-flow");
    assert.equal(migrated.nodes.length, 2);
    assert.equal(migrated.p10_gates_injected, 1);

    await assert.rejects(
      () =>
        client.platform.migrateLanggraphSource({
          workspace_id: "ws-p11",
          source_code: "import os\nos.system('rm -rf /')",
        }),
      (err) => err instanceof KeelwayError && err.status === 400,
    );

    await assert.rejects(
      () =>
        client.platform.promoteTraceToEval(
          { workspace_id: "ws-p11", trace_id: "trace_alpha_01" },
          { headers: { "X-Keelway-Role": "viewer" } },
        ),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );
  });
});
