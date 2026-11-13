import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  AirGapEgressError,
  AuthenticationError,
  BudgetExceededError,
  ConnectionError,
  KeelwayClient,
  KeelwayError,
  mapHttpError,
  PermissionDeniedError,
  PolicyViolationError,
  QuorumRequiredError,
  RateLimitExceededError,
  TaskNotFoundError,
} from "../dist/index.js";

/**
 * Starts an ephemeral 127.0.0.1 HTTP server simulating the Keelway v1 platform endpoints.
 */
async function startEphemeralKeelwayServer() {
  const recorded = [];
  const tenants = new Map();

  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) {
      chunks.push(chunk);
    }
    const rawBody = Buffer.concat(chunks).toString("utf8");
    const parsedBody = rawBody ? JSON.parse(rawBody) : null;
    const reqUrl = new URL(req.url ?? "/", "http://127.0.0.1");

    recorded.push({
      method: req.method,
      rawUrl: req.url,
      pathname: reqUrl.pathname,
      searchParams: Object.fromEntries(reqUrl.searchParams.entries()),
      headers: req.headers,
      body: parsedBody,
    });

    const sendJson = (status, payload) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(payload));
    };

    if (req.method === "GET" && reqUrl.pathname === "/v1/models") {
      return sendJson(200, {
        object: "list",
        data: [
          {
            id: "keelway-core:7b",
            category: "open_weight",
            provider: "local",
            owned_by: "open_weight",
            deployment: "local_daemon",
            deployment_type: "local_daemon",
          },
          {
            id: "gpt-4o",
            category: "closed_proprietary",
            provider: "openai",
            owned_by: "openai",
          },
        ],
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/v1/usage") {
      return sendJson(200, {
        currency: "USD",
        total_cost_usd: 1.25,
        billed_cloud_expenditure_usd: 1.25,
        quantified_local_savings_usd: 42.5,
        sovereign_efficiency_index: 98.4,
        local_inference_ratio: 0.85,
      });
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/chat/completions") {
      if (parsedBody?.stream) {
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        });
        // Deliberately write split SSE fragments across socket flushes
        const fragments = [
          ": keep-alive\r",
          "\n\r\nda",
          'ta: {"id":"chatcmpl-1","choices":[{"index":0,"delta":{"content":"Habari "}}]}\r\n',
          "\r\ndata: ",
          '{"id":"chatcmpl-1","choices":[{"index":0,"delta":{"content":"ulimwengu!"}}]}\n\n',
          "data: [DO",
          "NE]\n\n",
          'data: {"id":"ignored-after-done","choices":[{"index":0,"delta":{"content":"NEVER"}}]}\n\n',
        ];
        for (const frag of fragments) {
          res.write(frag);
          await new Promise((r) => setTimeout(r, 2));
        }
        return res.end();
      }
      return sendJson(200, {
        id: "chatcmpl-sync-1",
        object: "chat.completion",
        model: parsedBody?.model ?? "keelway-core:7b",
        choices: [
          {
            index: 0,
            message: { role: "assistant", content: '{"ok":true}' },
            finish_reason: "stop",
          },
        ],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      });
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/responses") {
      if (parsedBody?.stream) {
        res.writeHead(200, { "Content-Type": "text/event-stream" });
        res.write(
          'event: response.created\ndata: {"type":"response.created","response":{"id":"resp_stream_1","object":"response","model":"keelway-core:7b","output_text":""}}\n\n',
        );
        res.write(
          'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","response_id":"resp_stream_1","delta":"Zero-egress "}\n\n',
        );
        res.write(
          'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","response_id":"resp_stream_1","delta":"verified."}\n\n',
        );
        res.write(
          'event: response.completed\ndata: {"type":"response.completed","response":{"id":"resp_stream_1","object":"response","model":"keelway-core:7b","output_text":"Zero-egress verified."}}\n\n',
        );
        return res.end();
      }
      return sendJson(200, {
        id: "resp_keelway_001",
        object: "response",
        status: "completed",
        model: parsedBody?.model ?? "keelway-core:7b",
        previous_response_id: parsedBody?.previous_response_id ?? null,
        output_text: "Stateful hybrid response verified.",
        usage: { input_tokens: 14, output_tokens: 10, total_tokens: 24 },
      });
    }

    if (req.method === "GET" && reqUrl.pathname.startsWith("/v1/responses/")) {
      const respId = decodeURIComponent(reqUrl.pathname.split("/").pop());
      return sendJson(200, {
        id: respId,
        object: "response",
        model: "keelway-core:7b",
        output_text: "Fetched stored response.",
      });
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/routing/explain") {
      return sendJson(200, {
        decision_id: "rdec_001",
        requested_model: parsedBody?.model ?? null,
        selected_provider: "local",
        fallback_chain: ["local"],
        reason: "Privacy private enforced zero-egress OpenCore checkpoint.",
        governance_provenance: {
          license: "Apache-2.0",
          weight_category: "open_weight",
          hosting: "in_process_opencore",
          operator: "customer_self_operated",
          data_boundary: "zero_external_egress",
          open_weight_implies_local: false,
        },
        privacy_level: parsedBody?.privacy_level ?? "standard",
        privacy_compliant: true,
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/v1/routing/decisions") {
      return sendJson(200, {
        object: "list",
        count: 1,
        decisions: [
          {
            decision_id: "rdec_001",
            selected_provider: "local",
            fallback_chain: ["local"],
          },
        ],
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/v1/opencore/status") {
      return sendJson(200, {
        status: "healthy",
        hardware: { accelerator: "mps", vram_gb: 36.0 },
        telemetry: { loaded_count: 1, allocated_vram_gb: 4.5 },
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/v1/opencore/weights") {
      return sendJson(200, [
        {
          model_id: "keelway-core:7b",
          quantization: "q4_k_m",
          is_cached: true,
        },
      ]);
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/opencore/modelfile") {
      return sendJson(200, {
        model_id: parsedBody.model_id,
        modelfile: `FROM ${parsedBody.base_source ?? "qwen3.5:latest"}\nPARAMETER temperature 0.2`,
        cli_command: `ollama create ${parsedBody.model_id} -f ./Modelfile`,
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/v1/opencore/adapters") {
      return sendJson(200, {
        adapters: [
          {
            adapter_id: "afri-lora-v1",
            name: "East Africa Multilingual LoRA",
            base_model_id: "keelway-core:7b",
            languages: ["swahili", "amharic"],
            is_attached: true,
          },
        ],
        attached_by_model: { "keelway-core:7b": "afri-lora-v1" },
      });
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/governance/tenants") {
      if (tenants.has(parsedBody.tenant_id)) {
        return sendJson(409, {
          detail: `Tenant '${parsedBody.tenant_id}' already exists.`,
        });
      }
      tenants.set(parsedBody.tenant_id, { ...parsedBody });
      return sendJson(201, tenants.get(parsedBody.tenant_id));
    }

    if (req.method === "PATCH" && reqUrl.pathname.startsWith("/v1/governance/tenants/")) {
      const tenantId = decodeURIComponent(reqUrl.pathname.split("/").pop());
      const existing = tenants.get(tenantId);
      if (!existing) {
        return sendJson(404, { detail: `Tenant '${tenantId}' not found.` });
      }
      const updated = { ...existing, ...parsedBody, tenant_id: tenantId };
      tenants.set(tenantId, updated);
      return sendJson(200, updated);
    }

    if (req.method === "GET" && reqUrl.pathname.startsWith("/v1/governance/tenants/")) {
      const tenantId = decodeURIComponent(reqUrl.pathname.split("/").pop());
      const existing = tenants.get(tenantId);
      if (!existing) {
        return sendJson(404, { detail: `Tenant '${tenantId}' not found.` });
      }
      return sendJson(200, existing);
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/governance/keys") {
      return sendJson(201, {
        key_id: "k_001",
        tenant_id: parsedBody.tenant_id,
        name: parsedBody.name,
        scopes: parsedBody.scopes,
        api_key: "kw_live_issued_secret_9988",
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/v1/governance/audit") {
      return sendJson(200, {
        chain_valid: true,
        total: 2,
        entries: [
          {
            seq: 1,
            tenant_id: "tenant-nairobi",
            action: "tenant.create",
            entry_hash: "a".repeat(64),
          },
        ],
      });
    }

    if (req.method === "POST" && reqUrl.pathname === "/v1/eval/swarm") {
      return sendJson(200, {
        mode: parsedBody.mode ?? "mock",
        graph_id: "keelway-mirofish-01",
        telemetry: {
          total_calls: 8,
          open_weight_calls: 6,
          closed_cloud_calls: 2,
          total_cost_usd: 0.0004,
          estimated_all_cloud_cost_usd: 0.0016,
          savings_pct: 75.0,
          elapsed_ms: 12.4,
        },
      });
    }

    if (req.method === "GET" && reqUrl.pathname === "/slow-timeout") {
      await new Promise((r) => setTimeout(r, 250));
      return sendJson(200, { ok: true });
    }

    return sendJson(404, { detail: `Unhandled route ${req.method} ${reqUrl.pathname}` });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;

  return {
    baseUrl,
    recorded,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

describe("@keelway/sdk v1.0.0 — Official Zero-Dependency TypeScript SDK", () => {
  let srv;
  let client;
  const secretKey = "kw_live_unit_test_secret_token_42";

  before(async () => {
    srv = await startEphemeralKeelwayServer();
    client = new KeelwayClient({
      baseUrl: `${srv.baseUrl}/`,
      apiKey: secretKey,
      timeoutMs: 5_000,
      defaultHeaders: { "X-Keelway-Tenant": "tenant-nairobi" },
    });
  });

  after(async () => {
    await srv.close();
  });

  it("injects Bearer kw_live_* header and never leaks apiKey into URL query strings", async () => {
    srv.recorded.length = 0;
    const models = await client.models.list({
      category: "open_weight",
      provider: "local",
      capability: "code",
    });

    assert.equal(models.object, "list");
    assert.equal(models.data.length, 2);
    assert.equal(srv.recorded.length, 1);

    const req = srv.recorded[0];
    assert.equal(req.headers.authorization, `Bearer ${secretKey}`);
    assert.equal(req.headers["x-keelway-tenant"], "tenant-nairobi");
    assert.ok(!req.rawUrl.includes(secretKey), "API key must never appear in URL");
    assert.deepEqual(req.searchParams, {
      category: "open_weight",
      provider: "local",
      capability: "code",
    });

    const usage = await client.usage.get();
    assert.equal(usage.sovereign_efficiency_index, 98.4);
    assert.equal(usage.quantified_local_savings_usd, 42.5);
  });

  it("executes chat.completions.create and parses multi-chunk split SSE chat.completions.stream", async () => {
    srv.recorded.length = 0;
    const completion = await client.chat.completions.create({
      messages: "Return JSON status",
      model: "keelway-core:7b",
      temperature: 0.1,
      max_tokens: 256,
      response_format: { type: "json_object" },
      privacy_level: "private",
      required_capabilities: ["code", "json"],
      max_cost_usd: 0.0,
    });

    assert.equal(completion.choices[0].message.content, '{"ok":true}');
    assert.deepEqual(srv.recorded[0].body.messages, [
      { role: "user", content: "Return JSON status" },
    ]);
    assert.equal(srv.recorded[0].body.privacy_level, "private");
    assert.equal(srv.recorded[0].body.stream, false);

    const streamedChunks = [];
    for await (const chunk of client.chat.completions.stream({
      messages: [{ role: "user", content: "Stream Swahili greeting" }],
      model: "keelway-core:7b",
      privacy_level: "private",
    })) {
      streamedChunks.push(chunk);
    }

    assert.equal(streamedChunks.length, 2);
    const combined = streamedChunks.map((c) => c.choices[0].delta.content).join("");
    assert.equal(combined, "Habari ulimwengu!");
    assert.equal(srv.recorded[1].body.stream, true);
  });

  it("handles UTF-8 multi-byte codepoints split mid-character across ReadableStream byte chunks", async () => {
    const encoder = new TextEncoder();
    const rawSse =
      'data: {"id":"c-utf8","choices":[{"index":0,"delta":{"content":"Sovereign 🌍🚀"}}]}\n\ndata: [DONE]\n\n';
    const fullBytes = encoder.encode(rawSse);

    // Slice 1 byte at a time so multi-byte UTF-8 emojis are split across chunks
    const customClient = new KeelwayClient({
      baseUrl: "http://mock.keelway.local",
      apiKey: "kw_live_stream_test",
      fetchImpl: async () => {
        const stream = new ReadableStream({
          start(controller) {
            for (let i = 0; i < fullBytes.length; i += 3) {
              controller.enqueue(fullBytes.slice(i, i + 3));
            }
            controller.close();
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      },
    });

    const parts = [];
    for await (const chunk of customClient.chat.completions.stream({
      messages: "UTF-8 split test",
    })) {
      parts.push(chunk.choices[0].delta.content);
    }
    assert.equal(parts.join(""), "Sovereign 🌍🚀");
  });

  it("supports stateful /v1/responses create, get, and SSE stream with previous_response_id and privacy_level=private", async () => {
    srv.recorded.length = 0;
    const created = await client.responses.create({
      input: "Explain zero-egress routing",
      model: "keelway-core:7b",
      instructions: "Be concise",
      previous_response_id: "resp_prev_00",
      privacy_level: "private",
      speculative: true,
      text: { format: { type: "json_object" } },
    });

    assert.equal(created.id, "resp_keelway_001");
    assert.equal(created.previous_response_id, "resp_prev_00");
    assert.equal(srv.recorded[0].body.privacy_level, "private");
    assert.equal(srv.recorded[0].body.previous_response_id, "resp_prev_00");
    assert.equal(srv.recorded[0].body.speculative, true);

    const fetched = await client.responses.get("resp_keelway_001");
    assert.equal(fetched.id, "resp_keelway_001");
    assert.equal(fetched.output_text, "Fetched stored response.");

    const events = [];
    for await (const evt of client.responses.stream({
      input: "Stream stateful response",
      privacy_level: "private",
    })) {
      events.push(evt);
    }
    assert.equal(events.length, 4);
    assert.equal(events[0].type, "response.created");
    const deltas = events
      .filter((e) => e.type === "response.output_text.delta")
      .map((e) => e.delta)
      .join("");
    assert.equal(deltas, "Zero-egress verified.");
    assert.equal(events[3].type, "response.completed");
  });

  it("covers 4D routing provenance, OpenCore subsystem, multi-tenant governance, and MiroFish swarm", async () => {
    const explanation = await client.routing.explain({
      messages: "Inspect confidential payroll",
      privacy_level: "private",
      required_capabilities: ["code"],
      max_cost_usd: 0.0,
    });
    assert.equal(explanation.selected_provider, "local");
    assert.equal(explanation.governance_provenance.data_boundary, "zero_external_egress");
    assert.equal(explanation.governance_provenance.open_weight_implies_local, false);

    const history = await client.routing.decisions({ limit: 5 });
    assert.equal(history.count, 1);

    const ocStatus = await client.opencore.status();
    assert.equal(ocStatus.status, "healthy");

    const weights = await client.opencore.weights();
    assert.equal(weights[0].model_id, "keelway-core:7b");

    const mf = await client.opencore.compileModelfile({
      model_id: "keelway-core:7b",
      base_source: "qwen3.5:latest",
      quantization: "q4_k_m",
      adapter_id: "afri-lora-v1",
    });
    assert.ok(mf.modelfile.includes("FROM qwen3.5:latest"));

    const adapters = await client.opencore.adapters({ base_model_id: "keelway-core:7b" });
    assert.equal(adapters.adapters[0].adapter_id, "afri-lora-v1");

    // Governance: create via POST (201) then idempotent update via 409 -> PATCH fallback
    const createdPolicy = await client.governance.upsertPolicy({
      tenant_id: "tenant-nairobi",
      name: "Nairobi Sovereign Bank",
      residency_zone: "zero_egress",
      monthly_spend_limit_usd: 50.0,
    });
    assert.equal(createdPolicy.monthly_spend_limit_usd, 50.0);

    const updatedPolicy = await client.governance.upsertPolicy({
      tenant_id: "tenant-nairobi",
      name: "Nairobi Sovereign Bank",
      residency_zone: "zero_egress",
      monthly_spend_limit_usd: 125.0,
    });
    assert.equal(updatedPolicy.monthly_spend_limit_usd, 125.0);

    const fetchedPolicy = await client.governance.getPolicy("tenant-nairobi");
    assert.equal(fetchedPolicy.monthly_spend_limit_usd, 125.0);

    const issuedKey = await client.governance.issueKey({
      tenant_id: "tenant-nairobi",
      name: "prod-worker",
      scopes: ["inference:write"],
    });
    assert.ok(issuedKey.api_key.startsWith("kw_live_"));

    const audit = await client.governance.verifyAudit({ tenant_id: "tenant-nairobi" });
    assert.equal(audit.chain_valid, true);

    const swarm = await client.swarm.evaluate({
      seed_text: "Sovereign payment rail launch",
      simulation_goal: "Forecast Q3 developer adoption",
      rounds: 2,
      mode: "mock",
    });
    assert.equal(swarm.graph_id, "keelway-mirofish-01");
    assert.equal(swarm.telemetry.savings_pct, 75.0);
  });

  it("maps every HTTP error code (401, 402, 403 air-gap/quorum/permission, 404, 422, 429, 500) identically to Python SDK", async () => {
    const cases = [
      {
        status: 401,
        detail: "Invalid or expired kw_live token",
        expectedClass: AuthenticationError,
        expectedCode: "AUTHENTICATION_FAILED",
        expectedPrefix: "Authentication failed: ",
      },
      {
        status: 402,
        detail: "Tenant monthly spend cap of $25.00 exceeded",
        expectedClass: BudgetExceededError,
        expectedCode: "BUDGET_EXCEEDED",
        expectedPrefix: "Budget exceeded: ",
      },
      {
        status: 403,
        detail: "Blocked external cloud egress under Air-Gap policy",
        expectedClass: AirGapEgressError,
        expectedCode: "AIRGAP_EGRESS_BLOCKED",
        expectedPrefix: "Air-Gap zero-egress violation: ",
      },
      {
        status: 403,
        detail: "Dual-human quorum approval required",
        expectedClass: QuorumRequiredError,
        expectedCode: "QUORUM_APPROVAL_PENDING",
        expectedPrefix: "Dual-human quorum required: ",
      },
      {
        status: 403,
        detail: "Scope governance:admin missing",
        expectedClass: PermissionDeniedError,
        expectedCode: "PERMISSION_DENIED",
        expectedPrefix: "Permission denied: ",
      },
      {
        status: 404,
        detail: "Response resp_missing not found",
        expectedClass: TaskNotFoundError,
        expectedCode: "TASK_NOT_FOUND",
        expectedPrefix: "Resource not found: ",
      },
      {
        status: 422,
        detail: "Model violates sovereign policy",
        expectedClass: PolicyViolationError,
        expectedCode: "POLICY_VIOLATION",
        expectedPrefix: "Policy validation failed: ",
      },
      {
        status: 429,
        detail: "Tenant rate limit 120 RPM exceeded",
        expectedClass: RateLimitExceededError,
        expectedCode: "RATE_LIMIT_EXCEEDED",
        expectedPrefix: "Rate limit exceeded: ",
      },
      {
        status: 500,
        detail: "Unexpected upstream error",
        expectedClass: KeelwayError,
        expectedCode: "KEELWAY_ERROR",
        expectedPrefix: "HTTP 500: ",
      },
    ];

    for (const tc of cases) {
      const mapped = mapHttpError(tc.status, { detail: tc.detail });
      assert.ok(mapped instanceof tc.expectedClass);
      assert.ok(mapped instanceof KeelwayError);
      assert.equal(mapped.code, tc.expectedCode);
      assert.equal(mapped.status, tc.status);
      assert.equal(mapped.details.status, tc.status);
      assert.equal(mapped.message, `${tc.expectedPrefix}${tc.detail}`);

      const mockClient = new KeelwayClient({
        baseUrl: "http://mock.keelway.local",
        fetchImpl: async () =>
          new Response(JSON.stringify({ detail: tc.detail }), {
            status: tc.status,
            headers: { "Content-Type": "application/json" },
          }),
      });

      await assert.rejects(
        () => mockClient.usage.get(),
        (err) => {
          assert.ok(err instanceof tc.expectedClass);
          assert.equal(err.code, tc.expectedCode);
          assert.equal(err.details.status, tc.status);
          return true;
        },
      );

      await assert.rejects(
        async () => {
          for await (const _ of mockClient.chat.completions.stream({ messages: "hi" })) {
            // consume stream
          }
        },
        (err) => {
          assert.ok(err instanceof tc.expectedClass);
          assert.equal(err.code, tc.expectedCode);
          return true;
        },
      );
    }
  });

  it("enforces timeoutMs via AbortSignal and translates network / abort errors to ConnectionError", async () => {
    // 1. Timeout via delayed /slow-timeout endpoint
    const slowClient = new KeelwayClient({
      baseUrl: srv.baseUrl,
      timeoutMs: 40,
      fetchImpl: (input, init) => {
        const rewritten = String(input).replace("/v1/usage", "/slow-timeout");
        return globalThis.fetch(rewritten, init);
      },
    });

    await assert.rejects(
      () => slowClient.usage.get(),
      (err) => {
        assert.ok(err instanceof ConnectionError);
        assert.equal(err.code, "DAEMON_UNREACHABLE");
        assert.match(err.message, /timed out/i);
        return true;
      },
    );

    // 2. Network transport failure -> ConnectionError without leaking apiKey
    const offlineClient = new KeelwayClient({
      baseUrl: "http://127.0.0.1:1",
      apiKey: secretKey,
      fetchImpl: async () => {
        throw new TypeError("fetch failed: ECONNREFUSED");
      },
    });

    await assert.rejects(
      () => offlineClient.usage.get(),
      (err) => {
        assert.ok(err instanceof ConnectionError);
        assert.equal(err.code, "DAEMON_UNREACHABLE");
        assert.ok(!err.message.includes(secretKey), "ConnectionError must never leak apiKey");
        return true;
      },
    );

    // 3. Caller-supplied AbortController pre-aborted signal
    const abortCtrl = new AbortController();
    abortCtrl.abort(new Error("Caller cancelled"));
    await assert.rejects(
      () => client.usage.get({ signal: abortCtrl.signal }),
      (err) => {
        assert.ok(err instanceof ConnectionError);
        assert.equal(err.code, "DAEMON_UNREACHABLE");
        return true;
      },
    );
  });
});
