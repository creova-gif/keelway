import React, { useEffect, useRef, useState } from "react";
import { SettingsPanelHeader } from "@/components/screens/settings/SettingsPanelHeader";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  fetchGovernancePolicy,
  fetchSettlementSummary,
  fetchSubscriptionTiers,
} from "@/lib/api";
import { SUBSCRIPTION_TIERS } from "@/lib/platformData";
import type {
  BackendTierSpec,
  SettlementSummary,
  SubscriptionTierId,
  TenantGovernancePolicy,
} from "@/lib/types";

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value % 1_000_000 === 0 ? 0 : 1)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`;
  return String(value);
}

function priceLabelFor(tier: BackendTierSpec): string {
  if (tier.monthlyPriceUsd == null) return tier.pricingLabel ?? "Custom";
  if (tier.monthlyPriceUsd === 0) return "$0 / mo";
  const annual = tier.annualMonthlyPriceUsd;
  return annual != null && annual !== tier.monthlyPriceUsd
    ? `$${tier.monthlyPriceUsd} / mo · $${annual} annual`
    : `$${tier.monthlyPriceUsd} / mo`;
}

export interface SettingsBillingPanelProps {
  subscriptionTier: SubscriptionTierId;
  onChangeSubscriptionTier?: (tier: SubscriptionTierId) => void;
  fetchTiersFn?: () => Promise<BackendTierSpec[]>;
  fetchPolicyFn?: () => Promise<TenantGovernancePolicy>;
  fetchSettlementFn?: () => Promise<SettlementSummary>;
}

export function SettingsBillingPanel({
  subscriptionTier,
  onChangeSubscriptionTier,
  fetchTiersFn = fetchSubscriptionTiers,
  fetchPolicyFn = fetchGovernancePolicy,
  fetchSettlementFn = fetchSettlementSummary,
}: SettingsBillingPanelProps) {
  const [tiers, setTiers] = useState<BackendTierSpec[] | null>(null);
  const [policy, setPolicy] = useState<TenantGovernancePolicy | null>(null);
  const [settlement, setSettlement] = useState<SettlementSummary | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    Promise.allSettled([fetchTiersFn(), fetchPolicyFn(), fetchSettlementFn()]).then(
      ([tiersRes, policyRes, settlementRes]) => {
        if (!mountedRef.current) return;
        if (tiersRes.status === "fulfilled") setTiers(tiersRes.value);
        if (policyRes.status === "fulfilled") setPolicy(policyRes.value);
        if (settlementRes.status === "fulfilled") setSettlement(settlementRes.value);
        if (tiersRes.status === "rejected" && policyRes.status === "rejected") {
          setLoadError("Billing sources unreachable — showing cached tier specs only.");
        }
      },
    );
    return () => {
      mountedRef.current = false;
    };
  }, [fetchTiersFn, fetchPolicyFn, fetchSettlementFn]);

  const currentMeta = SUBSCRIPTION_TIERS[subscriptionTier];
  const currentSpec = tiers?.find((t) => t.id === subscriptionTier);
  const monthlyPct =
    policy && policy.monthlyBudgetUsd > 0
      ? Math.min(100, Math.round((policy.currentSpendUsd / policy.monthlyBudgetUsd) * 100))
      : null;
  const isOverCap =
    !!policy && policy.currentSpendUsd >= policy.monthlyBudgetUsd && policy.monthlyBudgetUsd > 0;
  const isWarnSpend = !isOverCap && monthlyPct != null && monthlyPct >= (policy?.warnThresholdPct ?? 80);

  return (
    <div className="space-y-5 text-ui text-fg">
      <SettingsPanelHeader
        title="Plan & Billing"
        status={`${currentMeta.badgeLabel} · active`}
        purpose={
          <>
            Tiers map to governance ceilings, not marketing claims. Usage is measured from the
            cost ledger; projections are always labeled. Tier selection sets your quota ceiling —
            enforcement is local and fail-closed.
          </>
        }
      />
      {loadError ? (
        <p role="status" className="rounded-sm border border-warning bg-warning-subtle px-3 py-2 text-xs text-fg">
          {loadError}
        </p>
      ) : null}

      <section aria-label="Current plan" className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[15px] font-medium text-fg">Current plan</h3>
          <span className="font-mono text-[11px] text-fg-dim">{currentMeta.priceLabel}</span>
        </div>
        <div className="rounded-sm border border-border-strong bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="text-sm font-semibold text-fg">{currentMeta.title}</span>
              <SemanticBadge kind="live" detail={currentMeta.badgeLabel} />
            </div>
            {currentSpec?.streamKind ? (
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-[10px] text-fg-dim">
                {currentSpec.streamKind}
              </code>
            ) : null}
          </div>
          <p className="mt-2 text-xs leading-5 text-fg-muted">{currentMeta.summary}</p>
          {currentSpec?.consumerSubscriptionNotice ? (
            <p className="mt-2 rounded-xs border border-warning bg-warning-subtle px-2.5 py-1.5 text-[11px] leading-4 text-fg">
              {currentSpec.consumerSubscriptionNotice}
            </p>
          ) : null}
        </div>
      </section>

      <section aria-label="Available tiers" className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[15px] font-medium text-fg">Tiers — quota ceilings</h3>
          <span className="font-mono text-[11px] text-fg-dim">
            {tiers ? `${tiers.length} tiers · from /v1/subscriptions/tiers` : "specs cached"}
          </span>
        </div>
        <div className="grid gap-2.5 md:grid-cols-2">
          {(tiers ?? []).map((tier) => {
            const isCurrent = tier.id === subscriptionTier;
            const meta = SUBSCRIPTION_TIERS[tier.id as SubscriptionTierId];
            return (
              <div
                key={tier.id}
                aria-current={isCurrent ? "true" : undefined}
                className={`flex flex-col gap-2 rounded-sm border p-3 ${
                  isCurrent ? "border-teal-accent bg-surface" : "border-border bg-canvas"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-fg">{tier.name}</span>
                  {isCurrent ? (
                    <span className="rounded-xs border border-teal-accent/50 bg-teal-surface px-1.5 py-0.5 font-mono text-[10px] text-teal-accent">
                      current
                    </span>
                  ) : null}
                </div>
                <div className="font-mono text-[11px] text-fg-muted">{priceLabelFor(tier)}</div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-fg-muted">
                  <div className="flex justify-between gap-1">
                    <dt>Daily tokens</dt>
                    <dd className="font-mono tabular-nums text-fg">
                      {formatTokens(tier.dailyOpenWeightTokens)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-1">
                    <dt>RPM</dt>
                    <dd className="font-mono tabular-nums text-fg">{tier.rpmLimit}</dd>
                  </div>
                  <div className="flex justify-between gap-1">
                    <dt>Agents</dt>
                    <dd className="font-mono tabular-nums text-fg">{tier.maxConcurrentAgents}</dd>
                  </div>
                  <div className="flex justify-between gap-1">
                    <dt>Workflows</dt>
                    <dd className="font-mono tabular-nums text-fg">
                      {formatTokens(tier.maxActiveWorkflows)}
                    </dd>
                  </div>
                </dl>
                {meta ? <p className="text-[11px] leading-4 text-fg-dim">{meta.summary}</p> : null}
                {!isCurrent && onChangeSubscriptionTier ? (
                  <button
                    type="button"
                    onClick={() => onChangeSubscriptionTier(tier.id as SubscriptionTierId)}
                    className="mt-auto inline-flex min-h-ctrl-sm items-center justify-center self-start rounded-xs border border-border-control bg-surface px-2.5 text-xs font-medium text-fg transition-colors duration-fast ease-state hover:bg-surface-elevated"
                  >
                    Switch to {meta?.badgeLabel ?? tier.name}
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      <section aria-label="Usage — measured from cost ledger" className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[15px] font-medium text-fg">Usage</h3>
          <span className="font-mono text-[11px] text-fg-dim">measured from the cost ledger</span>
        </div>
        {policy ? (
          <div className="space-y-2.5">
            <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-fg">Daily USD Spend</span>
                <span className="font-mono font-semibold tabular-nums text-fg">
                  {`$${(policy.dailySpendUsd ?? 0).toFixed(2)} / $${(policy.dailyBudgetUsd ?? 0).toFixed(2)}`}
                </span>
              </div>
              <div
                role="progressbar"
                aria-label="Billing daily USD spend"
                aria-valuenow={Number((policy.dailySpendUsd ?? 0).toFixed(2))}
                aria-valuemin={0}
                aria-valuemax={Math.max(1, policy.dailyBudgetUsd ?? 0)}
                className="h-2 w-full overflow-hidden rounded-xs border border-border bg-chrome"
              >
                <div
                  className="h-full bg-teal-accent transition-all duration-base ease-settle"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round(((policy.dailySpendUsd ?? 0) / Math.max(1, policy.dailyBudgetUsd ?? 0)) * 100),
                    )}%`,
                  }}
                />
              </div>
            </div>
            <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-fg">Monthly USD Spend</span>
                <span className="font-mono font-semibold tabular-nums text-fg">
                  {`$${policy.currentSpendUsd.toFixed(2)} / $${policy.monthlyBudgetUsd.toFixed(2)}`}
                </span>
              </div>
              <div
                role="progressbar"
                aria-label="Billing monthly USD spend"
                aria-valuenow={Number(policy.currentSpendUsd.toFixed(2))}
                aria-valuemin={0}
                aria-valuemax={Math.max(1, policy.monthlyBudgetUsd)}
                className="h-2 w-full overflow-hidden rounded-xs border border-border bg-chrome"
              >
                <div
                  className={`h-full transition-all duration-base ease-settle ${
                    isOverCap ? "bg-danger" : isWarnSpend ? "bg-warning" : "bg-teal-accent"
                  }`}
                  style={{ width: `${monthlyPct ?? 0}%` }}
                />
              </div>
            </div>
            <p className="text-[11px] leading-4 text-fg-dim">
              Budget caps are edited under Governance &amp; Keys — this panel is read-only
              measurement.
            </p>
          </div>
        ) : (
          <p className="rounded-sm border border-border bg-canvas px-3 py-2 text-xs text-fg-muted">
            Usage unavailable — cost ledger endpoint unreachable.
          </p>
        )}
      </section>

      <section aria-label="Settlement ledger" className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[15px] font-medium text-fg">Settlement</h3>
          <span className="font-mono text-[11px] text-fg-dim">
            {settlement?.receiptSigned ? "receipt-signed" : "unsigned"}
          </span>
        </div>
        {settlement && settlement.count > 0 ? (
          <dl className="grid grid-cols-3 gap-2.5">
            {[
              { label: "Gross", value: settlement.grossUsd },
              { label: "Creator payout", value: settlement.creatorPayoutUsd },
              { label: "Platform fee", value: settlement.platformFeeUsd },
            ].map((row) => (
              <div key={row.label} className="rounded-sm border border-border bg-canvas p-3">
                <dt className="text-[11px] text-fg-muted">{row.label}</dt>
                <dd className="mt-1 font-mono text-sm font-semibold tabular-nums text-fg">
                  ${row.value.toFixed(2)}
                </dd>
              </div>
            ))}
            <p className="col-span-3 text-[11px] leading-4 text-fg-dim">
              {settlement.count} settlement{settlement.count === 1 ? "" : "s"} — SHA-256
              receipt-verified, payout + fee reconciles to gross.
            </p>
          </dl>
        ) : (
          <p className="rounded-sm border border-border bg-canvas px-3 py-2 text-xs text-fg-muted">
            No marketplace settlements yet — purchases appear here with SHA-256 receipts.
          </p>
        )}
      </section>
    </div>
  );
}
