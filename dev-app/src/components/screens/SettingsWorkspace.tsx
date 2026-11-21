import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SettingsGovernancePanel } from "@/components/screens/settings/SettingsGovernancePanel";
import { SettingsModelsPanel } from "@/components/screens/settings/SettingsModelsPanel";
import {
  CURRENT_PROMPT_VERSION,
  isRuleDrifted,
  SettingsPermissionsPanel,
} from "@/components/screens/settings/SettingsPermissionsPanel";
import {
  ORLA_UNMEASURED_NETWORK_COPY,
  SettingsAppearancePanel,
  SettingsGeneralPanel,
  SettingsKeyboardPanel,
  SettingsLabsPanel,
  SettingsNetworkPanel,
} from "@/components/screens/settings/SettingsSystemPanels";
import {
  explainRouting,
  fetchAgentManifests,
  fetchAirGapAudit,
  fetchGovernancePersistence,
  fetchGovernancePolicy,
  fetchOpenCoreWeights,
  fetchSbom,
  fetchScopedKeys,
  inspectAgentManifest,
  mintScopedKey,
  runLabsBenchmark,
  toggleAgentManifest,
  toggleAirGap,
  updateGovernancePolicy,
  verifyScopedKey,
} from "@/lib/api";
import type {
  ApprovalRuleItem,
  DensityMode,
  LocaleCode,
  SettingsSubSection,
  ThemeMode,
} from "@/lib/types";

export { ORLA_UNMEASURED_NETWORK_COPY };

export const SETTINGS_SUB_SECTIONS: ReadonlyArray<{
  id: SettingsSubSection;
  label: string;
}> = [
  { id: "permissions", label: "Permissions & Manifests" },
  { id: "models", label: "Models & 4D Routing" },
  { id: "governance", label: "Governance & Keys" },
  { id: "network", label: "Network & Egress" },
  { id: "appearance", label: "Appearance & Density" },
  { id: "labs", label: "Labs" },
  { id: "general", label: "General & Workspace" },
  { id: "keyboard", label: "Keyboard Shortcuts" },
];

export function isEditableKeyboardTarget(target: EventTarget | null): boolean {
  const candidates: Array<Element | null> = [
    target instanceof Element ? target : null,
    typeof document !== "undefined" ? document.activeElement : null,
  ];
  for (const el of candidates) {
    if (!el) continue;
    const tag = el.tagName.toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return true;
    }
    if ((el instanceof HTMLElement && el.isContentEditable) || el.closest('[contenteditable="true"]')) {
      return true;
    }
  }
  return false;
}

export function applyThemeToDocument(mode: ThemeMode): void {
  if (typeof document === "undefined") return;
  let resolved: "dark" | "light" = "dark";
  if (mode === "light") {
    resolved = "light";
  } else if (
    mode === "system" &&
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
  ) {
    resolved = "light";
  }
  document.documentElement.dataset.theme = resolved;
}

export function applyDensityToDocument(density: DensityMode): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.density = density;
}

export function applyLocaleToDocument(locale: LocaleCode): void {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale;
  document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
}

export function applyReduceMotionToDocument(reduce: boolean): void {
  if (typeof document === "undefined") return;
  if (reduce) {
    document.documentElement.setAttribute("data-reduce-motion", "true");
  } else {
    document.documentElement.removeAttribute("data-reduce-motion");
  }
}

export interface SettingsSubNavProps {
  activeSubSection: SettingsSubSection;
  onSelectSubSection: (sub: SettingsSubSection) => void;
  driftedRulesCount?: number;
}

export function SettingsSubNav({
  activeSubSection,
  onSelectSubSection,
  driftedRulesCount = 0,
}: SettingsSubNavProps): React.JSX.Element {
  return (
    <nav aria-label="Settings sections" className="flex h-full flex-col overflow-y-auto py-5">
      <div className="px-5 pb-3.5 font-mono text-[11px] uppercase tracking-[0.14em] text-fg-dim">
        Settings
      </div>
      <div>
        {SETTINGS_SUB_SECTIONS.map((item) => {
          const isActive = item.id === activeSubSection;
          return (
            <button
              key={item.id}
              type="button"
              aria-current={isActive ? "page" : undefined}
              onClick={() => onSelectSubSection(item.id)}
              className={`flex w-full items-center justify-between gap-2 border-s-2 pe-5 ps-[18px] py-[7px] text-start text-[13px] transition-colors duration-fast ease-state ${
                isActive
                  ? "border-s-teal-accent text-fg"
                  : "border-s-transparent text-fg-muted hover:bg-surface-elevated hover:text-fg"
              }`}
            >
              <span className="truncate">{item.label}</span>
              {item.id === "permissions" && driftedRulesCount > 0 ? (
                <span className="font-mono text-[11px] text-ochre">{driftedRulesCount}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export interface SettingsWorkspaceProps {
  activeSubSection?: SettingsSubSection;
  defaultSubSection?: SettingsSubSection;
  onSelectSubSection?: (sub: SettingsSubSection) => void;
  renderSidebarInShell?: boolean;
  onSidebarStateChange?: (sidebarNode: React.ReactNode) => void;
  themeMode?: ThemeMode;
  onThemeModeChange?: (mode: ThemeMode) => void;
  densityMode?: DensityMode;
  onDensityModeChange?: (density: DensityMode) => void;
  locale?: LocaleCode;
  onLocaleChange?: (locale: LocaleCode) => void;
  reduceMotion?: boolean;
  onReduceMotionChange?: (reduce: boolean) => void;
  airGapEnabled?: boolean;
  onToggleAirGap?: (enabled: boolean) => void;
  disableGlobalAirGapShortcut?: boolean;
  scopedRules?: ApprovalRuleItem[];
  onUpdateScopedRules?: (rules: ApprovalRuleItem[]) => void;
  activeModelId?: string;
  onSelectActiveModel?: (modelId: string, modelLabel: string) => void;
  workspacePath?: string;
  workspaceBranch?: string;
  onOpenOnboarding?: () => void;
  fetchManifestsFn?: typeof fetchAgentManifests;
  toggleManifestFn?: typeof toggleAgentManifest;
  inspectManifestFn?: typeof inspectAgentManifest;
  fetchWeightsFn?: typeof fetchOpenCoreWeights;
  explainRoutingFn?: typeof explainRouting;
  fetchPersistenceFn?: typeof fetchGovernancePersistence;
  fetchPolicyFn?: typeof fetchGovernancePolicy;
  updatePolicyFn?: typeof updateGovernancePolicy;
  fetchKeysFn?: typeof fetchScopedKeys;
  mintKeyFn?: typeof mintScopedKey;
  verifyKeyFn?: typeof verifyScopedKey;
  fetchSbomFn?: typeof fetchSbom;
  toggleAirGapFn?: typeof toggleAirGap;
  fetchAirGapAuditFn?: typeof fetchAirGapAudit;
  onOpenRecordAudit?: () => void;
  runBenchmarkFn?: typeof runLabsBenchmark;
}

export function SettingsWorkspace({
  activeSubSection: controlledSubSection,
  defaultSubSection = "permissions",
  onSelectSubSection,
  renderSidebarInShell = false,
  onSidebarStateChange,
  themeMode: controlledTheme,
  onThemeModeChange,
  densityMode: controlledDensity,
  onDensityModeChange,
  locale: controlledLocale,
  onLocaleChange,
  reduceMotion: controlledReduceMotion,
  onReduceMotionChange,
  airGapEnabled: controlledAirGap,
  onToggleAirGap,
  disableGlobalAirGapShortcut = false,
  scopedRules: controlledScopedRules,
  onUpdateScopedRules,
  activeModelId: controlledActiveModelId,
  onSelectActiveModel,
  workspacePath = "/workspace/keelway",
  workspaceBranch = "feat/unified-dev-app",
  onOpenOnboarding,
  fetchManifestsFn,
  toggleManifestFn,
  inspectManifestFn,
  fetchWeightsFn,
  explainRoutingFn,
  fetchPersistenceFn,
  fetchPolicyFn,
  updatePolicyFn,
  fetchKeysFn,
  mintKeyFn,
  verifyKeyFn,
  fetchSbomFn,
  toggleAirGapFn,
  fetchAirGapAuditFn,
  onOpenRecordAudit,
  runBenchmarkFn,
}: SettingsWorkspaceProps): React.JSX.Element {
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  const [uncontrolledSubSection, setUncontrolledSubSection] =
    useState<SettingsSubSection>(defaultSubSection);
  const currentSubSection = controlledSubSection ?? uncontrolledSubSection;

  const [uncontrolledTheme, setUncontrolledTheme] = useState<ThemeMode>(() =>
    typeof document !== "undefined" && document.documentElement.dataset.theme === "light"
      ? "light"
      : "dark",
  );
  const currentTheme = controlledTheme ?? uncontrolledTheme;

  const [uncontrolledDensity, setUncontrolledDensity] = useState<DensityMode>(() => {
    if (typeof document !== "undefined") {
      const d = document.documentElement.dataset.density;
      if (d === "compact" || d === "comfortable" || d === "default") return d;
    }
    return "default";
  });
  const currentDensity = controlledDensity ?? uncontrolledDensity;

  const [uncontrolledLocale, setUncontrolledLocale] = useState<LocaleCode>("en-US");
  const currentLocale = controlledLocale ?? uncontrolledLocale;

  const [uncontrolledReduceMotion, setUncontrolledReduceMotion] = useState(false);
  const currentReduceMotion = controlledReduceMotion ?? uncontrolledReduceMotion;

  const [uncontrolledAirGap, setUncontrolledAirGap] = useState(false);
  const currentAirGap = controlledAirGap ?? uncontrolledAirGap;
  const currentAirGapRef = useRef(currentAirGap);
  currentAirGapRef.current = currentAirGap;
  const airGapReqSeqRef = useRef(0);

  useEffect(() => {
    if (currentTheme !== "system" || typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => applyThemeToDocument("system");
    applyThemeToDocument("system");
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    return undefined;
  }, [currentTheme]);

  /** Last rule list reported by the panel (load or mutation) — drives the drift badge. */
  const [knownRules, setKnownRules] = useState<ApprovalRuleItem[]>([]);
  const currentRules = controlledScopedRules ?? knownRules;

  const [uncontrolledModelId, setUncontrolledModelId] = useState("keelway-core:7b");
  const currentModelId = controlledActiveModelId ?? uncontrolledModelId;

  const onSidebarStateChangeRef = useRef(onSidebarStateChange);
  onSidebarStateChangeRef.current = onSidebarStateChange;

  const selectSubSection = useCallback(
    (next: SettingsSubSection) => {
      if (controlledSubSection === undefined) {
        setUncontrolledSubSection(next);
      }
      onSelectSubSection?.(next);
    },
    [controlledSubSection, onSelectSubSection],
  );

  const handleUpdateRules = useCallback(
    (nextRules: ApprovalRuleItem[]) => {
      setKnownRules(nextRules);
      onUpdateScopedRules?.(nextRules);
    },
    [onUpdateScopedRules],
  );

  const handleSelectModel = useCallback(
    (nextModelId: string, nextModelLabel: string) => {
      if (controlledActiveModelId === undefined) {
        setUncontrolledModelId(nextModelId);
      }
      onSelectActiveModel?.(nextModelId, nextModelLabel);
    },
    [controlledActiveModelId, onSelectActiveModel],
  );

  const handleThemeChange = useCallback(
    (next: ThemeMode) => {
      if (controlledTheme === undefined) setUncontrolledTheme(next);
      applyThemeToDocument(next);
      onThemeModeChange?.(next);
    },
    [controlledTheme, onThemeModeChange],
  );

  const handleDensityChange = useCallback(
    (next: DensityMode) => {
      if (controlledDensity === undefined) setUncontrolledDensity(next);
      applyDensityToDocument(next);
      onDensityModeChange?.(next);
    },
    [controlledDensity, onDensityModeChange],
  );

  const handleLocaleChange = useCallback(
    (next: LocaleCode) => {
      if (controlledLocale === undefined) setUncontrolledLocale(next);
      applyLocaleToDocument(next);
      onLocaleChange?.(next);
    },
    [controlledLocale, onLocaleChange],
  );

  const handleReduceMotionChange = useCallback(
    (next: boolean) => {
      if (controlledReduceMotion === undefined) setUncontrolledReduceMotion(next);
      applyReduceMotionToDocument(next);
      onReduceMotionChange?.(next);
    },
    [controlledReduceMotion, onReduceMotionChange],
  );

  const triggerToggleAirGap = useCallback(async () => {
    const previous = currentAirGapRef.current;
    const desired = !previous;
    if (controlledAirGap !== undefined && onToggleAirGap !== undefined && toggleAirGapFn === undefined) {
      onToggleAirGap(desired);
      return;
    }
    currentAirGapRef.current = desired;
    const reqSeq = ++airGapReqSeqRef.current;
    if (controlledAirGap === undefined) {
      setUncontrolledAirGap(desired);
    }
    onToggleAirGap?.(desired);
    try {
      const res = await (toggleAirGapFn ?? toggleAirGap)(desired);
      if (!mountedRef.current || reqSeq !== airGapReqSeqRef.current) return;
      currentAirGapRef.current = res.airGapEnabled;
      if (controlledAirGap === undefined) {
        setUncontrolledAirGap(res.airGapEnabled);
      }
      if (res.airGapEnabled !== desired) {
        onToggleAirGap?.(res.airGapEnabled);
      }
    } catch {
      if (!mountedRef.current || reqSeq !== airGapReqSeqRef.current) return;
      currentAirGapRef.current = previous;
      if (controlledAirGap === undefined) {
        setUncontrolledAirGap(previous);
      }
    }
  }, [controlledAirGap, onToggleAirGap, toggleAirGapFn]);

  useEffect(() => {
    if (disableGlobalAirGapShortcut || typeof window === "undefined") {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (document.querySelector('[role="dialog"], [role="alertdialog"]')) return;
      if (isEditableKeyboardTarget(event.target)) return;
      if (
        event.altKey &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        (event.code === "KeyA" || event.key.toLowerCase() === "a")
      ) {
        event.preventDefault();
        void triggerToggleAirGap();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [disableGlobalAirGapShortcut, triggerToggleAirGap]);

  const driftedCount = useMemo(
    () =>
      currentRules.filter((r) => isRuleDrifted(r, currentModelId, CURRENT_PROMPT_VERSION)).length,
    [currentRules, currentModelId],
  );

  const sidebarNode = useMemo(
    () => (
      <SettingsSubNav
        activeSubSection={currentSubSection}
        onSelectSubSection={selectSubSection}
        driftedRulesCount={driftedCount}
      />
    ),
    [currentSubSection, driftedCount, selectSubSection],
  );

  useEffect(() => {
    onSidebarStateChangeRef.current?.(sidebarNode);
  }, [sidebarNode]);

  return (
    <div className="flex h-full min-h-[480px] w-full flex-col overflow-hidden bg-canvas text-ui text-fg md:flex-row">
      {!renderSidebarInShell ? (
        <aside
          aria-label="Settings navigation"
          className="flex w-full shrink-0 flex-col overflow-x-auto border-b border-border bg-surface md:w-sidebar md:overflow-hidden md:border-b-0 md:border-e"
        >
          {sidebarNode}
        </aside>
      ) : null}

      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto px-8 py-7">
        <div>
          {currentSubSection === "permissions" ? (
            <SettingsPermissionsPanel
              scopedRules={controlledScopedRules}
              onUpdateScopedRules={handleUpdateRules}
              activeModelId={currentModelId}
              workspaceName={workspacePath}
              fetchManifestsFn={fetchManifestsFn}
              toggleManifestFn={toggleManifestFn}
              inspectManifestFn={inspectManifestFn}
            />
          ) : currentSubSection === "models" ? (
            <SettingsModelsPanel
              activeModelId={currentModelId}
              onSelectActiveModel={handleSelectModel}
              fetchWeightsFn={fetchWeightsFn}
              explainRoutingFn={explainRoutingFn}
            />
          ) : currentSubSection === "governance" ? (
            <SettingsGovernancePanel
              fetchPersistenceFn={fetchPersistenceFn}
              fetchPolicyFn={fetchPolicyFn}
              updatePolicyFn={updatePolicyFn}
              fetchKeysFn={fetchKeysFn}
              mintKeyFn={mintKeyFn}
              verifyKeyFn={verifyKeyFn}
              fetchSbomFn={fetchSbomFn}
            />
          ) : currentSubSection === "network" ? (
            <SettingsNetworkPanel
              airGapEnabled={currentAirGap}
              onToggleAirGap={() => void triggerToggleAirGap()}
              fetchAirGapAuditFn={fetchAirGapAuditFn}
              onOpenRecordAudit={onOpenRecordAudit}
            />
          ) : currentSubSection === "appearance" ? (
            <SettingsAppearancePanel
              themeMode={currentTheme}
              onThemeModeChange={handleThemeChange}
              densityMode={currentDensity}
              onDensityModeChange={handleDensityChange}
              locale={currentLocale}
              onLocaleChange={handleLocaleChange}
              reduceMotion={currentReduceMotion}
              onReduceMotionChange={handleReduceMotionChange}
            />
          ) : currentSubSection === "labs" ? (
            <SettingsLabsPanel runBenchmarkFn={runBenchmarkFn} />
          ) : currentSubSection === "general" ? (
            <SettingsGeneralPanel
              workspacePath={workspacePath}
              workspaceBranch={workspaceBranch}
              onOpenOnboarding={onOpenOnboarding}
            />
          ) : (
            <SettingsKeyboardPanel />
          )}
        </div>
      </div>
    </div>
  );
}
