import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "About Sorvex Labs",
  description:
    "Sorvex Labs builds Keelway — the sovereign AI platform for governed agentic software engineering: local-first inference, deterministic routing, and cryptographic audit.",
  alternates: { canonical: "/about" },
  openGraph: {
    title: "About Sorvex Labs · Keelway",
    description:
      "Sorvex Labs builds Keelway — sovereign, governed AI software engineering.",
    url: `${SITE_URL}/about`,
  },
};

/**
 * About Sorvex Labs (/about) — company and product positioning.
 */
export default function AboutPage() {
  return (
    <div>
      <section
        aria-labelledby="about-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
            <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
            <span className="font-semibold text-fg">SORVEX LABS</span>
            <span className="text-fg-dim">·</span>
            <span className="text-fg-muted">Makers of Keelway</span>
          </div>
          <h1
            id="about-heading"
            className="kw-display mt-4 text-fg"
          >
            Software engineering sovereignty,
            <br className="hidden sm:block" /> by <span className="text-teal-accent">Sorvex Labs</span>.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-fg-muted sm:text-lg">
            Sorvex Labs is the company behind Keelway — an open-core platform
            that lets engineering teams run AI agents on their own terms:
            open-weight models locally, frontier APIs under deterministic
            governance, and a cryptographic receipt for every action.
          </p>
        </div>
      </section>

      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-3xl space-y-10 px-4 sm:px-6">
          <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-8">
            <h2 className="text-xl font-bold text-fg">What we believe</h2>
            <ul className="mt-4 space-y-3">
              {[
                "Agentic engineering should not require surrendering your code, prompts, or spend to a third-party cloud.",
                "Governance must be deterministic and enforced in the runtime — not a policy document attached after the fact.",
                "Every agent action deserves a verifiable receipt. Hash-chained audit is infrastructure, not a feature tier.",
                "Open weights and frontier APIs are complements. A routing layer with hard spend ceilings and local fallback should decide — not a vendor lock-in.",
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm leading-relaxed text-fg-muted">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-accent" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-8">
            <h2 className="text-xl font-bold text-fg">What we ship</h2>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              Keelway is a unified sovereign agent IDE and control plane:
              a local-first runtime, deterministic 4D routing across
              open-weight and frontier models, KFlow orchestration,
              marketplace-verified skills, and P-10 human approval gates —
              licensed <strong className="text-fg">Apache-2.0</strong> at the
              core, with enterprise deployment options on top.
            </p>
            <div className="mt-5 flex flex-wrap gap-3 font-mono text-xs">
              <Link href="/" className="kw-btn kw-btn-secondary">Platform overview</Link>
              <Link href="/governance" className="kw-btn kw-btn-secondary">Security &amp; governance</Link>
              <Link href="/changelog" className="kw-btn kw-btn-secondary">Changelog</Link>
            </div>
          </div>

          <div className="rounded-md border border-border-subtle bg-canvas p-5 font-mono text-xs text-fg-muted">
            <p>
              Enterprise, VPC, and air-gapped deployments are onboarded through
              a design-partner review.{" "}
              <Link
                href="/contact"
                className="inline-flex items-center gap-1 text-teal-accent hover:underline"
              >
                <span>Contact Sorvex Labs</span>
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
