import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  PermissionDeniedError,
  PlatformClient,
  PlatformHealingClient,
  PlatformHealingDelegate,
  PolicyViolationError,
  TaskNotFoundError,
} from "../dist/index.js";

async function startPhase16MockServer() {
  const recorded = [];
  const structuredRuns = [];
  const diagnoses = [];

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

    if (req.headers.authorization !== "Bearer kw_live_phase16_ts") return sendJson(401, { detail: "Invalid bearer token" });
    const p = reqUrl.pathname;
    const isViewer = req.headers["x-keelway-role"] === "viewer";

    if (req.method === "POST" && p === "/v1/platform/healing/content-blocks/normalize") {
      const payloadText = typeof parsedBody.raw_payload === "string" ? parsedBody.raw_payload : JSON.stringify(parsedBody.raw_payload);
      const redacted = payloadText.includes("sk-live-secret") ? 1 : 0;
      return sendJson(200, {
        workspace_id: parsedBody.workspace_id ?? "default",
        provider_format: parsedBody.provider_format ?? "deepseek_opencore",
        model_id: parsedBody.model_id ?? "keelway-core:7b",
        block_count: 2,
        content_blocks: [
          { index: 0, kind: "reasoning", content: "Inspecting invoice total", tool_name: null, tool_call_id: null, tool_args: null, source_uri: null, structured_data: null },
          { index: 1, kind: "text", content: redacted ? "Token [REDACTED_SECRET]" : "Approved", tool_name: null, tool_call_id: null, tool_args: null, source_uri: null, structured_data: null },
        ],
        dlp_redactions: redacted,
        envelope_sha256: "a".repeat(64),
      });
    }

    if (req.method === "POST" && p === "/v1/platform/healing/structured/enforce") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied structured enforcement" });
      const rawOut = typeof parsedBody.raw_output === "string" ? parsedBody.raw_output : JSON.stringify(parsedBody.raw_output);
      const invalid = rawOut.includes("INVALID");
      const repaired = !invalid && !parsedBody.strict_mode && rawOut.includes("<think>");
      const run = {
        run_id: `srun-p16-${structuredRuns.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        schema_name: parsedBody.schema_name ?? "AgentDecisionContract",
        provider_format: parsedBody.provider_format ?? "deepseek_opencore",
        model_id: parsedBody.model_id ?? "keelway-core:7b",
        status: invalid ? "SCHEMA_REJECTED" : repaired ? "REPAIRED_VALID" : "VALID",
        repair_applied: repaired,
        repair_actions: repaired ? ["strip_think_tags", "coerce_scalar_types"] : [],
        validated_data: invalid ? null : { approved: true, score: 42 },
        validation_errors: invalid ? ["missing required property 'approved'"] : [],
        dlp_redactions: 0,
        run_sha256: "b".repeat(64),
        created_at: "2026-11-16T00:00:00Z",
      };
      structuredRuns.unshift(run);
      if (invalid && (parsedBody.fail_closed ?? true)) return sendJson(422, { detail: "Schema enforcement failed", code: "structured_schema_rejected", run });
      return sendJson(200, run);
    }

    if (req.method === "GET" && p === "/v1/platform/healing/structured/runs") {
      const wsId = searchParams.workspace_id ?? "default";
      const matched = structuredRuns.filter((r) => r.workspace_id === wsId).slice(0, Number(searchParams.limit ?? 25));
      return sendJson(200, { workspace_id: wsId, count: matched.length, runs: matched });
    }

    if (req.method === "POST" && p === "/v1/platform/healing/root-cause/diagnose") {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied diagnosis" });
      const diag = {
        diagnosis_id: diagnoses.length === 0 ? "diag/slash#1" : `diag-p16-${diagnoses.length + 1}`,
        workspace_id: parsedBody.workspace_id ?? "default",
        trace_id: parsedBody.trace_id ?? "trace-p16-1",
        workflow_name: parsedBody.workflow_name ?? "invoice-triage-agent",
        failure_class: "schema_mismatch",
        status: "DIAGNOSED",
        confidence: 0.94,
        failed_node: parsedBody.failed_step?.node_name ?? "extract_invoice",
        diagnostic_model: "keelway-core:7b",
        summary: "Scalar string returned for integer field",
        root_cause_evidence: ["expected integer at $.amount"],
        proposed_patch: { target_surface: "json_schema", recommended_model: "keelway-core:7b", unified_diff: "--- a/prompt\n+++ b/prompt", patched_prompt: "Return strict JSON integers." },
        verification_replay_trace_id: null,
        promoted_eval_case_id: null,
        dlp_redactions: 0,
        diagnosis_sha256: "c".repeat(64),
        created_at: "2026-11-16T00:01:00Z",
      };
      diagnoses.unshift(diag);
      return sendJson(200, diag);
    }

    if (req.method === "POST" && p.startsWith("/v1/platform/healing/root-cause/") && p.endsWith("/apply")) {
      if (isViewer) return sendJson(403, { detail: "Viewer role denied patch apply" });
      const diagId = decodeURIComponent(p.slice("/v1/platform/healing/root-cause/".length, -"/apply".length));
      const wsId = parsedBody.workspace_id ?? "default";
      const found = diagnoses.find((d) => d.diagnosis_id === diagId && d.workspace_id === wsId);
      if (!found) return sendJson(404, { detail: `Diagnosis '${diagId}' not found` });
      found.status = "VERIFIED_HEALED";
      found.verification_replay_trace_id = "replay-trace-p16";
      const evalCase = (parsedBody.promote_to_eval ?? true)
        ? { case_id: "eval-case-p16-1", title: parsedBody.eval_title ?? "Regression Case", case_sha256: "d".repeat(64) }
        : null;
      found.promoted_eval_case_id = evalCase?.case_id ?? null;
      return sendJson(200, { diagnosis: found, verified_healed: true, cached_steps_reused: 3, replay_cost_usd: 0.0012, promoted_eval_case: evalCase });
    }

    if (req.method === "GET" && p === "/v1/platform/healing/root-cause/diagnoses") {
      const wsId = searchParams.workspace_id ?? "default";
      const matched = diagnoses.filter((d) => d.workspace_id === wsId).slice(0, Number(searchParams.limit ?? 25));
      return sendJson(200, { workspace_id: wsId, count: matched.length, diagnoses: matched });
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

describe("@keelway/sdk Phase 16 Structured-Output Normalizer & Self-Healing Root-Causer", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase16MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase16_ts" });
  });
  after(async () => {
    await srv.close();
  });

  it("exports PlatformHealingClient, PlatformHealingDelegate, and mounts client.platform.healing", () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(typeof PlatformHealingClient, "function");
    assert.equal(PlatformHealingClient, PlatformHealingDelegate);
    assert.ok(client.platform.healing instanceof PlatformHealingClient);
  });

  it("normalizes content blocks with DLP scrubbing and enforces JSON-Schema contracts", async () => {
    assert.throws(() => client.platform.normalizeContentBlocks({ model_id: "  ", raw_payload: "hi" }), /model_id must be non-empty/);
    assert.throws(() => client.platform.listStructuredOutputRuns({ limit: 0 }), /limit must be >= 1/);

    const env = await client.platform.normalizeContentBlocks({
      workspace_id: "ws-p16",
      provider_format: "deepseek_opencore",
      raw_payload: "<think>Inspecting</think>Token sk-live-secret999",
    });
    assert.equal(env.block_count, 2);
    assert.equal(env.dlp_redactions, 1);
    assert.equal(env.envelope_sha256.length, 64);

    const repaired = await client.platform.enforceStructuredOutput({
      workspace_id: "ws-p16",
      schema_name: "InvoiceDecision",
      json_schema: { type: "object", required: ["approved", "score"] },
      raw_output: '<think>reasoning</think>{"approved": "true", "score": "42"}',
      strict_mode: false,
    });
    assert.equal(repaired.status, "REPAIRED_VALID");
    assert.equal(repaired.repair_applied, true);

    await assert.rejects(
      () => client.platform.enforceStructuredOutput({ workspace_id: "ws-p16", json_schema: { type: "object" }, raw_output: "INVALID", fail_closed: true }),
      (err) => err instanceof PolicyViolationError && err.status === 422,
    );

    const softFail = await client.platform.healing.enforceStructuredOutput({
      workspace_id: "ws-p16",
      json_schema: { type: "object" },
      raw_output: "INVALID",
      fail_closed: false,
    });
    assert.equal(softFail.status, "SCHEMA_REJECTED");

    const runs = await client.platform.listStructuredOutputRuns({ workspace_id: "ws-p16", limit: 10 });
    assert.equal(runs.count, 3);
  });

  it("diagnoses root causes, URL-encodes diagnosis_id on patch apply, and maps 403/404 errors", async () => {
    assert.throws(() => client.platform.diagnoseFailureRootCause({ workflow_name: "   " }), /workflow_name must be non-empty/);
    assert.throws(() => client.platform.applySelfHealingPatch("   "), /diagnosis_id must be non-empty/);

    const diag = await client.platform.diagnoseFailureRootCause({
      workspace_id: "ws-p16",
      workflow_name: "invoice-triage-agent",
      failed_step: { node_name: "extract_invoice", error_message: "schema mismatch" },
    });
    assert.equal(diag.diagnosis_id, "diag/slash#1");
    assert.equal(diag.status, "DIAGNOSED");

    const applied = await client.platform.applySelfHealingPatch(diag.diagnosis_id, {
      workspace_id: "ws-p16",
      promote_to_eval: true,
      eval_title: "Invoice Schema Regression",
    });
    assert.equal(applied.verified_healed, true);
    assert.equal(applied.diagnosis.status, "VERIFIED_HEALED");
    assert.equal(applied.promoted_eval_case.title, "Invoice Schema Regression");
    assert.ok(srv.recorded.some((r) => r.pathname === "/v1/platform/healing/root-cause/diag%2Fslash%231/apply"));

    const listed = await client.platform.listSelfHealingDiagnoses({ workspace_id: "ws-p16", limit: 5 });
    assert.equal(listed.count, 1);
    assert.equal(listed.diagnoses[0].status, "VERIFIED_HEALED");

    await assert.rejects(
      () => client.platform.diagnoseFailureRootCause({ workspace_id: "ws-p16" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );
    await assert.rejects(
      () => client.platform.applySelfHealingPatch("diag-missing", { workspace_id: "ws-p16" }),
      (err) => err instanceof TaskNotFoundError && err.status === 404,
    );
  });
});
