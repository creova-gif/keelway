import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Building2,
  Code2,
  Layers,
  Sparkles,
} from "lucide-react";

interface JourneyCard {
  badge: string;
  title: string;
  audience: string;
  summary: string;
  highlights: string[];
  ctaLabel: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const JOURNEYS: JourneyCard[] = [
  {
    badge: "NO-CODE & GUIDED",
    title: "Founders & Non-Technical Builders",
    audience: "Launch apps, internal tools & workflows in plain English",
    summary:
      "Run `keelway dev` to launch the local Keelway Dev Tool with the Guided No-Code Builder and all 10 Unified Workspace Views — compile plain-English briefs, tasks, and safe automations locally with zero cloud lock-in.",
    highlights: [
      "Guided No-Code Builder + all 10 Unified Workspace Views locally",
      "Plain-English safety approvals before changes go live",
      "Zero cloud lock-in · Start at $0 on the Free Community tier",
    ],
    ctaLabel: "Launch Local Dev Tool (60s)",
    href: "/#quickstart",
    icon: Sparkles,
  },
  {
    badge: "LOCAL IDE, CLI & SDK",
    title: "Software & AI Engineers",
    audience: "Code faster with local OpenCore models & 0%-markup BYOM",
    summary:
      "Run private open-weight models locally on Apple Silicon or CUDA at $0/token, or connect OpenAI, Anthropic, and Gemini API keys through typed Python & TypeScript SDKs.",
    highlights: [
      "1-command local CLI & IDE launch (`keelway dev`)",
      "0% token markup on your own cloud API keys",
      "Official Python & zero-dependency `@keelway/sdk`",
    ],
    ctaLabel: "Jump to 60s Quickstart",
    href: "/#quickstart",
    icon: Code2,
  },
  {
    badge: "UNIFIED TEAM WORKSPACE",
    title: "Startups & Product Teams",
    audience: "Replace disconnected PM, PRD, agent & CI tools",
    summary:
      "Keep PRDs, Linear-style sprint issues, multi-agent squads, code reviews, and verified Marketplace extensions synchronized in one 10-view workspace.",
    highlights: [
      "10 connected views with zero context switching",
      "Signed Marketplace agents, skills & plugins (85/15 creator split)",
      "Predictable $29/seat Pro pricing & spend caps",
    ],
    ctaLabel: "Explore Signed Marketplace",
    href: "/marketplace",
    icon: Layers,
  },
  {
    badge: "VPC, AIR-GAP & COMPLIANCE",
    title: "Enterprises & Security Leaders",
    audience: "Govern every model, prompt boundary & deployment",
    summary:
      "Deploy inside your own VPC or air-gapped environment with fail-closed data residency, PII redaction, Ed25519 package verification, and tamper-evident audit logs.",
    highlights: [
      "Private prompts never leave approved infrastructure",
      "SOC2, HIPAA, ISO27001 & GDPR retention controls",
      "Human-only sign-off on high-impact actions",
    ],
    ctaLabel: "Inspect Security & Governance",
    href: "/governance",
    icon: Building2,
  },
];

export function CustomerJourneyGrid() {
  return (
    <section
      id="journeys"
      aria-labelledby="journeys-heading"
      className="border-b border-border-subtle py-16 sm:py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-fg-muted">
              CHOOSE YOUR PATH
            </p>
            <h2
              id="journeys-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Built for every way you build and run a business
            </h2>
          </div>
          <Link
            href="/pricing"
            className="kw-btn kw-btn-secondary font-mono text-xs"
          >
            <span>Compare Free, Pro, BYOM &amp; Enterprise</span>
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2">
          {JOURNEYS.map((item) => {
            const Icon = item.icon;
            return (
              <article
                key={item.title}
                className="frame-crosshair flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-6 transition-colors duration-150 hover:border-fg-dim"
              >
                <div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-canvas text-fg">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <span className="chip-neutral rounded-sm px-2.5 py-1 font-mono text-[11px]">
                      {item.badge}
                    </span>
                  </div>

                  <h3 className="mt-4 text-xl font-bold text-fg">
                    {item.title}
                  </h3>
                  <p className="mt-1 font-mono text-xs text-fg-muted">
                    {item.audience}
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-fg-muted">
                    {item.summary}
                  </p>

                  <ul className="mt-4 space-y-1.5 text-xs text-fg">
                    {item.highlights.map((pt) => (
                      <li key={pt} className="flex items-start gap-2">
                        <span
                          className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-accent"
                          aria-hidden="true"
                        />
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-6 border-t border-border-subtle pt-4">
                  <Link
                    href={item.href}
                    className="inline-flex min-h-[40px] items-center gap-1.5 font-mono text-xs font-semibold text-fg transition-colors hover:text-teal-accent"
                  >
                    <span>{item.ctaLabel}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
