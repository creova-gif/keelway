import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  PermissionDeniedError,
  PlatformClient,
  PlatformSafetyMeshClient,
  PlatformSafetyMeshDelegate,
  PolicyViolationError,
} from "../dist/index.js";

async function startPhase17MockServer() {
  const verifications = [];
  const meshNodes = [
    {
      node_id: "edge-mac-m3-max",
      workspace_id: "ws-p17",
      name: "edge-mac-m3-max",
      tier: "edge_local",
      hardware_hal: "apple_metal_secure_enclave",
      region: "local-loopback",
      vram_gb: 64,
      status: "ONLINE",
      attestation_sha256: "sha256:" + "a".repeat(64),
      registered_at: "2026-11-16T00:00:00Z",
    },
    {
      node_id: "cluster-h100-us-east",
      workspace_id: "ws-p17",
      name: "cluster-h100-us-east",
      tier: "cluster_burst",
      hardware_hal: "nvidia_h100_cc",
      region: "us-east-1",
      vram_gb: 80,
      status: "ONLINE",
      attestation_sha256: "sha256:" + "b".repeat(64),
      registered_at: "2026-11-16T00:00:00Z",
    },
  ];
  const handoffs = [];

  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const rawBody = Buffer.concat(chunks).toString("utf8");
    const body = rawBody ? JSON.parse(rawBody) : null;
    const reqUrl = new URL(req.url ?? "/", "http://127.0.0.1");
    const q = Object.fromEntries(reqUrl.searchParams.entries());
    const sendJson = (status, payload) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(payload));
    };

    if (req.headers.authorization !== "Bearer kw_live_phase17_ts") return sendJson(401, { detail: "Invalid bearer token" });
    const p = reqUrl.pathname;
    const isViewer = req.headers["x-keelway-role"] === "viewer";

    if (req.method === "POST" && p === "/v1/platform/safety/verify") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied safety verification" });
      const nodes = body.nodes ?? [{ node_id: "wire_exec", tool_kind: "external_transfer", requires_p10: false }];
      const unguarded = nodes.filter((n) => (n.tool_kind === "destructive_shell" || n.tool_kind === "external_transfer") && !n.requires_p10);
      const injected = body.inject_p10_guards ? unguarded.map((n) => n.node_id) : [];
      const violations = !body.inject_p10_guards && unguarded.length > 0
        ? [{ invariant_id: "no_unguarded_destructive_tool", severity: "CRITICAL", offending_node: unguarded[0].node_id, counterexample_path: ["intake", unguarded[0].node_id], remediation: "Enable requires_p10=true" }]
        : [];
      const rec = {
        verification_id: `sver-p17-${verifications.length + 1}`,
        workspace_id: body.workspace_id ?? "default",
        workflow_id: body.workflow_id ?? "WF-TREASURY-01",
        workflow_name: body.workflow_name ?? "treasury-wire-approver",
        status: violations.length === 0 ? "VERIFIED_SAFE" : "VIOLATION_FOUND",
        states_explored: 6,
        invariants_checked: [{ invariant_id: "no_unguarded_destructive_tool", passed: violations.length === 0, description: "Destructive tools require P-10" }],
        violations,
        p10_guards_injected: injected,
        dlp_redactions: JSON.stringify(body).includes("sk-live") ? 1 : 0,
        proof_sha256: "sha256:" + "c".repeat(64),
        created_at: "2026-11-16T00:01:00Z",
      };
      verifications.unshift(rec);
      return sendJson(200, rec);
    }

    if (req.method === "GET" && p === "/v1/platform/safety/verifications") {
      const wsId = q.workspace_id ?? "default";
      const matched = verifications.filter((v) => v.workspace_id === wsId).slice(0, Number(q.limit ?? 25));
      return sendJson(200, { workspace_id: wsId, count: matched.length, verifications: matched });
    }

    if (req.method === "POST" && p === "/v1/platform/mesh/nodes") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied mesh node registration" });
      const rec = {
        node_id: body.node_id ?? `mesh-node-${meshNodes.length + 1}`,
        workspace_id: body.workspace_id ?? "default",
        name: body.name,
        tier: body.tier ?? "edge_local",
        hardware_hal: body.hardware_hal ?? "apple_metal_secure_enclave",
        region: body.region ?? "local-loopback",
        vram_gb: body.vram_gb ?? 32,
        status: body.status ?? "ONLINE",
        attestation_sha256: "sha256:" + "d".repeat(64),
        registered_at: "2026-11-16T00:02:00Z",
      };
      meshNodes.push(rec);
      return sendJson(200, rec);
    }

    if (req.method === "GET" && p === "/v1/platform/mesh/nodes") {
      const wsId = q.workspace_id ?? "default";
      const matched = meshNodes.filter((n) => n.workspace_id === wsId);
      return sendJson(200, { workspace_id: wsId, count: matched.length, nodes: matched });
    }

    if (req.method === "POST" && p === "/v1/platform/mesh/dispatch") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied mesh dispatch" });
      if (body.force_raw_cloud_burst && body.data_classification === "restricted_pii") {
        return sendJson(422, { detail: "Raw restricted_pii cannot burst off edge_local", code: "mesh_sovereignty_violation" });
      }
      const allowBurst = body.allow_sanitized_burst ?? true;
      const rec = {
        handoff_id: `mhand-p17-${handoffs.length + 1}`,
        workspace_id: body.workspace_id ?? "default",
        workflow_name: body.workflow_name ?? "clinical-synthesis-pipeline",
        data_classification: body.data_classification ?? "restricted_pii",
        status: allowBurst ? "ATTESTED_COMPLETE" : "PINNED_EDGE_ONLY",
        edge_node_id: "edge-mac-m3-max",
        burst_node_id: allowBurst ? "cluster-h100-us-east" : null,
        stages: [{ stage_name: "local_dlp_scrub", target_tier: "edge_local", node_id: "edge-mac-m3-max", model_id: "keelway-core:7b", hardware_hal: "apple_metal_secure_enclave", zero_raw_pii_egress: true, cost_usd: 0 }],
        total_cost_usd: allowBurst ? 0.0042 : 0,
        dlp_redactions: 2,
        attestation_sha256: "sha256:" + "e".repeat(64),
        created_at: "2026-11-16T00:03:00Z",
      };
      handoffs.unshift(rec);
      return sendJson(200, rec);
    }

    if (req.method === "GET" && p === "/v1/platform/mesh/handoffs") {
      const wsId = q.workspace_id ?? "default";
      const matched = handoffs.filter((h) => h.workspace_id === wsId).slice(0, Number(q.limit ?? 25));
      return sendJson(200, { workspace_id: wsId, count: matched.length, handoffs: matched });
    }

    return sendJson(404, { detail: `Unhandled ${req.method} ${p}` });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { baseUrl: `http://127.0.0.1:${server.address().port}`, close: () => (server.closeAllConnections?.(), new Promise((r) => server.close(r))) };
}

describe("@keelway/sdk Phase 17 Formal Safety Verifier & Federated Edge Mesh", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase17MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase17_ts" });
  });
  after(async () => {
    await srv.close();
  });

  it("exports PlatformSafetyMeshClient, PlatformSafetyMeshDelegate, and mounts client.platform.safetyMesh", () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(typeof PlatformSafetyMeshClient, "function");
    assert.equal(PlatformSafetyMeshClient, PlatformSafetyMeshDelegate);
    assert.ok(client.platform.safetyMesh instanceof PlatformSafetyMeshClient);
  });

  it("verifies workflow safety invariants, auto-injects P-10 guards, and lists verifications", async () => {
    assert.throws(() => client.platform.verifyWorkflowSafety({ workflow_id: "   " }), /workflow_id must be non-empty/);
    assert.throws(() => client.platform.listSafetyVerifications("ws-p17", 0), /limit must be >= 1/);

    const unsafe = await client.platform.verifyWorkflowSafety({
      workspace_id: "ws-p17",
      nodes: [{ node_id: "wire_exec", tool_kind: "external_transfer", requires_p10: false }],
    });
    assert.equal(unsafe.status, "VIOLATION_FOUND");
    assert.equal(unsafe.violations.length, 1);

    const safe = await client.platform.verifyWorkflowSafety({
      workspace_id: "ws-p17",
      nodes: [{ node_id: "wire_exec", tool_kind: "external_transfer", requires_p10: false }],
      inject_p10_guards: true,
    });
    assert.equal(safe.status, "VERIFIED_SAFE");
    assert.deepEqual(safe.p10_guards_injected, ["wire_exec"]);

    const listed = await client.platform.listSafetyVerifications("ws-p17", 10);
    assert.equal(listed.count, 2);
  });

  it("registers attested mesh nodes, dispatches edge-to-cluster handoffs, and enforces 422/403 sovereignty gates", async () => {
    assert.throws(() => client.platform.registerMeshNode({ name: "  " }), /name must be non-empty/);

    const created = await client.platform.registerMeshNode({
      workspace_id: "ws-p17",
      name: "edge-linux-tpm2-lab",
      tier: "edge_local",
      hardware_hal: "linux_tpm2",
      vram_gb: 24,
    });
    assert.equal(created.hardware_hal, "linux_tpm2");

    const nodes = await client.platform.listMeshNodes("ws-p17");
    assert.equal(nodes.count, 3);

    const attested = await client.platform.dispatchMeshHandoff({ workspace_id: "ws-p17", allow_sanitized_burst: true });
    assert.equal(attested.status, "ATTESTED_COMPLETE");
    assert.equal(attested.burst_node_id, "cluster-h100-us-east");

    const pinned = await client.platform.dispatchMeshHandoff({ workspace_id: "ws-p17", allow_sanitized_burst: false });
    assert.equal(pinned.status, "PINNED_EDGE_ONLY");
    assert.equal(pinned.burst_node_id, null);

    await assert.rejects(
      () => client.platform.dispatchMeshHandoff({ workspace_id: "ws-p17", data_classification: "restricted_pii", force_raw_cloud_burst: true }),
      (err) => err instanceof PolicyViolationError && err.status === 422,
    );
    await assert.rejects(
      () => client.platform.verifyWorkflowSafety({ workspace_id: "ws-p17" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );

    const handoffs = await client.platform.listMeshHandoffs("ws-p17", 10);
    assert.equal(handoffs.count, 2);
  });
});
