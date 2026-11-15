import React from "react";
import Link from "next/link";
import { evaluate } from "flags/next";
import {
  ArrowRight,
  Cpu,
  LayoutGrid,
  PackageCheck,
} from "lucide-react";
import { expHomeGateFlag, expQuickstartCliFlag } from "@/flags";
import { ExperimentFlagValues } from "@/components/experiments/ExperimentFlagValues";
import { HeroCtaLinks } from "@/components/home/HeroCtaLinks";
import { HeroControlCockpit } from "@/components/home/HeroControlCockpit";
import { CustomerJourneyGrid } from "@/components/home/CustomerJourneyGrid";
import { GoldenThreadStudioShowcase } from "@/components/home/GoldenThreadStudioShowcase";
import { RecordedDemosShowcase } from "@/components/home/RecordedDemosShowcase";
import { ApprovalGateStepper } from "@/components/home/ApprovalGateStepper";
import { P10InteractiveDeck } from "@/components/home/P10InteractiveDeck";
import { QuickstartTerminal } from "@/components/home/QuickstartTerminal";
import { EarlyAccessForm } from "@/components/home/EarlyAccessForm";

/**
 * Keelway Home (/)
 * Customer-focused, zero-clutter conversion hub serving Non-Technical Builders,
 * Developers, Startups, and Regulated Enterprises — instrumented with live
 * server-evaluated Vercel Flags (`exp-home-gate-v1` and `exp-quickstart-cli-v1`).
 */
export default async function HomePage() {
  const [homeGateVariant, quickstartCliVariant] = await evaluate([
    expHomeGateFlag,
    expQuickstartCliFlag,
  ]);

  return (
    <div>
      <ExperimentFlagValues
        surface="home"
        values={{
          "exp-home-gate-v1": homeGateVariant,
          "exp-quickstart-cli-v1": quickstartCliVariant,
        }}
      />

      {/* ====================================================================
          1. HERO — Clear Platform Value Prop + Playable Control Cockpit
          ==================================================================== */}
      <section
        aria-labelledby="hero-heading"
        className="blueprint-surface relative border-b border-border-subtle py-16 sm:py-24"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            {/* Left Copy & Clear CTAs */}
            <div className="lg:col-span-6">
              <div className="inline-flex flex-wrap items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1.5 font-mono text-xs">
                <span className="chip-teal rounded-sm px-2 py-0.5">
                  OPEN-CORE PLATFORM
                </span>
                <span className="text-fg-muted">
                  Local &amp; Cloud AI · 10 Unified Views · Signed Marketplace
                </span>
              </div>

              <h1
                id="hero-heading"
                className="mt-5 text-4xl font-extrabold tracking-tight text-fg sm:text-5xl lg:leading-[1.08]"
              >
                Build, automate, and scale with AI agents —{" "}
                <span className="text-teal-accent">on your terms.</span>
              </h1>

              <p className="mt-5 max-w-xl text-base leading-relaxed text-fg-muted sm:text-lg">
                One local-first workspace for{" "}
                <strong className="text-fg">
                  developers, non-technical builders, startups, and enterprises
                </strong>
                . Combine AI coding, project management, no-code workflows, and
                verified Marketplace skills using free local{" "}
                <strong className="text-fg">OpenCore</strong> models or your own{" "}
                <strong className="text-fg">
                  OpenAI, Anthropic, and Gemini
                </strong>{" "}
                keys.
              </p>

              <HeroCtaLinks />

              {/* Clean Customer Value Metrics */}
              <dl className="mt-9 grid grid-cols-3 gap-4 border-t border-border-subtle pt-6 font-mono">
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Local OpenCore
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-teal-accent">
                    $0 / Token
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    BYOM Cloud Fee
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    0% Markup
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Unified Workspace
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    10 Views
                  </dd>
                </div>
              </dl>
            </div>

            {/* Right Playable Control-Plane Cockpit */}
            <div className="lg:col-span-6">
              <HeroControlCockpit />
            </div>
          </div>
        </div>
      </section>

      {/* ====================================================================
          2. PERSONA & USER JOURNEY ROUTER (Founders, Devs, Startups, Enterprise)
          ==================================================================== */}
      <CustomerJourneyGrid />

      {/* ====================================================================
          2B. ZERO-INSTALL GOLDEN-THREAD STUDIO SHOWCASE (#studio-showcase)
          ==================================================================== */}
      <GoldenThreadStudioShowcase />

      {/* ====================================================================
          3. CORE PLATFORM ECOSYSTEM — Workspace, Open-Core Models & Marketplace
          ==================================================================== */}
      <section
        id="features"
        aria-labelledby="pillars-heading"
        className="py-16 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div className="max-w-2xl">
              <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
                UNIFIED AI ECOSYSTEM
              </p>
              <h2
                id="pillars-heading"
                className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
              >
                Everything your team needs in one governed platform
              </h2>
            </div>
            <Link
              href="/models"
              className="kw-btn kw-btn-secondary font-mono text-xs"
            >
              <span>Explore Supported Models</span>
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
            <article className="rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-teal-accent/60">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                <LayoutGrid className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-fg">
                10-View Connected Workspace
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Move seamlessly across Agents, IDE, Linear-style Project
                Manager, Product PRDs, Automation, Marketplace, Security, Docs,
                Operations, and No-Code Builder without losing context.
              </p>
            </article>

            <article className="rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-teal-accent/60">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                <Cpu className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-fg">
                Open-Weight &amp; Cloud Model Choice
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Run local OpenCore models privately on your own hardware, or
                connect authorized OpenAI, Anthropic, and Gemini API keys with
                spend caps and automatic local fallback.
              </p>
            </article>

            <article className="rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-teal-accent/60">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                <PackageCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-fg">
                Signed Marketplace &amp; 85/15 Split
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Install pre-scanned, Ed25519-signed agents, skills, plugins, and
                industry solutions — or publish your own extensions and keep 85%
                of creator revenue.
              </p>
            </article>
          </div>
        </div>
      </section>

      {/* ====================================================================
          4. REAL 60FPS PRODUCT CAPTURES
          ==================================================================== */}
      <RecordedDemosShowcase />

      {/* ====================================================================
          5. A/B EXPERIMENT 1 (`exp-home-gate-v1`):
             Control (`control-stepper`) vs Treatment (`interactive-p10-deck`)
          ==================================================================== */}
      {homeGateVariant === "interactive-p10-deck" ? (
        <P10InteractiveDeck />
      ) : (
        <ApprovalGateStepper />
      )}

      {/* ====================================================================
          6. A/B EXPERIMENT 2 (`exp-quickstart-cli-v1`) + ONBOARDING INTAKE
          ==================================================================== */}
      <QuickstartTerminal variant={quickstartCliVariant} />
      <EarlyAccessForm />
    </div>
  );
}
