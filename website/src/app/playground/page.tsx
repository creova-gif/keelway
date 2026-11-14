import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Terminal } from "lucide-react";
import { UnifiedPlatformPlayground } from "@/components/playground/UnifiedPlatformPlayground";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Interactive 10-View Unified Platform Playground",
  description:
    "Explore Keelway's 10-view sovereign AI workspace in your browser: switch between Builder Mode and Guided Non-Coder Mode across No-Code Blueprint, PRD, PM, Agents, IDE, DAG, and Marketplace.",
  alternates: {
    canonical: "/playground",
  },
  openGraph: {
    title: "10-View Unified Platform Playground · Keelway",
    description:
      "Compile natural-language ideas into governed PRDs, Linear-style sprint issues, multi-agent squads, P-10 diffs, and KFlow DAGs in real time.",
    url: `${SITE_URL}/playground`,
  },
};

/**
 * Interactive 10-View Unified Platform & Dual Builder / Non-Coder Workbench (/playground)
 */
export default function PlaygroundPage() {
  return (
    <div>
      {/* Page Hero */}
      <section
        aria-labelledby="playground-hero-heading"
        className="blueprint-surface border-b border-border-subtle py-12 sm:py-16"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1 font-mono text-xs">
                <span className="chip-teal rounded-sm px-2 py-0.5">
                  INTERACTIVE WORKBENCH
                </span>
                <span className="text-fg-muted">
                  10 Unified Views · Builder &amp; Guided Non-Coder Modes · Shared Live State
                </span>
              </div>

              <h1
                id="playground-hero-heading"
                className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
              >
                One Sovereign Architecture.{" "}
                <span className="text-teal-accent">Ten Connected Views.</span>
              </h1>

              <p className="mt-4 text-base leading-relaxed text-fg-muted sm:text-lg">
                Compile a product brief once and inspect how Keelway synchronizes{" "}
                <strong className="text-fg">Product PRDs</strong>,{" "}
                <strong className="text-fg">Project Manager</strong> sprint issues,{" "}
                <strong className="text-fg">Lifecycle Agents</strong>,{" "}
                <strong className="text-fg">IDE diffs</strong>,{" "}
                <strong className="text-fg">P-10 human approvals</strong>, and{" "}
                <strong className="text-fg">Marketplace extensions</strong>.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/#quickstart" className="kw-btn kw-btn-primary">
                <Terminal className="h-4 w-4" aria-hidden="true" />
                <span>Launch Local Studio (:7420)</span>
              </Link>
              <Link href="/pricing" className="kw-btn kw-btn-secondary">
                <span>5-Stream Pricing &amp; BYOM</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Main Interactive 10-View Workbench */}
      <section className="py-12 sm:py-16">
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <UnifiedPlatformPlayground />
        </div>
      </section>
    </div>
  );
}
