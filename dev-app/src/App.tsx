import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlatformWorkspaceBar } from "@/components/platform/PlatformWorkspaceBar";
import { useUnifiedPlatformState } from "@/components/platform/useUnifiedPlatformState";
import { CommandPalette, type CommandPaletteSettingItem } from "@/components/shell/CommandPalette";
import { DevAppShell, type CompanionTab, type LogsDrawerTab } from "@/components/shell/DevAppShell";
import { OnboardingModal } from "@/components/shell/OnboardingModal";
import {
  FilesExplorerSidebar, FilesWorkspace,
  type FilesExplorerSidebarProps, type FilesNavigationTarget,
} from "@/components/screens/FilesWorkspace";
import { RecordAuditLedger } from "@/components/screens/RecordAuditLedger";
import {
  applyDensityToDocument, applyLocaleToDocument, applyReduceMotionToDocument, applyThemeToDocument,
  isEditableKeyboardTarget, SettingsSubNav, SettingsWorkspace,
} from "@/components/screens/SettingsWorkspace";
import { CURRENT_PROMPT_VERSION, isRuleDrifted } from "@/components/screens/settings/SettingsPermissionsPanel";
import {
  buildLogsDrawerTabPanels, ReviewChangesContent, TasksWorkspace, type TerminalExecEntry,
} from "@/components/screens/TasksWorkspace";
import {
  connectStudioWebSocket, createApprovalRule, execSandboxTerminal, fetchAirGapAudit,
  fetchApprovalRules, fetchCodebaseSymbols,
  fetchFilesTree, fetchOpenCoreWeights, fetchStudioDiff, toggleAirGap,
} from "@/lib/api";
import { getFallbackDiffHunks } from "@/lib/apiFallbacks";
import {
  buildApprovalReceipt, buildPaletteModelsAndSettings,
  INITIAL_PROPOSALS, INITIAL_STEP_RECEIPTS, INITIAL_TASKS,
  mergeFocusedDiffHunks, readInitialUrlState, resolveMainAriaLabel, syncWorkspaceUrlParams,
} from "@/lib/appStateHelpers";
import type {
  CodeSymbolItem, DensityMode, EgressTelemetryState, FileDiffHunk, LocaleCode,
  OpenCoreWeightItem, P10ApprovalDecisionPayload, P10ApprovalReceipt, P10ScopedRuleSpec,
  PlatformViewId, RailSection, ApprovalRuleItem, SettingsSubSection, SidebarTaskItem, ThemeMode,
  WorkspaceFileNode,
} from "@/lib/types";

export interface AppProps {
  initialSection?: RailSection;
  initialSettingsSubSection?: SettingsSubSection;
  initialOnboardingOpen?: boolean;
  isDesktopApp?: boolean;
  isMobileCompanion?: boolean;
}

export function App({
  initialSection,
  initialSettingsSubSection,
  initialOnboardingOpen,
  isDesktopApp = false,
  isMobileCompanion,
}: AppProps): React.JSX.Element {
  const urlInit = useMemo(() => readInitialUrlState(), []);

  const [activeSection, setActiveSection] = useState<RailSection>(
    initialSection ?? urlInit.section ?? "tasks",
  );
  const [settingsSubSection, setSettingsSubSection] = useState<SettingsSubSection>(
    initialSettingsSubSection ?? urlInit.settings ?? "permissions",
  );
  const [companionTab, setCompanionTab] = useState<CompanionTab>("tasks");
  const [isNarrowViewport, setIsNarrowViewport] = useState<boolean>(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 767px)").matches
      : false,
  );
  const effectiveMobileCompanion = isMobileCompanion ?? (urlInit.companion || isNarrowViewport);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(max-width: 767px)");
    const onChange = (e: MediaQueryListEvent) => setIsNarrowViewport(e.matches);
    setIsNarrowViewport(mql.matches);
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    return undefined;
  }, []);

  const [themeMode, setThemeMode] = useState<ThemeMode>("dark");
  const [densityMode, setDensityMode] = useState<DensityMode>("default");
  const [locale, setLocale] = useState<LocaleCode>("en-US");
  const [reduceMotion, setReduceMotion] = useState(false);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (themeMode !== "system" || typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => applyThemeToDocument("system");
    applyThemeToDocument("system");
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    return undefined;
  }, [themeMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onPopState = () => {
      const next = readInitialUrlState();
      if (next.section) setActiveSection(next.section);
      if (next.settings) setSettingsSubSection(next.settings);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const [workspacePath, setWorkspacePath] = useState("/workspace/keelway");
  const [workspaceBranch, setWorkspaceBranch] = useState("feat/unified-dev-app");
  const [onboardingOpen, setOnboardingOpen] = useState<boolean>(
    initialOnboardingOpen ?? urlInit.onboarding,
  );
  const [paletteOpen, setPaletteOpen] = useState(false);

  const [tasks, setTasks] = useState<SidebarTaskItem[]>(INITIAL_TASKS);
  const [activeTaskId, setActiveTaskId] = useState<string>(INITIAL_TASKS[0]!.id);
  const [receiptsByProposalId, setReceiptsByProposalId] = useState<Record<string, P10ApprovalReceipt>>({});
  const [composerValue, setComposerValue] = useState("");
  const [politeAnnouncement, setPoliteAnnouncement] = useState("");

  const [reviewOpen, setReviewOpen] = useState(false);
  const [diffHunks, setDiffHunks] = useState<FileDiffHunk[]>(() => getFallbackDiffHunks());
  const [reviewStatus, setReviewStatus] = useState<"pending" | "kept" | "reverted">("pending");

  const [logsOpen, setLogsOpen] = useState(false);
  const [logsTab, setLogsTab] = useState<LogsDrawerTab>("logs");
  const [logLines, setLogLines] = useState<string[]>([
    "[loopback] Seatbelt workspace isolation active · writes scoped to project root.",
  ]);
  const [terminalCommand, setTerminalCommand] = useState("");
  const [terminalRunning, setTerminalRunning] = useState(false);
  const [terminalHistory, setTerminalHistory] = useState<TerminalExecEntry[]>([]);

  const [egress, setEgress] = useState<EgressTelemetryState>({
    mode: "unmeasured",
    cloudCallsCount: 0,
    bytesSent: null,
    airGapLocked: false,
    endpoints: [],
  });

  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFileNode[]>([]);
  const [workspaceSymbols, setWorkspaceSymbols] = useState<CodeSymbolItem[]>([]);
  const [openCoreWeights, setOpenCoreWeights] = useState<OpenCoreWeightItem[]>([]);
  const [filesNavTarget, setFilesNavTarget] = useState<FilesNavigationTarget | undefined>(undefined);
  const [filesSidebarProps, setFilesSidebarProps] = useState<FilesExplorerSidebarProps | null>(null);

  const [recordSelectedSeq, setRecordSelectedSeq] = useState<number | null | undefined>(undefined);
  const [recordVerifyNonce, setRecordVerifyNonce] = useState(0);
  const [recordSeqLatest, setRecordSeqLatest] = useState(1283);

  const [scopedRules, setScopedRules] = useState<ApprovalRuleItem[]>([]);
  const [activeModelId, setActiveModelId] = useState("keelway-core:7b");
  const [activeModelLabel, setActiveModelLabel] = useState("coder-7b v2.5.1");

  const approvalHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const navNonceRef = useRef(0);
  const taskSeqRef = useRef(3);
  const airGapLockedRef = useRef(egress.airGapLocked);
  airGapLockedRef.current = egress.airGapLocked;
  const airGapReqSeqRef = useRef(0);

  const syncUrlParams = useCallback(syncWorkspaceUrlParams, []);

  const handleBumpRecordSeq = useCallback(() => {
    let nextVal = 1284;
    setRecordSeqLatest((prev) => {
      nextVal = prev + 1;
      return nextVal;
    });
    return nextVal;
  }, []);

  const handleJumpToIdeComposer = useCallback(
    (prefill: string) => {
      setComposerValue(prefill);
      setActiveSection("tasks");
      syncUrlParams("tasks", settingsSubSection);
      setTimeout(() => composerTextareaRef.current?.focus(), 0);
    },
    [settingsSubSection, syncUrlParams],
  );

  const {
    platformView,
    setPlatformView,
    experienceMode,
    setExperienceMode,
    subscriptionTier,
    setSubscriptionTier,
    activeWorkspaceId,
    setActiveWorkspaceId,
    workspaces,
    handleCreateWorkspace,
    activeRbacRole,
    setActiveRbacRole,
    renderPlatformCanvas,
  } = useUnifiedPlatformState({
    onJumpToIdeComposer: handleJumpToIdeComposer,
    onBumpRecordSeq: handleBumpRecordSeq,
  });

  const handleSelectSection = useCallback(
    (next: RailSection) => {
      setPlatformView("ide");
      setActiveSection(next);
      syncUrlParams(next, settingsSubSection);
    },
    [setPlatformView, settingsSubSection, syncUrlParams],
  );

  const handleSelectPlatformView = useCallback(
    (nextView: PlatformViewId) => {
      setPlatformView(nextView);
      if (nextView === "ide" && activeSection !== "tasks" && activeSection !== "files") {
        setActiveSection("tasks");
        syncUrlParams("tasks", settingsSubSection);
      } else if (nextView === "security") {
        setActiveSection("record");
        syncUrlParams("record", settingsSubSection);
      }
    },
    [activeSection, setPlatformView, settingsSubSection, syncUrlParams],
  );

  const handleSelectSettingsSubSection = useCallback(
    (nextSub: SettingsSubSection) => {
      setPlatformView("ide");
      setSettingsSubSection(nextSub);
      syncUrlParams("settings", nextSub);
    },
    [setPlatformView, syncUrlParams],
  );

  useEffect(() => {
    let cancelled = false;
    const noteLoadFailure = (label: string, err: unknown) => {
      if (!cancelled) setLogLines((prev) => [...prev, `[load] ${label} failed: ${err instanceof Error ? err.message : "unknown error"}`]);
    };
    fetchFilesTree().then((nodes) => { if (!cancelled) setWorkspaceFiles(nodes); }).catch((err) => noteLoadFailure("workspace tree", err));
    fetchCodebaseSymbols().then((syms) => { if (!cancelled) setWorkspaceSymbols(syms); }).catch((err) => noteLoadFailure("codebase symbols", err));
    fetchStudioDiff().then((hunks) => { if (!cancelled) setDiffHunks(hunks); }).catch((err) => noteLoadFailure("studio diff", err));
    fetchOpenCoreWeights().then((w) => { if (!cancelled) setOpenCoreWeights(w); }).catch((err) => noteLoadFailure("OpenCore weights", err));
    fetchApprovalRules().then((rules) => { if (!cancelled) setScopedRules(rules); }).catch((err) => noteLoadFailure("approval rules", err));
    fetchAirGapAudit()
      .then((audit) => {
        if (!cancelled && airGapReqSeqRef.current === 0) {
          airGapLockedRef.current = audit.airGapLocked;
          setEgress(audit);
        }
      })
      .catch((err) => {
        if (!cancelled) setLogLines((prev) => [...prev, `[load] air-gap audit failed: ${err instanceof Error ? err.message : "unknown error"}`]);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const sub = connectStudioWebSocket((evt) => {
      setLogLines((prev) => [...prev, `[ws:${evt.type}] ${evt.timestamp}`]);
      const maybeSeq = evt.payload.seq ?? evt.payload.recordSeq;
      if (typeof maybeSeq === "number") {
        setRecordSeqLatest((prev) => Math.max(prev, maybeSeq));
      }
    });
    return () => sub.close();
  }, []);

  const handleToggleAirGap = useCallback(async (explicitNext?: boolean) => {
    const previous = airGapLockedRef.current;
    const desired = explicitNext ?? !previous;
    airGapLockedRef.current = desired;
    const reqSeq = ++airGapReqSeqRef.current;
    setEgress((prev) => ({
      ...prev,
      airGapLocked: desired,
      mode: desired ? "air_gapped_verified" : "unmeasured",
    }));
    try {
      const res = await toggleAirGap(desired);
      if (!mountedRef.current || reqSeq !== airGapReqSeqRef.current) return;
      airGapLockedRef.current = res.airGapEnabled;
      setEgress((curr) => ({ ...curr, airGapLocked: res.airGapEnabled, mode: res.mode, lastCheckedAt: res.verifiedAt }));
    } catch {
      if (!mountedRef.current || reqSeq !== airGapReqSeqRef.current) return;
      airGapLockedRef.current = previous;
      setEgress((curr) => ({ ...curr, airGapLocked: previous, mode: previous ? "air_gapped_verified" : "unmeasured" }));
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onKeyDown = (event: KeyboardEvent) => {
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
        void handleToggleAirGap();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleToggleAirGap]);

  const handleJumpToApprovalHeading = useCallback(() => {
    const pendingTask = tasks.find((t) => t.status === "needs_approval");
    if (pendingTask) setActiveTaskId(pendingTask.id);
    handleSelectSection("tasks");
    setTimeout(() => approvalHeadingRef.current?.focus(), 0);
  }, [handleSelectSection, tasks]);

  const handleSelectActiveModel = useCallback(
    (nextModelId: string, nextModelLabel: string) => {
      setActiveModelId(nextModelId);
      setActiveModelLabel(nextModelLabel);
    },
    [],
  );

  const handleProposalDecision = useCallback(
    (payload: P10ApprovalDecisionPayload): P10ApprovalReceipt => {
      const nextSeq = recordSeqLatest + 1;
      const receipt = buildApprovalReceipt(payload, nextSeq);
      setReceiptsByProposalId((prev) => ({ ...prev, [payload.proposalId]: receipt }));
      setRecordSeqLatest(nextSeq);
      setTasks((prev) =>
        prev.map((t) =>
          t.id === payload.taskId
            ? { ...t, status: payload.decision === "deny" ? "ready" : "done", updatedAt: "just now" }
            : t,
        ),
      );
      return receipt;
    },
    [recordSeqLatest],
  );

  const handleCreateScopedRule = useCallback(
    (spec: P10ScopedRuleSpec) => {
      void createApprovalRule({
        toolName: spec.actionKind === "command" ? "run_command" : "edit_file",
        scope: spec.scopePattern,
        modelId: spec.modelId || activeModelId,
        promptVersion: spec.promptVersion,
      })
        .then(({ rule }) => {
          setScopedRules((prev) =>
            prev.some((r) => r.id === rule.id) ? prev : [rule, ...prev],
          );
        })
        .catch((err) => {
          setLogLines((prev) => [...prev, `[permissions] standing approval rule NOT saved: ${err instanceof Error ? err.message : "unknown error"}`]);
        });
    },
    [activeModelId],
  );

  const handleRunTerminal = (event: React.FormEvent) => {
    event.preventDefault();
    const cmd = terminalCommand.trim();
    if (!cmd || terminalRunning) return;
    setTerminalRunning(true);
    execSandboxTerminal(cmd)
      .then((res) => {
        setTerminalHistory((prev) => [
          ...prev,
          {
            id: `term-${++navNonceRef.current}`,
            command: cmd,
            stdout: res.stdout,
            stderr: res.stderr,
            exitCode: res.exitCode,
            durationMs: res.durationMs,
          },
        ]);
        setLogLines((prev) => [...prev, `[sandbox] $ ${cmd} -> exit ${res.exitCode}`]);
        setTerminalCommand("");
      })
      .catch((err) => {
        const msg = err instanceof Error ? err.message : "unknown error";
        setLogLines((prev) => [...prev, `[sandbox] $ ${cmd} -> request failed: ${msg}`]);
        setTerminalHistory((prev) => [
          ...prev,
          { id: `term-${++navNonceRef.current}`, command: cmd, stdout: "", stderr: `request failed: ${msg}`, exitCode: -1, durationMs: 0 },
        ]);
      })
      .finally(() => setTerminalRunning(false));
  };

  const handleRunCommand = useCallback(
    (commandId: string) => {
      if (commandId === "verify-chain") {
        setRecordVerifyNonce((n) => n + 1);
        handleSelectSection("record");
        return;
      }
      if (commandId === "toggle-air-gap") {
        void handleToggleAirGap();
        return;
      }
      if (commandId === "switch-local-model") {
        handleSelectActiveModel("keelway-core:7b", "coder-7b v2.5.1");
        return;
      }
      if (commandId.startsWith("kstack-")) {
        const slash = commandId.replace("kstack-", "/");
        setComposerValue(`${slash} `);
        handleSelectSection("tasks");
        setTimeout(() => composerTextareaRef.current?.focus(), 0);
      }
    },
    [handleSelectActiveModel, handleSelectSection, handleToggleAirGap],
  );

  const handleSelectSettingOrModel = useCallback(
    (item: CommandPaletteSettingItem) => {
      if (item.kind === "model" && item.modelId) {
        handleSelectActiveModel(item.modelId, item.modelLabel ?? item.label);
        return;
      }
      if (item.settingsSection) {
        setPlatformView("ide");
        setSettingsSubSection(item.settingsSection);
        setActiveSection("settings");
        syncUrlParams("settings", item.settingsSection);
      }
    },
    [handleSelectActiveModel, setPlatformView, syncUrlParams],
  );

  const handleOpenDiffInReview = useCallback(
    (diffPath: string, seq?: number) => {
      setDiffHunks((prev) => mergeFocusedDiffHunks(prev, [], diffPath, seq));
      setReviewStatus("pending");
      setReviewOpen(true);
      if (effectiveMobileCompanion) {
        setCompanionTab("tasks");
        handleSelectSection("tasks");
      }
      fetchStudioDiff(diffPath)
        .then((fetched) => {
          if (mountedRef.current) {
            setDiffHunks((curr) => mergeFocusedDiffHunks(curr, fetched, diffPath, seq));
          }
        })
        .catch((err) => {
          if (mountedRef.current) setLogLines((prev) => [...prev, `[load] diff refresh failed: ${err instanceof Error ? err.message : "unknown error"}`]);
        });
    },
    [effectiveMobileCompanion, handleSelectSection],
  );

  const paletteModelsAndSettings = useMemo(
    () => buildPaletteModelsAndSettings(openCoreWeights),
    [openCoreWeights],
  );

  const activeTask = useMemo(
    () => tasks.find((t) => t.id === activeTaskId) ?? tasks[0]!,
    [activeTaskId, tasks],
  );
  const activeTaskProposals = useMemo(
    () => INITIAL_PROPOSALS.filter((p) => p.taskId === activeTask.id),
    [activeTask.id],
  );
  const driftedRulesCount = useMemo(
    () =>
      scopedRules.filter((r) => isRuleDrifted(r, activeModelId, CURRENT_PROMPT_VERSION)).length,
    [scopedRules, activeModelId],
  );

  const contextSidebarContent = useMemo(() => {
    if (activeSection === "files") {
      const effectiveProps: FilesExplorerSidebarProps = filesSidebarProps ?? {
        tree: workspaceFiles,
        symbols: workspaceSymbols,
        activeTab: "tree",
        onTabChange: () => {},
        activePath: filesNavTarget?.path ?? "core/main.py",
        dirtyByPath: {},
        saveErrorsByPath: {},
        onSelectFile: (path: string) =>
          setFilesNavTarget({ path, line: 1, nonce: ++navNonceRef.current }),
        onSelectSymbol: (sym: CodeSymbolItem) =>
          setFilesNavTarget({ path: sym.path, line: sym.line, nonce: ++navNonceRef.current }),
      };
      return <FilesExplorerSidebar {...effectiveProps} />;
    }
    if (activeSection === "settings") {
      return (
        <SettingsSubNav
          activeSubSection={settingsSubSection}
          onSelectSubSection={handleSelectSettingsSubSection}
          driftedRulesCount={driftedRulesCount}
        />
      );
    }
    return undefined;
  }, [
    activeSection, driftedRulesCount, filesNavTarget?.path, filesSidebarProps,
    handleSelectSettingsSubSection, settingsSubSection, workspaceFiles, workspaceSymbols,
  ]);

  const contextSidebarLabel =
    activeSection === "files"
      ? "Files explorer"
      : activeSection === "settings"
        ? "Settings navigation"
        : undefined;

  const pendingApprovalCount = useMemo(
    () => tasks.filter((t) => t.status === "needs_approval").length,
    [tasks],
  );

  const mainAriaLabel = resolveMainAriaLabel(platformView, activeSection);

  return (
    <>
      <DevAppShell
        activeSection={activeSection}
        onSelectSection={handleSelectSection}
        tasks={tasks}
        activeTaskId={activeTask.id}
        onSelectTask={(id) => {
          setActiveTaskId(id);
          handleSelectSection("tasks");
        }}
        onNewTask={() => {
          const id = `task-local-${++taskSeqRef.current}`;
          const created: SidebarTaskItem = {
            id,
            title: `Workspace task #${taskSeqRef.current}`,
            status: "ready",
            branch: workspaceBranch,
            modelLabel: activeModelLabel,
            updatedAt: "just now",
          };
          setTasks((prev) => [created, ...prev]);
          setActiveTaskId(id);
        }}
        onJumpToApprovalHeading={handleJumpToApprovalHeading}
        contextSidebarContent={contextSidebarContent}
        contextSidebarLabel={contextSidebarLabel}
        hideSidebar={platformView !== "ide"}
        topWorkspaceBar={
          <PlatformWorkspaceBar
            activeView={platformView}
            onSelectView={handleSelectPlatformView}
            experienceMode={experienceMode}
            onChangeExperienceMode={setExperienceMode}
            subscriptionTier={subscriptionTier}
            onChangeSubscriptionTier={setSubscriptionTier}
            workspacePath={workspacePath}
            workspaceBranch={workspaceBranch}
            activeModelLabel={activeModelLabel}
            pendingApprovalCount={pendingApprovalCount}
            activeWorkspaceId={activeWorkspaceId}
            workspaces={workspaces}
            onSelectWorkspaceId={setActiveWorkspaceId}
            onCreateWorkspace={handleCreateWorkspace}
            activeRbacRole={activeRbacRole}
            onChangeRbacRole={setActiveRbacRole}
          />
        }
        reviewDrawerOpen={reviewOpen}
        onToggleReviewDrawer={setReviewOpen}
        reviewDrawerTitle="Review changes"
        reviewDrawerContent={
          <ReviewChangesContent
            hunks={diffHunks}
            reviewStatus={reviewStatus}
            onKeepChanges={() => setReviewStatus("kept")}
            onRevertAll={() => {
              setDiffHunks([]);
              setReviewStatus("reverted");
            }}
            onAskForChanges={(hunk) => {
              const endLine = Math.max(hunk.newStart, hunk.newStart + Math.max(hunk.additions - 1, 0));
              setComposerValue(`Please revise ${hunk.path}:${hunk.newStart}-${endLine} — `);
              handleSelectSection("tasks");
              setTimeout(() => composerTextareaRef.current?.focus(), 0);
            }}
          />
        }
        logsDrawerOpen={logsOpen}
        onToggleLogsDrawer={setLogsOpen}
        logsTab={logsTab}
        onSelectLogsTab={setLogsTab}
        logsDrawerContent={buildLogsDrawerTabPanels({
          logLines,
          terminalCommand,
          onTerminalCommandChange: setTerminalCommand,
          terminalRunning,
          terminalHistory,
          onRunTerminal: handleRunTerminal,
          egressMode: egress.mode,
          airGapEnabled: egress.airGapLocked,
          onToggleAirGap: () => void handleToggleAirGap(),
        })}
        egress={egress}
        offlineSetting={true}
        onSwitchToLocalModel={() => handleSelectActiveModel("keelway-core:7b", "coder-7b v2.5.1")}
        onGoOffline={() => void handleToggleAirGap(true)}
        onOpenCommandPalette={() => setPaletteOpen(true)}
        workspaceBranch={workspaceBranch}
        activeModelLabel={activeModelLabel}
        recordSeqLatest={recordSeqLatest}
        mainAriaLabel={mainAriaLabel}
        politeAnnouncement={politeAnnouncement}
        isDesktopApp={isDesktopApp}
        isMobileCompanion={effectiveMobileCompanion}
        activeCompanionTab={companionTab}
        onSelectCompanionTab={setCompanionTab}
      >
        {platformView !== "ide" ? (
          renderPlatformCanvas({
            selectedSeq: recordSelectedSeq,
            onSelectSeq: setRecordSelectedSeq,
            verifyRequestNonce: recordVerifyNonce,
            onOpenDiffInReview: handleOpenDiffInReview,
          })
        ) : activeSection === "tasks" ? (
          <TasksWorkspace
            taskId={activeTask.id}
            taskTitle={activeTask.title}
            workspaceBranch={workspaceBranch}
            activeModelLabel={activeModelLabel}
            stepReceipts={activeTask.id === "task-csp-gate" ? INITIAL_STEP_RECEIPTS : []}
            proposals={activeTaskProposals}
            receipts={receiptsByProposalId}
            diffHunks={diffHunks}
            reviewOpen={reviewOpen}
            onToggleReview={setReviewOpen}
            renderReviewInShell={!effectiveMobileCompanion}
            logsOpen={logsOpen}
            onToggleLogs={setLogsOpen}
            renderLogsInShell={true}
            composerValue={composerValue}
            onComposerValueChange={setComposerValue}
            composerTextareaRef={composerTextareaRef}
            approvalHeadingRef={approvalHeadingRef}
            onPoliteAnnouncement={setPoliteAnnouncement}
            onSubmitDecision={handleProposalDecision}
            onCreateScopedRule={handleCreateScopedRule}
          />
        ) : activeSection === "files" ? (
          <FilesWorkspace
            navigationTarget={filesNavTarget}
            renderSidebarInShell={!effectiveMobileCompanion}
            onSidebarStateChange={setFilesSidebarProps}
            onTreeLoaded={setWorkspaceFiles}
            onSymbolsLoaded={setWorkspaceSymbols}
          />
        ) : activeSection === "record" ? (
          <RecordAuditLedger
            selectedSeq={recordSelectedSeq}
            onSelectSeq={setRecordSelectedSeq}
            verifyRequestNonce={recordVerifyNonce}
            onOpenDiffInReview={handleOpenDiffInReview}
          />
        ) : (
          <SettingsWorkspace
            activeSubSection={settingsSubSection}
            onSelectSubSection={handleSelectSettingsSubSection}
            renderSidebarInShell={!effectiveMobileCompanion}
            themeMode={themeMode}
            onThemeModeChange={(next) => { setThemeMode(next); applyThemeToDocument(next); }}
            densityMode={densityMode}
            onDensityModeChange={(next) => { setDensityMode(next); applyDensityToDocument(next); }}
            locale={locale}
            onLocaleChange={(next) => { setLocale(next); applyLocaleToDocument(next); }}
            reduceMotion={reduceMotion}
            onReduceMotionChange={(next) => { setReduceMotion(next); applyReduceMotionToDocument(next); }}
            airGapEnabled={egress.airGapLocked}
            onToggleAirGap={(enabled) => void handleToggleAirGap(enabled)}
            disableGlobalAirGapShortcut={true}
            scopedRules={scopedRules}
            onUpdateScopedRules={setScopedRules}
            activeModelId={activeModelId}
            onSelectActiveModel={handleSelectActiveModel}
            workspacePath={workspacePath}
            workspaceBranch={workspaceBranch}
            onOpenOnboarding={() => setOnboardingOpen(true)}
          />
        )}
      </DevAppShell>

      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        disableGlobalShortcut={true}
        tasks={tasks}
        files={workspaceFiles}
        symbols={workspaceSymbols}
        modelsAndSettings={paletteModelsAndSettings}
        onRunCommand={handleRunCommand}
        onSelectPlatformView={handleSelectPlatformView}
        onSelectTask={(taskId) => { setActiveTaskId(taskId); handleSelectSection("tasks"); }}
        onJumpToApprovalHeading={handleJumpToApprovalHeading}
        onSelectFile={(filePath) => {
          setFilesNavTarget({ path: filePath, line: 1, nonce: ++navNonceRef.current });
          handleSelectSection("files");
        }}
        onSelectSymbol={(sym) => {
          setFilesNavTarget({ path: sym.path, line: sym.line, nonce: ++navNonceRef.current });
          handleSelectSection("files");
        }}
        onSelectSettingOrModel={handleSelectSettingOrModel}
      />

      <OnboardingModal
        open={onboardingOpen}
        onOpenChange={setOnboardingOpen}
        defaultWorkspacePath={workspacePath}
        onComplete={({ workspacePath: chosenPath, branch }) => {
          setWorkspacePath(chosenPath);
          if (branch) setWorkspaceBranch(branch);
        }}
        onOpenSettingsLater={() => {
          setOnboardingOpen(false);
          handleSelectSection("settings");
        }}
      />
    </>
  );
}
export default App;
