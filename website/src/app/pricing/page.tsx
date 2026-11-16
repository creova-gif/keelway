import React from "react";
import type { Metadata } from "next";
import { PricingTiers } from "@/components/pricing/PricingTiers";
import { PRICING_FAQS } from "@/data/pricing";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Pricing, BYOM & Marketplace Tiers",
  description:
    "Transparent pricing for Keelway: $0 Free/Community OpenCore, $15/mo 0%-markup BYOM API routing (500K tok/day fallback), $29/mo Keelway Pro (2.5M tok/day + BYOM), Enterprise Sovereign VPC, and 85/15 Creator Marketplace.",
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: "Pricing, BYOM & Creator Marketplace · Keelway",
    description:
      "Start free locally under Apache-2.0, route cloud APIs at $15/mo with 0% token markup, or scale to $29/mo Keelway Pro, Enterprise Sovereign VPCs, and verified Marketplace extensions.",
    url: `${SITE_URL}/pricing`,
  },
};

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: PRICING_FAQS.map((item) => ({
    "@type": "Question",
    name: item.q,
    acceptedAnswer: {
      "@type": "Answer",
      text: item.a,
    },
  })),
};

/**
 * Page 4: Pricing, 0%-Markup BYOM & Deployment Tiers (/pricing)
 */
export default function PricingPage() {
  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      {/* Page Hero */}
      <section
        aria-labelledby="pricing-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="max-w-3xl">
            <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
              <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
              <span className="font-semibold text-fg">
                ZERO TOKEN TAX
              </span>
              <span className="text-fg-dim">·</span>
              <span className="text-fg-muted">
                $0 OpenCore · $15/mo BYOM (0% Markup) · $29/mo Pro · Sovereign
                VPC
              </span>
            </div>

            <h1
              id="pricing-hero-heading"
              className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
            >
              Free on Your Hardware.{" "}
              <span className="text-teal-accent">Zero Proxy Markup</span> in the
              Cloud.
            </h1>

            <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
              Run Keelway locally forever under{" "}
              <code className="font-mono text-sm text-fg">Apache-2.0</code>,
              connect authorized frontier API keys at{" "}
              <strong className="font-semibold text-fg">$15/seat/mo</strong>{" "}
              with <code className="font-mono text-sm text-fg">0%</code> token
              markup, or unlock the full 12-agent stack and{" "}
              <code className="font-mono text-sm text-fg">2.5M tok/day</code>{" "}
              open-weight pool on{" "}
              <strong className="font-semibold text-fg">
                Keelway Pro ($29/mo)
              </strong>
              .
            </p>
          </div>
        </div>
      </section>

      {/* Main Pricing Interactive Content */}
      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <PricingTiers />
        </div>
      </section>
    </div>
  );
}
