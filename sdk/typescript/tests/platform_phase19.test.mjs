import assert from "node:assert/strict";
import crypto from "node:crypto";
import http from "node:http";
import { after, before, describe, it } from "node:test";

import { KeelwayClient, PermissionDeniedError, PlatformClient, PlatformDistillClient, PlatformDistillDelegate } from "../dist/index.js";

const sha256Hex = (val) => crypto.createHash("sha256").update(val).digest("hex");
const scrubDlp = (txt) => {
  const matches = txt.match(/sk-live-\w+|ghp_\w+|AKIA\w+/g) ?? [];
  return { text: txt.replace(/sk-live-\w+|ghp_\w+|AKIA\w+/g, "[REDACTED_SECRET]"), count: matches.length };
};
const shingles3 = (txt) => {
  const words = txt.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(Boolean);
  if (words.length < 3) return new Set([words.join(" ")]);
  const s = new Set();
  for (let i = 0; i <= words.length - 3; i += 1) s.add(`${words[i]} ${words[i + 1]} ${words[i + 2]}`);
  return s;
};
const jaccard = (a, b) => {
  const [sa, sb] = [shingles3(a), shingles3(b)];
  let inter = 0;
  for (const x of sa) if (sb.has(x)) inter += 1;
  const union = sa.size + sb.size - inter;
  return union === 0 ? 1 : inter / union;
};

async function startPhase19MockServer() {
  const [cacheEntries, pairs, datasets, wsLookups] = [[], [], [], new Map()];

  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : null;
    const reqUrl = new URL(req.url ?? "/", "http://127.0.0.1");
    const q = Object.fromEntries(reqUrl.searchParams.entries());
    const sendJson = (status, payload) => (res.writeHead(status, { "Content-Type": "application/json" }), res.end(JSON.stringify(payload)));

    if (req.headers.authorization !== "Bearer kw_live_phase19_ts") return sendJson(401, { detail: "Invalid bearer token" });
    const p = reqUrl.pathname;
    const isReadOnly = req.headers["x-keelway-role"] === "viewer" || req.headers["x-keelway-role"] === "auditor";

    if (req.method === "POST" && p === "/v1/platform/distill/shadow/evaluate") {
      if (isReadOnly) return sendJson(403, { detail: "Read-only role denied shadow evaluate" });
      const [wsId, taskTag, threshold] = [body.workspace_id ?? "default", body.task_tag ?? "code-patch", body.similarity_threshold ?? 0.82];
      const [pScrub, fScrub, lScrub] = [scrubDlp(body.prompt), scrubDlp(body.frontier_response), scrubDlp(body.local_response)];
      const dlpCount = pScrub.count + fScrub.count + lScrub.count;
      wsLookups.set(wsId, (wsLookups.get(wsId) ?? 0) + 1);

      if (!body.bypass_cache) {
        for (const entry of cacheEntries) {
          if (entry.workspace_id !== wsId || entry.task_tag !== taskTag) continue;
          const exact = entry.prompt_sha256 === sha256Hex(pScrub.text);
          const sim = exact ? 1.0 : jaccard(entry.scrubbed_prompt, pScrub.text);
          if (exact || sim >= threshold) {
            const [savedCost, savedMs] = [body.frontier_cost_usd ?? 0.018, Math.max(0, (body.frontier_latency_ms ?? 840) - 2)];
            entry.hits += 1;
            entry.cost_saved_usd += savedCost;
            entry.latency_saved_ms += savedMs;
            return sendJson(200, {
              evaluation_id: `seval-${Date.now()}`, pair_id: null, cache_entry_id: entry.cache_entry_id,
              workspace_id: wsId, task_tag: taskTag, verdict: "CACHE_HIT",
              match_type: exact ? "exact_sha256" : "semantic_shingle", similarity_score: Number(sim.toFixed(4)),
              parity_score: entry.parity_score, frontier_model: body.frontier_model, local_model: body.local_model,
              scrubbed_prompt: pScrub.text, cached_response: entry.cached_response, cost_saved_usd: savedCost,
              latency_saved_ms: savedMs, dlp_redactions: dlpCount, event_sha256: sha256Hex(`hit:${entry.cache_entry_id}`), created_at: "2026-11-16T03:00:00Z",
            });
          }
        }
      }

      const parity = Number(jaccard(fScrub.text, lScrub.text).toFixed(4));
      const [pairId, cacheId] = [`spair-${pairs.length + 1}`, `scache-${cacheEntries.length + 1}`];
      pairs.unshift({
        pair_id: pairId, workspace_id: wsId, task_tag: taskTag, scrubbed_prompt: pScrub.text,
        scrubbed_frontier_response: fScrub.text, scrubbed_local_response: lScrub.text,
        frontier_model: body.frontier_model, local_model: body.local_model, parity_score: parity,
        frontier_cost_usd: body.frontier_cost_usd ?? 0.018, dlp_redactions: dlpCount, pair_sha256: sha256Hex(`${pairId}:${pScrub.text}`), created_at: "2026-11-16T03:00:00Z",
      });
      cacheEntries.push({
        cache_entry_id: cacheId, workspace_id: wsId, task_tag: taskTag, scrubbed_prompt: pScrub.text,
        prompt_sha256: sha256Hex(pScrub.text), cached_response: fScrub.text, parity_score: parity,
        hits: 0, cost_saved_usd: 0, latency_saved_ms: 0, dlp_redactions: dlpCount,
      });
      const verdict = parity >= 0.85 ? "LOCAL_PARITY_READY" : "SHADOW_CAPTURED";
      return sendJson(200, {
        evaluation_id: `seval-${pairs.length}`, pair_id: pairId, cache_entry_id: cacheId,
        workspace_id: wsId, task_tag: taskTag, verdict, match_type: "cache_miss", similarity_score: 0,
        parity_score: parity, frontier_model: body.frontier_model, local_model: body.local_model,
        scrubbed_prompt: pScrub.text, cached_response: fScrub.text, cost_saved_usd: 0, latency_saved_ms: 0,
        dlp_redactions: dlpCount, event_sha256: sha256Hex(`${verdict}:${pairId}`), created_at: "2026-11-16T03:00:00Z",
      });
    }

    if (req.method === "GET" && p === "/v1/platform/distill/shadow/pairs") {
      const wsId = q.workspace_id ?? "default";
      const matched = pairs.filter((r) => r.workspace_id === wsId && (!q.task_tag || r.task_tag === q.task_tag)).slice(0, Number(q.limit ?? 25));
      return sendJson(200, { workspace_id: wsId, count: matched.length, pairs: matched });
    }

    if (req.method === "GET" && p === "/v1/platform/distill/cache/stats") {
      const wsId = q.workspace_id ?? "default";
      const entries = cacheEntries.filter((e) => e.workspace_id === wsId);
      const [hits, lookups] = [entries.reduce((s, e) => s + e.hits, 0), wsLookups.get(wsId) ?? 0];
      return sendJson(200, {
        workspace_id: wsId, entry_count: entries.length, total_hits: hits, total_lookups: lookups,
        hit_rate: lookups > 0 ? Number((hits / lookups).toFixed(4)) : 0,
        total_cost_saved_usd: Number(entries.reduce((s, e) => s + e.cost_saved_usd, 0).toFixed(4)),
        total_latency_saved_ms: entries.reduce((s, e) => s + e.latency_saved_ms, 0),
        total_dlp_redactions: entries.reduce((s, e) => s + e.dlp_redactions, 0),
      });
    }

    if (req.method === "POST" && p === "/v1/platform/distill/datasets/compile") {
      if (isReadOnly) return sendJson(403, { detail: "Read-only role denied dataset compile" });
      const [wsId, tag] = [body.workspace_id ?? "default", body.task_tag ?? ""];
      const matched = pairs.filter((r) => r.workspace_id === wsId && (!tag || r.task_tag === tag) && r.parity_score >= (body.min_parity_score ?? 0));
      const preview = matched.map((r) => JSON.stringify({ prompt: r.scrubbed_prompt, chosen: r.scrubbed_frontier_response, rejected: r.scrubbed_local_response })).join("\n");
      const ds = {
        dataset_id: `qds-${datasets.length + 1}`, workspace_id: wsId, task_tag: tag,
        export_format: body.export_format ?? "dpo_preference", target_base_model: body.target_base_model ?? "keelway-core:7b",
        record_count: matched.length, avg_parity_score: matched.length ? Number((matched.reduce((s, r) => s + r.parity_score, 0) / matched.length).toFixed(4)) : 0,
        lora_rank: 16, lora_alpha: 32, dlp_redactions: matched.reduce((s, r) => s + r.dlp_redactions, 0),
        jsonl_preview: preview, dataset_sha256: sha256Hex(preview), created_at: "2026-11-16T03:01:00Z",
      };
      datasets.unshift(ds);
      return sendJson(200, ds);
    }

    if (req.method === "GET" && p === "/v1/platform/distill/datasets") {
      const wsId = q.workspace_id ?? "default";
      const matched = datasets.filter((d) => d.workspace_id === wsId).slice(0, Number(q.limit ?? 25));
      return sendJson(200, { workspace_id: wsId, count: matched.length, datasets: matched });
    }

    if (req.method === "POST" && p === "/v1/platform/distill/promotion/evaluate") {
      if (isReadOnly) return sendJson(403, { detail: "Read-only role denied promotion evaluate" });
      const [wsId, tag, minPairs, minAvg, vol] = [body.workspace_id ?? "default", body.task_tag ?? "code-patch", body.min_pairs ?? 3, body.min_avg_parity ?? 0.85, body.monthly_request_volume ?? 50000];
      const matched = pairs.filter((r) => r.workspace_id === wsId && r.task_tag === tag);
      const avgParity = matched.length ? Number((matched.reduce((s, r) => s + r.parity_score, 0) / matched.length).toFixed(4)) : 0;
      const avgCost = matched.length ? matched.reduce((s, r) => s + r.frontier_cost_usd, 0) / matched.length : 0.018;
      const verdict = matched.length < minPairs ? "NEEDS_MORE_PAIRS" : avgParity < minAvg ? "HOLD_ON_FRONTIER" : "PROMOTE_TO_OPENCORE";
      return sendJson(200, {
        evaluation_id: `pgate-${Date.now()}`, workspace_id: wsId, task_tag: tag,
        target_local_model: body.target_local_model ?? "keelway-core:7b", verdict, pair_count: matched.length,
        min_pairs: minPairs, avg_parity_score: avgParity, min_avg_parity: minAvg, avg_frontier_cost_usd: Number(avgCost.toFixed(4)),
        monthly_request_volume: vol, projected_monthly_savings_usd: verdict === "PROMOTE_TO_OPENCORE" ? Number((avgCost * vol).toFixed(2)) : 0,
        recommendation: `Verdict: ${verdict}`, gate_sha256: sha256Hex(`${wsId}:${tag}:${verdict}`), evaluated_at: "2026-11-16T03:02:00Z",
      });
    }
    return sendJson(404, { detail: `Unhandled ${req.method} ${p}` });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { baseUrl: `http://127.0.0.1:${server.address().port}`, close: () => (server.closeAllConnections?.(), new Promise((r) => server.close(r))) };
}

describe("@keelway/sdk Phase 19 Semantic Prompt Cache, Shadow Router & QLoRA Distillation", () => {
  let srv;
  let client;

  before(async () => {
    srv = await startPhase19MockServer();
    client = new KeelwayClient({ baseUrl: srv.baseUrl, apiKey: "kw_live_phase19_ts" });
  });
  after(async () => srv.close());

  it("enforces cross-workspace/task isolation, DLP scrubbing, shingle cache hits, dataset compile, and promotion gates", async () => {
    assert.equal(typeof PlatformClient, "function");
    assert.equal(PlatformDistillClient, PlatformDistillDelegate);
    assert.throws(() => client.platform.evaluateShadowPrompt({ prompt: "   " }), /prompt must be non-empty/);
    assert.throws(() => client.platform.listShadowPairs("ws-a", 0), /limit must be >= 1/);
    assert.throws(() => client.platform.compileDistillationDataset({ export_format: "csv" }), /Invalid export_format/);

    const promptText = "Generate deterministic SQL query for active tenant subscriptions using sk-live-987654";
    const missA = await client.platform.evaluateShadowPrompt({ workspace_id: "ws-a", task_tag: "sql-gen", prompt: promptText, similarity_threshold: 0.75 });
    assert.equal(missA.verdict, "LOCAL_PARITY_READY");
    assert.equal(missA.dlp_redactions, 1);
    assert.equal(missA.scrubbed_prompt.includes("sk-live-987654"), false);

    assert.notEqual((await client.platform.evaluateShadowPrompt({ workspace_id: "ws-b", task_tag: "sql-gen", prompt: promptText })).verdict, "CACHE_HIT");
    assert.notEqual((await client.platform.evaluateShadowPrompt({ workspace_id: "ws-a", task_tag: "code-review", prompt: promptText })).verdict, "CACHE_HIT");

    const shingleHit = await client.platform.evaluateShadowPrompt({
      workspace_id: "ws-a", task_tag: "sql-gen",
      prompt: "generate deterministic sql query for active tenant subscriptions using sk-live-987654!",
      similarity_threshold: 0.75,
    });
    assert.equal(shingleHit.verdict, "CACHE_HIT");
    assert.ok(["exact_sha256", "semantic_shingle"].includes(shingleHit.match_type));

    const stats = await client.platform.getSemanticCacheStats("ws-a");
    assert.equal(stats.total_hits, 1);
    assert.ok(stats.total_cost_saved_usd > 0);
    assert.equal((await client.platform.evaluateDistillationPromotion({ workspace_id: "ws-a", task_tag: "sql-gen", min_pairs: 2 })).verdict, "NEEDS_MORE_PAIRS");

    await client.platform.evaluateShadowPrompt({ workspace_id: "ws-a", task_tag: "sql-gen", prompt: "Select monthly recurring revenue per workspace", bypass_cache: true });
    assert.equal((await client.platform.listShadowPairs({ workspace_id: "ws-a", task_tag: "sql-gen", limit: 10 })).count, 2);

    const ds = await client.platform.compileDistillationDataset({ workspace_id: "ws-a", task_tag: "sql-gen", export_format: "dpo_preference" });
    assert.equal(ds.record_count, 2);
    assert.equal(ds.jsonl_preview.includes("sk-live-987654"), false);
    assert.equal((await client.platform.listDistillationDatasets("ws-a", 10)).count, 1);

    const promote = await client.platform.evaluateDistillationPromotion({ workspace_id: "ws-a", task_tag: "sql-gen", min_pairs: 2, min_avg_parity: 0.85, monthly_request_volume: 50000 });
    assert.equal(promote.verdict, "PROMOTE_TO_OPENCORE");
    assert.ok(promote.projected_monthly_savings_usd > 0);

    await assert.rejects(
      () => client.platform.evaluateShadowPrompt({ workspace_id: "ws-a" }, { headers: { "X-Keelway-Role": "viewer" } }),
      (e) => e instanceof PermissionDeniedError && e.status === 403,
    );
  });
});
