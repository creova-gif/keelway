import React, { useEffect, useId, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  fetchGovernancePersistence,
  fetchGovernancePolicy,
  fetchSbom,
  fetchScopedKeys,
  mintScopedKey,
  updateGovernancePolicy,
} from "@/lib/api";
import type {
  DataResidencyZone,
  GovernancePersistenceInfo,
  MintedScopedApiKeyResult,
  ScopedApiKeyItem,
  TenantGovernancePolicy,
} from "@/lib/types";

export interface SettingsGovernancePanelProps {
  fetchPersistenceFn?: typeof fetchGovernancePersistence;
  fetchPolicyFn?: typeof fetchGovernancePolicy;
  updatePolicyFn?: typeof updateGovernancePolicy;
  fetchKeysFn?: typeof fetchScopedKeys;
  mintKeyFn?: typeof mintScopedKey;
  fetchSbomFn?: typeof fetchSbom;
}

const DEFAULT_POLICY: TenantGovernancePolicy = {
  tenantId: "default",
  name: "Local Sovereign Workspace",
  residencyZone: "local_only",
  monthlyBudgetUsd: 50.0,
  currentSpendUsd: 12.4,
  warnThresholdPct: 80,
  hardCapEnforced: true,
  fallbackToOpencoreOnBudgetExceeded: true,
  fallbackModelId: "keelway-core:7b",
  requireHumanApprovalForNetwork: true,
  updatedAt: "2026-11-14T02:00:00Z",
};

const RESIDENCY_OPTIONS: ReadonlyArray<{ value: DataResidencyZone; label: string }> = [
  { value: "local_only", label: "Local machine only (127.0.0.1 loopback)" },
  { value: "africa_sovereign", label: "Africa Sovereign Enclave (africa_sovereign)" },
  { value: "eu_sovereign", label: "EU Sovereign Enclave (eu_sovereign)" },
  { value: "global", label: "Global Multi-Region (policy-gated)" },
];

const AVAILABLE_SCOPES = ["audit:read", "models:read", "routing:explain", "eval:run"] as const;

export function SettingsGovernancePanel({
  fetchPersistenceFn = fetchGovernancePersistence,
  fetchPolicyFn = fetchGovernancePolicy,
  updatePolicyFn = updateGovernancePolicy,
  fetchKeysFn = fetchScopedKeys,
  mintKeyFn = mintScopedKey,
  fetchSbomFn = fetchSbom,
}: SettingsGovernancePanelProps): React.JSX.Element {
  const [persistence, setPersistence] = useState<GovernancePersistenceInfo | null>(null);
  const [policy, setPolicy] = useState<TenantGovernancePolicy>(DEFAULT_POLICY);
  const [budgetDraft, setBudgetDraft] = useState("50");
  const [dlpRedaction, setDlpRedaction] = useState(true);
  const [keys, setKeys] = useState<ScopedApiKeyItem[]>([]);
  const [sbomInfo, setSbomInfo] = useState<{
    spdxVersion: string;
    packagesCount: number;
    generatedAt: string;
    zeroCdnVerified: boolean;
  } | null>(null);
  const [loadingSbom, setLoadingSbom] = useState(false);

  // Mint Scoped Key Modal State
  const [mintOpen, setMintOpen] = useState(false);
  const [keyLabel, setKeyLabel] = useState("ci-scoped-verifier");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["audit:read", "models:read"]);
  const [keySpendCap, setKeySpendCap] = useState(25);
  const [minting, setMinting] = useState(false);
  const [mintedResult, setMintedResult] = useState<MintedScopedApiKeyResult | null>(null);
  const [savedKeyChecked, setSavedKeyChecked] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);

  const residencySelectId = useId();
  const dlpCheckboxId = useId();
  const budgetInputId = useId();
  const fallbackCheckboxId = useId();
  const mintDescId = useId();
  const keyLabelId = useId();
  const keyCapId = useId();
  const savedKeyId = useId();
  const doneHelperId = useId();

  const fetchPersistenceRef = useRef(fetchPersistenceFn);
  fetchPersistenceRef.current = fetchPersistenceFn;
  const fetchPolicyRef = useRef(fetchPolicyFn);
  fetchPolicyRef.current = fetchPolicyFn;
  const fetchKeysRef = useRef(fetchKeysFn);
  fetchKeysRef.current = fetchKeysFn;

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchPersistenceRef.current(),
      fetchPolicyRef.current(),
      fetchKeysRef.current(),
    ])
      .then(([pers, pol, loadedKeys]) => {
        if (cancelled) return;
        setPersistence(pers);
        setPolicy(pol);
        setBudgetDraft(String(pol.monthlyBudgetUsd));
        setKeys(loadedKeys);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const handleResidencyChange = async (nextZone: DataResidencyZone) => {
    setPolicy((prev) => ({ ...prev, residencyZone: nextZone }));
    const updated = await updatePolicyFn({ residencyZone: nextZone });
    setPolicy(updated);
  };

  const handleBudgetUpdate = async (event: React.FormEvent) => {
    event.preventDefault();
    const numeric = Math.max(0, Number(budgetDraft) || 0);
    setPolicy((prev) => ({ ...prev, monthlyBudgetUsd: numeric }));
    const updated = await updatePolicyFn({ monthlyBudgetUsd: numeric });
    setPolicy(updated);
    setBudgetDraft(String(updated.monthlyBudgetUsd));
  };

  const handleFallbackToggle = async (checked: boolean) => {
    setPolicy((prev) => ({ ...prev, fallbackToOpencoreOnBudgetExceeded: checked }));
    const updated = await updatePolicyFn({ fallbackToOpencoreOnBudgetExceeded: checked });
    setPolicy(updated);
  };

  const handleInspectSbom = async () => {
    setLoadingSbom(true);
    try {
      const info = await fetchSbomFn();
      setSbomInfo(info);
    } finally {
      setLoadingSbom(false);
    }
  };

  const openMintDialog = () => {
    setKeyLabel("ci-scoped-verifier");
    setSelectedScopes(["audit:read", "models:read"]);
    setKeySpendCap(25);
    setMintedResult(null);
    setSavedKeyChecked(false);
    setCopiedSecret(false);
    setMintOpen(true);
  };

  const closeMintDialogSafely = () => {
    if (mintedResult && !savedKeyChecked) {
      return;
    }
    setMintOpen(false);
    setMintedResult(null);
    setSavedKeyChecked(false);
    setCopiedSecret(false);
  };

  const handleGenerateScopedKey = async (event: React.FormEvent) => {
    event.preventDefault();
    setMinting(true);
    try {
      const scopes = selectedScopes.length > 0 ? selectedScopes : ["audit:read"];
      const res = await mintKeyFn(keyLabel.trim() || "scoped-key", scopes, keySpendCap);
      setMintedResult(res);
      setSavedKeyChecked(false);
      setKeys((prev) => [res.key, ...prev.filter((k) => k.id !== res.key.id)]);
    } finally {
      setMinting(false);
    }
  };

  const handleCopySecret = () => {
    if (!mintedResult) return;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(mintedResult.plaintextSecret).catch(() => {});
    }
    setCopiedSecret(true);
  };

  const spendPct =
    policy.monthlyBudgetUsd > 0
      ? Math.min(100, Math.round((policy.currentSpendUsd / policy.monthlyBudgetUsd) * 100))
      : 100;
  const isOverCap = policy.currentSpendUsd >= policy.monthlyBudgetUsd && policy.monthlyBudgetUsd > 0;
  const isWarnSpend = !isOverCap && spendPct >= policy.warnThresholdPct;

  return (
    <div className="space-y-5 text-ui text-fg">
      <header className="space-y-1 border-b border-border pb-3">
        <h2 className="text-sm font-semibold text-fg">Governance, Tenant Keys &amp; Spend Caps</h2>
        <p className="text-xs text-fg-muted">
          Crash-safe SQLite WAL persistence, sovereign data residency, automatic OpenCore spend-cap fallback, and prefix-only{" "}
          <code dir="ltr" className="unicode-bidi-isolate font-mono">kw_live_*</code> tenant credentials.
        </p>
      </header>

      {/* 1. Crash-Safe Persistence Strip */}
      <section
        aria-label="Governance SQLite persistence"
        className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border-strong bg-surface px-4 py-3 text-xs"
      >
        <div className="flex flex-wrap items-center gap-2.5">
          {persistence?.healthy !== false ? (
            <SemanticBadge kind="passed" labelOverride="SQLite WAL Crash-Safe" />
          ) : (
            <SemanticBadge kind="failed" labelOverride="Persistence degraded" />
          )}
          <span className="font-mono text-fg">
            {`${persistence?.engine ?? "SQLite 3"} · journal=${persistence?.journalMode ?? "WAL"} · sync=${persistence?.synchronous ?? "NORMAL"}`}
          </span>
        </div>
        <code
          dir="ltr"
          className="unicode-bidi-isolate rounded-xs border border-border bg-code px-2 py-0.5 font-mono text-[11px] text-fg-muted"
        >
          {persistence?.dbPath ?? ".keelway/governance.db"}
        </code>
      </section>

      {isOverCap ? (
        <CalloutBanner
          variant="spend-cap"
          title="Monthly cloud spend cap reached"
          description={`Routed automatically to local OpenCore (${policy.fallbackModelId}) at $0.00/tok.`}
        />
      ) : isWarnSpend ? (
        <CalloutBanner
          variant="spend-warn"
          title={`Cloud spend at ${spendPct}% of monthly budget`}
          description="Approaching configured hard cap; local OpenCore fallback stands ready."
        />
      ) : null}

      {/* 2. Data Residency & DLP Policy Card */}
      <section
        aria-label="Data residency and DLP policy"
        className="space-y-3.5 rounded-md border border-border-strong bg-surface p-4"
      >
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
            Data Residency &amp; DLP Policy (<code dir="ltr" className="unicode-bidi-isolate font-mono">/v1/governance/tenants/default</code>)
          </h3>
          <p className="mt-0.5 text-xs text-fg-muted">
            Restricts eligible 4D routing boundaries by jurisdiction and scrubs secrets prior to any approved cloud call.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor={residencySelectId} className="block text-xs font-medium text-fg">
              Data residency zone
            </label>
            <select
              id={residencySelectId}
              value={policy.residencyZone}
              onChange={(e) => {
                const match = RESIDENCY_OPTIONS.find((o) => o.value === e.target.value);
                if (match) void handleResidencyChange(match.value);
              }}
              className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
            >
              {RESIDENCY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2.5 rounded-sm border border-border bg-canvas px-3 py-2">
            <input
              id={dlpCheckboxId}
              type="checkbox"
              checked={dlpRedaction}
              onChange={(e) => setDlpRedaction(e.target.checked)}
              className="h-4 w-4 accent-teal-accent"
            />
            <label htmlFor={dlpCheckboxId} className="text-xs text-fg">
              Redact secrets &amp; PII before external egress (DLP pre-flight)
            </label>
          </div>
        </div>
      </section>

      {/* 3. USD Spend Caps, OpenCore Fallback & SBOM */}
      <section
        aria-label="USD spend caps and OpenCore fallback"
        className="space-y-4 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
              USD Spend Caps &amp; OpenCore Fallback
            </h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Hard budget ceiling with zero-downtime fallback to{" "}
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">
                {policy.fallbackModelId}
              </code>{" "}
              ($0.00/tok local loopback).
            </p>
          </div>
          <span className="font-mono text-xs font-semibold tabular-nums text-fg">
            {`$${policy.currentSpendUsd.toFixed(2)} / $${policy.monthlyBudgetUsd.toFixed(2)}`}
          </span>
        </div>

        <div
          role="progressbar"
          aria-label="Monthly USD spend"
          aria-valuenow={Number(policy.currentSpendUsd.toFixed(2))}
          aria-valuemin={0}
          aria-valuemax={Math.max(1, policy.monthlyBudgetUsd)}
          className="h-2.5 w-full overflow-hidden rounded-xs border border-border bg-chrome"
        >
          <div
            className={`h-full transition-all ${
              isOverCap ? "bg-danger" : isWarnSpend ? "bg-warning" : "bg-teal-accent"
            }`}
            style={{ width: `${spendPct}%` }}
          />
        </div>

        <form onSubmit={(e) => void handleBudgetUpdate(e)} className="flex flex-wrap items-end gap-2.5">
          <div className="space-y-1">
            <label htmlFor={budgetInputId} className="block text-xs font-medium text-fg">
              Monthly budget cap ($ USD)
            </label>
            <input
              id={budgetInputId}
              type="number"
              min={0}
              step="any"
              value={budgetDraft}
              onChange={(e) => setBudgetDraft(e.target.value)}
              className="min-h-ctrl-sm w-36 rounded-xs border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs tabular-nums text-fg"
            />
          </div>
          <Button type="submit" size="sm" variant="secondary">
            Update budget
          </Button>
        </form>

        <div className="flex items-center gap-2.5 rounded-sm border border-border bg-canvas px-3 py-2.5">
          <input
            id={fallbackCheckboxId}
            type="checkbox"
            checked={policy.fallbackToOpencoreOnBudgetExceeded}
            onChange={(e) => void handleFallbackToggle(e.target.checked)}
            className="h-4 w-4 accent-teal-accent"
          />
          <label htmlFor={fallbackCheckboxId} className="text-xs text-fg">
            Auto-fallback to local OpenCore when budget exceeded ($0.00/tok local loopback)
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-canvas px-3 py-2 text-xs">
          <div className="space-y-0.5">
            <div className="font-semibold text-fg">Supply-Chain SBOM Verification (<code dir="ltr" className="unicode-bidi-isolate font-mono">/v1/sbom</code>)</div>
            {sbomInfo ? (
              <div className="font-mono text-[11px] text-fg-muted">
                <code dir="ltr" className="unicode-bidi-isolate">{sbomInfo.spdxVersion}</code>
                {` · ${sbomInfo.packagesCount} packages · `}
                {sbomInfo.zeroCdnVerified ? "Zero external CDN assets verified" : "Unverified"}
              </div>
            ) : (
              <div className="text-fg-muted">CycloneDX / SPDX dependency manifest &amp; zero-CDN bundle check.</div>
            )}
          </div>
          <Button size="sm" variant="secondary" loading={loadingSbom} onClick={() => void handleInspectSbom()}>
            Inspect SBOM
          </Button>
        </div>
      </section>

      {/* 4. Scoped kw_live_* Tenant API Keys */}
      <section
        aria-label="Scoped tenant API keys"
        className="space-y-3.5 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
              Scoped Tenant API Keys (<code dir="ltr" className="unicode-bidi-isolate font-mono">kw_live_*</code>)
            </h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Stored as salted SHA-256 digest only — plaintext secret is shown once at creation.
            </p>
          </div>
          <Button size="sm" variant="primary" onClick={openMintDialog}>
            + Mint scoped key
          </Button>
        </div>

        <div className="overflow-x-auto rounded-sm border border-border bg-canvas">
          <table
            aria-label="Scoped tenant API keys"
            className="w-full border-collapse text-start text-xs tabular-nums"
          >
            <thead className="border-b border-border-strong bg-chrome text-fg-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Label</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Key prefix</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Scopes</th>
                <th scope="col" className="px-3 py-2 text-end font-semibold">Spend cap</th>
                <th scope="col" className="px-3 py-2 text-end font-semibold">Spent</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {keys.map((item) => (
                <tr key={item.id} className="min-h-table-row hover:bg-surface-elevated">
                  <td className="px-3 py-2 font-medium text-fg">{item.label}</td>
                  <td className="px-3 py-2 font-mono text-fg-muted">
                    <code dir="ltr" className="unicode-bidi-isolate">{item.prefix}</code>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {item.scopes.map((sc) => (
                        <code
                          key={sc}
                          dir="ltr"
                          className="unicode-bidi-isolate rounded-xs border border-border bg-code px-1.5 py-0.5 font-mono text-[11px] text-fg"
                        >
                          {sc}
                        </code>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-end font-mono text-fg">{`$${item.spendCapUsd.toFixed(2)}`}</td>
                  <td className="px-3 py-2 text-end font-mono text-fg-muted">{`$${item.spentUsd.toFixed(2)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* One-Time Key Reveal Radix Modal */}
      <Dialog.Root
        open={mintOpen}
        onOpenChange={(next) => {
          if (!next) {
            closeMintDialogSafely();
          } else {
            setMintOpen(true);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
          <Dialog.Content
            aria-describedby={mintDescId}
            onEscapeKeyDown={(e) => {
              if (mintedResult && !savedKeyChecked) e.preventDefault();
            }}
            onPointerDownOutside={(e) => {
              if (mintedResult && !savedKeyChecked) e.preventDefault();
            }}
            onInteractOutside={(e) => {
              if (mintedResult && !savedKeyChecked) e.preventDefault();
            }}
            className="fixed start-1/2 top-[12%] z-50 flex w-full max-w-lg -translate-x-1/2 flex-col overflow-hidden rounded-md border border-border-strong bg-surface text-fg shadow-modal rtl:translate-x-1/2"
          >
            <div className="border-b border-border bg-chrome px-4 py-3">
              <Dialog.Title className="text-sm font-semibold text-fg">
                Mint scoped key
              </Dialog.Title>
              <Dialog.Description id={mintDescId} className="mt-0.5 text-xs text-fg-muted">
                {mintedResult
                  ? "One-time secret reveal — copy and confirm before closing."
                  : "Issue a least-privilege tenant key with a dedicated USD spend cap."}
              </Dialog.Description>
            </div>

            {!mintedResult ? (
              <form onSubmit={(e) => void handleGenerateScopedKey(e)} className="space-y-3.5 p-4 text-xs">
                <div className="space-y-1">
                  <label htmlFor={keyLabelId} className="block font-medium text-fg">
                    Key label
                  </label>
                  <input
                    id={keyLabelId}
                    type="text"
                    value={keyLabel}
                    onChange={(e) => setKeyLabel(e.target.value)}
                    className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
                  />
                </div>

                <fieldset className="space-y-1.5">
                  <legend className="font-medium text-fg">Allowed scopes</legend>
                  <div className="grid grid-cols-2 gap-2 rounded-sm border border-border bg-canvas p-2.5">
                    {AVAILABLE_SCOPES.map((scope) => {
                      const checked = selectedScopes.includes(scope);
                      return (
                        <label key={scope} className="flex items-center gap-2 font-mono text-xs text-fg">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              setSelectedScopes((prev) =>
                                e.target.checked
                                  ? [...prev, scope]
                                  : prev.filter((s) => s !== scope),
                              );
                            }}
                            className="h-3.5 w-3.5 accent-teal-accent"
                          />
                          <code dir="ltr" className="unicode-bidi-isolate">{scope}</code>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>

                <div className="space-y-1">
                  <label htmlFor={keyCapId} className="block font-medium text-fg">
                    Spend cap ($ USD)
                  </label>
                  <input
                    id={keyCapId}
                    type="number"
                    min={1}
                    step="any"
                    value={keySpendCap}
                    onChange={(e) => setKeySpendCap(Math.max(1, Number(e.target.value) || 1))}
                    className="min-h-ctrl-sm w-40 rounded-xs border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs tabular-nums text-fg"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button size="sm" variant="ghost" onClick={closeMintDialogSafely}>
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" variant="primary" loading={minting}>
                    Generate scoped key
                  </Button>
                </div>
              </form>
            ) : (
              <div className="space-y-3.5 p-4 text-xs">
                <p className="rounded-sm border border-warning bg-warning-subtle px-3 py-2 text-fg">
                  {mintedResult.oneTimeWarning}
                </p>

                <div className="flex items-center justify-between gap-2 rounded-sm border border-border-strong bg-code p-2.5">
                  <code
                    dir="ltr"
                    data-testid="minted-plaintext-secret"
                    className="unicode-bidi-isolate break-all font-mono text-xs font-semibold text-teal-accent"
                  >
                    {mintedResult.plaintextSecret}
                  </code>
                  <Button size="sm" variant="secondary" onClick={handleCopySecret}>
                    {copiedSecret ? "Copied" : "Copy key"}
                  </Button>
                </div>

                <div className="flex items-center gap-2 rounded-sm border border-border bg-canvas px-3 py-2">
                  <input
                    id={savedKeyId}
                    type="checkbox"
                    checked={savedKeyChecked}
                    onChange={(e) => setSavedKeyChecked(e.target.checked)}
                    className="h-4 w-4 accent-teal-accent"
                  />
                  <label htmlFor={savedKeyId} className="font-medium text-fg">
                    I have saved this key
                  </label>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <span id={doneHelperId} className="text-[11px] text-fg-muted">
                    {savedKeyChecked
                      ? "Secret saved confirmation recorded."
                      : "Confirm you have saved this key before closing"}
                  </span>
                  <Button
                    size="sm"
                    variant="primary"
                    aria-disabled={!savedKeyChecked}
                    aria-describedby={doneHelperId}
                    onClick={() => {
                      if (!savedKeyChecked) return;
                      closeMintDialogSafely();
                    }}
                  >
                    Done
                  </Button>
                </div>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
