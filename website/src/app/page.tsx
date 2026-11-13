import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Cpu,
  Globe2,
  KeyRound,
  Scale,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { HeroControlCockpit } from "@/components/home/HeroControlCockpit";
import { RecordedDemosShowcase } from "@/components/home/RecordedDemosShowcase";
import { ArchitectureTopology } from "@/components/home/ArchitectureTopology";
import { ApprovalGateStepper } from "@/components/home/ApprovalGateStepper";
import { QuickstartTerminal } from "@/components/home/QuickstartTerminal";
import { EarlyAccessForm } from "@/components/home/EarlyAccessForm";

/**
 * Page 1 (Stage 1): Keelway Home (/)
 * Dual-Track Conversion Hub serving both Self-Serve OSS/AI Builders and
 * Enterprise CTOs / Security Architects.
 */
export default function HomePage() {
  return (
    <div>
      {/* ====================================================================
          HERO — Blueprint Surface + Live Operable Control-Plane Cockpit
          ==================================================================== */}
      <section
        aria-labelledby="hero-heading"
        className="blueprint-surface relative border-b border-border-subtle py-16 sm:py-24"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            {/* Left Copy & Dual-Track CTAs */}
            <div className="lg:col-span-6">
              <div className="inline-flex flex-wrap items-center gap-2 rounded-sm border border-border-strong bg-surface/90 px-3 py-1.5 font-mono text-xs">
                <span className="chip-teal rounded-sm px-2 py-0.5">
                  APACHE-2.0
                </span>
                <span className="text-fg-muted">
                  OpenCore Weights + Frontier Cloud + Governed Agents
                </span>
              </div>

              <h1
                id="hero-heading"
                className="mt-5 text-4xl font-extrabold tracking-tight text-fg sm:text-5xl lg:leading-[1.08]"
              >
                Sovereign open weights.{" "}
                <span className="text-teal-accent">Frontier intelligence.</span>{" "}
                One verifiable control plane.
              </h1>

              <p className="mt-5 max-w-xl text-base leading-relaxed text-fg-muted sm:text-lg">
                Run local <strong className="text-fg">OpenCore</strong> models
                at zero marginal cost alongside{" "}
                <strong className="text-fg">Gemini, OpenAI, and Anthropic</strong>{" "}
                under deterministic 4D routing. Every code diff, spend ceiling,
                and provider boundary is approved, redacted, and hash-chained.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link href="#quickstart" className="kw-btn kw-btn-primary">
                  <span>Start in 60 Seconds</span>
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Link>
                <Link href="/models" className="kw-btn kw-btn-secondary">
                  <span>Explore OpenCore &amp; Frontier Models</span>
                </Link>
              </div>

              {/* Radical Transparency Telemetry Strip */}
              <dl className="mt-9 grid grid-cols-3 gap-4 border-t border-border-subtle pt-6 font-mono">
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Local Egress
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-teal-accent">
                    0 Bytes
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Swarm Savings
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    96.9%
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Verified Gates
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    167 / 167
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
          DUAL-TRACK PILLARS — Built for OSS Builders & Regulated Enterprises
          ==================================================================== */}
      <section
        id="features"
        aria-labelledby="pillars-heading"
        className="py-16 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              00 // FIRST-CLASS HYBRID FOUNDATION
            </p>
            <h2
              id="pillars-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Built without vendor lock-in from line one
            </h2>
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
            <article className="rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-teal-accent/60">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                <Cpu className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-fg">
                OpenCore Neural Runtime
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Compile deterministic Modelfiles for Ollama Metal and vLLM CUDA,
                verify weights with SHA-256 manifests, and hot-swap domain QLoRA
                adapters including Swahili, Yoruba, Hausa, and Amharic.
              </p>
            </article>

            <article className="rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-teal-accent/60">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                <Scale className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-fg">
                Deterministic 4D Routing
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Route by explicit model, capability, latency, and tenant data
                residency. Private workloads stay fail-closed on local hardware
                and never silently fail over to unauthorized commercial clouds.
              </p>
            </article>

            <article className="rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-teal-accent/60">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-teal-accent">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-lg font-bold text-fg">
                Scoped Governance &amp; Spend Caps
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Issue scoped <code className="font-mono text-xs text-fg">kw_live_*</code>{" "}
                tenant keys, enforce hard USD spend limits or automatic OpenCore
                local fallback, and verify every mutation in a hash-chained SQLite
                flight log.
              </p>
            </article>
          </div>
        </div>
      </section>

      {/* ====================================================================
          60FPS RECORDED STUDIO & APPLE METAL RUNTIME CAPTURES
          ==================================================================== */}
      <RecordedDemosShowcase />

      {/* ====================================================================
          INTERACTIVE 6-LAYER INTELLIGENCE ENGINE TOPOLOGY
          ==================================================================== */}
      <ArchitectureTopology />

      {/* ====================================================================
          INTERACTIVE 5-STEP AGENT APPROVAL GATE STEPPER
          ==================================================================== */}
      <ApprovalGateStepper />

      {/* ====================================================================
          OPENCORE vs. FRONTIER COMPARISON SNAPSHOT
          ==================================================================== */}
      <section
        aria-labelledby="hybrid-compare-heading"
        className="border-t border-border-subtle py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
                03 // TWO FIRST-CLASS MODEL CATEGORIES
              </p>
              <h2
                id="hybrid-compare-heading"
                className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
              >
                Open-weight sovereignty meets commercial frontier scale
              </h2>
            </div>
            <Link
              href="/governance"
              className="kw-btn kw-btn-secondary font-mono text-xs"
            >
              <span>Launch Cost &amp; Routing Simulator</span>
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>

          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Category A: Open-Weight */}
            <div className="rounded-lg border border-teal-accent/50 bg-surface p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="chip-teal rounded-sm px-2.5 py-1">
                  CATEGORY A · OPEN-WEIGHT AI
                </span>
                <span className="font-mono text-xs text-fg-muted">
                  $0.00 / 1M local tokens
                </span>
              </div>
              <h3 className="mt-4 text-xl font-bold text-fg">
                Keelway OpenCore, Qwen, Llama, Mistral &amp; DeepSeek
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                Downloadable weights deployed on your workstation, on-prem GPU
                racks, or dedicated VPC runners with explicit license inspection.
              </p>
              <ul className="mt-5 space-y-2.5 font-mono text-xs text-fg">
                <li className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-teal-accent" aria-hidden="true" />
                  <span>
                    Ollama Apple Silicon Metal &amp; vLLM CUDA tensor-parallel bridges
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Globe2
                    className="h-4 w-4 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>
                    Global &amp; African low-bandwidth / offline-resilient inference
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <KeyRound
                    className="h-4 w-4 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>
                    Zero external prompt egress for regulated code &amp; PHI/fintech data
                  </span>
                </li>
              </ul>
            </div>

            {/* Category B: Closed Frontier */}
            <div className="rounded-lg border border-border-strong bg-surface p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="chip-amber rounded-sm px-2.5 py-1">
                  CATEGORY B · CLOSED FRONTIER AI
                </span>
                <span className="font-mono text-xs text-fg-muted">
                  Metered per-tenant USD caps
                </span>
              </div>
              <h3 className="mt-4 text-xl font-bold text-fg">
                Google Gemini, OpenAI &amp; Anthropic Commercial APIs
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-muted">
                First-class normalized adapters for long-context synthesis,
                multimodal reasoning, and frontier judge verification — governed
                by tenant consent.
              </p>
              <ul className="mt-5 space-y-2.5 font-mono text-xs text-fg">
                <li className="flex items-center gap-2">
                  <ShieldCheck
                    className="h-4 w-4 text-amber-alert"
                    aria-hidden="true"
                  />
                  <span>
                    Header-isolated API credentials (zero URL query-string leakage)
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Scale
                    className="h-4 w-4 text-amber-alert"
                    aria-hidden="true"
                  />
                  <span>
                    Real-time token accounting, retry budgets &amp; HTTP 402 spend caps
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Cpu
                    className="h-4 w-4 text-amber-alert"
                    aria-hidden="true"
                  />
                  <span>
                    Automatic fallback to local OpenCore when cloud budgets saturate
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ====================================================================
          60-SECOND MULTI-SURFACE QUICKSTART TERMINAL
          ==================================================================== */}
      <QuickstartTerminal />

      {/* ====================================================================
          EARLY ACCESS & ENTERPRISE VPC INTAKE FORM
          ==================================================================== */}
      <EarlyAccessForm />
    </div>
  );
}
