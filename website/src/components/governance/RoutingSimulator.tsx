"use client";

import React, { useMemo, useState } from "react";
import * as Switch from "@radix-ui/react-switch";
import {
  AlertOctagon,
  CheckCircle2,
  Cpu,
  Globe2,
  Lock,
  ShieldAlert,
  TrendingDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

type ResidencyZone =
  | "global"
  | "africa_sovereign"
  | "eu_sovereign"
  | "local_only";

type FrontierBaseline = "claude_sonnet" | "gpt_4o" | "gemini_flash";

interface BaselineRate {
  id: FrontierBaseline;
  label: string;
  blendedUsdPerMtok: number; // Blended 75% input / 25% output per 1M tokens
}

const BASELINES: BaselineRate[] = [
  {
    id: "claude_sonnet",
    label: "Claude 3.5 Sonnet ($6.00/1M blended)",
    blendedUsdPerMtok: 6.0,
  },
  {
    id: "gpt_4o",
    label: "OpenAI GPT-4o ($4.38/1M blended)",
    blendedUsdPerMtok: 4.375,
  },
  {
    id: "gemini_flash",
    label: "Gemini 3.5 Flash ($0.26/1M blended)",
    blendedUsdPerMtok: 0.2625,
  },
];

const RESIDENCY_OPTIONS: {
  id: ResidencyZone;
  label: string;
  desc: string;
}[] = [
  {
    id: "global",
    label: "Global Hybrid",
    desc: "Local OpenCore + authorized commercial APIs",
  },
  {
    id: "africa_sovereign",
    label: "Africa Sovereign",
    desc: "Regional VPC GPU + Swahili/Yoruba/Hausa/Amharic LoRA",
  },
  {
    id: "eu_sovereign",
    label: "EU Sovereign (GDPR)",
    desc: "EU-pinned boundary + strict PII redaction",
  },
  {
    id: "local_only",
    label: "Air-Gapped Local Only",
    desc: "100% loopback Metal/CUDA — zero external sockets",
  },
];

function formatUsd(val: number): string {
  if (val >= 1000) {
    return `$${val.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}`;
  }
  return `$${val.toFixed(2)}`;
}

/**
 * Interactive 4D Hybrid Routing & Monthly Cost Arbitrage Simulator.
 * Demonstrates Layer 5 (`POST /v1/routing/explain`) and Layer 6 (`TenantPolicy`)
 * invariants in real time.
 */
export function RoutingSimulator() {
  const [monthlyMtok, setMonthlyMtok] = useState<number>(250); // 250M tokens/month
  const [residency, setResidency] = useState<ResidencyZone>("global");
  const [privacyPrivate, setPrivacyPrivate] = useState<boolean>(false);
  const [localOffloadPct, setLocalOffloadPct] = useState<number>(80);
  const [fallbackToOpenCore, setFallbackToOpenCore] = useState<boolean>(true);
  const [monthlyCapUsd, setMonthlyCapUsd] = useState<number>(250);
  const [baselineId, setBaselineId] =
    useState<FrontierBaseline>("claude_sonnet");

  const forceZeroEgress = residency === "local_only" || privacyPrivate;
  const effectiveLocalPct = forceZeroEgress ? 100 : localOffloadPct;

  const baseline =
    BASELINES.find((b) => b.id === baselineId) ?? BASELINES[0];

  const metrics = useMemo(() => {
    const allCloudCost = monthlyMtok * baseline.blendedUsdPerMtok;
    const cloudFraction = (100 - effectiveLocalPct) / 100;
    const rawHybridCloudCost =
      monthlyMtok * cloudFraction * baseline.blendedUsdPerMtok;

    const capTriggered =
      !forceZeroEgress && rawHybridCloudCost > monthlyCapUsd;

    const billedHybridCost = capTriggered
      ? monthlyCapUsd
      : rawHybridCloudCost;

    const monthlySavings = Math.max(0, allCloudCost - billedHybridCost);
    const savingsPct =
      allCloudCost > 0
        ? Math.min(100, (monthlySavings / allCloudCost) * 100)
        : 100;

    // 4D Provenance Resolution
    const primaryModel = forceZeroEgress
      ? "keelway-core:7b"
      : effectiveLocalPct >= 50
      ? "keelway-coder:7b + gemini-3.5-flash"
      : baselineId === "claude_sonnet"
      ? "claude-3-5-sonnet"
      : baselineId === "gpt_4o"
      ? "gpt-4o"
      : "gemini-3.5-flash";

    const provenance = {
      model_license: forceZeroEgress
        ? "open_weight_permissive (Apache-2.0)"
        : effectiveLocalPct === 0
        ? "commercial_proprietary"
        : "hybrid (Apache-2.0 + Commercial Opt-In)",
      hosting_topology:
        residency === "local_only"
          ? "local_loopback (127.0.0.1)"
          : forceZeroEgress
          ? "sovereign_self_hosted_gpu"
          : "hybrid_local_and_managed_cloud",
      operator_control: forceZeroEgress
        ? "100% tenant_operated"
        : "tenant_primary + governed_upstream",
      data_boundary: forceZeroEgress
        ? "zero_external_egress (0 bytes)"
        : residency === "africa_sovereign"
        ? "africa_sovereign_vpc + redacted_tls"
        : residency === "eu_sovereign"
        ? "eu_gdpr_boundary + redacted_tls"
        : "redacted_tls_egress",
      budget_outcome: forceZeroEgress
        ? "allow ($0.00 sovereign)"
        : !capTriggered
        ? "allow (within monthly cap)"
        : fallbackToOpenCore
        ? "downgrade_opencore -> keelway-core:7b ($0.00)"
        : "deny -> HTTP 402 BudgetExceededError",
    };

    return {
      allCloudCost,
      rawHybridCloudCost,
      billedHybridCost,
      monthlySavings,
      annualSavings: monthlySavings * 12,
      savingsPct,
      capTriggered,
      primaryModel,
      provenance,
    };
  }, [
    monthlyMtok,
    baseline,
    effectiveLocalPct,
    forceZeroEgress,
    monthlyCapUsd,
    residency,
    fallbackToOpenCore,
    baselineId,
  ]);

  return (
    <section
      aria-labelledby="sim-heading"
      className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 shadow-xl sm:p-8"
    >
      <div className="flex flex-col justify-between gap-4 border-b border-border-subtle pb-6 lg:flex-row lg:items-end">
        <div>
          <span className="chip-teal inline-block rounded-sm px-2.5 py-1">
            INTERACTIVE 4D ROUTER &amp; ARBITRAGE SIMULATOR
          </span>
          <h2
            id="sim-heading"
            className="mt-3 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
          >
            Simulate Tenant Policy, Data Boundary &amp; Monthly Spend Savings
          </h2>
          <p className="mt-1.5 max-w-2xl text-sm text-fg-muted">
            Open-weight does not automatically mean local. Keelway evaluates{" "}
            <strong className="text-fg">four independent provenance axes</strong>{" "}
            on every call so sensitive code never leaks across an unauthorized
            boundary.
          </p>
        </div>

        <div className="w-full lg:w-72">
          <label
            htmlFor="baseline-select"
            className="block font-mono text-[11px] uppercase text-fg-muted"
          >
            Compare Against All-Cloud Baseline
          </label>
          <select
            id="baseline-select"
            value={baselineId}
            onChange={(e) =>
              setBaselineId(e.target.value as FrontierBaseline)
            }
            className="mt-1 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3 font-mono text-xs text-fg"
          >
            {BASELINES.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* ================================================================
            LEFT CONTROLS: Workload, Residency, Privacy, Spend Cap
            ================================================================ */}
        <div className="space-y-6 lg:col-span-6">
          {/* 1. Monthly Token Volume Slider */}
          <div>
            <div className="flex items-center justify-between font-mono text-xs">
              <label htmlFor="volume-slider" className="font-semibold text-fg">
                1. Monthly Token Volume
              </label>
              <span className="font-bold tabular-nums text-teal-accent">
                {monthlyMtok >= 1000
                  ? `${(monthlyMtok / 1000).toFixed(2)}B tokens/mo`
                  : `${monthlyMtok}M tokens/mo`}
              </span>
            </div>
            <input
              id="volume-slider"
              type="range"
              min={10}
              max={2000}
              step={10}
              value={monthlyMtok}
              onChange={(e) => {
                setMonthlyMtok(Number(e.target.value));
                trackEvent("routing_simulator_updated", {
                  control: "monthly_mtok",
                });
              }}
              className="mt-2 h-2 w-full cursor-pointer accent-[#2DD4BF]"
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[25, 100, 250, 500, 1000, 2000].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setMonthlyMtok(preset)}
                  className={cn(
                    "min-h-[34px] rounded-sm border px-2.5 font-mono text-[11px] transition-colors duration-150",
                    monthlyMtok === preset
                      ? "border-teal-accent bg-teal-surface text-teal-accent"
                      : "border-border-subtle bg-canvas text-fg-muted hover:text-fg"
                  )}
                >
                  {preset >= 1000 ? `${preset / 1000}B` : `${preset}M`}
                </button>
              ))}
            </div>
          </div>

          {/* 2. Data Residency Zone */}
          <div>
            <span className="block font-mono text-xs font-semibold text-fg">
              2. Tenant Data Residency Zone (<code>residency_zone</code>)
            </span>
            <div
              role="radiogroup"
              aria-label="Data residency zone"
              className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2"
            >
              {RESIDENCY_OPTIONS.map((zone) => {
                const active = residency === zone.id;
                return (
                  <button
                    key={zone.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => {
                      setResidency(zone.id);
                      trackEvent("routing_simulator_updated", {
                        residency: zone.id,
                      });
                    }}
                    className={cn(
                      "min-h-[58px] rounded-md border p-3 text-left transition-colors duration-150",
                      active
                        ? "border-teal-accent bg-surface-elevated"
                        : "border-border-subtle bg-canvas hover:border-border-strong"
                    )}
                  >
                    <div className="font-mono text-xs font-bold text-fg">
                      {zone.label}
                    </div>
                    <div className="mt-0.5 text-[11px] text-fg-muted">
                      {zone.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. OpenCore Local Offload Slider */}
          <div>
            <div className="flex items-center justify-between font-mono text-xs">
              <label htmlFor="offload-slider" className="font-semibold text-fg">
                3. OpenCore Local Worker Offload
              </label>
              <span className="font-bold tabular-nums text-teal-accent">
                {effectiveLocalPct}% Local · {100 - effectiveLocalPct}% Cloud
              </span>
            </div>
            <input
              id="offload-slider"
              type="range"
              min={0}
              max={100}
              step={5}
              disabled={forceZeroEgress}
              value={effectiveLocalPct}
              onChange={(e) => setLocalOffloadPct(Number(e.target.value))}
              className="mt-2 h-2 w-full cursor-pointer accent-[#2DD4BF] disabled:opacity-50"
            />
            {forceZeroEgress && (
              <p className="mt-1 font-mono text-[11px] text-teal-accent">
                Locked to 100% local execution because zero-egress policy is
                active.
              </p>
            )}
          </div>

          {/* 4. Policy Switches & Spend Ceiling */}
          <div className="space-y-3 rounded-md border border-border-subtle bg-canvas p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <label
                  htmlFor="privacy-switch"
                  className="font-mono text-xs font-semibold text-fg"
                >
                  Request <code>privacy_level=&quot;private&quot;</code>
                </label>
                <p className="text-[11px] text-fg-muted">
                  Fail-closed: blocks all commercial cloud adapters immediately.
                </p>
              </div>
              <Switch.Root
                id="privacy-switch"
                checked={privacyPrivate}
                onCheckedChange={setPrivacyPrivate}
                className={cn(
                  "relative h-7 w-12 shrink-0 rounded-full border border-border-strong transition-colors duration-150",
                  privacyPrivate ? "bg-teal-accent" : "bg-surface-elevated"
                )}
              >
                <Switch.Thumb
                  className={cn(
                    "block h-5 w-5 translate-x-0.5 rounded-full transition-transform duration-150",
                    privacyPrivate
                      ? "translate-x-6 bg-teal-ink"
                      : "bg-fg-muted"
                  )}
                />
              </Switch.Root>
            </div>

            <div className="flex items-center justify-between gap-4 border-t border-border-subtle pt-3">
              <div>
                <label
                  htmlFor="fallback-switch"
                  className="font-mono text-xs font-semibold text-fg"
                >
                  Auto-Downgrade to OpenCore on Spend Cap
                </label>
                <p className="text-[11px] text-fg-muted">
                  When off, exceeding{" "}
                  <strong className="text-fg">${monthlyCapUsd}/mo</strong> raises
                  strict <code>HTTP 402</code>.
                </p>
              </div>
              <Switch.Root
                id="fallback-switch"
                checked={fallbackToOpenCore}
                onCheckedChange={setFallbackToOpenCore}
                className={cn(
                  "relative h-7 w-12 shrink-0 rounded-full border border-border-strong transition-colors duration-150",
                  fallbackToOpenCore ? "bg-teal-accent" : "bg-amber-alert"
                )}
              >
                <Switch.Thumb
                  className={cn(
                    "block h-5 w-5 translate-x-0.5 rounded-full transition-transform duration-150",
                    fallbackToOpenCore
                      ? "translate-x-6 bg-teal-ink"
                      : "bg-amber-ink"
                  )}
                />
              </Switch.Root>
            </div>

            <div className="border-t border-border-subtle pt-3">
              <div className="flex items-center justify-between font-mono text-xs">
                <label htmlFor="cap-slider" className="text-fg-muted">
                  Tenant Monthly Cloud Spend Cap:
                </label>
                <span className="font-bold tabular-nums text-fg">
                  ${monthlyCapUsd} / mo
                </span>
              </div>
              <input
                id="cap-slider"
                type="range"
                min={50}
                max={2000}
                step={50}
                value={monthlyCapUsd}
                onChange={(e) => setMonthlyCapUsd(Number(e.target.value))}
                className="mt-1.5 h-2 w-full cursor-pointer accent-[#F5B547]"
              />
            </div>
          </div>
        </div>

        {/* ================================================================
            RIGHT OUTPUT: Savings Telemetry + 4D Provenance Verdict
            ================================================================ */}
        <div
          aria-live="polite"
          className="flex flex-col justify-between space-y-5 lg:col-span-6"
        >
          {/* Savings Summary Cards */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-border-strong bg-canvas p-4">
              <div className="font-mono text-[10px] uppercase text-fg-muted">
                All-Cloud Spend
              </div>
              <div className="mt-1 font-mono text-xl font-bold tabular-nums text-fg-muted line-through">
                {formatUsd(metrics.allCloudCost)}
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-fg-dim">
                per month
              </div>
            </div>

            <div className="rounded-md border border-teal-accent bg-canvas p-4">
              <div className="font-mono text-[10px] uppercase text-teal-accent">
                Keelway Hybrid Spend
              </div>
              <div className="mt-1 font-mono text-xl font-bold tabular-nums text-fg">
                {formatUsd(metrics.billedHybridCost)}
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-teal-accent">
                {metrics.savingsPct.toFixed(1)}% cost reduction
              </div>
            </div>

            <div className="rounded-md border border-border-strong bg-teal-surface p-4">
              <div className="flex items-center gap-1 font-mono text-[10px] uppercase text-teal-accent">
                <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Annual Savings</span>
              </div>
              <div className="mt-1 font-mono text-xl font-bold tabular-nums text-fg">
                {formatUsd(metrics.annualSavings)}
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-fg-muted">
                retained per year
              </div>
            </div>
          </div>

          {/* Budget Cap Alert Banner when Triggered */}
          {metrics.capTriggered && (
            <div
              className={cn(
                "flex items-start gap-2.5 rounded-md border p-3.5 font-mono text-xs",
                fallbackToOpenCore
                  ? "border-teal-accent/60 bg-teal-surface text-fg"
                  : "border-fault/60 bg-fault-surface text-fg"
              )}
            >
              {fallbackToOpenCore ? (
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
              ) : (
                <AlertOctagon
                  className="mt-0.5 h-4 w-4 shrink-0 text-fault"
                  aria-hidden="true"
                />
              )}
              <div>
                <strong>
                  Cloud demand ({formatUsd(metrics.rawHybridCloudCost)}) hit the
                  ${monthlyCapUsd}/mo tenant ceiling:
                </strong>{" "}
                {fallbackToOpenCore
                  ? "Overflow requests seamlessly downgraded to local keelway-core:7b ($0.00) with zero downtime."
                  : "Strict fail-closed policy active — overflow cloud requests rejected with HTTP 402 BudgetExceededError."}
              </div>
            </div>
          )}

          {/* 4-Dimension Provenance Matrix */}
          <div className="rounded-md border border-border-strong bg-canvas p-4">
            <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
              <span className="font-mono text-xs font-bold text-fg">
                4-Dimension Routing Provenance (POST /v1/routing/explain)
              </span>
              <span className="chip-neutral rounded-sm px-2 py-0.5">
                {metrics.primaryModel}
              </span>
            </div>

            <dl className="mt-3 grid grid-cols-1 gap-2.5 font-mono text-xs sm:grid-cols-2">
              <div className="rounded border border-border-subtle bg-surface p-2.5">
                <dt className="flex items-center gap-1.5 text-[10px] uppercase text-fg-muted">
                  <Cpu className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
                  1. Model License
                </dt>
                <dd className="mt-1 font-semibold text-fg">
                  {metrics.provenance.model_license}
                </dd>
              </div>

              <div className="rounded border border-border-subtle bg-surface p-2.5">
                <dt className="flex items-center gap-1.5 text-[10px] uppercase text-fg-muted">
                  <Globe2
                    className="h-3.5 w-3.5 text-teal-accent"
                    aria-hidden="true"
                  />
                  2. Hosting Topology
                </dt>
                <dd className="mt-1 font-semibold text-fg">
                  {metrics.provenance.hosting_topology}
                </dd>
              </div>

              <div className="rounded border border-border-subtle bg-surface p-2.5">
                <dt className="flex items-center gap-1.5 text-[10px] uppercase text-fg-muted">
                  <ShieldAlert
                    className="h-3.5 w-3.5 text-teal-accent"
                    aria-hidden="true"
                  />
                  3. Operator Control
                </dt>
                <dd className="mt-1 font-semibold text-fg">
                  {metrics.provenance.operator_control}
                </dd>
              </div>

              <div className="rounded border border-border-subtle bg-surface p-2.5">
                <dt className="flex items-center gap-1.5 text-[10px] uppercase text-fg-muted">
                  <Lock className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
                  4. Data Boundary
                </dt>
                <dd className="mt-1 font-semibold text-teal-accent">
                  {metrics.provenance.data_boundary}
                </dd>
              </div>
            </dl>

            <pre className="mt-3 overflow-x-auto rounded border border-border-subtle bg-surface/70 p-3 font-mono text-[11px] leading-relaxed text-fg-muted">
              {JSON.stringify(
                {
                  residency_zone: residency,
                  privacy_level: privacyPrivate ? "private" : "standard",
                  audit_outcome: metrics.provenance.budget_outcome,
                },
                null,
                2
              )}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
