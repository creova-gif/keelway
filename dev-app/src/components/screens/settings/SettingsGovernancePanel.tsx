import React, { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { SettingsKeyMintModal } from "@/components/screens/settings/SettingsKeyMintModal";
import {
  fetchGovernancePersistence,
  fetchGovernancePolicy,
  fetchSbom,
  fetchScopedKeys,
  mintScopedKey,
  updateGovernancePolicy,
  verifyScopedKey,
} from "@/lib/api";
import type {
  DataResidencyZone,
  GovernancePersistenceInfo,
  MintedScopedApiKeyResult,
  ScopedApiKeyItem,
  ScopedKeyVerifyResult,
  TenantGovernancePolicy,
} from "@/lib/types";

export interface SettingsGovernancePanelProps {
  fetchPersistenceFn?: typeof fetchGovernancePersistence;
  fetchPolicyFn?: typeof fetchGovernancePolicy;
  updatePolicyFn?: typeof updateGovernancePolicy;
  fetchKeysFn?: typeof fetchScopedKeys;
  mintKeyFn?: typeof mintScopedKey;
  verifyKeyFn?: typeof verifyScopedKey;
  fetchSbomFn?: typeof fetchSbom;
}

const DEFAULT_POLICY: TenantGovernancePolicy = {
  tenantId: "default",
  name: "Local Sovereign Workspace",
  residencyZone: "local_only",
  dlpEnabled: true,
  dailyBudgetUsd: 10.0,
  dailySpendUsd: 1.42,
  monthlyBudgetUsd: 150.0,
  currentSpendUsd: 18.4,
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

export function SettingsGovernancePanel({
  fetchPersistenceFn = fetchGovernancePersistence,
  fetchPolicyFn = fetchGovernancePolicy,
  updatePolicyFn = updateGovernancePolicy,
  fetchKeysFn = fetchScopedKeys,
  mintKeyFn = mintScopedKey,
  verifyKeyFn = verifyScopedKey,
  fetchSbomFn = fetchSbom,
}: SettingsGovernancePanelProps): React.JSX.Element {
  const [persistence, setPersistence] = useState<GovernancePersistenceInfo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [policyLoaded, setPolicyLoaded] = useState(false);
  const [policy, setPolicy] = useState<TenantGovernancePolicy>(DEFAULT_POLICY);
  const [budgetDraft, setBudgetDraft] = useState("150");
  const [keys, setKeys] = useState<ScopedApiKeyItem[]>([]);
  const [verifyTokenInput, setVerifyTokenInput] = useState("");
  const [verifyingKey, setVerifyingKey] = useState(false);
  const [verifyKeyResult, setVerifyKeyResult] = useState<ScopedKeyVerifyResult | null>(null);
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
  const verifyKeyInputId = useId();

  const mountedRef = useRef(true);
  const policyRef = useRef(policy);
  policyRef.current = policy;
  const mintingRef = useRef(false);
  const verifyingRef = useRef(false);
  const inspectingSbomRef = useRef(false);
  const updatingBudgetRef = useRef(false);

  const fetchPersistenceRef = useRef(fetchPersistenceFn);
  fetchPersistenceRef.current = fetchPersistenceFn;
  const fetchPolicyRef = useRef(fetchPolicyFn);
  fetchPolicyRef.current = fetchPolicyFn;
  const fetchKeysRef = useRef(fetchKeysFn);
  fetchKeysRef.current = fetchKeysFn;

  useEffect(() => {
    mountedRef.current = true;
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
        setPolicyLoaded(true);
        setBudgetDraft(String(pol.monthlyBudgetUsd));
        setKeys(loadedKeys);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : "Failed to load governance state.");
      });
    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, []);

  const handleResidencyChange = async (nextZone: DataResidencyZone) => {
    const prevPolicy = policyRef.current;
    setPolicy((prev) => ({ ...prev, residencyZone: nextZone }));
    try {
      const updated = await updatePolicyFn({ residencyZone: nextZone });
      if (mountedRef.current) setPolicy(updated);
    } catch {
      if (mountedRef.current) setPolicy(prevPolicy);
    }
  };

  const handleDlpToggle = async (checked: boolean) => {
    const prevPolicy = policyRef.current;
    setPolicy((prev) => ({ ...prev, dlpEnabled: checked }));
    try {
      const updated = await updatePolicyFn({ dlpEnabled: checked });
      if (mountedRef.current) setPolicy(updated);
    } catch {
      if (mountedRef.current) setPolicy(prevPolicy);
    }
  };

  const handleVerifyKey = async (event: React.FormEvent) => {
    event.preventDefault();
    const token = verifyTokenInput.trim();
    if (!token || verifyingRef.current) return;
    verifyingRef.current = true;
    setVerifyingKey(true);
    try {
      const res = await verifyKeyFn(token);
      if (mountedRef.current) {
        setVerifyKeyResult(res);
        setVerifyTokenInput("");
      }
    } catch {
      if (mountedRef.current) {
        setVerifyKeyResult({
          valid: false,
          scopes: [],
          reason: "Key verification failed — loopback governance endpoint unreachable.",
        });
      }
    } finally {
      verifyingRef.current = false;
      if (mountedRef.current) setVerifyingKey(false);
    }
  };

  const handleBudgetUpdate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (updatingBudgetRef.current) return;
    updatingBudgetRef.current = true;
    const prevPolicy = policyRef.current;
    const numeric = Math.max(0, Number(budgetDraft) || 0);
    setPolicy((prev) => ({ ...prev, monthlyBudgetUsd: numeric }));
    try {
      const updated = await updatePolicyFn({ monthlyBudgetUsd: numeric });
      if (mountedRef.current) {
        setPolicy(updated);
        setBudgetDraft(String(updated.monthlyBudgetUsd));
      }
    } catch {
      if (mountedRef.current) {
        setPolicy(prevPolicy);
        setBudgetDraft(String(prevPolicy.monthlyBudgetUsd));
      }
    } finally {
      updatingBudgetRef.current = false;
    }
  };

  const handleFallbackToggle = async (checked: boolean) => {
    const prevPolicy = policyRef.current;
    setPolicy((prev) => ({ ...prev, fallbackToOpencoreOnBudgetExceeded: checked }));
    try {
      const updated = await updatePolicyFn({ fallbackToOpencoreOnBudgetExceeded: checked });
      if (mountedRef.current) setPolicy(updated);
    } catch {
      if (mountedRef.current) setPolicy(prevPolicy);
    }
  };

  const handleInspectSbom = async () => {
    if (inspectingSbomRef.current) return;
    inspectingSbomRef.current = true;
    setLoadingSbom(true);
    try {
      const info = await fetchSbomFn();
      if (mountedRef.current) setSbomInfo(info);
    } catch {
      // Preserve existing SBOM state if inspection fails
    } finally {
      inspectingSbomRef.current = false;
      if (mountedRef.current) setLoadingSbom(false);
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
    if (mintingRef.current || minting || (mintedResult && !savedKeyChecked)) {
      return;
    }
    setMintOpen(false);
    setMintedResult(null);
    setSavedKeyChecked(false);
    setCopiedSecret(false);
  };

  const handleGenerateScopedKey = async (event: React.FormEvent) => {
    event.preventDefault();
    if (mintingRef.current) return;
    mintingRef.current = true;
    setMinting(true);
    try {
      const scopes = selectedScopes.length > 0 ? selectedScopes : ["audit:read"];
      const res = await mintKeyFn(keyLabel.trim() || "scoped-key", scopes, keySpendCap);
      if (!mountedRef.current) return;
      setMintedResult(res);
      setSavedKeyChecked(false);
      setKeys((prev) => [res.key, ...prev.filter((k) => k.id !== res.key.id)]);
    } catch {
      // Keep Mint dialog open on form so user can retry on transient failure
    } finally {
      mintingRef.current = false;
      if (mountedRef.current) setMinting(false);
    }
  };

  const handleCopySecret = () => {
    if (!mintedResult) return;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(mintedResult.plaintextSecret)
        .then(() => setCopiedSecret(true))
        .catch(() => setCopiedSecret(false));
    } else {
      setCopiedSecret(true);
    }
  };

  const dailySpend = policy.dailySpendUsd ?? 1.42;
  const dailyBudget = policy.dailyBudgetUsd ?? 10.0;
  const dailyPct = dailyBudget > 0 ? Math.min(100, Math.round((dailySpend / dailyBudget) * 100)) : 100;
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

      {loadError ? (
        <div role="alert" className="rounded-sm border border-danger/55 bg-danger-subtle px-4 py-2.5 text-xs text-fg">
          <span className="font-semibold text-danger">{`Failed to load governance state: ${loadError}`}</span>
          {" "}Values below are unsaved defaults, not server state. Check the local API and reload.
        </div>
      ) : null}

      {/* 1. Crash-Safe Persistence Strip */}
      <section
        aria-label="Governance SQLite persistence"
        className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border-strong bg-surface px-4 py-3 text-xs"
      >
        <div className="flex flex-wrap items-center gap-2.5">
          {persistence?.healthy !== false ? (
            <SemanticBadge kind="passed" labelOverride="SQLite WAL Crash-Safe" />
          ) : (
            <SemanticBadge kind="reconfirm" labelOverride="Ephemeral memory · not WAL" />
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
              checked={policy.dlpEnabled ?? true}
              onChange={(e) => void handleDlpToggle(e.target.checked)}
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

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-fg">Daily USD Spend</span>
              <span className="font-mono font-semibold tabular-nums text-fg">
                {`$${dailySpend.toFixed(2)} / $${dailyBudget.toFixed(2)}`}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label="Daily USD spend"
              aria-valuenow={Number(dailySpend.toFixed(2))}
              aria-valuemin={0}
              aria-valuemax={Math.max(1, dailyBudget)}
              className="h-2 w-full overflow-hidden rounded-xs border border-border bg-chrome"
            >
              <div className="h-full bg-teal-accent transition-all" style={{ width: `${dailyPct}%` }} />
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
              aria-label="Monthly USD spend"
              aria-valuenow={Number(policy.currentSpendUsd.toFixed(2))}
              aria-valuemin={0}
              aria-valuemax={Math.max(1, policy.monthlyBudgetUsd)}
              className="h-2 w-full overflow-hidden rounded-xs border border-border bg-chrome"
            >
              <div
                className={`h-full transition-all ${
                  isOverCap ? "bg-danger" : isWarnSpend ? "bg-warning" : "bg-teal-accent"
                }`}
                style={{ width: `${spendPct}%` }}
              />
            </div>
          </div>
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

        <form onSubmit={(e) => void handleVerifyKey(e)} className="space-y-2 rounded-sm border border-border bg-canvas p-3 text-xs">
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-48 flex-1 space-y-1">
              <label htmlFor={verifyKeyInputId} className="block font-medium text-fg">
                Verify scoped key (<code dir="ltr" className="unicode-bidi-isolate font-mono">POST /v1/governance/keys/verify</code>)
              </label>
              <input
                id={verifyKeyInputId}
                type="password"
                dir="ltr"
                value={verifyTokenInput}
                onChange={(e) => setVerifyTokenInput(e.target.value)}
                placeholder="kw_live_…"
                className="unicode-bidi-isolate min-h-ctrl-sm w-full rounded-xs border border-border-control bg-surface px-2.5 py-1 font-mono text-xs text-fg"
              />
            </div>
            <Button type="submit" size="sm" variant="secondary" loading={verifyingKey}>
              Verify key
            </Button>
          </div>
          {verifyKeyResult ? (
            <div className="flex flex-wrap items-center gap-2 pt-0.5">
              {verifyKeyResult.valid ? (
                <SemanticBadge kind="passed" labelOverride="Key valid" />
              ) : (
                <SemanticBadge kind="failed" labelOverride="Key rejected" />
              )}
              <span className="text-fg-muted">{verifyKeyResult.reason}</span>
            </div>
          ) : null}
        </form>
      </section>

      <SettingsKeyMintModal
        open={mintOpen}
        onOpen={() => setMintOpen(true)}
        onRequestClose={closeMintDialogSafely}
        keyLabel={keyLabel}
        onKeyLabelChange={setKeyLabel}
        selectedScopes={selectedScopes}
        onSelectedScopesChange={setSelectedScopes}
        keySpendCap={keySpendCap}
        onKeySpendCapChange={setKeySpendCap}
        minting={minting}
        mintedResult={mintedResult}
        savedKeyChecked={savedKeyChecked}
        onSavedKeyCheckedChange={setSavedKeyChecked}
        copiedSecret={copiedSecret}
        onCopySecret={handleCopySecret}
        onSubmitMint={(e) => void handleGenerateScopedKey(e)}
      />
    </div>
  );
}
