import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, Building2, Fingerprint, ShieldCheck, Workflow } from "lucide-react";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Enterprise — VPC & Air-Gapped Deployments",
  description:
    "Keelway Enterprise: sovereign VPC and air-gapped deployment, SCIM 2.0 provisioning, dual-human P-10 quorum, SIEM audit export, and design-partner onboarding.",
  alternates: { canonical: "/enterprise" },
  openGraph: {
    title: "Keelway Enterprise · Sorvex Labs",
    description:
      "Sovereign VPC and air-gapped agent orchestration with dual-human P-10 quorum and SIEM audit export.",
    url: `${SITE_URL}/enterprise`,
  },
};

const PILLARS = [
  {
    icon: Building2,
    title: "Sovereign Deployment",
    body: "Air-gapped AWS, GCP, and on-prem topologies. Local Ollama or private vLLM/TGI clusters for open-weight inference; frontier APIs behind the same deterministic routing policy — or fully disabled.",
  },
  {
    icon: Fingerprint,
    title: "Identity & Provisioning",
    body: "OIDC sign-in (self-issued HS256 token profile for sovereign deployments) and SCIM 2.0 directory provisioning into least-privilege RBAC roles. External IdP JWKS federation and SAML are on the roadmap — scoped honestly.",
  },
  {
    icon: ShieldCheck,
    title: "Governance & Audit",
    body: "P-10 human-only gates and 2-of-2 dual-human quorum on high-impact actions. SHA-256 hash-chained audit ledger streaming to SIEM via OCSF, CEF, or JSONL — with automatic DLP secret redaction.",
  },
  {
    icon: Workflow,
    title: "Controlled Orchestration",
    body: "KFlow deterministic DAGs with per-run token budgets, hard USD spend ceilings with local fallback, and marketplace packages gated by Ed25519 signing plus deterministic pre-publish scanning.",
  },
] as const;

/**
 * Enterprise (/enterprise) — deployment models, identity, governance, procurement.
 */
export default function EnterprisePage() {
  return (
    <div>
      <section
        aria-labelledby="enterprise-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
            <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
            <span className="font-semibold text-fg">KEELWAY ENTERPRISE</span>
            <span className="text-fg-dim">·</span>
            <span className="text-fg-muted">VPC &amp; air-gapped</span>
          </div>
          <h1
            id="enterprise-heading"
            className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
          >
            Agentic engineering inside
            <br className="hidden sm:block" /> <span className="text-teal-accent">your trust boundary</span>.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-fg-muted sm:text-lg">
            Keelway runs where your code already lives — developer laptops,
            a private VPC, or a fully air-gapped enclave — with the same
            fail-closed governance and cryptographic audit in every topology.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/contact" className="kw-btn kw-btn-primary">
              Request enterprise review
            </Link>
            <Link href="/governance" className="kw-btn kw-btn-secondary">
              Governance deep-dive
            </Link>
          </div>
        </div>
      </section>

      <section className="py-14 sm:py-16">
        <div className="mx-auto grid max-w-container grid-cols-1 gap-5 px-4 sm:px-6 md:grid-cols-2">
          {PILLARS.map((p) => (
            <article
              key={p.title}
              className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-7"
            >
              <p.icon className="h-5 w-5 text-teal-accent" aria-hidden="true" />
              <h2 className="mt-3 text-lg font-bold text-fg">{p.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">{p.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-t border-border-subtle py-14 sm:py-16">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <h2 className="text-2xl font-bold text-fg">How enterprise onboarding works</h2>
          <ol className="mt-5 space-y-4">
            {[
              "Request a review — tell us your topology (VPC region, air-gap requirements, identity provider).",
              "Design-partner architecture session — we map residency zones, routing policy, and P-10 gate scope against your environment.",
              "Scoped deployment — deterministic installer or hardened container into your VPC, with SBOM attestation and SIEM wiring verified in-session.",
              "Production handover — audit-ledger verification walkthrough and operations runbook for your team.",
            ].map((step, i) => (
              <li key={step} className="flex items-start gap-3 text-sm leading-relaxed text-fg-muted">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm border border-teal-accent bg-teal-surface font-mono text-[11px] font-bold text-teal-accent">
                  {i + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <div className="mt-6 rounded-md border border-border-subtle bg-canvas p-5 font-mono text-xs text-fg-muted">
            <Link
              href="/contact"
              className="inline-flex items-center gap-1 text-teal-accent hover:underline"
            >
              <span>Start the enterprise review</span>
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
