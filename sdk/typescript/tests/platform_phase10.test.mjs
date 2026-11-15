import assert from "node:assert/strict";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import {
  KeelwayClient,
  KeelwayError,
  PermissionDeniedError,
} from "../dist/index.js";

async function startPhase10MockServer() {
  const recorded = [];
  const facts = new Map();
  const skills = [
    {
      id: "skill-ast-profiler",
      name: "AST Boundary Profiler",
      source_type: "agents_skill",
      digest_sha256: "a".repeat(64),
      air_gap_ready: true,
      version: "1.0.0",
    },
    {
      id: "skill-sbom-auditor",
      name: "CycloneDX SBOM Auditor",
      source_type: "claude_skill",
      digest_sha256: "b".repeat(64),
      air_gap_ready: true,
      version: "1.0.0",
    },
  ];

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

    if (req.headers.authorization !== "Bearer kw_live_phase10_ts") {
      return sendJson(401, { detail: "Invalid bearer token" });
    }
    if (req.headers["x-keelway-role"] === "viewer" && req.method === "POST") {
      return sendJson(403, { detail: "Viewer role denied KBrain/KHub mutation" });
    }

    const p = reqUrl.pathname;

    if (req.method === "POST" && p === "/v1/platform/kbrain/facts") {
      if (String(parsedBody.statement).includes("sk-ant-secret")) {
        return sendJson(400, { detail: "DLP secret leak detected in KBrain fact statement" });
      }
      const existing = [...facts.values()].find(
        (f) =>
          f.workspace_id === parsedBody.workspace_id &&
          f.key === parsedBody.key &&
          f.scope === parsedBody.scope &&
          (f.status === "approved" || f.status === "proposed") &&
          f.statement !== parsedBody.statement,
      );
      const id = `kb_fact_${facts.size + 1}`;
      const record = {
        id,
        workspace_id: parsedBody.workspace_id,
        key: parsedBody.key,
        statement: parsedBody.statement,
        scope: parsedBody.scope,
        status: existing ? "conflict" : parsedBody.auto_approve ? "approved" : "proposed",
        conflict_with_fact_id: existing ? existing.id : null,
        provenance_uri: parsedBody.provenance_uri ?? "",
        tags: parsedBody.tags ?? [],
        created_by: "operator",
        fact_sha256: "c".repeat(64),
        created_at: "2026-11-15T00:00:00Z",
      };
      facts.set(id, record);
      return sendJson(200, record);
    }

    if (req.method === "GET" && p === "/v1/platform/kbrain/search") {
      const wsId = searchParams.workspace_id ?? "default";
      const q = (searchParams.query ?? "").toLowerCase();
      const maxScope = searchParams.max_scope ?? "org";
      const includeConflicts = searchParams.include_conflicts === "true";
      const limit = Number(searchParams.limit ?? 20);
      const rank = { local_session: 1, project: 2, team: 3, org: 4 };
      const allowed = rank[maxScope] ?? 4;
      const matches = [...facts.values()]
        .filter((f) => {
          if (f.workspace_id !== wsId) return false;
          if ((rank[f.scope] ?? 1) > allowed) return false;
          if (f.status === "rejected" || f.status === "withdrawn") return false;
          if (!includeConflicts && f.status === "conflict") return false;
          if (q && !f.statement.toLowerCase().includes(q) && !f.key.toLowerCase().includes(q)) {
            return false;
          }
          return true;
        })
        .slice(0, limit)
        .map((f) => ({ ...f, score: 0.94, bm25_score: 0.91, ngram_score: 0.88 }));
      return sendJson(200, {
        workspace_id: wsId,
        query: searchParams.query ?? "",
        max_scope: maxScope,
        total_matches: matches.length,
        results: matches,
      });
    }

    const resolveMatch = p.match(/^\/v1\/platform\/kbrain\/facts\/([^/]+)\/resolve$/);
    if (req.method === "POST" && resolveMatch) {
      const factId = decodeURIComponent(resolveMatch[1]);
      const existing = facts.get(factId);
      if (!existing) {
        return sendJson(404, { detail: `Fact ${factId} not found` });
      }
      existing.status = parsedBody.resolution === "approve" ? "approved" : "rejected";
      existing.conflict_with_fact_id = null;
      facts.set(factId, existing);
      return sendJson(200, existing);
    }

    if (req.method === "GET" && p === "/v1/platform/khub/skills") {
      const wsId = searchParams.workspace_id ?? "default";
      return sendJson(200, {
        workspace_id: wsId,
        total_skills: skills.length,
        air_gap_compliant: true,
        catalog_digest_sha256: "d".repeat(64),
        skills,
      });
    }

    if (req.method === "POST" && p === "/v1/platform/khub/mirror/verify") {
      const wsId = parsedBody.workspace_id ?? "default";
      const requestedIds = parsedBody.skill_ids ?? [];
      const targetCount = requestedIds.length > 0 ? requestedIds.length : skills.length;
      return sendJson(200, {
        workspace_id: wsId,
        verified: true,
        mirror_format: "khub-skill-bundle-v1",
        skills_verified: targetCount,
        catalog_digest_sha256: "d".repeat(64),
        verified_at: "2026-11-15T00:00:05Z",
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

describe("@keelway/sdk Phase 10 KBrain Hybrid Memory & KHub Skill Mirror Parity", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase10MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase10_ts" });
  });

  after(async () => {
    await srv.close();
  });

  it("records, searches, detects conflicts, and resolves KBrain facts with DLP & RBAC checks", async () => {
    const f1 = await client.platform.recordKbrainFact({
      workspace_id: "ws-p10",
      key: "db.engine",
      statement: "Primary persistence uses SQLite WAL mode with deterministic digests.",
      scope: "project",
      provenance_uri: "file://docs/architecture.md",
      tags: ["storage", "wal"],
      auto_approve: true,
    });
    assert.equal(f1.status, "approved");
    assert.equal(f1.fact_sha256.length, 64);
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p10",
      key: "db.engine",
      statement: "Primary persistence uses SQLite WAL mode with deterministic digests.",
      scope: "project",
      provenance_uri: "file://docs/architecture.md",
      tags: ["storage", "wal"],
      auto_approve: true,
    });

    await assert.rejects(
      () =>
        client.platform.recordKbrainFact({
          workspace_id: "ws-p10",
          key: "leaked.key",
          statement: "Token is sk-ant-secret-0123456789abcdef0123456789",
        }),
      (err) => err instanceof KeelwayError && err.status === 400,
    );

    await assert.rejects(
      () =>
        client.platform.recordKbrainFact(
          { key: "denied.key", statement: "Viewer cannot write" },
          { headers: { "X-Keelway-Role": "viewer" } },
        ),
      (err) => err instanceof PermissionDeniedError && err.status === 403,
    );

    const f2 = await client.platform.recordKbrainFact({
      workspace_id: "ws-p10",
      key: "db.engine",
      statement: "Primary persistence uses external Postgres.",
      scope: "project",
    });
    assert.equal(f2.status, "conflict");
    assert.equal(f2.conflict_with_fact_id, f1.id);

    const searchClean = await client.platform.searchKbrainFacts({
      workspace_id: "ws-p10",
      query: "persistence",
      max_scope: "team",
      include_conflicts: false,
      limit: 10,
    });
    assert.equal(searchClean.total_matches, 1);
    assert.deepEqual(srv.recorded.at(-1).searchParams, {
      workspace_id: "ws-p10",
      query: "persistence",
      max_scope: "team",
      include_conflicts: "false",
      limit: "10",
    });

    const searchWithConflicts = await client.platform.searchKbrainFacts({
      workspace_id: "ws-p10",
      query: "persistence",
      max_scope: "org",
      include_conflicts: true,
      limit: 10,
    });
    assert.equal(searchWithConflicts.total_matches, 2);

    const resolved = await client.platform.resolveKbrainFact(f2.id, {
      workspace_id: "ws-p10",
      resolution: "reject",
    });
    assert.equal(resolved.status, "rejected");
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p10",
      resolution: "reject",
    });
  });

  it("lists air-gapped KHub skills and verifies SHA-256 mirror bundles", async () => {
    const catalog = await client.platform.listKhubSkills("ws-p10");
    assert.equal(catalog.workspace_id, "ws-p10");
    assert.equal(catalog.total_skills, 2);
    assert.equal(catalog.air_gap_compliant, true);
    assert.equal(catalog.catalog_digest_sha256.length, 64);
    assert.deepEqual(srv.recorded.at(-1).searchParams, { workspace_id: "ws-p10" });

    const receipt = await client.platform.verifyKhubMirror({
      workspace_id: "ws-p10",
      skill_ids: ["skill-ast-profiler"],
    });
    assert.equal(receipt.verified, true);
    assert.equal(receipt.mirror_format, "khub-skill-bundle-v1");
    assert.equal(receipt.skills_verified, 1);
    assert.deepEqual(srv.recorded.at(-1).body, {
      workspace_id: "ws-p10",
      skill_ids: ["skill-ast-profiler"],
    });
  });
});
