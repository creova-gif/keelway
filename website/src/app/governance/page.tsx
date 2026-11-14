import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  FileCheck2,
  Gauge,
  LockKeyhole,
  ServerCrash,
} from "lucide-react";
import { RoutingSimulator } from "@/components/governance/RoutingSimulator";
import { GovernanceGuardrailsLab } from "@/components/governance/GovernanceGuardrailsLab";
import { RecordTamperLab } from "@/components/governance/RecordTamperLab";
import { ManifestDriftSimulator } from "@/components/governance/ManifestDriftSimulator";
import { LatencyCostFrontierChart } from "@/components/charts/LatencyCostFrontierChart";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Hybrid Routing & Enterprise Governance",
  description:
    "Deterministic 4D AI routing, zero-egress privacy boundaries, scoped kw_live_* tenant keys, hard USD spend caps, and tamper-evident SHA-256 audit chains.",
  alternates: {
    canonical: "/governance",
  },
  openGraph: {
    title: "Hybrid Routing & Enterprise Governance · Keelway",
    description:
      "Simulate 4-dimension routing provenance and monthly OpenCore vs. Frontier cost savings under fail-closed tenant governance.",
    url: `${SITE_URL}/governance`,
  },
};

const GOVERNANCE_INVARIANTS = [
  {
    title: "Fail-Closed Tenant Isolation",
    code: "allowed_providers=['local']",
    desc: "New regulated tenants default to sovereign local execution. External commercial APIs cannot be invoked unless explicitly allowlisted in TenantPolicy.",
    icon: LockKeyhole,
  },
  {
    title: "Dual-Axis Rate & Token Quotas",
    code: "RPM + TPM Sliding Window",
    desc: "Per-tenant requests-per-minute and tokens-per-minute ceilings prevent noisy-neighbor saturation and runaway agent loops before upstream dispatch.",
    icon: Gauge,
  },
  {
    title: "Graceful Budget Saturation",
    code: "HTTP 402 | OpenCore Fallback",
    desc: "Choose hard HTTP 402 enforcement for strict cost centers, or automatic zero-downtime downgrade to local keelway-core:7b when monthly cloud budgets hit 100%.",
    icon: ServerCrash,
  },
  {
    title: "Genesis-Anchored Hash Ledger",
    code: "GET /v1/governance/audit/verify",
    desc: "Every allow, deny, and budget downgrade links cryptographically to the previous event digest from 0000...0000, making silent log deletion mathematically detectable.",
    icon: FileCheck2,
  },
];

/**
 * Page 3 (Stage 3): Hybrid Routing & Security/Governance (/governance)
 */
export default function GovernancePage() {
  return (
    <div>
      {/* Page Hero */}
      <section
        aria-labelledby="gov-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
                <span className="chip-teal rounded-sm px-2 py-0.5">
                  LAYERS 5 &amp; 6
                </span>
                <span className="text-fg-muted">
                  Deterministic 4D Router · Multi-Tenant Spend &amp; Residency
                  Governance
                </span>
              </div>

              <h1
                id="gov-hero-heading"
                className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
              >
                Never Silently Route Private Data to an{" "}
                <span className="text-teal-accent">Unauthorized Cloud.</span>
              </h1>

              <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
                Keelway replaces opaque black-box routers with deterministic
                policy evaluation, pre-egress credential scrubbing, per-tenant
                USD spend ceilings, and hash-chained execution proofs.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/pricing" className="kw-btn kw-btn-primary">
                <span>Compare Deployment Tiers</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/#early-access" className="kw-btn kw-btn-secondary">
                <span>Request VPC Architecture Review</span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Main Simulator + Empirical Pareto Frontier Section */}
      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-container space-y-12 px-4 sm:px-6">
          <RoutingSimulator />
          <LatencyCostFrontierChart compact />
        </div>
      </section>

      {/* Interactive Security & Redaction Sandbox */}
      <section
        aria-labelledby="guardrails-heading"
        className="border-t border-border-subtle bg-surface/35 py-16"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="mb-8 max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              LIVE SECURITY &amp; CREDENTIAL HYGIENE LAB
            </p>
            <h2
              id="guardrails-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Test Pre-Egress Secret Redaction &amp; Scoped Tenant Keys
            </h2>
          </div>

          <GovernanceGuardrailsLab />
        </div>
      </section>

      {/* Interactive Hash-Chained Record Tamper Lab & Manifest Drift / Marketplace Scanner */}
      <section
        id="tamper-lab"
        aria-labelledby="tamper-lab-heading"
        className="border-t border-border-subtle py-16"
      >
        <div className="mx-auto max-w-container space-y-10 px-4 sm:px-6">
          <div className="max-w-3xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              CRYPTOGRAPHIC AUDIT &amp; EXTENSION GOVERNANCE LABS
            </p>
            <h2
              id="tamper-lab-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Prove Ledger Tamper-Evidence, Prompt Drift Freeze &amp; Marketplace Safety
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              Mutate row <code>#1279</code> in-place to inspect real-time SHA-256 chain
              breaks, trigger standing-scope drift pauses on <code>p-13 → p-14</code>, and
              test pre-publication Marketplace extension validation.
            </p>
          </div>

          <RecordTamperLab />
          <div id="manifest-drift">
            <ManifestDriftSimulator />
          </div>
        </div>
      </section>

      {/* 4 Core Governance Invariants */}
      <section
        aria-labelledby="invariants-heading"
        className="border-t border-border-subtle py-16 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              PRODUCTION SECURITY POSTURE
            </p>
            <h2
              id="invariants-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Four non-negotiable platform invariants
            </h2>
          </div>

          <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2">
            {GOVERNANCE_INVARIANTS.map((item) => {
              const Icon = item.icon;
              return (
                <article
                  key={item.title}
                  className="rounded-lg border border-border-strong bg-surface p-6"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <code className="rounded-sm border border-border-subtle bg-canvas px-2.5 py-1 font-mono text-xs text-teal-accent">
                      {item.code}
                    </code>
                  </div>
                  <h3 className="mt-4 text-lg font-bold text-fg">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                    {item.desc}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}
