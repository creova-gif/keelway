import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  FileCheck2,
  Gauge,
  LockKeyhole,
  ShieldAlert,
} from "lucide-react";
import { RoutingSimulator } from "@/components/governance/RoutingSimulator";
import { RecordTamperLab } from "@/components/governance/RecordTamperLab";
import { ManifestDriftSimulator } from "@/components/governance/ManifestDriftSimulator";
import { SelfHealingWorktreeLab } from "@/components/governance/SelfHealingWorktreeLab";
import { LatencyCostFrontierChart } from "@/components/charts/LatencyCostFrontierChart";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Hybrid Routing & Enterprise Governance",
  description:
    "Deterministic 4D AI routing, zero-egress privacy boundaries, hard USD spend ceilings, Dual-Human P-10 Quorum, and tamper-evident HMAC-SHA256 audit chains.",
  alternates: {
    canonical: "/governance",
  },
  openGraph: {
    title: "Hybrid Routing & Enterprise Governance · Keelway",
    description:
      "Simulate 4-dimension routing economics and cryptographic execution proofs under fail-closed enterprise governance.",
    url: `${SITE_URL}/governance`,
  },
};

const GOVERNANCE_INVARIANTS = [
  {
    title: "Fail-Closed Data Sovereignty",
    code: "Zero Cloud Egress",
    desc: "Regulated workloads execute exclusively on local or customer-VPC hardware unless external providers are explicitly authorized.",
    icon: LockKeyhole,
  },
  {
    title: "Predictable Unit Economics",
    code: "Hard USD Spend Ceilings",
    desc: "Per-workspace budgets enforce strict caps or automatic zero-downtime fallback to local OpenCore inference before upstream dispatch.",
    icon: Gauge,
  },
  {
    title: "Tamper-Evident Execution Ledger",
    code: "HMAC-SHA256 Hash Chain",
    desc: "Every allow, deny, and model routing decision links cryptographically to the genesis digest so any log mutation is immediately detected.",
    icon: FileCheck2,
  },
  {
    title: "Separation of Duties for High-Risk Actions",
    code: "Dual-Human P-10 Quorum",
    desc: "Production deployments and external mutations pause for independent human sign-off — initiators can never self-approve.",
    icon: ShieldAlert,
  },
];

/**
 * Hybrid Routing & Enterprise Governance (/governance)
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
              <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
                <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
                <span className="font-semibold text-fg">
                  SECURITY &amp; GOVERNANCE
                </span>
                <span className="text-fg-dim">·</span>
                <span className="text-fg-muted">
                  4D Router · Spend Caps · SOC2 / HIPAA / GDPR Ready
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
                Deterministic policy routing, hard USD spend ceilings, and
                cryptographic execution proofs built for regulated engineering
                teams.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/pricing" className="kw-btn kw-btn-primary">
                <span>Compare Deployment Tiers</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/#early-access" className="kw-btn kw-btn-secondary">
                <span>Request VPC Review</span>
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

      {/* Interactive Hash-Chained Record Tamper Lab & Manifest Drift / Marketplace Scanner */}
      <section
        id="tamper-lab"
        aria-labelledby="tamper-lab-heading"
        className="border-t border-border-subtle py-16"
      >
        <div className="mx-auto max-w-container space-y-10 px-4 sm:px-6">
          <div className="max-w-3xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              CRYPTOGRAPHIC AUDIT &amp; EXTENSION GOVERNANCE
            </p>
            <h2
              id="tamper-lab-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Verify Hash-Chain Integrity &amp; Standing-Scope Drift Live
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">
              Simulate an in-place ledger edit or prompt version drift to see
              fail-closed cryptographic verification in real time.
            </p>
          </div>

          <RecordTamperLab />
          <div id="manifest-drift">
            <ManifestDriftSimulator />
          </div>
          <div id="self-healing-worktree">
            <SelfHealingWorktreeLab />
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
              CISO &amp; ENTERPRISE GUARANTEES
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
