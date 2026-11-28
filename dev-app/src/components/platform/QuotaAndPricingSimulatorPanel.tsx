import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import { StatCard } from "@/components/ui/StatCard";
import {
  postSimulatePricing,
  type PricingSimulationResult,
  type RbacRoleId,
} from "@/lib/platformRuntimeApi";

export interface QuotaAndPricingSimulatorPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

interface CalibratedTierCardSpec {
  id: string;
  badgeKind: SemanticBadgeKind;
  badgeText: string;
  headline: string;
  subline: (seats: number) => string;
  highlighted?: boolean;
}

const CALIBRATED_TIER_CARDS: CalibratedTierCardSpec[] = [
  {
    id: "community",
    badgeKind: "opencore",
    badgeText: "OPEN-CORE · APACHE-2.0",
    headline: "Community $0 · 150K tok/day",
    subline: () => "$0 forever · Unlimited local OpenCore + 150K/day hosted pool",
  },
  {
    id: "byom",
    badgeKind: "passed",
    badgeText: "BYOM · 0% TOKEN MARKUP",
    headline: "BYOM $15/mo · 0% Markup · 500K tok/day",
    subline: (seats) => `${seats} seats = $${15 * seats}/mo annual ($19/mo monthly) · $0 proxy tax`,
  },
  {
    id: "pro",
    badgeKind: "live",
    badgeText: "MOST POPULAR · FULL STACK",
    headline: "Keelway Pro $29/mo · 2.5M tok/day",
    subline: (seats) => `${seats} seats = $${29 * seats}/mo annual ($35/mo monthly) · All 10 views`,
    highlighted: true,
  },
  {
    id: "enterprise",
    badgeKind: "locked",
    badgeText: "SOVEREIGN VPC & SLA",
    headline: "Enterprise Custom VPC · 50M+ tok/day",
    subline: () => "Dedicated VPC · Air-Gap · SLA · Dual-human P-10 quorum",
  },
];

const API_SPEND_OPTIONS = [500, 1200, 5000, 15000] as const;

function toPct(rate: number): number {
  return Math.round(rate <= 1 ? rate * 100 : rate);
}

export function QuotaAndPricingSimulatorPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: QuotaAndPricingSimulatorPanelProps): React.JSX.Element {
  const [seats, setSeats] = useState<number>(8);
  const [monthlyApiSpendUsd, setMonthlyApiSpendUsd] = useState<number>(1200);
  const [simRunning, setSimRunning] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<PricingSimulationResult | null>(null);

  const handleRunSimulation = async () => {
    setSimRunning(true);
    try {
      const next = await postSimulatePricing({
        seats,
        monthlyApiSpendUsd,
        workspaceId,
        role: activeRbacRole,
      });
      setSimResult(next);
    } finally {
      setSimRunning(false);
    }
  };

  const supportiveCount = simResult
    ? simResult.personas.filter((p) => p.stance === "supportive").length
    : 0;

  return (
    <section
      aria-label="Calibrated pricing and MiroFish market simulator"
      className="space-y-4 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-0.5">
          <h2 className="text-sm font-semibold text-fg">
            Calibrated Tier Quotas &amp; MiroFish 5-Persona Pricing Simulator
          </h2>
          <p className="text-xs text-fg-muted">
            Zero-markup BYOM ($15/mo) and Full-Stack Pro ($29/mo) unit economics validated via OASIS 5-persona buyer simulation.
          </p>
        </div>
        <SemanticBadge kind="simulated" labelOverride="MiroFish OASIS · 5 Personas" />
      </div>

      <div className="grid gap-2.5 md:grid-cols-2 lg:grid-cols-4">
        {CALIBRATED_TIER_CARDS.map((card) => (
          <article
            key={card.id}
            className={`space-y-1.5 rounded-sm border p-3 ${
              card.highlighted
                ? "border-accent/60 bg-chrome"
                : "border-border bg-chrome"
            }`}
          >
            <SemanticBadge kind={card.badgeKind} labelOverride={card.badgeText} />
            <h3 className="font-mono text-xs font-semibold text-fg">{card.headline}</h3>
            <p className="font-mono text-[11px] text-fg-muted">{card.subline(seats)}</p>
          </article>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3 border-t border-border pt-3">
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Team seats</span>
          <input
            type="number"
            min={1}
            max={500}
            aria-label="Simulation team seats"
            value={seats}
            onChange={(e) => setSeats(Math.max(1, Math.min(500, Number(e.target.value) || 1)))}
            className="min-h-ctrl-sm w-28 rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Monthly API spend (USD)</span>
          <select
            aria-label="Simulation monthly API spend"
            value={String(monthlyApiSpendUsd)}
            onChange={(e) => setMonthlyApiSpendUsd(Number(e.target.value) || 1200)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
          >
            {API_SPEND_OPTIONS.map((amt) => (
              <option key={amt} value={String(amt)}>
                {`$${amt.toLocaleString("en-US")} / mo`}
              </option>
            ))}
          </select>
        </label>

        <Button
          size="sm"
          variant="primary"
          loading={simRunning}
          onClick={() => void handleRunSimulation()}
        >
          Run 5-Persona MiroFish Pricing Check
        </Button>
      </div>

      {simResult ? (
        <div className="space-y-3 border-t border-border pt-3">
          <dl className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Personas supportive"
              value={`${supportiveCount}/${simResult.personas.length}`}
              delta={`${toPct(simResult.supportiveRate)}% vs ${toPct(simResult.legacySupportiveRate)}% legacy`}
            />
            <StatCard
              label="Hidden-fee distrust"
              value={simResult.hiddenFeeDistrustScore.toFixed(2)}
            />
            <StatCard
              label="Pro gross margin P50/P95"
              value={`${simResult.proGrossMarginP50Pct.toFixed(1)}% / ${simResult.proGrossMarginP95Pct.toFixed(1)}%`}
            />
            <StatCard
              emphasis
              label="Saved vs 20% proxy tax"
              value={`+$${simResult.proxyTaxSavingsMonthlyUsd}/mo`}
            />
          </dl>

          <ul aria-label="Simulated buyer persona verdicts" className="grid gap-2 md:grid-cols-2">
            {simResult.personas.map((persona) => (
              <li
                key={persona.name}
                className="space-y-1 rounded-sm border border-border bg-chrome p-2.5 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <div>
                    <span className="font-semibold text-fg">{persona.name}</span>
                    <span className="text-fg-muted">{` · ${persona.role}`}</span>
                  </div>
                  <SemanticBadge
                    kind={persona.stance === "supportive" ? "passed" : "reconfirm"}
                    labelOverride={persona.stance === "supportive" ? "Supportive" : "Skeptical"}
                  />
                </div>
                <div className="font-mono text-[11px] text-accent">
                  {`Recommended: ${persona.recommendedTier}`}
                </div>
                <p className="text-[11px] text-fg-muted">{persona.rationale}</p>
              </li>
            ))}
          </ul>

          <div
            role="status"
            className="rounded-sm border border-border-strong bg-canvas px-3 py-2 font-mono text-xs text-fg"
          >
            {simResult.reportSummary}
          </div>
        </div>
      ) : null}
    </section>
  );
}
