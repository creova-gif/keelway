import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import { KeelwayClient, KeelwayError, PermissionDeniedError } from "../dist/index.js";

async function startPhase8MockServer() {
  const recorded = [];
  const runs = [];
  const kspaces = new Map();

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

    const p = reqUrl.pathname;

    if (req.method === "POST" && p === "/v1/platform/automation/workflows/execute") {
      if (req.headers["x-keelway-role"] === "viewer") {
        return sendJson(403, { detail: "Viewer role cannot execute KFlow workflows" });
      }
      const nodes = parsedBody.nodes ?? [];
      if (nodes.some((n) => Array.isArray(n.depends_on) && n.depends_on.includes(n.id))) {
        return sendJson(400, { detail: "Cycle detected in KFlow DAG" });
      }
      const approved = new Set(parsedBody.approved_node_ids ?? []);
      const gated = nodes.find((n) => n.requires_p10 && !approved.has(n.id));
      const runRec = {
        run_id: `kflow-run-${runs.length + 1}`,
        workspace_id: parsedBody.workspace_id,
        workflow_id: parsedBody.workflow_id,
        trigger: parsedBody.trigger,
        status: gated ? "awaiting_p10" : "completed",
        held_node_id: gated ? gated.id : null,
        topological_order: nodes.map((n) => n.id),
        waves: nodes.map((n) => [n.id]),
        tokens_used: gated ? 120 : 240,
        token_budget: parsedBody.token_budget,
        receipt_sha256: `sha256:${"d".repeat(64)}`,
      };
      runs.unshift(runRec);
      return sendJson(200, runRec);
    }

    if (req.method === "GET" && p === "/v1/platform/automation/runs") {
      const wsId = searchParams.workspace_id ?? "default";
      let filtered = runs.filter((r) => r.workspace_id === wsId);
      if (searchParams.workflow_id) {
        filtered = filtered.filter((r) => r.workflow_id === searchParams.workflow_id);
      }
      if (searchParams.limit) {
        filtered = filtered.slice(0, Number(searchParams.limit));
      }
      return sendJson(200, { workspace_id: wsId, count: filtered.length, runs: filtered });
    }

    if (req.method === "POST" && p === "/v1/platform/kspaces/sync") {
      const wsId = parsedBody.workspace_id ?? "default";
      const ops = parsedBody.operations ?? [];
      for (const op of ops) {
        const ns = op.namespace ?? "workspace";
        const compositeKey = `${wsId}:${ns}:${op.key}`;
        const ts = Number(op.lamport_ts ?? 1);
        kspaces.set(compositeKey, {
          namespace: ns,
          key: op.key,
          value: op.op === "remove" ? null : op.value,
          lamport_ts: ts,
          peer_id: parsedBody.peer_id,
          tombstone: op.op === "remove",
        });
      }
      const entries = [...kspaces.values()];
      return sendJson(200, {
        workspace_id: wsId,
        peer_id: parsedBody.peer_id,
        applied_count: ops.length,
        vector_clock: { [parsedBody.peer_id]: 7 },
        active_keys_count: entries.filter((e) => !e.tombstone).length,
        state_digest_sha256: `sha256:${"e".repeat(64)}`,
        entries,
      });
    }

    if (req.method === "GET" && p === "/v1/platform/kspaces/state") {
      const wsId = searchParams.workspace_id ?? "default";
      const ns = searchParams.namespace;
      const entries = [...kspaces.values()].filter((rec) => !ns || rec.namespace === ns);
      return sendJson(200, {
        workspace_id: wsId,
        vector_clock: { "node-alpha": 7 },
        active_keys_count: entries.filter((e) => !e.tombstone).length,
        state_digest_sha256: `sha256:${"e".repeat(64)}`,
        entries,
      });
    }

    if (req.method === "GET" && p === "/v1/platform/security/sbom") {
      return sendJson(200, {
        workspace_id: searchParams.workspace_id ?? "default",
        verified: true,
        verification_status: "VERIFIED",
        bom_format: "CycloneDX",
        spec_version: "1.5",
        component_count: 2,
        root_digest_sha256: "f".repeat(64),
        provenance_signature: "9".repeat(64),
        manifest: {
          components: [
            { name: "keelway/core", version: "1.0.0", component_type: "application" },
            { name: "keelway/keelway", version: "1.0.0", component_type: "application" },
          ],
        },
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

describe("@keelway/sdk Phase 8 KFlow DAG, KSpaces CRDT & SBOM Parity", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase8MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase8_ts" });
  });

  after(async () => {
    await srv.close();
  });

  it("executes KFlow DAGs with P-10 gating, rejects cycles/viewer RBAC, and lists runs", async () => {
    const gated = await client.platform.executeKflowDag({
      workflow_id: "WF-DEPLOY-01",
      workspace_id: "ws-p8",
      nodes: [
        { id: "plan", kind: "agent" },
        { id: "prod_gate", kind: "p10_gate", depends_on: ["plan"], requires_p10: true },
      ],
    });
    assert.equal(gated.status, "awaiting_p10");
    assert.equal(gated.held_node_id, "prod_gate");
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p8",
      workflow_id: "WF-DEPLOY-01",
      nodes: [
        { id: "plan", kind: "agent" },
        { id: "prod_gate", kind: "p10_gate", depends_on: ["plan"], requires_p10: true },
      ],
      trigger: "manual",
      token_budget: 25000,
      approved_node_ids: [],
    });

    const approved = await client.platform.executeKflowDag({
      workflow_id: "WF-DEPLOY-01",
      workspace_id: "ws-p8",
      trigger: "webhook",
      token_budget: 4096,
      approved_node_ids: ["prod_gate"],
      nodes: [
        { id: "plan", kind: "agent" },
        { id: "prod_gate", kind: "p10_gate", depends_on: ["plan"], requires_p10: true },
      ],
    });
    assert.equal(approved.status, "completed");

    await assert.rejects(
      () => client.platform.executeKflowDag({ workflow_id: "WF-CYCLE", nodes: [{ id: "self", depends_on: ["self"] }] }),
      (err) => err instanceof KeelwayError && err.status === 400,
    );

    await assert.rejects(
      () => client.platform.executeKflowDag({ workflow_id: "WF-VIEW" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );

    const runList = await client.platform.listKflowRuns({ workspace_id: "ws-p8", workflow_id: "WF-DEPLOY-01", limit: 1 });
    assert.equal(runList.runs.length, 1);
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p8", workflow_id: "WF-DEPLOY-01", limit: "1" });
  });

  it("synchronizes KSpaces LWW CRDT state and verifies CycloneDX SBOM provenance", async () => {
    const syncRes = await client.platform.syncKspacesCrdt({
      workspace_id: "ws-p8",
      peer_id: "node-alpha",
      operations: [{ namespace: "cursor", key: "active_file", value: "core/main.py", lamport_ts: 7 }],
    });
    assert.equal(syncRes.applied_count, 1);
    assert.equal(syncRes.active_keys_count, 1);

    const state = await client.platform.getKspacesState({ workspace_id: "ws-p8", namespace: "cursor" });
    assert.equal(state.entries[0].value, "core/main.py");
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p8", namespace: "cursor" });

    const sbom = await client.platform.getPlatformSbom("ws-p8");
    assert.equal(sbom.verified, true);
    assert.equal(sbom.bom_format, "CycloneDX");
    assert.equal(srv.recorded.at(-1).searchParams.workspace_id, "ws-p8");
  });
});
