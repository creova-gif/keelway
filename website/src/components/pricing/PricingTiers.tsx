"use client";

import React, { useState } from "react";
import Link from "next/link";
import * as Accordion from "@radix-ui/react-accordion";
import {
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  Cpu,
  Minus,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";
import { PRICING_FAQS } from "@/data/pricing";

interface MatrixRow {
  category: string;
  feature: string;
  oss: string | boolean;
  team: string | boolean;
  enterprise: string | boolean;
}

const COMPARISON_ROWS: MatrixRow[] = [
  {
    category: "Models & Runtime",
    feature: "Keelway OpenCore 1.5B–14B Weights & Modelfile Compiler",
    oss: true,
    team: true,
    enterprise: true,
  },
  {
    category: "Models & Runtime",
    feature: "Commercial Frontier Adapters (Gemini, OpenAI, Anthropic)",
    oss: "BYOK Local",
    team: "BYOK Shared Vault (0% Markup)",
    enterprise: "Private VPC Gateway + Custom SLAs",
  },
  {
    category: "Models & Runtime",
    feature: "Custom Domain & Multilingual QLoRA Distillation",
    oss: "Self-Managed Recipes",
    team: "Shared Team Registry",
    enterprise: "Dedicated Distillation Pipeline",
  },
  {
    category: "Routing & Privacy",
    feature: "Deterministic 4D Provenance Router (/v1/routing/explain)",
    oss: true,
    team: true,
    enterprise: true,
  },
  {
    category: "Routing & Privacy",
    feature: "Data Residency Zones (Africa, EU GDPR, Local-Only)",
    oss: "Local Loopback",
    team: "Policy Enforced",
    enterprise: "Dedicated Regional GPU Clusters",
  },
  {
    category: "Governance & Security",
    feature: "Scoped kw_live_* Tenant Keys & Salted SHA-256 Vault",
    oss: "Single-Tenant",
    team: "Multi-Project RBAC",
    enterprise: "SSO / SAML + Hardware KMS",
  },
  {
    category: "Governance & Security",
    feature: "Per-Tenant USD Spend Caps & OpenCore Auto-Downgrade",
    oss: true,
    team: true,
    enterprise: true,
  },
  {
    category: "Governance & Security",
    feature: "Hash-Chained FlightRecorder & CycloneDX 1.5 SBOM",
    oss: "Local SQLite",
    team: "Hosted Tamper-Evident Sync",
    enterprise: "SIEM Export + Compliance Attestation",
  },
];

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
 * Interactive Pricing Tiers, Seat Calculator, Comparison Matrix & Radix FAQ Accordion.
 */
export function PricingTiers() {
  const [annual, setAnnual] = useState<boolean>(true);
  const [seats, setSeats] = useState<number>(8);

  const perSeatPrice = annual ? 39 : 49;
  const estimatedTeamMonthly = seats * perSeatPrice;

  return (
    <div className="space-y-16">
      {/* ====================================================================
          1. BILLING CYCLE & TEAM SEAT CALCULATOR BAR
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
              Team Engineering Seats:
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
          2. THREE DEPLOYMENT TIER CARDS
          ==================================================================== */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Tier 1: OpenCore Open Source */}
        <article className="flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-6">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-neutral rounded-sm px-2.5 py-1">
                SELF-HOSTED OSS
              </span>
              <Cpu className="h-5 w-5 text-teal-accent" aria-hidden="true" />
            </div>

            <h2 className="mt-4 text-xl font-bold text-fg">
              OpenCore Local
            </h2>
            <p className="mt-1 text-xs text-fg-muted">
              Full local-first AI platform, Studio IDE, CLI, and Python SDK.
            </p>

            <div className="mt-5 flex items-baseline gap-2 font-mono">
              <span className="text-4xl font-extrabold tabular-nums text-fg">
                $0
              </span>
              <span className="text-xs text-fg-muted">
                forever · Apache-2.0
              </span>
            </div>

            <ul className="mt-6 space-y-2.5 border-t border-border-subtle pt-5 text-xs text-fg-muted">
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  Unlimited local OpenCore, Qwen, Mistral &amp; DeepSeek
                  inference ($0.00/tok)
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  Keelway Studio (port 7420) + 6-tab Governance Web Console
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  5-step Human Approval Gate &amp; local SQLite hash-chained log
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>100% offline &amp; air-gapped workstation ready</span>
              </li>
            </ul>
          </div>

          <div className="mt-8">
            <Link
              href="/#quickstart"
              className="kw-btn kw-btn-secondary w-full"
            >
              <span>Clone &amp; Run Locally</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </article>

        {/* Tier 2: Team Hybrid Cloud (Highlighted) */}
        <article className="frame-crosshair flex flex-col justify-between rounded-lg border-2 border-teal-accent bg-surface p-6 shadow-xl">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-teal rounded-sm px-2.5 py-1">
                MOST POPULAR · 0% TOKEN MARKUP
              </span>
              <Users className="h-5 w-5 text-teal-accent" aria-hidden="true" />
            </div>

            <h2 className="mt-4 text-xl font-bold text-fg">
              Team Hybrid Cloud
            </h2>
            <p className="mt-1 text-xs text-fg-muted">
              Shared governance, hosted workspace sync, and multi-provider
              spend control.
            </p>

            <div className="mt-5 flex items-baseline gap-2 font-mono">
              <span className="text-4xl font-extrabold tabular-nums text-fg">
                ${perSeatPrice}
              </span>
              <span className="text-xs text-fg-muted">
                / seat / mo {annual ? "(billed annually)" : "(billed monthly)"}
              </span>
            </div>
            <p className="mt-1 font-mono text-[11px] text-teal-accent">
              Est. for {seats} {seats === 1 ? "engineer" : "engineers"}: $
              {estimatedTeamMonthly.toLocaleString("en-US")}/mo + $0 BYOK proxy
              fee
            </p>

            <ul className="mt-6 space-y-2.5 border-t border-border-subtle pt-5 text-xs text-fg">
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  Everything in OpenCore Local + hosted CRDT KSpaces sync
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  Multi-tenant <code>kw_live_*</code> RBAC keys &amp; shared
                  secret redaction
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  Per-team USD spend caps with automatic OpenCore local fallback
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span>
                  MiroFish 12-agent hybrid swarm evaluation harness
                </span>
              </li>
            </ul>
          </div>

          <div className="mt-8">
            <Link
              href="/#early-access"
              className="kw-btn kw-btn-primary w-full"
            >
              <span>Request Team Access</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </article>

        {/* Tier 3: Enterprise Sovereign VPC */}
        <article className="flex flex-col justify-between rounded-lg border border-border-strong bg-surface p-6">
          <div>
            <div className="flex items-center justify-between">
              <span className="chip-amber rounded-sm px-2.5 py-1">
                DEDICATED VPC &amp; ON-PREM
              </span>
              <Building2
                className="h-5 w-5 text-amber-alert"
                aria-hidden="true"
              />
            </div>

            <h2 className="mt-4 text-xl font-bold text-fg">
              Enterprise Sovereign VPC
            </h2>
            <p className="mt-1 text-xs text-fg-muted">
              Customer-owned GPU fleets, regional residency, and custom LoRA
              distillation.
            </p>

            <div className="mt-5 flex items-baseline gap-2 font-mono">
              <span className="text-3xl font-extrabold text-fg">Custom</span>
              <span className="text-xs text-fg-muted">
                annual architecture agreement
              </span>
            </div>

            <ul className="mt-6 space-y-2.5 border-t border-border-subtle pt-5 text-xs text-fg-muted">
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert"
                  aria-hidden="true"
                />
                <span>
                  Dedicated vLLM GPU clusters in Africa, EU, US, or air-gapped
                  racks
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert"
                  aria-hidden="true"
                />
                <span>
                  Custom domain &amp; multilingual QLoRA training (Swahili,
                  Yoruba, Hausa, Amharic)
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert"
                  aria-hidden="true"
                />
                <span>
                  Dual-human quorum mutation policies, SAML SSO &amp; SIEM audit
                  export
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert"
                  aria-hidden="true"
                />
                <span>
                  CycloneDX 1.5 SBOM attestation &amp; 99.95% uptime SLA
                </span>
              </li>
            </ul>
          </div>

          <div className="mt-8">
            <Link
              href="/#early-access"
              className="kw-btn kw-btn-secondary w-full"
            >
              <span>Schedule Architecture Review</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </article>
      </div>

      {/* ====================================================================
          3. ACCESSIBLE RESPONSIVE FEATURE COMPARISON TABLE
          ==================================================================== */}
      <section aria-labelledby="matrix-heading">
        <h2
          id="matrix-heading"
          className="text-2xl font-bold tracking-tight text-fg"
        >
          Platform Capability Matrix
        </h2>
        <p className="mt-1 text-sm text-fg-muted">
          Honest architectural breakdown across self-hosted open source, managed
          hybrid teams, and customer-owned VPC deployments.
        </p>

        <div className="mt-6 overflow-x-auto rounded-lg border border-border-strong bg-surface">
          <table className="w-full min-w-[680px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border-strong bg-surface-elevated font-mono text-xs uppercase text-fg">
                <th scope="col" className="px-4 py-3.5">
                  Capability
                </th>
                <th scope="col" className="px-4 py-3.5 text-center">
                  OpenCore Local
                </th>
                <th
                  scope="col"
                  className="px-4 py-3.5 text-center text-teal-accent"
                >
                  Team Hybrid
                </th>
                <th scope="col" className="px-4 py-3.5 text-center">
                  Enterprise VPC
                </th>
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
                    <div className="mt-0.5 text-xs sm:text-sm">
                      {row.feature}
                    </div>
                  </th>
                  <td className="px-4 py-3.5 text-center">
                    {renderCell(row.oss)}
                  </td>
                  <td className="bg-teal-surface/20 px-4 py-3.5 text-center">
                    {renderCell(row.team)}
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    {renderCell(row.enterprise)}
                  </td>
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
          LICENSING, BILLING &amp; SOVEREIGNTY FAQ
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
