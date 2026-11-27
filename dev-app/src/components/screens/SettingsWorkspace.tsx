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
import { SettingsBillingPanel } from "@/components/screens/settings/SettingsBillingPanel";
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
  SubscriptionTierId,
} from "@/lib/types";

import {
  applyDensityToDocument,
  applyLocaleToDocument,
  applyReduceMotionToDocument,
  applyThemeToDocument,
  isEditableKeyboardTarget,
  SettingsSubNav,
} from "@/components/screens/settings/navigation";

export { ORLA_UNMEASURED_NETWORK_COPY };
export {
  SETTINGS_SUB_SECTIONS,
  isEditableKeyboardTarget,
  applyThemeToDocument,
  applyDensityToDocument,
  applyLocaleToDocument,
  applyReduceMotionToDocument,
  SettingsSubNav,
  type SettingsSubNavProps,
} from "@/components/screens/settings/navigation";

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
  subscriptionTier?: SubscriptionTierId;
  onChangeSubscriptionTier?: (tier: SubscriptionTierId) => void;
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
    subscriptionTier = "pro",
    onChangeSubscriptionTier,
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
          ) : currentSubSection === "billing" ? (
            <SettingsBillingPanel
              subscriptionTier={subscriptionTier}
              onChangeSubscriptionTier={onChangeSubscriptionTier}
            />
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
