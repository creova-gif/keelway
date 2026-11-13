import { NextRequest, NextResponse } from "next/server";

const REPO_OWNER = "creova-gif";
const REPO_NAME = "kora";
const LABEL = "early-access";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const INTEREST_LABELS: Record<string, string> = {
  hybrid_routing: "Hybrid OpenCore + Frontier API Routing",
  local: "Local desktop IDE & OpenCore Weights",
  agent: "Approval-Gated Autonomous Agents",
  team: "Team Governance & Spend Caps",
  vpc: "Dedicated Customer-Owned VPC Fleet",
};

const ROLE_LABELS: Record<string, string> = {
  ai_engineer: "AI / Platform Engineer",
  cto_vp: "CTO / VP of Engineering",
  security_lead: "Security & Governance Architect",
  ml_researcher: "Applied ML / OpenCore Researcher",
};

/**
 * POST /api/early-access
 * Preserves full GitHub Issue intake compatibility from legacy api/early-access.js
 * while recording upgraded Dual-Track fields (role, interest, residency region).
 */
export async function POST(req: NextRequest) {
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

  if (!EMAIL_RE.test(email)) {
    return NextResponse.json(
      { ok: false, error: "A valid work email is required." },
      { status: 400 }
    );
  }

  const token = process.env.EARLY_ACCESS_GH_TOKEN;
  if (!token) {
    if (process.env.NODE_ENV !== "production") {
      return NextResponse.json(
        { ok: true, preview: true },
        { status: 200 }
      );
    }
    console.error("early-access: EARLY_ACCESS_GH_TOKEN is not set");
    return NextResponse.json(
      { ok: false, error: "Signup intake is not configured yet." },
      { status: 500 }
    );
  }

  const issueBody = [
    `**Email:** ${email}`,
    `**Role:** ${ROLE_LABELS[role] || role}`,
    `**Primary workload:** ${INTEREST_LABELS[interest] || interest}`,
    `**Deployment region:** ${region.toUpperCase()}`,
    `**Submitted:** ${new Date().toISOString()}`,
    "",
    "_Filed automatically from the Keelway Hybrid AI Platform Early Access intake._",
  ].join("\n");

  try {
    const ghRes = await fetch(
      `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/issues`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "keelway-early-access-intake",
        },
        body: JSON.stringify({
          title: `Early access: ${email} (${region.toUpperCase()})`,
          body: issueBody,
          labels: [LABEL],
        }),
      }
    );

    if (!ghRes.ok) {
      const detail = await ghRes.text();
      console.error("early-access: GitHub API error", ghRes.status, detail);
      return NextResponse.json(
        {
          ok: false,
          error: "Could not record the request, please try again shortly.",
        },
        { status: 502 }
      );
    }

    return NextResponse.json({ ok: true }, { status: 200 });
  } catch (err) {
    console.error("early-access: request failed", err);
    return NextResponse.json(
      {
        ok: false,
        error: "Could not record the request, please try again shortly.",
      },
      { status: 502 }
    );
  }
}
