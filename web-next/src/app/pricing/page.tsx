import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Pricing — Keelway",
  description:
    "Community free, BYOM from $15/seat/mo, Pro from $29/seat/mo — 0% token markup. Enterprise Sovereign VPC on request. Marketplace runs a separate 85/15 revenue share.",
};

interface SeatTier {
  name: string;
  monthlyUsd: number | null;
  annualMonthlyUsd: number | null;
  tokensPerDay: string;
  rpm: number;
  concurrentAgents: number;
  workflows: number;
  note?: string;
  accent?: boolean;
}

// Canonical seat tiers — mirrors SUBSCRIPTION_TIERS in core/platform/subscription.py.
const SEAT_TIERS: SeatTier[] = [
  {
    name: "Community",
    monthlyUsd: 0,
    annualMonthlyUsd: 0,
    tokensPerDay: "150K open-weight tokens/day",
    rpm: 20,
    concurrentAgents: 2,
    workflows: 3,
    note: "Apache-2.0 core · runs fully offline",
  },
  {
    name: "BYOM",
    monthlyUsd: 19,
    annualMonthlyUsd: 15,
    tokensPerDay: "500K tokens/day",
    rpm: 120,
    concurrentAgents: 12,
    workflows: 100,
    note: "Your provider keys — 0% token markup",
  },
  {
    name: "Pro",
    monthlyUsd: 35,
    annualMonthlyUsd: 29,
    tokensPerDay: "2.5M tokens/day",
    rpm: 120,
    concurrentAgents: 12,
    workflows: 100,
    note: "Frontier routing + P-10 gates + audit exports",
    accent: true,
  },
  {
    name: "Enterprise",
    monthlyUsd: null,
    annualMonthlyUsd: null,
    tokensPerDay: "50M tokens/day",
    rpm: 2_000,
    concurrentAgents: 128,
    workflows: 10_000,
    note: "Sovereign VPC · air-gap · dual-human quorum · SAML/SSO",
  },
];

const MARKETPLACE_SPLITS = [
  { tier: "First-party packs", split: "0 / 100", scope: "Keelway keeps nothing" },
  { tier: "Verified third-party", split: "85 / 15", scope: "creator / platform" },
  { tier: "Enterprise partner", split: "80 / 20", scope: "creator / platform" },
] as const;

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-16 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Pricing</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-fg">Priced like a ledger.</h1>
      <p className="mt-4 max-w-xl text-sm leading-6 text-fg-muted">
        Four seat plans plus a marketplace revenue stream. Annual pricing shown;
        every paid tier routes tokens at 0% Keelway markup.
      </p>

      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {SEAT_TIERS.map((t) => (
          <section
            key={t.name}
            aria-label={`${t.name} seat plan`}
            className={`flex h-full flex-col rounded-md border p-5 transition-colors hover:border-border-strong ${
              t.accent ? "border-accent/40 bg-accent-subtle" : "border-border bg-surface"
            }`}
          >
            <p className={`font-mono text-[11px] uppercase tracking-wide ${t.accent ? "text-accent" : "text-fg-muted"}`}>
              {t.name}
            </p>
            <p className="mt-3 text-3xl font-semibold tracking-tight text-fg">
              {t.annualMonthlyUsd === null ? "Custom" : `$${t.annualMonthlyUsd}`}
              {t.annualMonthlyUsd !== null && t.annualMonthlyUsd > 0 && (
                <span className="text-sm font-normal text-fg-muted">/seat/mo</span>
              )}
            </p>
            <p className="mt-1 font-mono text-[10px] text-fg-muted">
              {t.monthlyUsd === null
                ? "annual contract"
                : t.monthlyUsd === 0
                  ? "free forever"
                  : `annual · $${t.monthlyUsd} monthly`}
            </p>
            <ul className="mt-4 flex-1 space-y-2 border-t border-border pt-4 text-[13px] text-fg-muted">
              <li>{t.tokensPerDay}</li>
              <li>{t.rpm} requests/min</li>
              <li>{t.concurrentAgents} concurrent agents</li>
              <li>{t.workflows} workflows</li>
            </ul>
            <p className="mt-4 text-[12px] text-fg-muted">{t.note}</p>
          </section>
        ))}
      </div>

      <section aria-label="Marketplace revenue share" className="mt-6 rounded-md border border-border bg-surface p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">Marketplace — revenue share, not a seat</h2>
          <p className="font-mono text-[10px] text-fg-muted">$0 subscription · ecosystem_revenue_share · receipt-signed settlements</p>
        </div>
        <ul className="mt-4 grid gap-px overflow-hidden rounded-sm border border-border bg-border sm:grid-cols-3">
          {MARKETPLACE_SPLITS.map((m) => (
            <li key={m.tier} className="bg-surface px-4 py-3">
              <p className="text-[13px] font-medium text-fg">{m.tier}</p>
              <p className="mt-0.5 font-mono text-[11px] text-fg-muted">
                <span className="text-accent">{m.split}</span> · {m.scope}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <p className="mt-6 rounded-sm border border-border bg-surface px-4 py-3 text-[12px] leading-5 text-fg-muted">
        BYOM requires authorized developer API keys or official integrations
        (Anthropic, Gemini, OpenAI, self-hosted vLLM). Consumer ChatGPT Plus/Pro or
        Claude Pro/Max web subscriptions do not provide third-party API access.
      </p>

      <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
        <p className="text-sm text-fg-muted">Volume seats or a dedicated deployment — annual contract.</p>
        <Button variant="secondary" asChild>
          <Link href="/">Back to overview</Link>
        </Button>
      </div>
    </main>
  );
}
