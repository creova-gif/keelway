import React, { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { SettingsPanelHeader } from "@/components/screens/settings/SettingsPanelHeader";
import { fetchAirGapAudit, runLabsBenchmark } from "@/lib/api";
import type {
  DensityMode,
  EgressTelemetryState,
  LabsExperimentItem,
  LocaleCode,
  ThemeMode,
} from "@/lib/types";

export const ORLA_UNMEASURED_NETWORK_COPY =
  "Set to keep your use on this machine. Network use isn't measured yet.";

const LOCALE_OPTIONS: ReadonlyArray<{ code: LocaleCode; label: string }> = [
  { code: "en-US", label: "English (US) · en-US" },
  { code: "es", label: "Español · es" },
  { code: "fr", label: "Français · fr" },
  { code: "de", label: "Deutsch · de" },
  { code: "ja", label: "日本語 · ja" },
  { code: "zh-CN", label: "简体中文 · zh-CN" },
  { code: "pt-BR", label: "Português (Brasil) · pt-BR" },
  { code: "ar", label: "العربية (RTL) · ar" },
];

const DENSITY_CARDS: ReadonlyArray<{
  mode: DensityMode;
  title: string;
  rowPx: number;
  note: string;
}> = [
  { mode: "compact", title: "Compact · 24px", rowPx: 24, note: "High-density diff & ledger scan" },
  { mode: "default", title: "Default · 28px", rowPx: 28, note: "Balanced IDE & P-10 review" },
  { mode: "comfortable", title: "Comfortable · 32px", rowPx: 32, note: "Relaxed reading & coarse pointer" },
];

interface LabsCardRecord extends LabsExperimentItem {
  actionLabel?: string;
  runKind?: "benchmark" | "swarm" | "speculative";
}

const INITIAL_LABS_CARDS: LabsCardRecord[] = [
  {
    id: "benchmark",
    kind: "benchmark",
    title: "Model benchmark",
    summary: "Local OpenCore throughput & latency harness across representative coding tasks.",
    epistemicStatus: "simulated",
    metricLabel: "Baseline reference",
    metricValue: "42.0 tok/s (fixture)",
    methodologyNote: "Upgrades to Live once executed against loopback /v1/eval/benchmark.",
    actionLabel: "Run local benchmark",
    runKind: "benchmark",
  },
  {
    id: "swarm",
    kind: "swarm",
    title: "Agent swarm (MiroFish)",
    summary: "Concept only. Approval rules stay per action, per person.",
    epistemicStatus: "simulated",
    metricLabel: "Quorum dry-run",
    metricValue: "3-agent local sandbox",
    methodologyNote: "Multi-agent deliberation never bypasses individual human P-10 approval.",
    actionLabel: "Run swarm eval",
    runKind: "swarm",
  },
  {
    id: "estimator",
    kind: "drift",
    title: "Cost & token estimator",
    summary: "Pre-flight token and USD ceiling heuristics prior to frontier routing.",
    epistemicStatus: "estimated",
    metricLabel: "Tokenizer heuristic",
    metricValue: "±6% BPE variance",
    methodologyNote: "Computed locally from character/AST byte ratios without calling vendor APIs.",
  },
  {
    id: "egress-counter",
    kind: "drift",
    title: "Egress byte counter",
    summary: "Loopback proxy socket byte accounting for status-bar verification.",
    epistemicStatus: "prototype",
    metricLabel: "Socket hook stage",
    metricValue: "sent: unmeasured",
    methodologyNote: "Until kernel/proxy byte hooks complete, status bar reports sent: unmeasured.",
  },
  {
    id: "cli-verifier",
    kind: "benchmark",
    title: "Chain verifier (CLI)",
    summary: "Independent offline SHA-256 & Merkle root audit verification tool.",
    epistemicStatus: "live",
    metricLabel: "CLI command",
    metricValue: "python3 cli.py audit verify",
    methodologyNote: "Verifies SQLite WAL and exported NDJSON bundles with zero network access.",
  },
  {
    id: "speculative",
    kind: "speculative",
    title: "Speculative decoding",
    summary: "Draft-model assisted local token generation on unified memory.",
    epistemicStatus: "simulated",
    metricLabel: "Draft speedup target",
    metricValue: "1.6x draft acceptance",
    methodologyNote: "Evaluates draft/target token acceptance on 127.0.0.1.",
    actionLabel: "Run speculative eval",
    runKind: "speculative",
  },
];

const INITIAL_UNVERIFIED_AUDIT: EgressTelemetryState = {
  mode: "unmeasured",
  cloudCallsCount: 0,
  bytesSent: null,
  airGapLocked: false,
  endpoints: [],
  sc7Compliant: undefined,
};

export interface SettingsNetworkPanelProps {
  airGapEnabled: boolean;
  onToggleAirGap: () => void;
  fetchAirGapAuditFn?: typeof fetchAirGapAudit;
}

export function SettingsNetworkPanel({
  airGapEnabled,
  onToggleAirGap,
  fetchAirGapAuditFn = fetchAirGapAudit,
}: SettingsNetworkPanelProps): React.JSX.Element {
  const [audit, setAudit] = useState<EgressTelemetryState>(INITIAL_UNVERIFIED_AUDIT);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError, setAuditError] = useState<string | null>(null);
  const fetchAuditRef = useRef(fetchAirGapAuditFn);
  fetchAuditRef.current = fetchAirGapAuditFn;

  useEffect(() => {
    let cancelled = false;
    setAuditLoading(true);
    fetchAuditRef
      .current()
      .then((res) => {
        if (!cancelled) setAudit(res);
      })
      .catch((err) => {
        if (!cancelled) setAuditError(err instanceof Error ? err.message : "Failed to load air-gap telemetry.");
      })
      .finally(() => {
        if (!cancelled) setAuditLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-5 text-ui text-fg">
      <SettingsPanelHeader
        title="Network & Egress"
        status={airGapEnabled ? "Air-Gap locked" : "Egress measured"}
        purpose="Honest egress telemetry, Tier-3 Air-Gap socket lock, and NIST SP 800-53 SC-7 boundary checks."
      />

      <section
        aria-label="Network posture and Air-Gap lock"
        className="space-y-3.5 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-fg">
                {airGapEnabled ? "Air-gapped · verified" : "Offline (setting)"}
              </span>
              {airGapEnabled ? (
                <SemanticBadge kind="locked" />
              ) : (
                <SemanticBadge kind="unmeasured" />
              )}
            </div>
            <p className="text-xs text-fg-muted">{ORLA_UNMEASURED_NETWORK_COPY}</p>
          </div>

          <Button
            size="md"
            variant={airGapEnabled ? "primary" : "secondary"}
            aria-pressed={airGapEnabled}
            shortcutHint="Alt+A"
            onClick={onToggleAirGap}
          >
            {airGapEnabled ? "Air-Gap Lock: Enabled" : "Enable Air-Gap Lock"}
          </Button>
        </div>
      </section>

      <section
        aria-label="NIST SP 800-53 SC-7 boundary checklist"
        className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-semibold text-fg">
            NIST SP 800-53 SC-7 Boundary Protection Audit (<code dir="ltr" className="unicode-bidi-isolate font-mono">/v1/airgap/audit</code>)
          </h3>
          {audit.sc7Compliant === true ? (
            <SemanticBadge kind="passed" labelOverride="SC-7 Verified" />
          ) : audit.sc7Compliant === false ? (
            <SemanticBadge kind="reconfirm" labelOverride="SC-7 Drift · cloud active" />
          ) : (
            <SemanticBadge kind="unmeasured" labelOverride="SC-7 Unverified" />
          )}
        </div>

        <ul className="divide-y divide-border rounded-sm border border-border bg-canvas text-xs">
          {auditError ? (
            <li role="alert" className="px-3 py-2 font-mono text-danger">
              {`Air-gap telemetry unavailable: ${auditError}. Egress claims are unverified — check the local API and reload.`}
            </li>
          ) : auditLoading && !audit.sc7Checks ? (
            <li className="px-3 py-2 font-mono text-fg-muted">
              Auditing loopback socket &amp; environment boundary…
            </li>
          ) : audit.sc7Checks && audit.sc7Checks.length > 0 ? (
            audit.sc7Checks.map((chk) => (
              <li key={chk.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className="text-fg">{chk.label}</span>
                <div className="flex flex-wrap items-center gap-2">
                  {chk.detail ? (
                    <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg-muted">
                      {chk.detail}
                    </code>
                  ) : null}
                  {chk.passed ? (
                    <SemanticBadge kind="passed" labelOverride="Pass" />
                  ) : (
                    <SemanticBadge kind="reconfirm" labelOverride="Drift" />
                  )}
                </div>
              </li>
            ))
          ) : (
            <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
              <span className="text-fg">Loopback HTTP/WS origin binding</span>
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-teal-accent">
                127.0.0.1:7420
              </code>
            </li>
          )}
          <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
            <span className="text-fg">Recorded session cloud endpoints</span>
            <span className="font-mono tabular-nums text-fg-muted">
              {`${audit.endpoints.length} endpoints`}
            </span>
          </li>
        </ul>
      </section>
    </div>
  );
}

export interface SettingsAppearancePanelProps {
  themeMode: ThemeMode;
  onThemeModeChange: (mode: ThemeMode) => void;
  densityMode: DensityMode;
  onDensityModeChange: (density: DensityMode) => void;
  locale: LocaleCode;
  onLocaleChange: (locale: LocaleCode) => void;
  reduceMotion: boolean;
  onReduceMotionChange: (reduce: boolean) => void;
}

export function SettingsAppearancePanel({
  themeMode,
  onThemeModeChange,
  densityMode,
  onDensityModeChange,
  locale,
  onLocaleChange,
  reduceMotion,
  onReduceMotionChange,
}: SettingsAppearancePanelProps): React.JSX.Element {
  const localeSelectId = useId();
  const reduceMotionId = useId();

  return (
    <div className="space-y-5 text-ui text-fg">
      <SettingsPanelHeader
        title="Appearance, Density & Locale"
        purpose="WCAG 2.2 AA calibrated surface tokens, live 3-mode row density, and bidirectional locale switching."
      />

      {/* Theme Selector */}
      <section aria-label="Color theme" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <h3 className="text-[15px] font-semibold text-fg">Color Theme</h3>
        <div role="group" aria-label="Theme mode" className="flex flex-wrap gap-2">
          {(
            [
              { mode: "dark", label: "Dark (Default)" },
              { mode: "light", label: "Light" },
              { mode: "system", label: "Match system" },
            ] as const
          ).map((opt) => {
            const active = themeMode === opt.mode;
            return (
              <button
                key={opt.mode}
                type="button"
                aria-pressed={active}
                onClick={() => onThemeModeChange(opt.mode)}
                className={`min-h-ctrl-md rounded-sm border px-3 py-1.5 text-xs font-medium transition-colors duration-fast ease-state ${
                  active
                    ? "border-teal-accent bg-teal-surface text-teal-accent"
                    : "border-border-control bg-canvas text-fg hover:bg-surface-elevated"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* 3-Up Live Density Preview */}
      <section aria-label="Interface density" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <div>
          <h3 className="text-[15px] font-semibold text-fg">
            Row &amp; Control Density
          </h3>
          <p className="mt-0.5 text-xs text-fg-muted">
            Select a density profile; coarse touch pointers automatically enforce 44×44px minimum hit targets.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {DENSITY_CARDS.map((card) => {
            const selected = densityMode === card.mode;
            return (
              <button
                key={card.mode}
                type="button"
                aria-pressed={selected}
                onClick={() => onDensityModeChange(card.mode)}
                className={`flex flex-col gap-2.5 rounded-md border p-3 text-start transition-colors duration-fast ease-state ${
                  selected
                    ? "border-teal-accent bg-teal-surface text-fg"
                    : "border-border-control bg-canvas text-fg hover:bg-surface-elevated"
                }`}
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-fg">{card.title}</span>
                  {selected ? <SemanticBadge kind="opencore" labelOverride="Active" /> : null}
                </div>
                <div className="w-full space-y-1 rounded-xs border border-border bg-surface p-1.5 font-mono text-[11px]">
                  <div
                    style={{ height: `${card.rowPx}px` }}
                    className="flex items-center justify-between rounded-xs bg-chrome px-2 text-fg"
                  >
                    <span>#1283 Edited</span>
                    <span>{`${card.rowPx}px`}</span>
                  </div>
                  <div
                    style={{ height: `${card.rowPx}px` }}
                    className="flex items-center justify-between rounded-xs bg-canvas px-2 text-fg-muted"
                  >
                    <span>#1282 Allowed</span>
                    <span>✓</span>
                  </div>
                </div>
                <span className="text-[11px] text-fg-muted">{card.note}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* 8-Locale Switcher & Reduce Motion */}
      <section aria-label="Locale and motion" className="space-y-3.5 rounded-md border border-border-strong bg-surface p-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor={localeSelectId} className="block text-xs font-semibold text-fg">
              Interface locale
            </label>
            <select
              id={localeSelectId}
              value={locale}
              onChange={(e) => {
                const found = LOCALE_OPTIONS.find((l) => l.code === e.target.value);
                if (found) onLocaleChange(found.code);
              }}
              className="min-h-ctrl-md w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1.5 text-xs text-fg"
            >
              {LOCALE_OPTIONS.map((opt) => (
                <option key={opt.code} value={opt.code}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2.5 self-end rounded-sm border border-border bg-canvas px-3 py-2.5">
            <input
              id={reduceMotionId}
              type="checkbox"
              checked={reduceMotion}
              onChange={(e) => onReduceMotionChange(e.target.checked)}
              className="h-4 w-4 accent-teal-accent"
            />
            <label htmlFor={reduceMotionId} className="text-xs font-medium text-fg">
              Reduce motion (disable non-essential transitions)
            </label>
          </div>
        </div>
      </section>
    </div>
  );
}

export interface SettingsLabsPanelProps {
  runBenchmarkFn?: typeof runLabsBenchmark;
}

export function SettingsLabsPanel({
  runBenchmarkFn = runLabsBenchmark,
}: SettingsLabsPanelProps): React.JSX.Element {
  const [cards, setCards] = useState<LabsCardRecord[]>(INITIAL_LABS_CARDS);
  const [runningIds, setRunningIds] = useState<Record<string, boolean>>({});
  const runningSetRef = useRef<Set<string>>(new Set());
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const handleRunCard = async (card: LabsCardRecord) => {
    if (!card.runKind || runningSetRef.current.has(card.id)) return;
    runningSetRef.current.add(card.id);
    setRunningIds((prev) => ({ ...prev, [card.id]: true }));
    try {
      const res = await runBenchmarkFn(card.runKind);
      if (!mountedRef.current) return;
      setCards((prev) =>
        prev.map((item) =>
          item.id === card.id
            ? {
                ...item,
                epistemicStatus: res.epistemicStatus,
                metricLabel: res.metricLabel,
                metricValue: res.metricValue,
                lastRunAt: res.completedAt,
              }
            : item,
        ),
      );
    } catch {
      // Retain existing epistemic status if benchmark run fails
    } finally {
      runningSetRef.current.delete(card.id);
      if (mountedRef.current) {
        setRunningIds((prev) => {
          const next = { ...prev };
          delete next[card.id];
          return next;
        });
      }
    }
  };

  return (
    <div className="space-y-5 text-ui text-fg">
      <SettingsPanelHeader
        title="Labs — Epistemic Workbench"
        purpose="Every experimental capability carries an explicit epistemic badge (Simulated, Estimated, Prototype, or Live) so synthetic fixtures never masquerade as measured telemetry."
      />

      <div className="grid gap-3.5 md:grid-cols-2">
        {cards.map((card) => {
          const isSimulated = card.epistemicStatus === "simulated";
          return (
            <section
              key={card.id}
              data-testid={`labs-card-${card.id}`}
              aria-label={card.title}
              className={`flex flex-col justify-between gap-3 rounded-md border p-4 ${
                isSimulated
                  ? "border-dashed border-border-control bg-surface"
                  : "border-solid border-border-strong bg-surface"
              }`}
            >
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-fg">{card.title}</h3>
                  <SemanticBadge kind={card.epistemicStatus} />
                </div>
                <p className="text-xs text-fg-muted">{card.summary}</p>
                <div className="rounded-xs border border-border bg-canvas px-2.5 py-2 text-xs">
                  <div className="text-[11px] text-fg-muted">{card.metricLabel}</div>
                  <div className="mt-0.5 font-mono font-semibold text-fg">
                    <code dir="ltr" className="unicode-bidi-isolate">
                      {card.metricValue}
                    </code>
                  </div>
                </div>
                <p className="text-[11px] text-fg-dim">{card.methodologyNote}</p>
              </div>

              {card.actionLabel && card.runKind ? (
                <div className="flex justify-end pt-1">
                  <Button
                    size="sm"
                    variant={card.epistemicStatus === "live" ? "secondary" : "primary"}
                    loading={Boolean(runningIds[card.id])}
                    onClick={() => void handleRunCard(card)}
                  >
                    {card.actionLabel}
                  </Button>
                </div>
              ) : null}
            </section>
          );
        })}
      </div>
    </div>
  );
}

export function SettingsGeneralPanel({
  workspacePath = "/workspace/keelway",
  workspaceBranch = "feat/unified-dev-app",
  onOpenOnboarding,
}: {
  workspacePath?: string;
  workspaceBranch?: string;
  onOpenOnboarding?: () => void;
}): React.JSX.Element {
  return (
    <div className="space-y-5 text-ui text-fg">
      <SettingsPanelHeader
        title="General & Workspace"
        purpose="Bound local repository root, loopback runtime address, and first-run readiness wizard."
      />

      <section aria-label="Workspace binding" className="space-y-3 rounded-md border border-border-strong bg-surface p-4 text-xs">
        <dl className="divide-y divide-border rounded-sm border border-border bg-canvas">
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <dt className="text-fg-muted">Workspace root</dt>
            <dd className="font-mono text-fg">
              <code dir="ltr" className="unicode-bidi-isolate">{workspacePath}</code>
            </dd>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <dt className="text-fg-muted">Active Git branch</dt>
            <dd className="font-mono text-fg">
              <code dir="ltr" className="unicode-bidi-isolate">{workspaceBranch}</code>
            </dd>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <dt className="text-fg-muted">Loopback daemon origin</dt>
            <dd className="font-mono text-teal-accent">
              <code dir="ltr" className="unicode-bidi-isolate">http://127.0.0.1:7420</code>
            </dd>
          </div>
        </dl>

        <div className="flex justify-end pt-1">
          <Button size="sm" variant="secondary" onClick={() => onOpenOnboarding?.()}>
            Re-open first-run setup
          </Button>
        </div>
      </section>
    </div>
  );
}

const SHORTCUT_ROWS: ReadonlyArray<{ keys: string; scope: string; behavior: string }> = [
  { keys: "⌘K / Ctrl+K", scope: "Global shell", behavior: "Open Command Palette (navigation only; never runs approvals)" },
  { keys: "F6 / Shift+F6", scope: "Global shell", behavior: "Cycle landmark panes (Sidebar → Workspace → Review → Logs → Status bar)" },
  { keys: "⌘1 / ⌘2 / ⌘3", scope: "Global shell", behavior: "Focus Sidebar (⌘1), Main workspace (⌘2), or focus open Review drawer (⌘3)" },
  { keys: "⌘J / Ctrl+J", scope: "Global shell", behavior: "Toggle Logs, Sandbox Terminal & Network drawer" },
  { keys: "⌘⇧A / Ctrl+Shift+A", scope: "Pending P-10 gate", behavior: "Jump focus directly to active P-10 approval heading" },
  { keys: "⌘↵ / Ctrl+Enter", scope: "Composer only", behavior: "Send prompt from AgentComposer (strictly isolated from P-10 gates)" },
  { keys: "⌘⇧Y / ⌘⇧N", scope: "Local P-10 Variants A/B", behavior: "Allow once / Deny local edit or command (disabled on Variant C network gates)" },
  { keys: "Alt+A", scope: "Non-input shell", behavior: "Toggle Tier-3 Air-Gap socket lock (ignored while typing in inputs)" },
  { keys: "⌘⇧R", scope: "Desktop shell only", behavior: "Open Record SHA-256 ledger (yielded to browser reload in web tabs)" },
];

export function SettingsKeyboardPanel(): React.JSX.Element {
  return (
    <div className="space-y-5 text-ui text-fg">
      <SettingsPanelHeader
        title="Keyboard Shortcuts"
        purpose="Collision-free landmark navigation and P-10 human-only approval gesture boundaries."
      />

      <div className="overflow-x-auto rounded-md border border-border-strong bg-surface">
        <table aria-label="Keyboard shortcuts reference" className="w-full border-collapse text-start text-xs">
          <thead className="border-b border-border-strong bg-chrome text-fg-muted">
            <tr>
              <th scope="col" className="px-3 py-2 text-start font-semibold">Shortcut</th>
              <th scope="col" className="px-3 py-2 text-start font-semibold">Scope</th>
              <th scope="col" className="px-3 py-2 text-start font-semibold">Action &amp; Safety Invariant</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {SHORTCUT_ROWS.map((row) => (
              <tr key={row.keys} className="min-h-table-row hover:bg-surface-elevated">
                <td className="px-3 py-2 font-mono font-semibold text-fg">
                  <kbd className="rounded-xs border border-border-control bg-canvas px-1.5 py-0.5 text-[11px]">
                    {row.keys}
                  </kbd>
                </td>
                <td className="px-3 py-2 text-fg-muted">{row.scope}</td>
                <td className="px-3 py-2 text-fg">{row.behavior}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
