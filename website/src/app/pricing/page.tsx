import React from "react";
import type { Metadata } from "next";
import { PricingTiers } from "@/components/pricing/PricingTiers";
import { PRICING_FAQS } from "@/data/pricing";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Pricing & Deployment Tiers",
  description:
    "Transparent pricing for Keelway: $0 forever Apache-2.0 OpenCore Local, 0%-markup BYOK Team Hybrid Cloud, and dedicated Enterprise Sovereign VPC fleets.",
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: "Pricing & Sovereign Deployment Tiers · Keelway",
    description:
      "Start free locally under Apache-2.0 or scale to Team Hybrid Cloud and Enterprise Sovereign VPCs with 0% commercial token markup.",
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
 * Page 4 (Stage 4a): Pricing & Deployment Tiers (/pricing)
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
            <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
              <span className="chip-teal rounded-sm px-2 py-0.5">
                ZERO TOKEN TAX
              </span>
              <span className="text-fg-muted">
                Apache-2.0 OpenCore · BYOK Cloud Routing · Dedicated Sovereign
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
              <code className="font-mono text-sm text-fg">Apache-2.0</code>, or
              add multi-tenant governance, hosted workspace sync, and dedicated
              regional GPU runners as your engineering organization grows.
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
