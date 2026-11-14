import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { MarketplaceCatalogExplorer } from "@/components/marketplace/MarketplaceCatalogExplorer";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Marketplace · Signed AI Agents, Skills, Plugins & Workflows",
  description:
    "Explore Keelway's cryptographically signed Marketplace across 7 package categories: AI Agents, Multi-Agent Systems, Agent Skills, Plugins, Automation Workflows, Dev Tools, and Enterprise Solutions.",
  alternates: {
    canonical: "/marketplace",
  },
  openGraph: {
    title: "Keelway Marketplace · Ed25519 Signed Agents, Skills & Plugins",
    description:
      "Pre-publish security verified extensions (Risk Grade A), SHA-256 digests, Apache-2.0 / MIT open packages, and 85/15 creator revenue sharing.",
    url: `${SITE_URL}/marketplace`,
  },
};

const marketplaceJsonLd = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  name: "Keelway Sovereign AI Marketplace",
  url: `${SITE_URL}/marketplace`,
  description:
    "Ed25519-signed AI Agents, Multi-Agent Systems, Agent Skills, Plugins, KFlow Workflows, Dev Tools, and Enterprise Solutions.",
};

/**
 * Dedicated Flagship Keelway Marketplace Route (/marketplace)
 */
export default function MarketplacePage() {
  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(marketplaceJsonLd) }}
      />

      {/* Page Hero */}
      <section
        aria-labelledby="marketplace-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-12 sm:py-16"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
                <span className="chip-teal rounded-sm px-2 py-0.5">
                  VERIFIED MARKETPLACE
                </span>
                <span className="text-fg-muted">
                  7 Categories · Ed25519 Signed · 85/15 Creator Split
                </span>
              </div>

              <h1
                id="marketplace-hero-heading"
                className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
              >
                Signed AI Agents, Skills &amp;{" "}
                <span className="text-teal-accent">Governed Extensions.</span>
              </h1>

              <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
                Every <code className="font-mono text-fg">keelway.package/v1</code>{" "}
                bundle passes static prompt-injection, shell-exfiltration, and
                least-privilege scope validation before Ed25519 cryptographic signing.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/governance#manifest-drift" className="kw-btn kw-btn-primary">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                <span>Inspect Security Scanner</span>
              </Link>
              <Link href="/pricing#byom-compliance" className="kw-btn kw-btn-secondary">
                <span>85/15 Creator Economics</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Main Catalog & Security Inspector */}
      <section className="py-12 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <MarketplaceCatalogExplorer />
        </div>
      </section>
    </div>
  );
}
