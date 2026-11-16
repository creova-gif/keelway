import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import { KeelwayClient, KeelwayError, PermissionDeniedError } from "../dist/index.js";

async function startPhase7MockServer() {
  const recorded = [];
  const servers = new Map([
    [
      "keelway-core-mcp",
      {
        id: "keelway-core-mcp",
        name: "Keelway Core MCP",
        transport: "builtin",
        endpoint: "builtin://keelway-core",
        workspace_id: "default",
        builtin: true,
        status: "active",
      },
    ],
  ]);

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

    if (req.method === "GET" && p === "/v1/platform/mcp/servers") {
      const items = [...servers.values()];
      return sendJson(200, {
        workspace_id: searchParams.workspace_id ?? "default",
        servers: items,
        total: items.length,
      });
    }

    if (req.method === "POST" && p === "/v1/platform/mcp/servers") {
      if (String(parsedBody.endpoint ?? "").includes("169.254.169.254")) {
        return sendJson(400, { detail: "SSRF metadata endpoint blocked: 169.254.169.254" });
      }
      if (/[;|&$`]/.test(String(parsedBody.endpoint ?? ""))) {
        return sendJson(400, { detail: "Shell metacharacters forbidden in stdio command" });
      }
      const rec = {
        id: parsedBody.id,
        name: parsedBody.name,
        transport: parsedBody.transport,
        endpoint: parsedBody.endpoint,
        workspace_id: parsedBody.workspace_id ?? "default",
        allowed_tools: parsedBody.allowed_tools ?? [],
        status: "registered",
      };
      servers.set(rec.id, rec);
      return sendJson(201, rec);
    }

    if (req.method === "DELETE" && p.startsWith("/v1/platform/mcp/servers/")) {
      const serverId = decodeURIComponent(p.slice("/v1/platform/mcp/servers/".length));
      if (serverId === "keelway-core-mcp") {
        return sendJson(400, { detail: "Built-in keelway-core-mcp cannot be deleted" });
      }
      servers.delete(serverId);
      return sendJson(200, {
        deleted: true,
        server_id: serverId,
        workspace_id: searchParams.workspace_id ?? "default",
      });
    }

    if (req.method === "GET" && p === "/v1/platform/mcp/tools") {
      return sendJson(200, {
        workspace_id: searchParams.workspace_id ?? "default",
        tools: [
          { name: "workspace.list_files", server_id: "keelway-core-mcp", read_only: true },
          { name: "vault.list_metadata", server_id: "keelway-core-mcp", read_only: true },
        ],
        total: 2,
      });
    }

    if (req.method === "POST" && p === "/v1/platform/mcp/call") {
      if (req.headers["x-keelway-role"] === "viewer") {
        return sendJson(403, { detail: "Viewer role cannot invoke MCP tools" });
      }
      return sendJson(200, {
        workspace_id: parsedBody.workspace_id,
        tool_name: parsedBody.tool_name,
        ok: true,
        redacted: true,
        result: { files: ["pyproject.toml", "cli.py"], echo_args: parsedBody.arguments },
        receipt_sha256: "a".repeat(64),
      });
    }

    if (req.method === "POST" && p === "/v1/platform/evals/golden") {
      return sendJson(200, {
        eval_run_id: "eval-ts-01",
        workspace_id: parsedBody.workspace_id,
        category: parsedBody.category,
        total_cases: 16,
        passed_cases: 16,
        failed_cases: 0,
        pass_rate: 1.0,
        cases: [{ id: "sec-ssrf-imds", category: "security_redteam", passed: true }],
      });
    }

    if (req.method === "GET" && p === "/v1/platform/evals/latest") {
      return sendJson(200, {
        workspace_id: searchParams.workspace_id ?? "default",
        has_run: true,
        latest: {
          eval_run_id: "eval-ts-01",
          workspace_id: searchParams.workspace_id ?? "default",
          category: "all",
          total_cases: 16,
          passed_cases: 16,
          failed_cases: 0,
          pass_rate: 1.0,
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

describe("@keelway/sdk Phase 7 MCP Control Plane & Golden Evaluation Parity", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase7MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase7_ts" });
  });

  after(async () => {
    await srv.close();
  });

  it("manages MCP servers, blocks SSRF/metacharacters, lists tools, and invokes redacted MCP calls", async () => {
    const initial = await client.platform.listMcpServers("ws-p7");
    assert.equal(initial.workspace_id, "ws-p7");
    assert.equal(initial.servers[0].id, "keelway-core-mcp");
    assert.equal(srv.recorded.at(-1).headers.authorization, "Bearer kw_live_phase7_ts");

    await assert.rejects(
      () =>
        client.platform.registerMcpServer({
          id: "ssrf-mcp",
          name: "SSRF Probe",
          transport: "sse",
          endpoint: "http://169.254.169.254/latest/meta-data",
        }),
      (err) => err instanceof KeelwayError && err.status === 400,
    );

    const reg = await client.platform.registerMcpServer({
      id: "local-docs/mcp",
      name: "Local Docs MCP",
      transport: "sse",
      endpoint: "http://127.0.0.1:8910/sse",
      workspace_id: "ws-p7",
      allowed_tools: ["docs.search"],
    });
    assert.equal(reg.id, "local-docs/mcp");
    assert.deepEqual(srv.recorded.at(-1).body.allowed_tools, ["docs.search"]);

    const tools = await client.platform.listMcpTools({ workspace_id: "ws-p7" });
    assert.equal(tools.total, 2);

    const callObj = await client.platform.callMcpTool({
      tool_name: "workspace.list_files",
      arguments: { limit: 5 },
      workspace_id: "ws-p7",
    });
    assert.equal(callObj.ok, true);
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p7",
      tool_name: "workspace.list_files",
      arguments: { limit: 5 },
    });

    const callPos = await client.platform.callMcpTool("vault.list_metadata");
    assert.equal(callPos.tool_name, "vault.list_metadata");
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "default",
      tool_name: "vault.list_metadata",
      arguments: {},
    });

    await assert.rejects(
      () => client.platform.callMcpTool({ tool_name: "workspace.list_files" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );

    const del = await client.platform.deleteMcpServer("local-docs/mcp", "ws-p7");
    assert.equal(del.deleted, true);
    assert.equal(srv.recorded.at(-1).pathname, "/v1/platform/mcp/servers/local-docs%2Fmcp");
    assert.equal(srv.recorded.at(-1).searchParams.workspace_id, "ws-p7");
  });

  it("runs 16-probe golden evals and retrieves the latest scorecard", async () => {
    const defRun = await client.platform.runGoldenEvals();
    assert.equal(defRun.passed_cases, 16);
    assert.equal(defRun.pass_rate, 1.0);
    assert.deepEqual(srv.recorded.at(-1).body, { workspace_id: "default", category: "all" });

    const catRun = await client.platform.runGoldenEvals({ category: "security_redteam", workspace_id: "ws-p7" });
    assert.equal(catRun.category, "security_redteam");
    assert.deepEqual(srv.recorded.at(-1).body, { workspace_id: "ws-p7", category: "security_redteam" });

    const latest = await client.platform.getLatestGoldenEvals({ workspace_id: "ws-p7" });
    assert.equal(latest.has_run, true);
    assert.equal(latest.latest.eval_run_id, "eval-ts-01");
    assert.equal(srv.recorded.at(-1).searchParams.workspace_id, "ws-p7");
  });
});
