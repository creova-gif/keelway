import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import { KeelwayClient, KeelwayError, PlatformNamespace } from "../dist/index.js";

async function startRuntimeMockServer() {
  const recorded = [];
  let secretVersion = 1;

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
    const p = reqUrl.pathname;

    if (req.method === "GET" && p === "/v1/platform/docs") {
      return sendJson(200, {
        workspace_id: searchParams.workspace_id ?? "default",
        count: 2,
        docs: [
          { id: "DOC-01", title: "Vault Spec", diataxis_kind: "reference", summary: "AES-256-GCM", body: "# Vault" },
          { id: "DOC-09", title: "Quickstart", diataxis_kind: "tutorial", summary: "Intro", body: "# Intro" },
        ],
      });
    }
    if (req.method === "POST" && p === "/v1/platform/docs") {
      return sendJson(201, { id: "DOC-02", title: parsedBody.title, diataxis_kind: parsedBody.diataxis_kind ?? "reference", summary: parsedBody.summary ?? "", body: parsedBody.body ?? "" });
    }
    if (req.method === "PUT" && p.startsWith("/v1/platform/docs/")) {
      return sendJson(200, { id: decodeURIComponent(p.split("/").pop()), title: parsedBody.title, diataxis_kind: parsedBody.diataxis_kind ?? "reference", summary: parsedBody.summary ?? "", body: parsedBody.body ?? "" });
    }
    if (req.method === "PATCH" && p.startsWith("/v1/platform/pm/issues/")) {
      return sendJson(200, { id: decodeURIComponent(p.split("/").pop()), title: parsedBody.title ?? "Existing", status: parsedBody.status ?? "in_progress", priority: parsedBody.priority ?? "high" });
    }
    if (req.method === "GET" && p === "/v1/platform/product/feedback") {
      return sendJson(200, { workspace_id: searchParams.workspace_id ?? "default", count: 1, total: 1, feedback: [{ id: "FB-01", persona: "CISO", quote: "Need zero-egress vault", impact_score: 9.5 }] });
    }
    if (req.method === "POST" && p === "/v1/platform/product/feedback") {
      return sendJson(201, { id: "FB-02", persona: parsedBody.persona, quote: parsedBody.quote, impact_score: parsedBody.impact_score ?? 8.5 });
    }
    if (req.method === "POST" && p === "/v1/platform/security/scan") {
      const clean = !String(parsedBody.content ?? "").includes("sk-live-");
      return sendJson(200, {
        workspace_id: parsedBody.workspace_id ?? "default",
        target_name: parsedBody.target_name ?? "workspace-snippet",
        passed: clean,
        risk_grade: clean ? "A" : "BLOCKED",
        findings: clean ? [] : [{ category: "hardcoded_secret", rule_id: "workspace_secret_detected", severity: "critical" }],
        findings_count: clean ? 0 : 1,
      });
    }
    if (req.method === "GET" && p === "/v1/platform/workspaces") {
      return sendJson(200, { workspaces: [{ id: "default", name: "Default", branch: "main", isolation_mode: "seatbelt_local" }], total: 1 });
    }
    if (req.method === "POST" && p === "/v1/platform/workspaces") {
      return sendJson(201, { id: parsedBody.id ?? "hipaa-intake", name: parsedBody.name, branch: parsedBody.branch ?? "main", isolation_mode: parsedBody.isolation_mode ?? "air_gap" });
    }
    if (req.method === "GET" && p === "/v1/platform/rbac/members") {
      return sendJson(200, { workspace_id: searchParams.workspace_id ?? "default", members: [{ actor_id: "usr_owner", role: "owner" }], roles: ["owner", "admin", "builder", "operator", "viewer"] });
    }
    if (req.method === "POST" && p === "/v1/platform/rbac/members") {
      return sendJson(200, { workspace_id: parsedBody.workspace_id ?? "default", actor_id: parsedBody.actor_id, role: parsedBody.role });
    }
    if (req.method === "POST" && p === "/v1/platform/rbac/check") {
      const allowed = parsedBody.role === "owner" || parsedBody.role === "admin";
      return sendJson(200, { allowed, role: parsedBody.role ?? "viewer", permission: parsedBody.permission, reason: allowed ? "Permitted" : "Denied" });
    }
    if (req.method === "GET" && p === "/v1/platform/vault/secrets") {
      return sendJson(200, { workspace_id: searchParams.workspace_id ?? "default", secrets: [{ name: "OPENAI_API_KEY", namespace: "byom", masked_preview: "sk-l****2345", fingerprint_sha256: "a1b2c3d4", version: secretVersion, updated_at: "2026-11-14T20:00:00Z" }], total: 1 });
    }
    if (req.method === "POST" && p === "/v1/platform/vault/secrets") {
      return sendJson(201, { name: parsedBody.name, namespace: parsedBody.namespace ?? "byom", masked_preview: "sk-l****2345", fingerprint_sha256: "a1b2c3d4", version: 1, updated_at: "2026-11-14T20:00:00Z" });
    }
    if (req.method === "POST" && p.endsWith("/rotate") && p.startsWith("/v1/platform/vault/secrets/")) {
      secretVersion += 1;
      const parts = p.split("/");
      return sendJson(200, { name: decodeURIComponent(parts[parts.length - 2]), namespace: parsedBody.namespace ?? "byom", masked_preview: "sk-r****9999", fingerprint_sha256: "f9e8d7c6", version: secretVersion, updated_at: "2026-11-14T20:01:00Z" });
    }
    if (req.method === "DELETE" && p.startsWith("/v1/platform/vault/secrets/")) {
      return sendJson(200, { deleted: true, name: decodeURIComponent(p.split("/").pop()), workspace_id: searchParams.workspace_id ?? "default" });
    }
    if (req.method === "GET" && p === "/v1/platform/webhooks") {
      return sendJson(200, { webhooks: [{ id: "wh_01", url: "https://hooks.example.com/keelway", events: ["run.completed"] }], deliveries: [], total: 1 });
    }
    if (req.method === "POST" && p === "/v1/platform/webhooks") {
      if (String(parsedBody.url).includes("169.254.169.254")) return sendJson(400, { detail: "SSRF target blocked: 169.254.169.254" });
      return sendJson(201, { id: "wh_02", url: parsedBody.url, events: parsedBody.events ?? ["*"], description: parsedBody.description ?? "" });
    }
    if (req.method === "POST" && p.endsWith("/test") && p.startsWith("/v1/platform/webhooks/")) {
      const parts = p.split("/");
      return sendJson(200, { webhook_id: decodeURIComponent(parts[parts.length - 2]), event_id: "evt_test_01", signature: "sha256=deadbeef1234", headers: { "X-Keelway-Signature-256": "sha256=deadbeef1234" }, delivered: true });
    }
    if (req.method === "POST" && p === "/v1/platform/webhooks/verify") {
      const valid = parsedBody.signature === "sha256=deadbeef1234";
      return sendJson(200, { valid, reason: valid ? "ok" : "signature_mismatch" });
    }
    if (req.method === "DELETE" && p.startsWith("/v1/platform/webhooks/")) {
      return sendJson(200, { deleted: true, webhook_id: decodeURIComponent(p.split("/").pop()) });
    }
    if (req.method === "POST" && p === "/v1/platform/execution/runs") {
      return sendJson(200, {
        run_id: "run_live_01",
        workspace_id: parsedBody.workspace_id ?? "default",
        kind: parsedBody.kind ?? "agent",
        target_id: parsedBody.target_id,
        objective: parsedBody.objective,
        status: parsedBody.requires_p10 ? "awaiting_p10_approval" : "completed",
        requires_p10: Boolean(parsedBody.requires_p10),
        events: [{ type: "run.started", run_id: "run_live_01", seq: 1 }],
      });
    }
    if (req.method === "GET" && p.endsWith("/events") && p.startsWith("/v1/platform/execution/runs/")) {
      res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "close" });
      const fragments = [
        ": keep-alive\r\nevent: run.started\r\nda",
        'ta: {"type":"run.started","run_id":"run_live_01","seq":1,"note":"Sovereign ✓"}\r\n\r',
        '\ndata: {"type":"p10.',
        'held","run_id":"run_live_01","seq":2,"status":"awaiting_p10_approval"}\n\n',
        'data: {"type":"run.completed","run_id":"run_live_01","seq":3,"status":"completed"}\n\n',
        "data: [DO",
        "NE]\n\n",
        'data: {"type":"ignored.after.done","seq":99}\n\n',
      ];
      for (const frag of fragments) {
        res.write(frag);
        await new Promise((r) => setTimeout(r, 2));
      }
      return res.end();
    }
    if (req.method === "POST" && p.endsWith("/p10") && p.startsWith("/v1/platform/execution/runs/")) {
      const parts = p.split("/");
      return sendJson(200, {
        run_id: decodeURIComponent(parts[parts.length - 2]),
        kind: "agent",
        target_id: "feature-coder",
        objective: "Deploy migration",
        status: parsedBody.decision === "approve" ? "completed" : "aborted_by_p10",
        events: [{ type: "p10.resolved", decision: parsedBody.decision }],
      });
    }
    if (req.method === "POST" && p === "/v1/platform/pricing/simulate") {
      return sendJson(200, {
        schedule: parsedBody.schedule ?? "compare",
        seats: parsedBody.seats ?? 8,
        monthly_api_spend_usd: parsedBody.monthly_api_spend_usd ?? 1200,
        run_swarm: Boolean(parsedBody.run_swarm),
        calibrated: { pro_annual_usd: 29, byom_annual_usd: 15, pricing_health_score: 96.5 },
        legacy: { pro_annual_usd: 39, pricing_health_score: 54.0 },
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

describe("@keelway/sdk Phase 4 + Phase 5 Platform Runtime Parity", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startRuntimeMockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase5_test_token" });
  });

  after(async () => {
    await srv.close();
  });

  it("covers Phase 4 docs, issue patching, feedback, and workspace security scanning", async () => {
    assert.ok(client.platform instanceof PlatformNamespace);
    const docs = await client.platform.listDocs({ workspace_id: "ws-p4", diataxis_kind: "reference" });
    assert.equal(docs.count, 1);
    assert.equal(docs.docs[0].id, "DOC-01");

    const createdDoc = await client.platform.createDoc({ title: "Runbook", diataxis_kind: "howto", summary: "Ops", body: "Step 1", workspace_id: "ws-p4" });
    assert.equal(createdDoc.id, "DOC-02");
    assert.equal((await client.platform.updateDoc("DOC-02", { title: "Runbook v2", diataxis_kind: "howto", body: "Step 1+2", workspace_id: "ws-p4" })).title, "Runbook v2");

    const patchedIssue = await client.platform.updateIssue("KEEL-201", { status: "done", priority: "critical", workspace_id: "ws-p4" });
    assert.equal(patchedIssue.id, "KEEL-201");
    assert.equal(patchedIssue.status, "done");

    assert.equal((await client.platform.listFeedback({ workspace_id: "ws-p4" })).total, 1);
    assert.equal((await client.platform.createFeedback({ persona: "Staff SRE", quote: "Rock solid", impact_score: 9.2, workspace_id: "ws-p4" })).id, "FB-02");

    const scanBlocked = await client.platform.scanWorkspaceSecurity({ target_name: "env.ts", content: "const k = 'sk-live-secret-999';", workspace_id: "ws-p4" });
    assert.equal(scanBlocked.passed, false);
    assert.equal(scanBlocked.risk_grade, "BLOCKED");
  });

  it("covers Phase 5 workspaces, RBAC checks, AES-256-GCM vault lifecycle, and SSRF-guarded webhooks", async () => {
    assert.equal((await client.platform.listWorkspaces()).total, 1);
    assert.equal((await client.platform.createWorkspace({ id: "hipaa-intake", name: "HIPAA Intake", branch: "main", isolation_mode: "air_gap" })).id, "hipaa-intake");
    assert.equal((await client.platform.listRbacMembers({ workspace_id: "hipaa-intake" })).members[0].role, "owner");
    assert.equal((await client.platform.upsertRbacMember({ workspace_id: "hipaa-intake", actor_id: "usr_auditor", role: "viewer" })).role, "viewer");

    assert.equal((await client.platform.checkRbac({ workspace_id: "hipaa-intake", actor_id: "usr_auditor", role: "viewer", permission: "secrets:write" })).allowed, false);
    assert.equal((await client.platform.checkRbac({ workspace_id: "hipaa-intake", actor_id: "usr_owner", role: "owner", permission: "secrets:write" })).allowed, true);

    const putRes = await client.platform.putSecret({ name: "OPENAI_API_KEY", secret_value: "sk-live-secret-12345", workspace_id: "hipaa-intake", namespace: "byom" });
    assert.equal(putRes.masked_preview, "sk-l****2345");
    assert.equal("secret_value" in putRes, false);
    assert.equal((await client.platform.listSecrets({ workspace_id: "hipaa-intake" })).secrets[0].fingerprint_sha256, "a1b2c3d4");
    assert.equal((await client.platform.rotateSecret("OPENAI_API_KEY", { secret_value: "sk-rotated-9999", workspace_id: "hipaa-intake" })).version, 2);
    assert.equal((await client.platform.deleteSecret("OPENAI_API_KEY", { workspace_id: "hipaa-intake" })).deleted, true);

    await assert.rejects(
      () => client.platform.createWebhook({ url: "http://169.254.169.254/latest/meta-data", events: ["*"] }),
      (err) => err instanceof KeelwayError && err.status === 400,
    );
    const wh = await client.platform.createWebhook({ url: "https://hooks.example.com/p10", events: ["p10.held", "run.completed"], workspace_id: "hipaa-intake" });
    assert.equal(wh.id, "wh_02");
    assert.equal((await client.platform.listWebhooks({ workspace_id: "hipaa-intake" })).total, 1);

    const receipt = await client.platform.testWebhook("wh_02");
    assert.equal(receipt.signature, "sha256=deadbeef1234");
    assert.equal((await client.platform.verifyWebhook({ payload: '{"event":"test"}', signature: receipt.signature, secret: "whsec_test", timestamp: 1700000000 })).valid, true);
    assert.equal((await client.platform.deleteWebhook("wh_02")).deleted, true);
  });

  it("starts non-streaming execution runs, streams chunk-split SSE events up to [DONE], and resolves P-10 gates", async () => {
    srv.recorded.length = 0;
    const snap = await client.platform.startExecutionRun({ kind: "agent", target_id: "feature-coder", objective: "Deploy schema migration", workspace_id: "hipaa-intake", requires_p10: true });
    assert.equal(snap.run_id, "run_live_01");
    assert.equal(snap.status, "awaiting_p10_approval");
    assert.equal(srv.recorded[0].body.stream, false);

    const events = [];
    for await (const ev of client.platform.streamExecutionEvents("run_live_01", { workspace_id: "hipaa-intake" })) {
      events.push(ev);
    }
    assert.equal(events.length, 3);
    assert.equal(events[0].type, "run.started");
    assert.equal(events[0].event, "run.started");
    assert.equal(events[0].note, "Sovereign ✓");
    assert.equal(events[1].type, "p10.held");
    assert.equal(events[2].type, "run.completed");

    const sseReq = srv.recorded.find((r) => r.pathname.endsWith("/events"));
    assert.equal(sseReq.headers.authorization, "Bearer kw_live_phase5_test_token");
    assert.equal(sseReq.headers.accept, "text/event-stream");

    const resolved = await client.platform.resolveExecutionP10("run_live_01", { decision: "approve", approver: "usr_owner", reason: "Reviewed migration diff" });
    assert.equal(resolved.status, "completed");
    assert.equal(srv.recorded.at(-1).body.approver, "usr_owner");
  });

  it("simulates calibrated vs legacy pricing schedules via POST /v1/platform/pricing/simulate", async () => {
    const defSim = await client.platform.simulatePricing();
    assert.equal(defSim.schedule, "compare");
    assert.equal(defSim.seats, 8);
    assert.equal(defSim.monthly_api_spend_usd, 1200);
    assert.equal(defSim.run_swarm, true);
    assert.equal(defSim.calibrated.pro_annual_usd, 29);

    const customSim = await client.platform.simulatePricing({
      schedule: "calibrated",
      seats: 16,
      monthly_api_spend_usd: 2500,
      run_swarm: false,
    });
    assert.equal(customSim.schedule, "calibrated");
    assert.equal(customSim.seats, 16);
    assert.equal(customSim.monthly_api_spend_usd, 2500);
    assert.equal(customSim.run_swarm, false);
  });
});
