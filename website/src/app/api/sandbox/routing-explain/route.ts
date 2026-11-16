import crypto from "crypto";
import { NextRequest, NextResponse } from "next/server";

/**
 * Rate-Limited Live Read-Only Sandbox Endpoint (`POST /api/sandbox/routing-explain`).
 * OpenRouter-style network playground allowing visitors on `/` and `/api-reference`
 * to execute real HTTP routing & secret-redaction explain calls without exposing
 * upstream cloud credentials.
 */

const WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 30;
const ipBuckets = new Map<string, number[]>();

function checkRateLimit(ip: string): { allowed: boolean; remaining: number } {
  const now = Date.now();
  const recent = (ipBuckets.get(ip) ?? []).filter((ts) => now - ts < WINDOW_MS);
  if (recent.length >= MAX_REQUESTS_PER_WINDOW) {
    ipBuckets.set(ip, recent);
    return { allowed: false, remaining: 0 };
  }
  recent.push(now);
  ipBuckets.set(ip, recent);
  return {
    allowed: true,
    remaining: Math.max(0, MAX_REQUESTS_PER_WINDOW - recent.length),
  };
}

const SECRET_PATTERNS: { regex: RegExp; replacement: string }[] = [
  { regex: /\bsk-[A-Za-z0-9_-]{12,}\b/g, replacement: "[REDACTED_OPENAI_KEY]" },
  { regex: /\bAIza[0-9A-Za-z_-]{16,}\b/g, replacement: "[REDACTED_GEMINI_KEY]" },
  { regex: /\bkw_live_[A-Za-z0-9_]{8,}\b/g, replacement: "[REDACTED_KEELWAY_KEY]" },
  {
    regex: /\bBearer\s+[A-Za-z0-9._-]{14,}\b/gi,
    replacement: "Bearer [REDACTED_TOKEN]",
  },
  {
    regex: /\b(?:postgres|postgresql|redis|mongodb(?:\+srv)?):\/\/[^\s"']+/gi,
    replacement: "[REDACTED_DATABASE_DSN]",
  },
  {
    regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
    replacement: "[REDACTED_EMAIL]",
  },
];

function scrubSecrets(raw: string): { scrubbed: string; count: number } {
  let scrubbed = raw;
  let count = 0;
  for (const { regex, replacement } of SECRET_PATTERNS) {
    scrubbed = scrubbed.replace(regex, () => {
      count += 1;
      return replacement;
    });
  }
  return { scrubbed, count };
}

export interface SandboxExplainRequest {
  prompt?: string;
  privacy_level?: "standard" | "private";
  residency_zone?: "global" | "africa_sovereign" | "eu_sovereign" | "local_only";
  required_capabilities?: string[];
  max_cost_usd?: number;
}

export async function POST(req: NextRequest) {
  const t0 = performance.now();
  const forwarded = req.headers.get("x-forwarded-for");
  const clientIp = forwarded?.split(",")[0]?.trim() || "127.0.0.1";

  const rl = checkRateLimit(clientIp);
  if (!rl.allowed) {
    return NextResponse.json(
      {
        error: "sandbox_rate_limit_exceeded",
        message:
          "Rate limit exceeded (30 live sandbox calls per 60s). Run `python3 cli.py serve` locally for unlimited zero-cost routing.",
      },
      {
        status: 429,
        headers: {
          "X-RateLimit-Limit": String(MAX_REQUESTS_PER_WINDOW),
          "X-RateLimit-Remaining": "0",
          "Retry-After": "60",
        },
      }
    );
  }

  let body: SandboxExplainRequest = {};
  try {
    body = (await req.json()) as SandboxExplainRequest;
  } catch {
    return NextResponse.json(
      { error: "invalid_json", message: "Request body must be valid JSON." },
      { status: 400 }
    );
  }

  const rawPrompt = String(
    body.prompt ??
      "Audit src/billing/retry.py for discount rounding bugs without leaking sk-proj-918273645abcde."
  ).slice(0, 2000);

  const privacy = body.privacy_level === "private" ? "private" : "standard";
  const residency = body.residency_zone ?? "global";
  const caps = Array.isArray(body.required_capabilities)
    ? body.required_capabilities.slice(0, 8)
    : ["code"];
  const maxCostUsd =
    typeof body.max_cost_usd === "number" ? body.max_cost_usd : 0.005;

  const { scrubbed, count: redactedCount } = scrubSecrets(rawPrompt);

  // Optional fast live proxy if an upstream Keelway FastAPI daemon is configured
  const upstreamUrl = process.env.KEELWAY_BACKEND_URL;
  if (upstreamUrl) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 600);
      const upstreamRes = await fetch(
        `${upstreamUrl.replace(/\/$/, "")}/v1/routing/explain`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: scrubbed,
            privacy_level: privacy,
            residency_zone: residency,
            required_capabilities: caps,
          }),
          signal: ctrl.signal,
        }
      );
      clearTimeout(timer);
      if (upstreamRes.ok) {
        const upstreamData = (await upstreamRes.json()) as Record<
          string,
          unknown
        >;
        const computeMs = (performance.now() - t0).toFixed(2);
        return NextResponse.json(
          {
            ...upstreamData,
            sandbox_mode: "proxied_fastapi_daemon",
            redacted_prompt_preview: scrubbed,
            redacted_tokens_count: redactedCount,
          },
          {
            status: 200,
            headers: {
              "X-RateLimit-Limit": String(MAX_REQUESTS_PER_WINDOW),
              "X-RateLimit-Remaining": String(rl.remaining),
              "X-Keelway-Sandbox-Mode": "proxied-fastapi",
              "X-Keelway-Compute-Ms": computeMs,
            },
          }
        );
      }
    } catch {
      // Fall through cleanly to deterministic edge control-plane evaluator
    }
  }

  // Deterministic 4D Routing Policy Evaluation matching `core/api/responses_routes.py`
  const forceSovereignLocal =
    privacy === "private" ||
    residency === "local_only" ||
    residency === "africa_sovereign" ||
    maxCostUsd <= 0;

  let selectedModel = "keelway-core:7b";
  let category: "open_weight" | "frontier" = "open_weight";
  let license = "Apache-2.0";
  let hostingTopology = "local_loopback_or_sovereign_vpc";
  let operatorControl = "tenant_owned_weights";
  let dataBoundary = "zero_external_egress";
  let estimatedCostUsd = 0.0;
  let fallbackChain = ["keelway-nano:1.5b"];
  const policyTrace: string[] = [];

  if (forceSovereignLocal) {
    policyTrace.push(
      privacy === "private"
        ? "privacy_level='private' -> blocked all external commercial providers (fail-closed)."
        : `residency_zone='${residency}' -> enforced sovereign open-weight execution.`
    );
    if (caps.includes("reasoning") && rawPrompt.length > 140) {
      selectedModel = "keelway-reasoning:14b";
      fallbackChain = ["keelway-core:7b", "keelway-nano:1.5b"];
      policyTrace.push(
        "capability='reasoning' -> selected keelway-reasoning:14b (Apache-2.0)."
      );
    } else if (caps.includes("code") || /def |src\/|\.py|bug|audit/i.test(rawPrompt)) {
      selectedModel = "keelway-coder:7b";
      fallbackChain = ["keelway-core:7b", "keelway-nano:1.5b"];
      policyTrace.push(
        "code/AST workload detected -> selected keelway-coder:7b ($0.00 local Metal/vLLM)."
      );
    } else {
      selectedModel = "keelway-core:7b";
      policyTrace.push(
        "default sovereign route -> selected keelway-core:7b ($0.00 local Metal/vLLM)."
      );
    }
  } else {
    // Hybrid Arbitrage mode (`standard` privacy + global/eu residency)
    if (caps.includes("vision") || rawPrompt.length > 500) {
      selectedModel = "gemini-3.5-flash";
      category = "frontier";
      license = "Commercial Cloud API (Google)";
      hostingTopology = "managed_cloud_tls";
      operatorControl = "tenant_opt_in_byok";
      dataBoundary = "redacted_tls_egress";
      estimatedCostUsd = 0.00052;
      fallbackChain = ["gemini-3.5-flash-lite", "keelway-core:7b"];
      policyTrace.push(
        "multimodal / long-context escalation -> selected gemini-3.5-flash after pre-egress redaction."
      );
    } else if (caps.includes("reasoning")) {
      selectedModel = "gemini-3.5-flash-lite";
      category = "frontier";
      license = "Commercial Cloud API (Google)";
      hostingTopology = "managed_cloud_tls";
      operatorControl = "tenant_opt_in_byok";
      dataBoundary = "redacted_tls_egress";
      estimatedCostUsd = 0.00016;
      fallbackChain = ["keelway-reasoning:14b", "keelway-core:7b"];
      policyTrace.push(
        "hybrid arbitrage -> selected low-cost frontier judge gemini-3.5-flash-lite ($0.16/1M) with OpenCore fallback."
      );
    } else {
      selectedModel = "keelway-coder:7b";
      category = "open_weight";
      estimatedCostUsd = 0.0;
      fallbackChain = ["gemini-3.5-flash-lite", "keelway-nano:1.5b"];
      policyTrace.push(
        "cost-optimal hybrid route -> kept routine code/tool task on $0.00 OpenCore keelway-coder:7b."
      );
    }
  }

  if (redactedCount > 0) {
    policyTrace.unshift(
      `pre_egress_scrubber -> redacted ${redactedCount} sensitive credential/PII token(s).`
    );
  }

  const receiptPayload = JSON.stringify({
    selectedModel,
    privacy,
    residency,
    redactedCount,
    scrubbedLen: scrubbed.length,
  });
  const decisionDigest = crypto
    .createHash("sha256")
    .update(receiptPayload)
    .digest("hex");

  const computeMs = (performance.now() - t0).toFixed(2);

  return NextResponse.json(
    {
      object: "routing.explanation",
      sandbox_mode: "edge_deterministic_evaluator",
      selected_model: selectedModel,
      category,
      estimated_cost_usd: estimatedCostUsd,
      redacted_tokens_count: redactedCount,
      redacted_prompt_preview: scrubbed,
      fallback_chain: fallbackChain,
      provenance: {
        model_license: license,
        hosting_topology: hostingTopology,
        operator_control: operatorControl,
        data_boundary: dataBoundary,
      },
      policy_trace: policyTrace,
      audit_receipt_sha256: `sha256:${decisionDigest.slice(0, 32)}`,
    },
    {
      status: 200,
      headers: {
        "X-RateLimit-Limit": String(MAX_REQUESTS_PER_WINDOW),
        "X-RateLimit-Remaining": String(rl.remaining),
        "X-Keelway-Sandbox-Mode": "edge-deterministic",
        "X-Keelway-Compute-Ms": computeMs,
      },
    }
  );
}
