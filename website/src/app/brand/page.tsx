import React from "react";
import type { Metadata } from "next";
import { BrandKitLab } from "@/components/brand/BrandKitLab";
import { BrandMark } from "@/components/ui/BrandMark";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Interface Identity & Brand Kit",
  description:
    "Official Keelway K-with-dot wordmark lockup, monochrome zinc dark and light color tokens, single-teal action accent, self-hosted variable typography, and WCAG 2.2 AA UI guardrails.",
  alternates: {
    canonical: "/brand",
  },
  openGraph: {
    title: "Interface Identity & Brand Kit · Keelway",
    description:
      "Geometric K-with-dot lockup, monochrome zinc + single-teal design tokens, variable typography, and Calm Utility interface rules.",
    url: `${SITE_URL}/brand`,
  },
};

export default function BrandPage() {
  return (
    <div>
      <section
        aria-labelledby="brand-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto flex max-w-container flex-col items-start justify-between gap-8 px-4 sm:flex-row sm:items-center sm:px-6">
          <div className="max-w-2xl">
            <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
              <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
              <span className="font-semibold text-fg">
                DESIGN.MD SPEC
              </span>
              <span className="text-fg-dim">·</span>
              <span className="text-fg-muted">
                Calm Utility · Monochrome Zinc · Single-Teal Accent
              </span>
            </div>

            <h1
              id="brand-hero-heading"
              className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
            >
              Keelway Interface Identity
            </h1>

            <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
              One geometric K-with-dot wordmark lockup, a clean monochrome zinc
              palette (#09090B dark, #FAFAFA light) that reserves teal strictly
              for the logo dot, primary CTA, and focus ring, and self-hosted
              variable typography shared across Keelway Studio, the Web Console,
              and public documentation.
            </p>
          </div>

          <BrandMark
            size={88}
            variant="tile"
            aria-label="Keelway geometric K mark"
            className="shrink-0 shadow-2xl"
          />
        </div>
      </section>

      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <BrandKitLab />
        </div>
      </section>
    </div>
  );
}
