// Vercel serverless function: POST /api/early-access
// Routes validated early-access requests exclusively to a private HTTPS webhook
// (EARLY_ACCESS_WEBHOOK_URL). Never posts PII to public GitHub Issues.

const crypto = require('node:crypto');

const MAX_BODY_BYTES = 4096;
const MAX_EMAIL_LENGTH = 254;
const MAX_LOCAL_PART_LENGTH = 64;
const MAX_FIELD_LENGTH = 64;
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 5;
const RATE_LIMIT_MAX_KEYS = 2048;

const DEFAULT_ALLOWED_ORIGINS = [
  'https://keelway.dev',
  'https://www.keelway.dev',
  'https://kora-sable.vercel.app',
  'https://kora-eight-nu.vercel.app',
];

const DEV_ALLOWED_ORIGINS = [
  'http://localhost:3000',
  'http://127.0.0.1:3000',
];

const INTEREST_LABELS = Object.freeze({
  unspecified: 'Unspecified',
  hybrid_routing: 'Hybrid OpenCore + Frontier API Routing',
  local: 'Local desktop IDE & OpenCore Weights',
  agent: 'Approval-Gated Autonomous Agents',
  team: 'Team Governance & Spend Caps',
  vpc: 'Dedicated Customer-Owned VPC Fleet',
});

const ROLE_LABELS = Object.freeze({
  unspecified: 'Unspecified',
  ai_engineer: 'AI / Platform Engineer',
  cto_vp: 'CTO / VP of Engineering',
  security_lead: 'Security & Governance Architect',
  ml_researcher: 'Applied ML / OpenCore Researcher',
});

const REGION_RE = /^[A-Za-z0-9_-]{2,32}$/;
const LOCAL_PART_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$/;
const DOMAIN_LABEL_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/;
const TLD_RE = /^[A-Za-z]{2,63}$/;

const rateLimitStore = new Map();

function json(res, status, body, extraHeaders = {}) {
  res.status(status);
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.setHeader('cache-control', 'no-store');
  for (const [key, value] of Object.entries(extraHeaders)) {
    res.setHeader(key, value);
  }
  res.end(JSON.stringify(body));
}

function getHeader(req, name) {
  const headers = req?.headers || {};
  const lower = name.toLowerCase();
  const raw = headers[lower] ?? headers[name];
  if (Array.isArray(raw)) {
    return raw[0] || '';
  }
  return typeof raw === 'string' ? raw : '';
}

function resolveAllowedOrigins() {
  const allowed = new Set(DEFAULT_ALLOWED_ORIGINS);
  if (process.env.NODE_ENV !== 'production') {
    for (const devOrigin of DEV_ALLOWED_ORIGINS) {
      allowed.add(devOrigin);
    }
  }
  const configured = process.env.EARLY_ACCESS_ALLOWED_ORIGINS || '';
  for (const entry of configured.split(',')) {
    const trimmed = entry.trim();
    if (!trimmed || trimmed === '*') {
      continue;
    }
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol === 'https:' || (process.env.NODE_ENV !== 'production' && parsed.protocol === 'http:')) {
        allowed.add(parsed.origin);
      }
    } catch {
      // Ignore malformed origin entries cleanly
    }
  }
  return allowed;
}

function isOriginAllowed(originHeader) {
  if (!originHeader || typeof originHeader !== 'string') {
    return false;
  }
  const trimmed = originHeader.trim();
  if (!trimmed || trimmed === '*' || trimmed === 'null') {
    return false;
  }
  try {
    const parsed = new URL(trimmed);
    return resolveAllowedOrigins().has(parsed.origin);
  } catch {
    return false;
  }
}

function isValidWorkEmail(email) {
  if (typeof email !== 'string') {
    return false;
  }
  if (email.length < 6 || email.length > MAX_EMAIL_LENGTH) {
    return false;
  }
  if (/[\s\r\n\0]/.test(email) || email.includes('..')) {
    return false;
  }
  const atIndex = email.indexOf('@');
  if (atIndex <= 0 || atIndex !== email.lastIndexOf('@')) {
    return false;
  }
  const local = email.slice(0, atIndex);
  const domain = email.slice(atIndex + 1);
  if (
    !local ||
    local.length > MAX_LOCAL_PART_LENGTH ||
    local.startsWith('.') ||
    local.endsWith('.') ||
    !LOCAL_PART_RE.test(local)
  ) {
    return false;
  }
  if (!domain || domain.length > 253) {
    return false;
  }
  const labels = domain.split('.');
  if (labels.length < 2) {
    return false;
  }
  for (const label of labels) {
    if (!DOMAIN_LABEL_RE.test(label)) {
      return false;
    }
  }
  const tld = labels[labels.length - 1];
  return TLD_RE.test(tld);
}

function isForbiddenWebhookHost(hostname) {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, '');
  if (
    !host ||
    host === 'localhost' ||
    host.endsWith('.localhost') ||
    host.endsWith('.local') ||
    host === 'github.com' ||
    host === 'api.github.com' ||
    host.endsWith('.github.com') ||
    host === '0.0.0.0' ||
    host === '::1' ||
    host === '169.254.169.254' ||
    host.startsWith('127.') ||
    host.startsWith('10.') ||
    host.startsWith('192.168.') ||
    host.startsWith('169.254.') ||
    host.startsWith('fe80:') ||
    host.startsWith('fc') ||
    host.startsWith('fd')
  ) {
    return true;
  }
  const octets = host.split('.');
  if (octets.length === 4 && octets.every((part) => /^\d+$/.test(part))) {
    const first = Number(octets[0]);
    const second = Number(octets[1]);
    if (first === 172 && second >= 16 && second <= 31) {
      return true;
    }
  }
  return false;
}

function validatePrivateWebhookUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return null;
  }
  try {
    const parsed = new URL(rawUrl.trim());
    if (parsed.protocol !== 'https:') {
      return null;
    }
    if (parsed.username || parsed.password) {
      return null;
    }
    if (isForbiddenWebhookHost(parsed.hostname)) {
      return null;
    }
    if (/\/repos\/[^/]+\/[^/]+\/issues\b/i.test(parsed.pathname)) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function resolveClientIp(req) {
  const forwarded = getHeader(req, 'x-forwarded-for');
  if (forwarded) {
    const first = forwarded.split(',')[0].trim();
    if (first) {
      return first.slice(0, 64);
    }
  }
  const realIp = getHeader(req, 'x-real-ip').trim();
  if (realIp) {
    return realIp.slice(0, 64);
  }
  return String(req?.socket?.remoteAddress || 'unknown').slice(0, 64);
}

function checkRateLimit(clientKey, now = Date.now()) {
  const cutoff = now - RATE_LIMIT_WINDOW_MS;
  const existing = rateLimitStore.get(clientKey) || [];
  const active = existing.filter((ts) => ts > cutoff);

  if (active.length >= RATE_LIMIT_MAX_REQUESTS) {
    const retryAfterSec = Math.max(1, Math.ceil((active[0] + RATE_LIMIT_WINDOW_MS - now) / 1000));
    rateLimitStore.set(clientKey, active);
    return { allowed: false, retryAfterSec };
  }

  if (!rateLimitStore.has(clientKey) && rateLimitStore.size >= RATE_LIMIT_MAX_KEYS) {
    const oldestKey = rateLimitStore.keys().next().value;
    if (oldestKey !== undefined) {
      rateLimitStore.delete(oldestKey);
    }
  }

  active.push(now);
  rateLimitStore.set(clientKey, active);
  return { allowed: true, retryAfterSec: 0 };
}

async function readBoundedJsonBody(req) {
  const declaredLength = getHeader(req, 'content-length');
  if (declaredLength) {
    const parsedLen = Number(declaredLength);
    if (!Number.isFinite(parsedLen) || parsedLen < 0) {
      return { status: 400, error: 'invalid content-length header' };
    }
    if (parsedLen > MAX_BODY_BYTES) {
      return { status: 413, error: 'payload too large' };
    }
  }

  let rawText = null;
  if (typeof req?.body === 'string') {
    if (Buffer.byteLength(req.body, 'utf8') > MAX_BODY_BYTES) {
      return { status: 413, error: 'payload too large' };
    }
    rawText = req.body;
  } else if (Buffer.isBuffer(req?.body)) {
    if (req.body.length > MAX_BODY_BYTES) {
      return { status: 413, error: 'payload too large' };
    }
    rawText = req.body.toString('utf8');
  } else if (req?.body !== undefined && req?.body !== null) {
    if (typeof req.body !== 'object' || Array.isArray(req.body)) {
      return { status: 400, error: 'invalid json payload' };
    }
    const serialized = JSON.stringify(req.body);
    if (Buffer.byteLength(serialized, 'utf8') > MAX_BODY_BYTES) {
      return { status: 413, error: 'payload too large' };
    }
    return { status: 200, data: req.body };
  } else if (req && typeof req[Symbol.asyncIterator] === 'function') {
    const chunks = [];
    let totalBytes = 0;
    for await (const chunk of req) {
      const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), 'utf8');
      totalBytes += buf.length;
      if (totalBytes > MAX_BODY_BYTES) {
        return { status: 413, error: 'payload too large' };
      }
      chunks.push(buf);
    }
    rawText = Buffer.concat(chunks).toString('utf8');
  } else {
    return { status: 400, error: 'invalid json payload' };
  }

  if (!rawText || !rawText.trim()) {
    return { status: 400, error: 'invalid json payload' };
  }

  try {
    const parsed = JSON.parse(rawText);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { status: 400, error: 'invalid json payload' };
    }
    return { status: 200, data: parsed };
  } catch {
    return { status: 400, error: 'invalid json payload' };
  }
}

async function handler(req, res) {
  if (req?.method !== 'POST') {
    return json(res, 405, { ok: false, error: 'method not allowed' }, { allow: 'POST' });
  }

  const origin = getHeader(req, 'origin');
  if (!isOriginAllowed(origin)) {
    return json(res, 403, { ok: false, error: 'forbidden origin' });
  }

  const rate = checkRateLimit(resolveClientIp(req));
  if (!rate.allowed) {
    return json(
      res,
      429,
      { ok: false, error: 'too many requests, please try again later' },
      { 'retry-after': String(rate.retryAfterSec) }
    );
  }

  const parsedBody = await readBoundedJsonBody(req);
  if (parsedBody.status !== 200) {
    return json(res, parsedBody.status, { ok: false, error: parsedBody.error });
  }

  const body = parsedBody.data;
  const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
  const interest = typeof body.interest === 'string' && body.interest.trim() ? body.interest.trim() : 'unspecified';
  const role = typeof body.role === 'string' && body.role.trim() ? body.role.trim() : 'unspecified';
  const region = typeof body.region === 'string' && body.region.trim() ? body.region.trim() : 'global';

  if (!isValidWorkEmail(email)) {
    return json(res, 400, { ok: false, error: 'a valid work email is required' });
  }

  if (
    interest.length > MAX_FIELD_LENGTH ||
    !Object.prototype.hasOwnProperty.call(INTEREST_LABELS, interest)
  ) {
    return json(res, 400, { ok: false, error: 'invalid interest selection' });
  }

  if (
    role.length > MAX_FIELD_LENGTH ||
    !Object.prototype.hasOwnProperty.call(ROLE_LABELS, role)
  ) {
    return json(res, 400, { ok: false, error: 'invalid role selection' });
  }

  if (!REGION_RE.test(region)) {
    return json(res, 400, { ok: false, error: 'invalid region selection' });
  }

  const webhookUrl = validatePrivateWebhookUrl(process.env.EARLY_ACCESS_WEBHOOK_URL);
  if (!webhookUrl) {
    console.error('early-access: EARLY_ACCESS_WEBHOOK_URL is unset or invalid; failing closed');
    return json(res, 503, { ok: false, error: 'early access intake is temporarily unavailable' });
  }

  const referenceId = `KW-${crypto.randomBytes(4).toString('hex').toUpperCase()}`;
  const payloadString = JSON.stringify({
    event: 'keelway.early_access.requested',
    reference_id: referenceId,
    email,
    role,
    role_label: ROLE_LABELS[role],
    interest,
    interest_label: INTEREST_LABELS[interest],
    region: region.toUpperCase(),
    submitted_at: new Date().toISOString(),
  });

  const outboundHeaders = {
    'Content-Type': 'application/json',
    'User-Agent': 'keelway-early-access-intake/2.0',
  };

  const signingSecret = (process.env.EARLY_ACCESS_WEBHOOK_SECRET || '').trim();
  if (signingSecret) {
    const signature = crypto
      .createHmac('sha256', signingSecret)
      .update(payloadString, 'utf8')
      .digest('hex');
    outboundHeaders['X-Keelway-Signature-256'] = `sha256=${signature}`;
  }

  try {
    const webhookRes = await fetch(webhookUrl, {
      method: 'POST',
      headers: outboundHeaders,
      body: payloadString,
      redirect: 'error',
      signal: AbortSignal.timeout(5000),
    });

    if (!webhookRes.ok) {
      console.error('early-access: private webhook rejected request', {
        referenceId,
        status: webhookRes.status,
      });
      return json(res, 502, { ok: false, error: 'could not record the request, try again shortly' });
    }

    return json(res, 200, { ok: true, referenceId });
  } catch (err) {
    console.error('early-access: private webhook request failed', {
      referenceId,
      reason: err instanceof Error ? err.name : 'unknown_error',
    });
    return json(res, 502, { ok: false, error: 'could not record the request, try again shortly' });
  }
}

handler.MAX_BODY_BYTES = MAX_BODY_BYTES;
handler.isValidWorkEmail = isValidWorkEmail;
handler.isOriginAllowed = isOriginAllowed;
handler.validatePrivateWebhookUrl = validatePrivateWebhookUrl;
handler._resetRateLimitForTests = () => rateLimitStore.clear();

module.exports = handler;
