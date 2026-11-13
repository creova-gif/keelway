import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ModelExplorer } from "@/components/models/ModelExplorer";
import { LatencyCostFrontierChart } from "@/components/charts/LatencyCostFrontierChart";
import { CATALOG_MODELS } from "@/data/models";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Models & OpenCore Catalog",
  description:
    "Explore Keelway's 15 registered OpenCore open-weight and commercial Frontier AI models. Calculate live VRAM fit, inspect Apache-2.0 licenses, and compile deterministic Ollama Modelfiles.",
  alternates: {
    canonical: "/models",
  },
  openGraph: {
    title: "Models & OpenCore Catalog · Keelway",
    description:
      "First-class Open-Weight OpenCore models ($0.00 local inference) + Google Gemini, OpenAI, and Anthropic under one unified registry.",
    url: `${SITE_URL}/models`,
  },
};

const catalogJsonLd = {
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
 * Page 2 (Stage 2): Models & OpenCore Catalog (/models)
 */
export default function ModelsCatalogPage() {
  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(catalogJsonLd) }}
      />

      {/* Page Hero */}
      <section
        aria-labelledby="models-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
                <span className="chip-teal rounded-sm px-2 py-0.5">
                  LAYER 4 REGISTRY
                </span>
                <span className="text-fg-muted">
                  9 Open-Weight Models · 6 Frontier Cloud APIs · 3 Verified QLoRAs
                </span>
              </div>

              <h1
                id="models-hero-heading"
                className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
              >
                OpenCore Sovereignty &amp;{" "}
                <span className="text-teal-accent">Frontier Scale</span> in One
                Registry
              </h1>

              <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
                Every model in Keelway carries verified context limits,
                capability flags, quantization memory specs, and explicit
                licensing — so your router never confuses an{" "}
                <code className="font-mono text-sm text-fg">Apache-2.0</code>{" "}
                local checkpoint with a metered commercial endpoint.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/governance" className="kw-btn kw-btn-primary">
                <span>Simulate Hybrid Routing</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/api-reference" className="kw-btn kw-btn-secondary">
                <span>GET /v1/models Spec</span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Main Interactive Explorer + Empirical Scatter Plot */}
      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-container space-y-12 px-4 sm:px-6">
          <LatencyCostFrontierChart />
          <ModelExplorer />
        </div>
      </section>
    </div>
  );
}
