import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import earlyAccessHandler from "../../api/early-access.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");

function createMockRes() {
  const headers = new Map();
  let statusCode = 200;
  let rawBody = "";
  return {
    status(code) {
      statusCode = code;
      return this;
    },
    setHeader(key, value) {
      headers.set(String(key).toLowerCase(), String(value));
      return this;
    },
    end(chunk = "") {
      rawBody = String(chunk);
    },
    get statusCode() {
      return statusCode;
    },
    get headers() {
      return Object.fromEntries(headers.entries());
    },
    json() {
      return rawBody ? JSON.parse(rawBody) : null;
    },
  };
}

function createReq({
  method = "POST",
  origin = "https://keelway.dev",
  ip = "203.0.113.10",
  body = { email: "security@acme-corp.com", role: "security_lead", interest: "vpc", region: "us-east" },
  extraHeaders = {},
} = {}) {
  const headers = { ...extraHeaders };
  if (origin !== undefined) {
    headers.origin = origin;
  }
  if (ip !== undefined) {
    headers["x-forwarded-for"] = ip;
  }
  return {
    method,
    headers,
    body,
    socket: { remoteAddress: ip || "127.0.0.1" },
  };
}

test("source audit: api/early-access.js contains no GitHub Issues API sink or EARLY_ACCESS_GH_TOKEN", () => {
  const src = fs.readFileSync(path.join(REPO_ROOT, "api/early-access.js"), "utf8");
  assert.equal(src.includes("EARLY_ACCESS_GH_TOKEN"), false);
  assert.equal(src.includes("https://api.github.com/repos/"), false);
});

test("fails closed with 503 when EARLY_ACCESS_WEBHOOK_URL is unset even if legacy EARLY_ACCESS_GH_TOKEN is set", async () => {
  earlyAccessHandler._resetRateLimitForTests();
  const originalFetch = globalThis.fetch;
  const originalWebhook = process.env.EARLY_ACCESS_WEBHOOK_URL;
  const originalGhToken = process.env.EARLY_ACCESS_GH_TOKEN;
  const originalError = console.error;
  const fetchCalls = [];
  const loggedText = [];

  globalThis.fetch = async (url, init) => {
    fetchCalls.push({ url: String(url), init });
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  console.error = (...args) => {
    loggedText.push(JSON.stringify(args));
  };

  try {
    delete process.env.EARLY_ACCESS_WEBHOOK_URL;
    process.env.EARLY_ACCESS_GH_TOKEN = `ghp_${"0".repeat(36)}`;

    const submitterEmail = "alice.sensitive@enterprise.io";
    const req = createReq({ body: { email: submitterEmail, role: "cto_vp", interest: "vpc", region: "eu" } });
    const res = createMockRes();
    await earlyAccessHandler(req, res);

    assert.equal(res.statusCode, 503);
    assert.equal(res.json().ok, false);
    assert.equal(fetchCalls.length, 0, "No network request may be made when private webhook is unconfigured");
    assert.equal(
      loggedText.join(" ").includes(submitterEmail),
      false,
      "Submitter email must never leak to server error logs"
    );
  } finally {
    globalThis.fetch = originalFetch;
    console.error = originalError;
    if (originalWebhook === undefined) delete process.env.EARLY_ACCESS_WEBHOOK_URL;
    else process.env.EARLY_ACCESS_WEBHOOK_URL = originalWebhook;
    if (originalGhToken === undefined) delete process.env.EARLY_ACCESS_GH_TOKEN;
    else process.env.EARLY_ACCESS_GH_TOKEN = originalGhToken;
  }
});

test("rejects GitHub Issues URLs, HTTP URLs, and SSRF loopback/private targets as EARLY_ACCESS_WEBHOOK_URL", async () => {
  const forbiddenUrls = [
    "https://api.github.com/repos/creova-gif/keelway/issues",
    "https://github.com/creova-gif/keelway/issues",
    "https://enterprise.github.com/repos/org/repo/issues",
    "http://hooks.internal.example.com/early-access",
    "https://127.0.0.1/webhook",
    "https://localhost:8443/webhook",
    "https://169.254.169.254/latest/meta-data/",
    "https://10.0.0.12/intake",
    "https://172.16.5.4/intake",
    "https://192.168.1.20/intake",
    "https://user:pass@hooks.example.com/intake",
  ];

  for (const badUrl of forbiddenUrls) {
    assert.equal(
      earlyAccessHandler.validatePrivateWebhookUrl(badUrl),
      null,
      `Expected ${badUrl} to be rejected`
    );
  }

  earlyAccessHandler._resetRateLimitForTests();
  const originalFetch = globalThis.fetch;
  const originalWebhook = process.env.EARLY_ACCESS_WEBHOOK_URL;
  const fetchCalls = [];
  globalThis.fetch = async (url) => {
    fetchCalls.push(String(url));
    return new Response("{}", { status: 200 });
  };

  try {
    process.env.EARLY_ACCESS_WEBHOOK_URL = "https://api.github.com/repos/creova-gif/keelway/issues";
    const res = createMockRes();
    await earlyAccessHandler(createReq(), res);
    assert.equal(res.statusCode, 503);
    assert.equal(fetchCalls.length, 0, "Must never dispatch PII to api.github.com");
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWebhook === undefined) delete process.env.EARLY_ACCESS_WEBHOOK_URL;
    else process.env.EARLY_ACCESS_WEBHOOK_URL = originalWebhook;
  }
});

test("enforces POST method, strict Origin allowlist, payload byte cap, and input validation bounds", async () => {
  earlyAccessHandler._resetRateLimitForTests();

  // 1. Non-POST rejected with 405
  {
    const res = createMockRes();
    await earlyAccessHandler(createReq({ method: "GET" }), res);
    assert.equal(res.statusCode, 405);
    assert.equal(res.headers.allow, "POST");
  }

  // 2. Missing, untrusted, or wildcard Origin rejected with 403
  for (const badOrigin of ["", "https://evil.example.com", "*", "null"]) {
    const res = createMockRes();
    await earlyAccessHandler(createReq({ origin: badOrigin }), res);
    assert.equal(res.statusCode, 403, `Origin '${badOrigin}' must be forbidden`);
  }

  // 3. Oversized payload (> 4096 bytes) rejected with 413
  {
    const hugeString = JSON.stringify({
      email: "valid@company.com",
      padding: "x".repeat(earlyAccessHandler.MAX_BODY_BYTES + 100),
    });
    const res = createMockRes();
    await earlyAccessHandler(createReq({ body: hugeString, ip: "203.0.113.20" }), res);
    assert.equal(res.statusCode, 413);
  }

  // 4. Declared Content-Length > 4096 rejected with 413 immediately
  {
    const res = createMockRes();
    await earlyAccessHandler(
      createReq({
        ip: "203.0.113.21",
        extraHeaders: { "content-length": "99999" },
      }),
      res
    );
    assert.equal(res.statusCode, 413);
  }

  // 5. Invalid JSON or array payload rejected with 400
  for (const invalidBody of ["{malformed", ["array"], null]) {
    earlyAccessHandler._resetRateLimitForTests();
    const res = createMockRes();
    await earlyAccessHandler(createReq({ body: invalidBody, ip: "203.0.113.22" }), res);
    assert.equal(res.statusCode, 400);
  }

  // 6. Malformed, CRLF-injected, or oversized emails rejected with 400
  const invalidEmails = [
    "",
    "plainaddress",
    "user@localhost",
    "user@domain.c",
    "user..double@company.com",
    ".leading@company.com",
    "trailing.@company.com",
    "user@-badlabel.com",
    "user@company.com\r\nBcc:attacker@evil.com",
    `${"a".repeat(65)}@company.com`,
    `${"a".repeat(60)}@${"b".repeat(200)}.com`,
  ];
  for (const badEmail of invalidEmails) {
    earlyAccessHandler._resetRateLimitForTests();
    const res = createMockRes();
    await earlyAccessHandler(createReq({ body: { email: badEmail }, ip: "203.0.113.23" }), res);
    assert.equal(res.statusCode, 400, `Email '${badEmail}' should fail validation`);
  }

  // 7. Unknown enum / out-of-bounds role, interest, or region rejected with 400
  for (const badFieldBody of [
    { email: "eng@company.com", interest: "drop_table_users" },
    { email: "eng@company.com", role: "superadmin_override" },
    { email: "eng@company.com", region: "us east; rm -rf /" },
  ]) {
    earlyAccessHandler._resetRateLimitForTests();
    const res = createMockRes();
    await earlyAccessHandler(createReq({ body: badFieldBody, ip: "203.0.113.24" }), res);
    assert.equal(res.statusCode, 400);
  }
});

test("routes valid submissions to private HTTPS webhook with HMAC-SHA256 signature and enforces rate limit", async () => {
  earlyAccessHandler._resetRateLimitForTests();
  const originalFetch = globalThis.fetch;
  const originalWebhook = process.env.EARLY_ACCESS_WEBHOOK_URL;
  const originalSecret = process.env.EARLY_ACCESS_WEBHOOK_SECRET;
  const delivered = [];

  globalThis.fetch = async (url, init) => {
    delivered.push({ url: String(url), init });
    return new Response(JSON.stringify({ accepted: true }), { status: 202 });
  };

  try {
    process.env.EARLY_ACCESS_WEBHOOK_URL = "https://intake.keelway.internal.example/v1/leads";
    process.env.EARLY_ACCESS_WEBHOOK_SECRET = "whsec_test_ephemeral_signing_secret";

    const res = createMockRes();
    await earlyAccessHandler(
      createReq({
        ip: "198.51.100.42",
        body: {
          email: "VP.Eng@Enterprise.example",
          role: "cto_vp",
          interest: "vpc",
          region: "eu-west",
        },
      }),
      res
    );

    assert.equal(res.statusCode, 200);
    const body = res.json();
    assert.equal(body.ok, true);
    assert.match(body.referenceId, /^KW-[0-9A-F]{8}$/);

    assert.equal(delivered.length, 1);
    assert.equal(delivered[0].url, "https://intake.keelway.internal.example/v1/leads");
    assert.equal(delivered[0].init.redirect, "error");

    const rawSent = delivered[0].init.body;
    const expectedHmac = crypto
      .createHmac("sha256", "whsec_test_ephemeral_signing_secret")
      .update(rawSent, "utf8")
      .digest("hex");
    assert.equal(delivered[0].init.headers["X-Keelway-Signature-256"], `sha256=${expectedHmac}`);

    const parsedSent = JSON.parse(rawSent);
    assert.equal(parsedSent.email, "vp.eng@enterprise.example");
    assert.equal(parsedSent.role, "cto_vp");
    assert.equal(parsedSent.interest, "vpc");
    assert.equal(parsedSent.region, "EU-WEST");

    // Exhaust remaining 4 requests in the 5-per-10-min window for the same IP, then assert 429 on #6
    for (let i = 0; i < 4; i += 1) {
      const okRes = createMockRes();
      await earlyAccessHandler(createReq({ ip: "198.51.100.42" }), okRes);
      assert.equal(okRes.statusCode, 200);
    }
    const throttledRes = createMockRes();
    await earlyAccessHandler(createReq({ ip: "198.51.100.42" }), throttledRes);
    assert.equal(throttledRes.statusCode, 429);
    assert.ok(Number(throttledRes.headers["retry-after"]) >= 1);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWebhook === undefined) delete process.env.EARLY_ACCESS_WEBHOOK_URL;
    else process.env.EARLY_ACCESS_WEBHOOK_URL = originalWebhook;
    if (originalSecret === undefined) delete process.env.EARLY_ACCESS_WEBHOOK_SECRET;
    else process.env.EARLY_ACCESS_WEBHOOK_SECRET = originalSecret;
  }
});
