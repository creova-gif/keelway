"use client";

import React, { useState } from "react";
import Link from "next/link";
import * as Accordion from "@radix-ui/react-accordion";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  Cpu,
  KeyRound,
  Minus,
  PackageCheck,
  ShieldCheck,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";
import {
  COMPARISON_ROWS,
  MARKETPLACE_PUBLISHER_SPLITS,
  PRICING_FAQS,
} from "@/data/pricing";

function renderCell(val: string | boolean) {
  if (val === true) {
    return (
      <span className="inline-flex items-center justify-center text-teal-accent">
        <Check className="h-4 w-4" aria-label="Included" />
      </span>
    );
  }
  if (val === false) {
    return (
      <span className="inline-flex items-center justify-center text-fg-dim">
        <Minus className="h-4 w-4" aria-label="Not included" />
      </span>
    );
  }
  return <span className="font-mono text-xs text-fg">{val}</span>;
}

/**
 * 5-Stream Subscription, BYOM Compliance, Enterprise VPC & Creator Marketplace Pricing.
 */
export function PricingTiers() {
  const [annual, setAnnual] = useState<boolean>(true);
  const [seats, setSeats] = useState<number>(8);

  const perSeatPrice = annual ? 39 : 49;
  const estimatedTeamMonthly = seats * perSeatPrice;

  return (
    <div className="space-y-16">
      {/* ====================================================================
          1. BILLING CADENCE & TEAM SEAT CALCULATOR BAR
          ==================================================================== */}
      <div className="flex flex-col items-start justify-between gap-6 rounded-lg border border-border-strong bg-surface p-5 sm:flex-row sm:items-center sm:p-6">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-xs font-semibold uppercase text-fg-muted">
            Billing Cadence:
          </span>
          <div
            role="group"
            aria-label="Billing cycle"
            className="inline-flex rounded-sm border border-border-strong bg-canvas p-0.5"
          >
            <button
              type="button"
              onClick={() => {
                setAnnual(true);
                trackEvent("pricing_billing_toggled", { cycle: "annual" });
              }}
              className={cn(
                "min-h-[40px] rounded-sm px-3.5 font-mono text-xs font-semibold transition-colors duration-150",
                annual
                  ? "bg-teal-accent text-teal-ink"
                  : "text-fg-muted hover:text-fg"
              )}
            >
              Annual (Save 20%)
            </button>
            <button
              type="button"
              onClick={() => {
                setAnnual(false);
                trackEvent("pricing_billing_toggled", { cycle: "monthly" });
              }}
              className={cn(
                "min-h-[40px] rounded-sm px-3.5 font-mono text-xs font-semibold transition-colors duration-150",
                !annual
                  ? "bg-teal-accent text-teal-ink"
                  : "text-fg-muted hover:text-fg"
              )}
            >
              Monthly
            </button>
          </div>
        </div>

        <div className="w-full sm:w-80">
          <div className="flex items-center justify-between font-mono text-xs">
            <label htmlFor="seat-slider" className="text-fg-muted">
              Keelway Pro / BYOM Seats:
            </label>
            <span className="font-bold tabular-nums text-teal-accent">
              {seats} {seats === 1 ? "seat" : "seats"} (${estimatedTeamMonthly}
              /mo)
            </span>
          </div>
          <input
            id="seat-slider"
            type="range"
            min={1}
            max={50}
            step={1}
            value={seats}
            onChange={(e) => setSeats(Number(e.target.value))}
            className="mt-2 h-2 w-full cursor-pointer accent-[#2DD4BF]"
          />
        </div>
      </div>

      {/* ====================================================================
          2. STREAMS 1–4: CORE PLATFORM, PRO, BYOM & ENTERPRISE CARDS
          ==================================================================== */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
        {/* Stream 1: Free / Community Tier */}
        <article className="flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-5">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-neutral rounded-sm px-2 py-1">
                STREAM 1 · APACHE-2.0
              </span>
              <Cpu className="h-5 w-5 text-teal-accent" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-bold text-fg">
              Free / Community Tier
            </h2>
            <p className="mt-1 text-xs text-fg-muted">
              Open-core local platform, OpenCore weights, selected agents &amp;
              dev tools.
            </p>
            <div className="mt-4 flex items-baseline gap-2 font-mono">
              <span className="text-3xl font-extrabold tabular-nums text-fg">
                $0
              </span>
              <span className="text-xs text-fg-muted">forever</span>
            </div>
            <ul className="mt-5 space-y-2 border-t border-border-subtle pt-4 text-xs text-fg-muted">
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Unlimited local OpenCore weights ($0.00/tok)</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Community open-weight pool (150K tok/day · 20 RPM)</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Selected agents (2 concurrent), IDE &amp; basic DAGs</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>P-10 Human Approval Gate &amp; local SQLite ledger</span>
              </li>
            </ul>
          </div>
          <div className="mt-6">
            <Link href="/#quickstart" className="kw-btn kw-btn-secondary w-full text-xs">
              <span>Run Free Locally</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </article>

        {/* Stream 2: Keelway Pro (Highlighted) */}
        <article className="frame-crosshair flex flex-col justify-between rounded-lg border-2 border-teal-accent bg-surface p-5 shadow-xl">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-teal rounded-sm px-2 py-1">
                STREAM 2 · MOST POPULAR
              </span>
              <Users className="h-5 w-5 text-teal-accent" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-bold text-fg">Keelway Pro</h2>
            <p className="mt-1 text-xs text-fg-muted">
              12 lifecycle AI agents, multi-agent squads, KSpaces sync &amp;
              higher quotas.
            </p>
            <div className="mt-4 flex items-baseline gap-1.5 font-mono">
              <span className="text-3xl font-extrabold tabular-nums text-fg">
                ${perSeatPrice}
              </span>
              <span className="text-xs text-fg-muted">
                / seat / mo {annual ? "(annual)" : "(monthly)"}
              </span>
            </div>
            <p className="mt-1 font-mono text-[11px] text-teal-accent">
              {seats} {seats === 1 ? "seat" : "seats"} = $
              {estimatedTeamMonthly.toLocaleString("en-US")}/mo
            </p>
            <ul className="mt-5 space-y-2 border-t border-border-subtle pt-4 text-xs text-fg">
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>All 12 specialized lifecycle agents &amp; squads</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>2.5M daily open-weight tokens &amp; 120 RPM ceiling</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Full 10-View Workspace + hosted KSpaces CRDT sync</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Unlimited KFlow automation workflows &amp; PM boards</span>
              </li>
            </ul>
          </div>
          <div className="mt-6">
            <Link href="/#early-access" className="kw-btn kw-btn-primary w-full text-xs">
              <span>Start Keelway Pro</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </article>

        {/* Stream 3: Bring Your Own Model (BYOM) */}
        <article className="flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-5">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-teal rounded-sm px-2 py-1">
                STREAM 3 · 0% MARKUP
              </span>
              <KeyRound className="h-5 w-5 text-teal-accent" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-bold text-fg">
              Bring Your Own Model (BYOM)
            </h2>
            <p className="mt-1 text-xs text-fg-muted">
              Connect authorized provider API keys with 0% token proxy markup.
            </p>
            <div className="mt-4 flex items-baseline gap-1.5 font-mono">
              <span className="text-2xl font-extrabold text-fg">0% Markup</span>
              <span className="text-xs text-fg-muted">+ platform seat</span>
            </div>
            <ul className="mt-5 space-y-2 border-t border-border-subtle pt-4 text-xs text-fg-muted">
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Authorized OpenAI, Anthropic, Gemini &amp; vLLM APIs</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>Billed separately for Keelway orchestration &amp; workspace</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>USD spend caps with automatic OpenCore local fallback</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                <span>SPDX &amp; commercial model license pre-dispatch check</span>
              </li>
            </ul>
          </div>
          <div className="mt-6">
            <a
              href="#byom-compliance"
              onClick={() => trackEvent("pricing_byom_inspected", { source: "card" })}
              className="kw-btn kw-btn-secondary w-full text-xs"
            >
              <span>Read BYOM API Policy</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
        </article>

        {/* Stream 4: Keelway Enterprise */}
        <article className="flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-5">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-amber rounded-sm px-2 py-1">
                STREAM 4 · SOVEREIGN VPC
              </span>
              <Building2 className="h-5 w-5 text-amber-alert" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-bold text-fg">
              Keelway Enterprise
            </h2>
            <p className="mt-1 text-xs text-fg-muted">
              Dedicated VPC or air-gapped clusters, custom AI systems &amp; SLAs.
            </p>
            <div className="mt-4 flex items-baseline gap-2 font-mono">
              <span className="text-3xl font-extrabold text-fg">Custom</span>
              <span className="text-xs text-fg-muted">annual / usage / VPC</span>
            </div>
            <ul className="mt-5 space-y-2 border-t border-border-subtle pt-4 text-xs text-fg-muted">
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert" aria-hidden="true" />
                <span>Dedicated regional GPU VPCs or air-gapped on-prem racks</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert" aria-hidden="true" />
                <span>SAML/SSO, multi-org RBAC, retention &amp; SIEM audit</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert" aria-hidden="true" />
                <span>Dual-human P-10 quorum &amp; CycloneDX 1.5 SBOMs</span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert" aria-hidden="true" />
                <span>Custom multi-agent engineering &amp; 99.95% SLA</span>
              </li>
            </ul>
          </div>
          <div className="mt-6">
            <Link href="/#early-access" className="kw-btn kw-btn-secondary w-full text-xs">
              <span>Request VPC Architecture</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </article>
      </div>

      {/* ====================================================================
          MANDATORY BYOM CONSUMER-SUBSCRIPTION COMPLIANCE NOTICE BANNER
          ==================================================================== */}
      <section
        id="byom-compliance"
        aria-labelledby="byom-compliance-heading"
        className="rounded-lg border border-amber-alert/70 bg-amber-surface p-5 sm:p-6"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
          <AlertTriangle
            className="mt-0.5 h-5 w-5 shrink-0 text-amber-alert"
            aria-hidden="true"
          />
          <div>
            <div className="font-mono text-xs font-bold uppercase text-amber-alert">
              BYOM Provider Credential &amp; Subscription Compliance Notice
            </div>
            <h3
              id="byom-compliance-heading"
              className="mt-1 text-base font-bold text-fg"
            >
              Authorized API Credentials Required — Consumer Web Subscriptions Are Separate
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-fg">
              Users with existing <strong>ChatGPT</strong> or <strong>Claude</strong>{" "}
              subscriptions can use officially supported integrations where available;{" "}
              <strong>
                however, consumer ChatGPT Plus/Pro or Claude Pro/Max web subscriptions
                do NOT automatically grant third-party API access
              </strong>
              . Keelway&apos;s BYOM router fails closed on consumer web session cookies
              and requires authorized provider API credentials (OpenAI Platform,
              Anthropic Console, Google Gemini/Vertex API keys, or self-hosted{" "}
              <code>vLLM</code> / <code>Ollama</code> endpoints), billed directly by your
              provider at <code>0%</code> Keelway token markup.
            </p>
          </div>
        </div>
      </section>

      {/* ====================================================================
          STREAM 5: KEELWAY MARKETPLACE & CREATOR ECONOMY (85% / 15%)
          ==================================================================== */}
      <section
        id="marketplace-economy"
        aria-labelledby="marketplace-economy-heading"
        className="rounded-lg border border-border-strong bg-surface p-6"
      >
        <div className="flex flex-col justify-between gap-4 border-b border-border-subtle pb-5 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <span className="chip-teal inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1">
              <PackageCheck className="h-3.5 w-3.5" aria-hidden="true" />
              STREAM 5 · MARKETPLACE &amp; CREATOR ECONOMY
            </span>
            <h2
              id="marketplace-economy-heading"
              className="mt-3 text-2xl font-bold tracking-tight text-fg"
            >
              85% Creator / 15% Platform Revenue Share — Security-Validated Pre-Listing
            </h2>
            <p className="mt-1.5 text-sm text-fg-muted">
              Monetize specialized AI agents, multi-agent squads, reusable{" "}
              <code>SKILL.md</code> bundles, MCP plugins, workflow templates, and
              enterprise solutions inside <code>keelway.package/v1</code>.
            </p>
          </div>
          <Link href="/governance#manifest-drift" className="kw-btn kw-btn-secondary text-xs">
            <ShieldCheck className="h-4 w-4 text-teal-accent" aria-hidden="true" />
            <span>Test Pre-Publish Security Scanner</span>
          </Link>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
          {MARKETPLACE_PUBLISHER_SPLITS.map((item) => (
            <div
              key={item.tier}
              className="rounded-md border border-border-strong bg-canvas p-4"
            >
              <div className="font-mono text-xs font-semibold text-fg-muted">
                {item.tier}
              </div>
              <div className="mt-2 flex items-baseline gap-2 font-mono">
                <span className="text-xl font-extrabold text-teal-accent">
                  {item.creatorShare}
                </span>
                <span className="text-xs text-fg-muted">/ {item.platformShare}</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-fg-muted">
                {item.scope}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ====================================================================
          3. ACCESSIBLE RESPONSIVE FEATURE COMPARISON MATRIX
          ==================================================================== */}
      <section aria-labelledby="matrix-heading">
        <h2
          id="matrix-heading"
          className="text-2xl font-bold tracking-tight text-fg"
        >
          5-Stream Platform Capability Matrix
        </h2>
        <div className="mt-5 overflow-x-auto rounded-lg border border-border-strong bg-surface">
          <table className="w-full min-w-[740px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border-strong bg-surface-elevated font-mono text-xs uppercase text-fg">
                <th scope="col" className="px-4 py-3.5">Capability</th>
                <th scope="col" className="px-4 py-3.5 text-center">Community ($0)</th>
                <th scope="col" className="px-4 py-3.5 text-center text-teal-accent">Keelway Pro</th>
                <th scope="col" className="px-4 py-3.5 text-center">BYOM (0% Markup)</th>
                <th scope="col" className="px-4 py-3.5 text-center">Enterprise VPC</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {COMPARISON_ROWS.map((row) => (
                <tr
                  key={row.feature}
                  className="transition-colors duration-150 hover:bg-surface-elevated/50"
                >
                  <th scope="row" className="px-4 py-3.5 font-medium text-fg">
                    <div className="font-mono text-[10px] uppercase text-fg-dim">
                      {row.category}
                    </div>
                    <div className="mt-0.5 text-xs sm:text-sm">{row.feature}</div>
                  </th>
                  <td className="px-4 py-3.5 text-center">{renderCell(row.community)}</td>
                  <td className="bg-teal-surface/20 px-4 py-3.5 text-center">{renderCell(row.pro)}</td>
                  <td className="px-4 py-3.5 text-center">{renderCell(row.byom)}</td>
                  <td className="px-4 py-3.5 text-center">{renderCell(row.enterprise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ====================================================================
          4. RADIX ACCESSIBLE ACCORDION FAQ
          ==================================================================== */}
      <section aria-labelledby="faq-heading" className="max-w-3xl">
        <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
          LICENSING, BYOM COMPLIANCE &amp; MARKETPLACE FAQ
        </p>
        <h2
          id="faq-heading"
          className="mt-2 text-2xl font-bold tracking-tight text-fg"
        >
          Frequently Asked Questions
        </h2>

        <Accordion.Root
          type="single"
          collapsible
          defaultValue="item-0"
          onValueChange={(val) => {
            if (val) trackEvent("pricing_faq_opened", { item: val });
          }}
          className="mt-6 divide-y divide-border-subtle rounded-lg border border-border-strong bg-surface"
        >
          {PRICING_FAQS.map((item, idx) => (
            <Accordion.Item key={item.q} value={`item-${idx}`}>
              <Accordion.Header>
                <Accordion.Trigger className="group flex min-h-[54px] w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold text-fg transition-colors duration-150 hover:text-teal-accent">
                  <span>{item.q}</span>
                  <ChevronDown
                    className="h-4 w-4 shrink-0 text-fg-muted transition-transform duration-150 group-data-[state=open]:rotate-180 group-data-[state=open]:text-teal-accent"
                    aria-hidden="true"
                  />
                </Accordion.Trigger>
              </Accordion.Header>
              <Accordion.Content className="px-5 pb-4 text-sm leading-relaxed text-fg-muted">
                {item.a}
              </Accordion.Content>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      </section>
    </div>
  );
}
