import React from "react";
import type { Metadata } from "next";
import { DocsHub } from "@/components/docs/DocsHub";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Developer documentation for Keelway: 5-minute quickstart, Studio & Governance surfaces, OpenCore Modelfiles, 4D routing provenance, and honest v1 capability status.",
  alternates: {
    canonical: "/docs",
  },
  openGraph: {
    title: "Developer Documentation · Keelway",
    description:
      "Get started in 5 minutes with local OpenCore weights, governed commercial APIs, and hash-chained agent execution.",
    url: `${SITE_URL}/docs`,
    type: "article",
  },
};

const techArticleJsonLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "Keelway Hybrid AI Platform Documentation",
  description:
    "Complete technical guide to Keelway Studio, Unified Responses API, OpenCore weights, 4D deterministic routing, and tenant governance.",
  author: {
    "@type": "Organization",
    name: "Keelway",
  },
  url: `${SITE_URL}/docs`,
};

/**
 * Page 6 (Stage 5a): Developer Documentation (/docs)
 * Also reached via permanent redirect from legacy `/docs.html`.
 */
export default function DocsPage() {
  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(techArticleJsonLd) }}
      />

      <section
        aria-labelledby="docs-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-12 sm:py-16"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
              <span className="chip-teal rounded-sm px-2 py-0.5">
                DEVELOPER GUIDE
              </span>
              <span className="text-fg-muted">
                v1 Architecture · Runnable Examples · Apache-2.0
              </span>
            </div>

            <h1
              id="docs-hero-heading"
              className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
            >
              Keelway Documentation
            </h1>

            <p className="mt-3 text-base leading-relaxed text-fg-muted sm:text-lg">
              How Keelway works in plain engineering terms — from a 60-second
              local clone to multi-tenant hybrid routing and cryptographic
              execution records.
            </p>
          </div>
        </div>
      </section>

      <section className="py-12 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <DocsHub />
        </div>
      </section>
    </div>
  );
}
