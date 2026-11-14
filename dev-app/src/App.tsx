import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  DEFAULT_SCOPED_RULES, isEditableKeyboardTarget, SettingsSubNav, SettingsWorkspace,
} from "@/components/screens/SettingsWorkspace";
import {
  buildLogsDrawerTabPanels, ReviewChangesContent, TasksWorkspace, type TerminalExecEntry,
} from "@/components/screens/TasksWorkspace";
import {
  connectStudioWebSocket, execSandboxTerminal, fetchCodebaseSymbols,
  fetchFilesTree, fetchStudioDiff, toggleAirGap,
} from "@/lib/api";
import { getFallbackDiffHunks } from "@/lib/apiFallbacks";
import type {
  CodeSymbolItem, DensityMode, EgressTelemetryState, FileDiffHunk, LocaleCode,
  P10ApprovalDecisionPayload, P10ApprovalProposal, P10ApprovalReceipt, P10ScopedRuleSpec,
  RailSection, ScopedPermissionRule, SettingsSubSection, SidebarTaskItem, StepReceiptItem,
  ThemeMode, WorkspaceFileNode,
} from "@/lib/types";

function isRailSection(val: string | null): val is RailSection {
  return val === "tasks" || val === "files" || val === "record" || val === "settings";
}

function isSettingsSubSection(val: string | null): val is SettingsSubSection {
  return (
    val === "permissions" ||
    val === "models" ||
    val === "governance" ||
    val === "network" ||
    val === "appearance" ||
    val === "labs" ||
    val === "general" ||
    val === "keyboard"
  );
}

function readInitialUrlState(): {
  section?: RailSection;
  settings?: SettingsSubSection;
  companion: boolean;
  onboarding: boolean;
} {
  if (typeof window === "undefined") {
    return { companion: false, onboarding: false };
  }
  try {
    const params = new URLSearchParams(window.location.search);
    const rawSection = params.get("section");
    const rawSettings = params.get("settings");
    return {
      section: isRailSection(rawSection) ? rawSection : undefined,
      settings: isSettingsSubSection(rawSettings) ? rawSettings : undefined,
      companion: params.get("companion") === "1",
      onboarding: params.get("onboarding") === "1",
    };
  } catch {
    return { companion: false, onboarding: false };
  }
}

const INITIAL_TASKS: SidebarTaskItem[] = [
  {
    id: "task-csp-gate",
    title: "Harden loopback CSP & verify Studio token middleware",
    status: "needs_approval",
    branch: "feat/unified-dev-app",
    modelLabel: "coder-7b v2.5.1",
    updatedAt: "2m ago",
    pendingApprovalId: "prop-csp-pytest",
    filesChangedCount: 1,
  },
  {
    id: "task-merkle-audit",
    title: "Audit SHA-256 Merkle inclusion proofs",
    status: "ready",
    branch: "feat/unified-dev-app",
    modelLabel: "coder-7b v2.5.1",
    updatedAt: "14m ago",
    filesChangedCount: 0,
  },
];

const INITIAL_PROPOSALS: P10ApprovalProposal[] = [
  {
    id: "prop-csp-pytest",
    taskId: "task-csp-gate",
    kind: "command",
    title: "Run pytest Studio CSP suite",
    summary: "Execute isolated pytest verification over Studio strict CSP and loopback auth.",
    whyReason: "Confirm X-Content-Type-Options and strict 'self' CSP headers pass before commit.",
    command: "pytest tests/test_studio.py -q",
    workingDir: "/workspace/keelway",
    previewStatus: "ready",
    modelId: "coder-7b",
    modelVersion: "2.5.1",
    promptVersion: "p-14",
    confidence: "Medium",
    createdAt: "2026-11-14T02:14:20Z",
    recordSeqCandidate: 1284,
  },
];

const INITIAL_STEP_RECEIPTS: StepReceiptItem[] = [
  { id: "step-read-main", kind: "read", title: "Read file", target: "core/main.py", status: "ready", recordSeq: 1281 },
  {
    id: "step-edit-csp",
    kind: "edited",
    title: "Edited file",
    target: "core/main.py",
    linesAdded: 3,
    linesRemoved: 1,
    status: "ready",
    recordSeq: 1283,
  },
];

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
  const [filesNavTarget, setFilesNavTarget] = useState<FilesNavigationTarget | undefined>(undefined);
  const [filesSidebarProps, setFilesSidebarProps] = useState<FilesExplorerSidebarProps | null>(null);

  const [recordSelectedSeq, setRecordSelectedSeq] = useState<number | null | undefined>(undefined);
  const [recordVerifyNonce, setRecordVerifyNonce] = useState(0);
  const [recordSeqLatest, setRecordSeqLatest] = useState(1283);

  const [scopedRules, setScopedRules] = useState<ScopedPermissionRule[]>(() =>
    structuredClone(DEFAULT_SCOPED_RULES),
  );
  const [activeModelId, setActiveModelId] = useState("keelway-core:7b");
  const [activeModelLabel, setActiveModelLabel] = useState("coder-7b v2.5.1");

  const approvalHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const composerTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const navNonceRef = useRef(0);
  const taskSeqRef = useRef(3);

  const syncUrlParams = useCallback((nextSection: RailSection, nextSettings: SettingsSubSection) => {
    if (typeof window === "undefined" || !window.history?.replaceState) return;
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("section", nextSection);
      if (nextSection === "settings") {
        url.searchParams.set("settings", nextSettings);
      } else {
        url.searchParams.delete("settings");
      }
      window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
    } catch {
      // Ignore URL update errors in constrained environments
    }
  }, []);

  const handleSelectSection = useCallback(
    (next: RailSection) => {
      setActiveSection(next);
      syncUrlParams(next, settingsSubSection);
    },
    [settingsSubSection, syncUrlParams],
  );

  const handleSelectSettingsSubSection = useCallback(
    (nextSub: SettingsSubSection) => {
      setSettingsSubSection(nextSub);
      syncUrlParams("settings", nextSub);
    },
    [syncUrlParams],
  );

  useEffect(() => {
    let cancelled = false;
    fetchFilesTree().then((nodes) => { if (!cancelled) setWorkspaceFiles(nodes); }).catch(() => {});
    fetchCodebaseSymbols().then((syms) => { if (!cancelled) setWorkspaceSymbols(syms); }).catch(() => {});
    fetchStudioDiff().then((hunks) => { if (!cancelled) setDiffHunks(hunks); }).catch(() => {});
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

  const airGapLockedRef = useRef(egress.airGapLocked);
  airGapLockedRef.current = egress.airGapLocked;
  const airGapReqSeqRef = useRef(0);

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
      if (nextModelId !== activeModelId) {
        setScopedRules((prev) => prev.map((rule) => ({ ...rule, driftDetected: true })));
      }
      setActiveModelId(nextModelId);
      setActiveModelLabel(nextModelLabel);
    },
    [activeModelId],
  );

  const handleProposalDecision = useCallback(
    (payload: P10ApprovalDecisionPayload): P10ApprovalReceipt => {
      const nextSeq = recordSeqLatest + 1;
      const receipt: P10ApprovalReceipt = {
        proposalId: payload.proposalId,
        recordSeq: nextSeq,
        decision: payload.decision,
        summary:
          payload.decision === "deny" && payload.denyReason
            ? `Denied — ${payload.denyReason}`
            : "Run pytest Studio CSP suite",
        modifiedByUser: Boolean(payload.modifiedCommand || payload.modifiedTargetPath),
        ...(payload.escalatedToNetwork ? { escalatedByEdit: true } : {}),
        decidedAt: payload.decidedAt,
        actorLabel: "you (local keyboard)",
      };
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
      const created: ScopedPermissionRule = {
        id: `rule-${Date.now()}`,
        capability: spec.actionKind === "command" ? "Run sandboxed command" : "Edit workspace files",
        scopePattern: spec.scopePattern,
        mode: "allow_scoped",
        boundModelId: activeModelId,
        boundPromptVersion: spec.promptVersion,
        currentPromptVersion: spec.promptVersion,
        driftDetected: false,
        createdAt: new Date().toISOString(),
      };
      setScopedRules((prev) => [created, ...prev]);
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
      .catch(() => {})
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
        handleSelectActiveModel("keelway-core:7b", item.modelId);
        return;
      }
      if (item.settingsSection) {
        setSettingsSubSection(item.settingsSection);
        setActiveSection("settings");
        syncUrlParams("settings", item.settingsSection);
      }
    },
    [handleSelectActiveModel, syncUrlParams],
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
    () => scopedRules.filter((r) => r.driftDetected).length,
    [scopedRules],
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

  const mainAriaLabel =
    activeSection === "files"
      ? "Files codebase workspace"
      : activeSection === "record"
        ? "Record audit ledger"
        : activeSection === "settings"
          ? "Settings sovereign control plane"
          : "Agent workspace";

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
        {activeSection === "tasks" ? (
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
            renderReviewInShell={true}
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
            onOpenDiffInReview={(diffPath) => {
              setDiffHunks((prev) => {
                if (prev.length > 0) return prev;
                const matched = getFallbackDiffHunks().filter((h) => h.path === diffPath);
                return matched.length > 0 ? matched : getFallbackDiffHunks();
              });
              setReviewOpen(true);
            }}
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
        onRunCommand={handleRunCommand}
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
        onComplete={({ workspacePath: chosenPath }) => {
          setWorkspacePath(chosenPath);
          setWorkspaceBranch("feat/unified-dev-app");
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
