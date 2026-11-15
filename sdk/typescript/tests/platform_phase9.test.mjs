import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  PermissionDeniedError,
  QuorumRequiredError,
} from "../dist/index.js";

const SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User";
const SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse";

async function startPhase9MockServer() {
  const recorded = [];
  const oidcConfigs = new Map();
  const scimUsers = new Map();
  const quorumProposals = new Map();

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

    if (req.headers.authorization !== "Bearer kw_live_phase9_ts") {
      return sendJson(401, { detail: "Invalid bearer token" });
    }
    if (req.headers["x-keelway-role"] === "viewer") {
      return sendJson(403, { detail: "Viewer role denied enterprise mutation" });
    }

    const p = reqUrl.pathname;

    if (req.method === "PUT" && p === "/v1/platform/enterprise/oidc") {
      const cfg = {
        workspace_id: parsedBody.workspace_id,
        issuer_url: parsedBody.issuer_url,
        client_id: parsedBody.client_id,
        enabled: Boolean(parsedBody.enabled),
        signing_secret_configured: Boolean(parsedBody.signing_secret),
        signing_secret_fingerprint: parsedBody.signing_secret ? `sha256:${"a".repeat(64)}` : null,
        group_role_mapping: parsedBody.group_role_mapping ?? {},
        updated_at: "2026-11-15T00:00:00Z",
      };
      oidcConfigs.set(parsedBody.workspace_id, cfg);
      return sendJson(200, cfg);
    }

    if (req.method === "POST" && p === "/v1/platform/enterprise/scim/v2/Users") {
      const wsId = parsedBody.workspace_id ?? "default";
      const cfg = oidcConfigs.get(wsId);
      const mapping = cfg?.group_role_mapping ?? {};
      const groups = parsedBody.groups ?? [];
      const mappedRole = groups.map((g) => mapping[g]).find(Boolean) ?? "viewer";
      const user = {
        schemas: [SCIM_USER_SCHEMA],
        id: `scim-${parsedBody.userName}`,
        userName: parsedBody.userName,
        displayName: parsedBody.displayName ?? "",
        active: Boolean(parsedBody.active),
        groups,
        mapped_role: mappedRole,
        updated_at: "2026-11-15T00:00:01Z",
      };
      scimUsers.set(`${wsId}:${parsedBody.userName}`, user);
      return sendJson(200, user);
    }

    if (req.method === "GET" && p === "/v1/platform/enterprise/scim/v2/Users") {
      const wsId = searchParams.workspace_id ?? "default";
      const resources = [...scimUsers.entries()]
        .filter(([k]) => k.startsWith(`${wsId}:`))
        .map(([, v]) => v);
      return sendJson(200, {
        schemas: [SCIM_LIST_SCHEMA],
        workspace_id: wsId,
        totalResults: resources.length,
        Resources: resources,
      });
    }

    if (req.method === "POST" && p === "/v1/platform/enterprise/p10-quorum/approve") {
      if (parsedBody.initiator_id && parsedBody.approver_id === parsedBody.initiator_id) {
        return sendJson(403, {
          detail: "Dual-human P-10 quorum violation: initiator cannot self-approve",
        });
      }
      const key = `${parsedBody.workspace_id}:${parsedBody.proposal_id}`;
      const existing = quorumProposals.get(key) ?? {
        workspace_id: parsedBody.workspace_id,
        proposal_id: parsedBody.proposal_id,
        initiator_id: parsedBody.initiator_id,
        required_approvals: parsedBody.required_approvals ?? 2,
        approvals: [],
      };
      if (existing.approvals.some((a) => a.approver_id === parsedBody.approver_id)) {
        return sendJson(403, {
          detail: "Dual-human P-10 quorum requires distinct approvers",
        });
      }
      existing.approvals.push({
        approver_id: parsedBody.approver_id,
        reason: parsedBody.reason ?? "",
        approved_at: "2026-11-15T00:00:02Z",
      });
      const approved = existing.approvals.length >= existing.required_approvals;
      quorumProposals.set(key, existing);
      return sendJson(200, {
        ...existing,
        approval_count: existing.approvals.length,
        status: approved ? "quorum_approved" : "awaiting_quorum",
        quorum_receipt_sha256: approved ? "b".repeat(64) : null,
      });
    }

    if (req.method === "GET" && p === "/v1/platform/enterprise/siem/export") {
      const wsId = searchParams.workspace_id ?? "default";
      const fmt = searchParams.format ?? "ocsf";
      const limit = Number(searchParams.limit ?? 100);
      const sample =
        fmt === "cef"
          ? ["CEF:0|SorvexLabs|Keelway|1.0.0|oidc.configure|OIDC Configured|3|"]
          : [{ class_uid: 3002, workspace_id: wsId, limit_applied: limit }];
      return sendJson(200, {
        workspace_id: wsId,
        format: fmt,
        record_count: sample.length,
        batch_sha256: "c".repeat(64),
        exported_at: "2026-11-15T00:00:03Z",
        records: sample,
      });
    }

    if (req.method === "GET" && p === "/v1/platform/observability/metrics") {
      const wsId = searchParams.workspace_id ?? "default";
      const fmt = searchParams.format ?? "otlp_json";
      return sendJson(200, {
        workspace_id: wsId,
        format: fmt,
        generated_at: "2026-11-15T00:00:04Z",
        counters: { scim_users_total: 1, p10_quorum_approved_total: 1 },
        prometheus_text:
          fmt === "prometheus"
            ? 'keelway_scim_users_total{workspace_id="' + wsId + '"} 1\n'
            : null,
        otlp_resource_metrics:
          fmt === "otlp_json"
            ? [{ resource: { attributes: [{ key: "service.name", value: { stringValue: "keelway" } }] } }]
            : null,
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

describe("@keelway/sdk Phase 9 Enterprise Identity, SCIM 2.0, P-10 Quorum, SIEM & Observability Parity", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase9MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase9_ts" });
  });

  after(async () => {
    await srv.close();
  });

  it("configures OIDC federation, provisions & lists SCIM 2.0 users, and maps RBAC denials", async () => {
    const oidc = await client.platform.configureOidcProvider({
      workspace_id: "ws-ent",
      issuer_url: "https://idp.keelway.example.com",
      client_id: "keelway-enterprise",
      signing_secret: "oidc-hs256-secret-xyz",
      group_role_mapping: { "okta:platform-admins": "admin", "okta:builders": "builder" },
      enabled: true,
    });
    assert.equal(oidc.signing_secret_configured, true);
    assert.equal(oidc.group_role_mapping["okta:platform-admins"], "admin");
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-ent",
      issuer_url: "https://idp.keelway.example.com",
      client_id: "keelway-enterprise",
      signing_secret: "oidc-hs256-secret-xyz",
      group_role_mapping: { "okta:platform-admins": "admin", "okta:builders": "builder" },
      enabled: true,
    });

    await assert.rejects(
      () =>
        client.platform.configureOidcProvider(
          { issuer_url: "https://idp.keelway.example.com", client_id: "denied" },
          { headers: { "X-Keelway-Role": "viewer" } },
        ),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );

    const provisioned = await client.platform.provisionScimUser({
      workspace_id: "ws-ent",
      userName: "alice@example.com",
      displayName: "Alice Security",
      groups: ["okta:platform-admins"],
      active: true,
    });
    assert.equal(provisioned.mapped_role, "admin");
    assert.equal(provisioned.active, true);

    const listed = await client.platform.listScimUsers("ws-ent");
    assert.equal(listed.totalResults, 1);
    assert.equal(listed.Resources[0].userName, "alice@example.com");
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-ent" });
  });

  it("enforces dual-human P-10 quorum, exports SIEM records, and queries OTLP/Prometheus metrics", async () => {
    await assert.rejects(
      () =>
        client.platform.approveP10Quorum({
          workspace_id: "ws-ent",
          proposal_id: "PROP-PROD-99",
          initiator_id: "alice@example.com",
          approver_id: "alice@example.com",
        }),
      (err) => err instanceof QuorumRequiredError && err.status === 403,
    );

    const first = await client.platform.approveP10Quorum({
      workspace_id: "ws-ent",
      proposal_id: "PROP-PROD-99",
      initiator_id: "alice@example.com",
      approver_id: "bob@example.com",
      required_approvals: 2,
      reason: "Reviewed terraform plan",
    });
    assert.equal(first.status, "awaiting_quorum");
    assert.equal(first.approval_count, 1);

    const second = await client.platform.approveP10Quorum({
      workspace_id: "ws-ent",
      proposal_id: "PROP-PROD-99",
      initiator_id: "alice@example.com",
      approver_id: "carol@example.com",
      required_approvals: 2,
      reason: "Independent security sign-off",
    });
    assert.equal(second.status, "quorum_approved");
    assert.equal(second.approval_count, 2);
    assert.equal(second.quorum_receipt_sha256?.length, 64);

    const siemCef = await client.platform.exportSiemAudit({
      workspace_id: "ws-ent",
      format: "cef",
      limit: 25,
    });
    assert.equal(siemCef.format, "cef");
    assert.equal(siemCef.record_count, 1);
    assert.deepEqual(srv.recorded.at(-1).searchParams, {
      workspace_id: "ws-ent",
      format: "cef",
      limit: "25",
    });

    const otlp = await client.platform.getObservabilityMetrics("ws-ent");
    assert.equal(otlp.format, "otlp_json");
    assert.equal(otlp.counters.p10_quorum_approved_total, 1);

    const prom = await client.platform.getObservabilityMetrics({
      workspace_id: "ws-ent",
      format: "prometheus",
    });
    assert.equal(prom.format, "prometheus");
    assert.match(prom.prometheus_text ?? "", /keelway_scim_users_total/);
  });
});
