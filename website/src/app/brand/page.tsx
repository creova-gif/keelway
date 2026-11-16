import React from "react";
import type { Metadata } from "next";
import { BrandKitLab } from "@/components/brand/BrandKitLab";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Interface Identity & Brand Kit",
  description:
    "Official Keelway mark, SVG lockups, dark and light semantic color tokens, self-hosted variable typography, and WCAG 2.2 AA UI guardrails.",
  alternates: {
    canonical: "/brand",
  },
  openGraph: {
    title: "Interface Identity & Brand Kit · Keelway",
    description:
      "Geometric 'K' mark, click-to-copy design tokens, variable typography, and Calm Utility interface rules.",
    url: `${SITE_URL}/brand`,
  },
};

/**
 * Page 5 (Stage 4b): Brand Kit & Open-Source Identity (/brand)
 * Also reached via permanent redirect from legacy `/brand.html`.
 */
export default function BrandPage() {
  return (
    <div>
      {/* Hero */}
      <section
        aria-labelledby="brand-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto flex max-w-container flex-col items-start justify-between gap-8 px-4 sm:flex-row sm:items-center sm:px-6">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
              <span className="chip-teal rounded-sm px-2 py-0.5">
                DESIGN.MD SPEC
              </span>
              <span className="text-fg-muted">
                Calm Utility · Radical Transparency · WCAG AAA Primary Ink
              </span>
            </div>

            <h1
              id="brand-hero-heading"
              className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
            >
              Keelway Interface Identity
            </h1>

            <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
              One geometric mark, two semantic color schemes, self-hosted
              variable typography, and deterministic controls shared across
              Keelway Studio, the Web Console, and public documentation.
            </p>
          </div>

          <svg
            width="88"
            height="88"
            viewBox="0 0 48 48"
            role="img"
            aria-label="Keelway geometric K mark"
            className="shrink-0 shadow-2xl"
          >
            <rect width="48" height="48" rx="11" fill="#2DD4BF" />
            <path d="M15 9h7v30H15z" fill="#0B0F14" />
            <path d="M22 24 32 9h7L30 24l9 15h-7z" fill="#0B0F14" />
          </svg>
        </div>
      </section>

      {/* Main Interactive Brand Lab */}
      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <BrandKitLab />
        </div>
      </section>
    </div>
  );
}
