import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ModelExplorer } from "@/components/models/ModelExplorer";
import { SpeculativeDecodingLab } from "@/components/models/SpeculativeDecodingLab";
import { LatencyCostFrontierChart } from "@/components/charts/LatencyCostFrontierChart";
import { CATALOG_MODELS } from "@/data/models";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Models & Hybrid Economics",
  description:
    "Hybrid AI unit economics: $0 local OpenCore inference on developer or VPC hardware (0% token COGS) plus zero-markup BYOM bursting to Frontier APIs.",
  alternates: {
    canonical: "/models",
  },
  openGraph: {
    title: "Models & Hybrid Economics · Keelway",
    description:
      "$0 local OpenCore inference + Google Gemini, OpenAI, and Anthropic at 0% BYOM markup under one governed router.",
    url: `${SITE_URL}/models`,
  },
};

const modelsDatasetSchema = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "Keelway Hybrid AI Model Registry",
  numberOfItems: CATALOG_MODELS.length,
  itemListElement: CATALOG_MODELS.map((m, idx) => ({
    "@type": "ListItem",
    position: idx + 1,
    name: m.name,
    description: `${m.description} (${m.license})`,
  })),
};

/**
 * Models & Hybrid Economics (/models)
 */
export default function ModelsCatalogPage() {
  return (
    <div data-theme="dark" className="bg-canvas text-fg">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(modelsDatasetSchema) }}
      />

      {/* Page Hero */}
      <section
        aria-labelledby="models-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
                <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
                <span className="font-semibold text-fg">
                  HYBRID UNIT ECONOMICS
                </span>
                <span className="text-fg-dim">·</span>
                <span className="text-fg-muted">
                  $0 Local Inference · 0% Token COGS · 0% BYOM Markup
                </span>
              </div>

              <h1
                id="models-hero-heading"
                className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
              >
                Hybrid Gross-Margin &amp;{" "}
                <span className="text-teal-accent">Data Sovereignty</span>
              </h1>

              <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
                $0 local OpenCore inference handles routine agent loops on
                developer or on-prem hardware at 0% token COGS, while complex
                multi-step synthesis bursts to Frontier models with 0% BYOM
                markup.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/governance" className="kw-btn kw-btn-primary">
                <span>Simulate Hybrid Routing</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/api-reference" className="kw-btn kw-btn-secondary">
                <span>Core API Spec</span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Empirical Cost-Latency Frontier + Model Explorer */}
      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-container space-y-12 px-4 sm:px-6">
          <LatencyCostFrontierChart />
          <ModelExplorer />
          <SpeculativeDecodingLab />
        </div>
      </section>
    </div>
  );
}
