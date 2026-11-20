import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import { KeelwayClient } from "../dist/index.js";

async function startPhase21MockServer() {
  const recorded = [];

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

    if (req.method === "POST" && reqUrl.pathname === "/v1/kstack/execute") {
      sendJson(200, {
        proof: {
          execution_id: "exec-ts-1",
          skill_name: parsedBody.name,
          skill_digest_sha256: "abc123",
          actor: "ts-client",
          inputs: parsedBody.inputs,
          outputs: { pass_rate_pct: 90.0, drift: { drift_severity: "NONE" } },
          permissions_used: ["execute_restricted"],
          success: true,
          duration_ms: 9.5,
          timestamp_utc: "2026-11-19T00:00:00Z",
          signature_sha256: "deadbeef",
        },
      });
      return;
    }
    if (req.method === "GET" && reqUrl.pathname === "/v1/agents/registry") {
      sendJson(200, {
        manifests: [
          { id: 1, name: "devops-sre", version: "1.0.0", owner: "system", digest: "d1", enabled: true },
          { id: 2, name: "pr-reviewer", version: "1.0.0", owner: "system", digest: "d2", enabled: false },
        ],
      });
      return;
    }
    if (req.method === "POST" && reqUrl.pathname === "/v1/agents/registry/devops-sre/1.0.0/toggle") {
      sendJson(200, { id: 1, enabled: parsedBody.enabled, updated_at: "2026-11-19T00:00:00Z" });
      return;
    }
    sendJson(404, { detail: "not found" });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return { server, recorded, baseUrl: `http://127.0.0.1:${address.port}` };
}

describe("Phase 21: KStack execute + agent registry SDK parity", () => {
  let server;
  let recorded;
  let baseUrl;
  let client;

  before(async () => {
    ({ server, recorded, baseUrl } = await startPhase21MockServer());
    client = new KeelwayClient({ baseUrl, token: "kw_live_ts_p21" });
  });

  after(() => server.close());

  it("kstack.execute posts name + inputs and returns the sealed proof", async () => {
    const proof = await client.kstack.execute({
      name: "kstack/golden-eval",
      inputs: { model_name: "m1", compare_to: "latest" },
    });
    assert.equal(proof.success, true);
    assert.equal(proof.skill_name, "kstack/golden-eval");
    assert.equal(proof.outputs.drift.drift_severity, "NONE");
    assert.equal(proof.signature_sha256, "deadbeef");

    const call = recorded.at(-1);
    assert.equal(call.method, "POST");
    assert.equal(call.body.inputs.compare_to, "latest");
    assert.equal(call.headers.authorization, "Bearer kw_live_ts_p21");
  });

  it("agents.listRegistry reads /v1/agents/registry with enabled_only param", async () => {
    const res = await client.agents.listRegistry({ enabled_only: true });
    assert.equal(res.manifests.length, 2);
    assert.equal(res.manifests[0].name, "devops-sre");

    const call = recorded.at(-1);
    assert.equal(call.method, "GET");
    assert.equal(call.searchParams.enabled_only, "true");
  });

  it("agents.toggleManifest posts the kill-switch body to the versioned path", async () => {
    const res = await client.agents.toggleManifest("devops-sre", "1.0.0", false);
    assert.equal(res.enabled, false);
    assert.equal(res.id, 1);

    const call = recorded.at(-1);
    assert.equal(call.pathname, "/v1/agents/registry/devops-sre/1.0.0/toggle");
    assert.deepEqual(call.body, { enabled: false });
  });
});
