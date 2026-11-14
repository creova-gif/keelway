import { NextRequest, NextResponse } from "next/server";

const LABEL = "early-access";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const INTEREST_LABELS: Record<string, string> = {
  nocode_automation: "No-Code App & Business Workflow Automation",
  hybrid_routing: "Hybrid OpenCore + Frontier API Routing",
  local: "Local Desktop IDE & OpenCore Weights",
  agent: "Approval-Gated Autonomous Agent Teams",
  team: "Team Workspace, Linear-Style PM & Spend Caps",
  marketplace_publish: "Publishing Marketplace Agents, Skills & Plugins",
  vpc: "Dedicated Enterprise VPC / Air-Gapped Deployment",
};

const ROLE_LABELS: Record<string, string> = {
  founder_ops: "Founder / Product or Operations Builder",
  ai_engineer: "Software / AI Engineer",
  cto_vp: "CTO / VP of Engineering",
  security_lead: "Security, Risk & Governance Architect",
  creator_partner: "Marketplace Creator / Solution Partner",
  ml_researcher: "Applied ML Researcher",
};

// Lightweight per-instance IP rate limiter (15 submissions / 10 minutes)
const rateBuckets = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const existing = rateBuckets.get(ip);
  if (!existing || existing.resetAt <= now) {
    rateBuckets.set(ip, { count: 1, resetAt: now + 10 * 60 * 1000 });
    return true;
  }
  if (existing.count >= 15) {
    return false;
  }
  existing.count += 1;
  return true;
}

/**
 * POST /api/early-access
 * Validates customer & enterprise onboarding requests across all user journeys.
 * Forwards to optional configured intake repository/webhook when present, and
 * always returns a clean confirmation reference ID without leaking internal names.
 */
export async function POST(req: NextRequest) {
  const forwarded = req.headers.get("x-forwarded-for") || "local";
  const clientIp = forwarded.split(",")[0]?.trim() || "local";

  if (!checkRateLimit(clientIp)) {
    return NextResponse.json(
      {
        ok: false,
        error: "Too many requests from this network. Please wait a few minutes and try again.",
      },
      { status: 429 }
    );
  }

  let body: Record<string, unknown> = {};
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }

  const email = typeof body.email === "string" ? body.email.trim() : "";
  const interest =
    typeof body.interest === "string" ? body.interest.trim() : "unspecified";
  const role = typeof body.role === "string" ? body.role.trim() : "unspecified";
  const region =
    typeof body.region === "string" ? body.region.trim() : "global";

  if (!EMAIL_RE.test(email) || email.length > 254) {
    return NextResponse.json(
      { ok: false, error: "Please enter a valid work or team email address." },
      { status: 400 }
    );
  }

  const referenceId = `KW-${Date.now().toString(36).toUpperCase().slice(-6)}`;
  const token = process.env.EARLY_ACCESS_GH_TOKEN;
  const repoSlug = process.env.EARLY_ACCESS_GH_REPO;

  if (token && repoSlug && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repoSlug)) {
    const issueBody = [
      `**Reference:** ${referenceId}`,
      `**Email:** ${email}`,
      `**Role:** ${ROLE_LABELS[role] || role}`,
      `**Primary journey:** ${INTEREST_LABELS[interest] || interest}`,
      `**Deployment region:** ${region.toUpperCase()}`,
      `**Submitted:** ${new Date().toISOString()}`,
    ].join("\n");

    try {
      const ghRes = await fetch(
        `https://api.github.com/repos/${repoSlug}/issues`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "keelway-onboarding-intake",
          },
          body: JSON.stringify({
            title: `Onboarding (${referenceId}): ${region.toUpperCase()} · ${ROLE_LABELS[role] || role}`,
            body: issueBody,
            labels: [LABEL],
          }),
        }
      );

      if (!ghRes.ok) {
        console.warn("early-access: upstream sync returned", ghRes.status);
      }
    } catch (err) {
      console.warn("early-access: upstream sync skipped", err);
    }
  } else {
    console.info(
      JSON.stringify({
        event: "keelway_onboarding_request",
        referenceId,
        role: ROLE_LABELS[role] || role,
        interest: INTEREST_LABELS[interest] || interest,
        region: region.toUpperCase(),
        submittedAt: new Date().toISOString(),
      })
    );
  }

  return NextResponse.json(
    { ok: true, referenceId },
    { status: 200 }
  );
}
