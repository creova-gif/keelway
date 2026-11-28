import { createHmac, randomBytes } from "node:crypto";

// POST /api/early-access — validates the intake and forwards exclusively to a
// private HTTPS webhook (EARLY_ACCESS_WEBHOOK_URL). Mirrors api/early-access.js
// semantics: fail-closed 503 when unconfigured, no PII to public surfaces.

const MAX_BODY_BYTES = 4096;
const MAX_EMAIL_LENGTH = 254;
const MAX_LOCAL_PART_LENGTH = 64;
const MAX_FIELD_LENGTH = 64;
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 5;
const RATE_LIMIT_MAX_KEYS = 2048;

const DEFAULT_ALLOWED_ORIGINS = [
  "https://keelway.dev",
  "https://www.keelway.dev",
  "https://kora-sable.vercel.app",
  "https://kora-eight-nu.vercel.app",
];

const DEV_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"];

const INTEREST_LABELS: Record<string, string> = {
  unspecified: "Unspecified",
  hybrid_routing: "Hybrid OpenCore + Frontier API Routing",
  local: "Local desktop IDE & OpenCore Weights",
  agent: "Approval-Gated Autonomous Agents",
  team: "Team Governance & Spend Caps",
  vpc: "Dedicated Customer-Owned VPC Fleet",
};

const ROLE_LABELS: Record<string, string> = {
  unspecified: "Unspecified",
  ai_engineer: "AI / Platform Engineer",
  cto_vp: "CTO / VP of Engineering",
  security_lead: "Security & Governance Architect",
  ml_researcher: "Applied ML / OpenCore Researcher",
};

const REGION_RE = /^[A-Za-z0-9_-]{2,32}$/;
const LOCAL_PART_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$/;
const DOMAIN_LABEL_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;
const TLD_RE = /^[A-Za-z]{2,63}$/;

const rateLimitStore = new Map<string, number[]>();

function json(status: number, body: Record<string, unknown>, extraHeaders: Record<string, string> = {}) {
  return Response.json(body, {
    status,
    headers: { "cache-control": "no-store", ...extraHeaders },
  });
}

function resolveAllowedOrigins() {
  const allowed = new Set(DEFAULT_ALLOWED_ORIGINS);
  if (process.env.NODE_ENV !== "production") {
    for (const devOrigin of DEV_ALLOWED_ORIGINS) allowed.add(devOrigin);
  }
  const configured = process.env.EARLY_ACCESS_ALLOWED_ORIGINS || "";
  for (const entry of configured.split(",")) {
    const trimmed = entry.trim();
    if (!trimmed || trimmed === "*") continue;
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol === "https:" || (process.env.NODE_ENV !== "production" && parsed.protocol === "http:")) {
        allowed.add(parsed.origin);
      }
    } catch {
      // Ignore malformed origin entries cleanly
    }
  }
  return allowed;
}

function isOriginAllowed(originHeader: string | null) {
  if (!originHeader) return false;
  const trimmed = originHeader.trim();
  if (!trimmed || trimmed === "*" || trimmed === "null") return false;
  try {
    return resolveAllowedOrigins().has(new URL(trimmed).origin);
  } catch {
    return false;
  }
}

function isValidWorkEmail(email: string) {
  if (email.length < 6 || email.length > MAX_EMAIL_LENGTH) return false;
  if (/[\s\r\n\0]/.test(email) || email.includes("..")) return false;
  const atIndex = email.indexOf("@");
  if (atIndex <= 0 || atIndex !== email.lastIndexOf("@")) return false;
  const local = email.slice(0, atIndex);
  const domain = email.slice(atIndex + 1);
  if (
    !local ||
    local.length > MAX_LOCAL_PART_LENGTH ||
    local.startsWith(".") ||
    local.endsWith(".") ||
    !LOCAL_PART_RE.test(local)
  ) {
    return false;
  }
  if (!domain || domain.length > 253) return false;
  const labels = domain.split(".");
  if (labels.length < 2) return false;
  for (const label of labels) {
    if (!DOMAIN_LABEL_RE.test(label)) return false;
  }
  const tld = labels[labels.length - 1];
  return TLD_RE.test(tld);
}

function validatePrivateWebhookUrl(raw: string | undefined) {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "https:") return null;
    const host = parsed.hostname.toLowerCase();
    if (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "::1" ||
      host.endsWith(".internal") ||
      host.endsWith(".local") ||
      /^10\./.test(host) ||
      /^192\.168\./.test(host) ||
      /^169\.254\./.test(host) ||
      /^172\.(1[6-9]|2[0-9]|3[01])\./.test(host)
    ) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function resolveClientIp(request: Request) {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    const first = forwarded.split(",")[0].trim();
    if (first) return first;
  }
  return request.headers.get("x-real-ip")?.trim() || "unknown";
}

function checkRateLimit(clientKey: string, now = Date.now()) {
  const windowStart = now - RATE_LIMIT_WINDOW_MS;
  const entries = (rateLimitStore.get(clientKey) || []).filter((ts) => ts > windowStart);
  if (rateLimitStore.size >= RATE_LIMIT_MAX_KEYS && !rateLimitStore.has(clientKey)) {
    return { allowed: false, retryAfterSec: Math.ceil(RATE_LIMIT_WINDOW_MS / 1000) };
  }
  if (entries.length >= RATE_LIMIT_MAX_REQUESTS) {
    const oldest = entries[0];
    return { allowed: false, retryAfterSec: Math.max(1, Math.ceil((oldest + RATE_LIMIT_WINDOW_MS - now) / 1000)) };
  }
  entries.push(now);
  rateLimitStore.set(clientKey, entries);
  return { allowed: true, retryAfterSec: 0 };
}

export async function POST(request: Request) {
  const origin = request.headers.get("origin");
  if (!isOriginAllowed(origin)) {
    return json(403, { ok: false, error: "forbidden origin" });
  }

  const rate = checkRateLimit(resolveClientIp(request));
  if (!rate.allowed) {
    return json(429, { ok: false, error: "too many requests, please try again later" }, { "retry-after": String(rate.retryAfterSec) });
  }

  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > MAX_BODY_BYTES) {
    return json(413, { ok: false, error: "payload too large" });
  }

  let body: Record<string, unknown>;
  try {
    const text = await request.text();
    if (Buffer.byteLength(text, "utf8") > MAX_BODY_BYTES) {
      return json(413, { ok: false, error: "payload too large" });
    }
    const parsed: unknown = JSON.parse(text);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return json(400, { ok: false, error: "invalid json payload" });
    }
    body = parsed as Record<string, unknown>;
  } catch {
    return json(400, { ok: false, error: "invalid json payload" });
  }

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  const interest = typeof body.interest === "string" && body.interest.trim() ? body.interest.trim() : "unspecified";
  const role = typeof body.role === "string" && body.role.trim() ? body.role.trim() : "unspecified";
  const region = typeof body.region === "string" && body.region.trim() ? body.region.trim() : "global";

  if (!isValidWorkEmail(email)) {
    return json(400, { ok: false, error: "a valid work email is required" });
  }
  if (interest.length > MAX_FIELD_LENGTH || !Object.prototype.hasOwnProperty.call(INTEREST_LABELS, interest)) {
    return json(400, { ok: false, error: "invalid interest selection" });
  }
  if (role.length > MAX_FIELD_LENGTH || !Object.prototype.hasOwnProperty.call(ROLE_LABELS, role)) {
    return json(400, { ok: false, error: "invalid role selection" });
  }
  if (!REGION_RE.test(region)) {
    return json(400, { ok: false, error: "invalid region selection" });
  }

  const webhookUrl = validatePrivateWebhookUrl(process.env.EARLY_ACCESS_WEBHOOK_URL);
  if (!webhookUrl) {
    console.error("early-access: EARLY_ACCESS_WEBHOOK_URL is unset or invalid; failing closed");
    return json(503, { ok: false, error: "early access intake is temporarily unavailable" });
  }

  const referenceId = `KW-${randomBytes(4).toString("hex").toUpperCase()}`;
  const payloadString = JSON.stringify({
    event: "keelway.early_access.requested",
    reference_id: referenceId,
    email,
    role,
    role_label: ROLE_LABELS[role],
    interest,
    interest_label: INTEREST_LABELS[interest],
    region: region.toUpperCase(),
    submitted_at: new Date().toISOString(),
  });

  const outboundHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    "User-Agent": "keelway-early-access-intake/2.0",
  };

  const signingSecret = (process.env.EARLY_ACCESS_WEBHOOK_SECRET || "").trim();
  if (signingSecret) {
    const signature = createHmac("sha256", signingSecret).update(payloadString, "utf8").digest("hex");
    outboundHeaders["X-Keelway-Signature-256"] = `sha256=${signature}`;
  }

  try {
    const webhookRes = await fetch(webhookUrl, {
      method: "POST",
      headers: outboundHeaders,
      body: payloadString,
      redirect: "error",
      signal: AbortSignal.timeout(5000),
    });
    if (!webhookRes.ok) {
      console.error("early-access: private webhook rejected request", { referenceId, status: webhookRes.status });
      return json(502, { ok: false, error: "could not record the request, try again shortly" });
    }
    return json(200, { ok: true, referenceId });
  } catch (err) {
    console.error("early-access: private webhook request failed", {
      referenceId,
      reason: err instanceof Error ? err.name : "unknown_error",
    });
    return json(502, { ok: false, error: "could not record the request, try again shortly" });
  }
}
