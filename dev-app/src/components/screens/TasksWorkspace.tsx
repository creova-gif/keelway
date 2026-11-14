import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import type { LogsDrawerTab } from "@/components/shell/DevAppShell";
import { DiffLinesView, P10ApprovalCard } from "@/components/screens/P10ApprovalCard";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import { execSandboxTerminal, toggleAirGap } from "@/lib/api";
import { getFallbackDiffHunks } from "@/lib/apiFallbacks";
import type {
  EgressBarMode, FileDiffHunk, P10ApprovalDecisionPayload, P10ApprovalProposal,
  P10ApprovalReceipt, P10ScopedRuleSpec, StepReceiptItem,
} from "@/lib/types";

function isPromiseLike<T>(value: unknown): value is PromiseLike<T> {
  return typeof value === "object" && value !== null && typeof (value as { then?: unknown }).then === "function";
}

export interface PlanStepItem { id: string; label: string; done: boolean }
export interface ConversationMessage { id: string; role: "user" | "agent"; content: string; timestamp?: string }
export interface TerminalExecEntry {
  id: string; command: string; stdout: string; stderr: string; exitCode: number; durationMs: number;
}

export interface ReviewChangesContentProps {
  hunks: FileDiffHunk[];
  reviewStatus: "pending" | "kept" | "reverted";
  onKeepChanges: () => void;
  onRevertAll: () => void;
  onAskForChanges: (hunk: FileDiffHunk) => void;
}

export function ReviewChangesContent({
  hunks,
  reviewStatus,
  onKeepChanges,
  onRevertAll,
  onAskForChanges,
}: ReviewChangesContentProps): React.JSX.Element {
  const totalAdded = hunks.reduce((sum, h) => sum + h.additions, 0);
  const totalDeleted = hunks.reduce((sum, h) => sum + h.deletions, 0);

  return (
    <div className="space-y-3 text-ui text-fg">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-canvas/60 px-2.5 py-2 text-xs">
        <div className="font-mono tabular-nums text-fg-muted">
          <span>{`${hunks.length} ${hunks.length === 1 ? "file" : "files"}`}</span>
          <span aria-hidden="true" className="mx-1.5 text-fg-dim">·</span>
          <span className="text-ok">{`+${totalAdded}`}</span>
          <span aria-hidden="true" className="mx-1 text-fg-dim">/</span>
          <span className="text-danger">{`-${totalDeleted}`}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button size="sm" variant="primary" onClick={onKeepChanges}>
            ✓ Keep changes
          </Button>
          <Button size="sm" variant="danger-ghost" onClick={onRevertAll}>
            Revert all
          </Button>
        </div>
      </div>

      {reviewStatus !== "pending" ? (
        <div role="status" className="rounded-sm border border-border-strong bg-surface-elevated px-2.5 py-1.5 text-xs text-fg-muted">
          {reviewStatus === "kept" ? "Changes kept in working tree." : "Working tree changes reverted."}
        </div>
      ) : null}

      {hunks.length === 0 ? (
        <p className="py-4 text-xs text-fg-muted">No uncommitted changes in working tree.</p>
      ) : (
        <div className="space-y-3">
          {hunks.map((hunk) => (
            <div key={`${hunk.path}-${hunk.newStart}`} className="overflow-hidden rounded-sm border border-border-strong bg-canvas">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-elevated px-2.5 py-1.5 text-xs">
                <div className="flex min-w-0 items-center gap-2">
                  <code dir="ltr" className="unicode-bidi-isolate truncate font-mono text-fg">
                    {hunk.path}
                  </code>
                  {typeof hunk.aiRecordSeq === "number" ? (
                    <SemanticBadge kind="ai" detail={`#${hunk.aiRecordSeq}`} />
                  ) : null}
                </div>
                <Button size="sm" variant="secondary" onClick={() => onAskForChanges(hunk)}>
                  Ask for changes
                </Button>
              </div>
              <DiffLinesView lines={hunk.lines} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function resolveStepBadgeKind(item: StepReceiptItem): SemanticBadgeKind {
  if (item.status === "running") return "running";
  if (item.kind === "read" || item.kind === "searched" || item.kind === "edited") {
    return "ready";
  }
  if (item.exitCode === 0 || (item.exitCode === undefined && item.status === "passed")) {
    return "passed";
  }
  if ((typeof item.exitCode === "number" && item.exitCode !== 0) || item.status === "failed") {
    return "failed";
  }
  return "ready";
}

function StepReceiptRow({ item }: { item: StepReceiptItem }): React.JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const badgeKind = resolveStepBadgeKind(item);

  return (
    <div data-testid={`step-receipt-${item.id}`} className="rounded-sm border border-border bg-surface text-xs">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((prev) => !prev)}
        className="flex min-h-row w-full flex-wrap items-center justify-between gap-2 px-2.5 py-1 text-start hover:bg-surface-elevated"
      >
        <div className="flex min-w-0 items-center gap-2">
          <span aria-hidden="true" className="font-mono text-[10px] text-fg-dim">
            {expanded ? "▾" : "▸"}
          </span>
          <span className="font-medium text-fg">{item.title}</span>
          <code dir="ltr" className="unicode-bidi-isolate truncate font-mono text-fg-muted">
            {item.target}
          </code>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {typeof item.exitCode === "number" ? (
            <span className="font-mono tabular-nums text-fg-dim">{`exit ${item.exitCode}`}</span>
          ) : null}
          {typeof item.recordSeq === "number" ? (
            <span className="font-mono tabular-nums text-fg-dim">{`#${item.recordSeq}`}</span>
          ) : null}
          <SemanticBadge kind={badgeKind} />
        </div>
      </button>
      {expanded ? (
        <div className="border-t border-border bg-code p-2.5 font-mono text-code text-fg-muted">
          <pre className="whitespace-pre-wrap break-words">
            {item.output ?? item.detail ?? "No output captured for this step."}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

function LogsDrawerSection({
  tab,
  onTabChange,
  onClose,
  logLines,
  terminalCommand,
  onTerminalCommandChange,
  terminalRunning,
  terminalHistory,
  onRunTerminal,
  egressMode,
  airGapEnabled,
  onToggleAirGap,
}: {
  tab: LogsDrawerTab;
  onTabChange: (next: LogsDrawerTab) => void;
  onClose: () => void;
  logLines: string[];
  terminalCommand: string;
  onTerminalCommandChange: (val: string) => void;
  terminalRunning: boolean;
  terminalHistory: TerminalExecEntry[];
  onRunTerminal: (event: React.FormEvent) => void;
  egressMode: EgressBarMode;
  airGapEnabled: boolean;
  onToggleAirGap: () => void;
}): React.JSX.Element {
  const terminalInputId = useId();

  return (
    <section
      aria-label="Logs and terminal"
      tabIndex={-1}
      data-programmatic-focus="true"
      className="flex h-[300px] shrink-0 flex-col border-t border-border-strong bg-chrome"
    >
      <Tabs.Root value={tab} onValueChange={(v) => onTabChange(v as LogsDrawerTab)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-border px-3 py-1">
          <Tabs.List aria-label="Workspace output tabs" className="flex items-center gap-1">
            {(["logs", "terminal", "network"] as const).map((t) => (
              <Tabs.Trigger
                key={t}
                value={t}
                className="rounded-xs px-2.5 py-1 text-xs font-medium capitalize text-fg-muted data-[state=active]:bg-surface-elevated data-[state=active]:text-fg"
              >
                {t}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Button size="sm" variant="ghost" aria-label="Close logs drawer" onClick={onClose}>
            Close
          </Button>
        </div>

        <Tabs.Content value="logs" className="min-h-0 flex-1 overflow-y-auto bg-code p-3">
          <div className="space-y-1 font-mono text-xs text-fg-muted">
            {logLines.map((line, idx) => (
              <div key={`${idx}-${line}`}>{line}</div>
            ))}
          </div>
        </Tabs.Content>

        <Tabs.Content value="terminal" className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto bg-code p-3">
          <form onSubmit={onRunTerminal} className="flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1">
              <label htmlFor={terminalInputId} className="mb-1 block text-[11px] font-medium text-fg-muted">
                Sandbox command
              </label>
              <input
                id={terminalInputId}
                type="text"
                dir="ltr"
                value={terminalCommand}
                onChange={(e) => onTerminalCommandChange(e.target.value)}
                placeholder="pytest -q"
                className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-surface px-2.5 py-1 font-mono text-xs text-fg"
              />
            </div>
            <Button type="submit" size="sm" variant="secondary" loading={terminalRunning}>
              Run in sandbox
            </Button>
          </form>
          <div className="space-y-2 font-mono text-xs">
            {terminalHistory.map((entry) => (
              <div key={entry.id} className="rounded-xs border border-border bg-surface/60 p-2 text-fg">
                <div className="flex items-center justify-between text-fg-muted">
                  <code dir="ltr" className="unicode-bidi-isolate">{`$ ${entry.command}`}</code>
                  <span>{`exit ${entry.exitCode}`}</span>
                </div>
                {entry.stdout ? <pre className="mt-1 whitespace-pre-wrap text-fg">{entry.stdout}</pre> : null}
                {entry.stderr ? <pre className="mt-1 whitespace-pre-wrap text-danger">{entry.stderr}</pre> : null}
              </div>
            ))}
          </div>
        </Tabs.Content>

        <Tabs.Content value="network" className="min-h-0 flex-1 overflow-y-auto bg-code p-3">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-surface p-3 text-xs">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2 font-medium text-fg">
                <span>{egressMode === "air_gapped_verified" ? "Air-gapped · verified" : "Network · unmeasured"}</span>
                <span aria-hidden="true" className="text-fg-dim">·</span>
                <span className="font-mono text-fg-muted">sent: unmeasured</span>
                <SemanticBadge kind={egressMode === "air_gapped_verified" ? "locked" : "unmeasured"} />
              </div>
              <p className="text-[11px] text-fg-muted">
                Loopback byte counter is not active yet. Enable Air-Gap to block all outbound sockets at the runtime gate.
              </p>
            </div>
            <Button
              size="sm"
              variant={airGapEnabled ? "primary" : "secondary"}
              aria-pressed={airGapEnabled}
              onClick={onToggleAirGap}
            >
              {airGapEnabled ? "Disable Air-Gap" : "Lock Air-Gap"}
            </Button>
          </div>
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}

export interface TasksWorkspaceProps {
  taskId?: string;
  taskTitle?: string;
  workspaceBranch?: string;
  activeModelLabel?: string;
  planSteps?: PlanStepItem[];
  stepReceipts?: StepReceiptItem[];
  proposals?: P10ApprovalProposal[];
  initialMessages?: ConversationMessage[];
  diffHunks?: FileDiffHunk[];
  runtimeReachable?: boolean;
  defaultRunning?: boolean;
  isRunning?: boolean;
  onStopRun?: () => void;
  defaultReviewOpen?: boolean;
  reviewOpen?: boolean;
  onToggleReview?: (open: boolean) => void;
  renderReviewInShell?: boolean;
  defaultLogsOpen?: boolean;
  logsOpen?: boolean;
  onToggleLogs?: (open: boolean) => void;
  renderLogsInShell?: boolean;
  defaultAirGapEnabled?: boolean;
  approvalHeadingRef?: React.Ref<HTMLHeadingElement>;
  onPoliteAnnouncement?: (message: string) => void;
  onSendPrompt?: (prompt: string) => void;
  onSubmitDecision?: (
    payload: P10ApprovalDecisionPayload,
  ) => Promise<P10ApprovalReceipt | void> | P10ApprovalReceipt | void;
  onRetryPreview?: (proposalId: string) => void;
  onCreateScopedRule?: (rule: P10ScopedRuleSpec) => void;
  onEgressModeChange?: (mode: EgressBarMode, airGapEnabled: boolean) => void;
  execTerminalFn?: typeof execSandboxTerminal;
  toggleAirGapFn?: typeof toggleAirGap;
}

const DEFAULT_PLAN_STEPS: PlanStepItem[] = [
  { id: "plan-1", label: "Inspect loopback CSP and token middleware", done: true },
  { id: "plan-2", label: "Prepare minimal diff with P-10 human gate", done: false },
];

export function TasksWorkspace(props: TasksWorkspaceProps): React.JSX.Element {
  const {
    taskTitle = "Active workspace task", workspaceBranch = "feat/unified-dev-app",
    activeModelLabel = "coder-7b v2.5.1", planSteps = DEFAULT_PLAN_STEPS, stepReceipts = [],
    proposals = [], initialMessages = [], diffHunks, runtimeReachable = true,
    defaultRunning = false, isRunning: controlledRunning, onStopRun,
    defaultReviewOpen = false, reviewOpen: controlledReviewOpen, onToggleReview,
    renderReviewInShell = false, defaultLogsOpen = false, logsOpen: controlledLogsOpen,
    onToggleLogs, renderLogsInShell = false, defaultAirGapEnabled = false,
    approvalHeadingRef, onPoliteAnnouncement, onSendPrompt, onSubmitDecision,
    onRetryPreview, onCreateScopedRule, onEgressModeChange,
    execTerminalFn = execSandboxTerminal, toggleAirGapFn = toggleAirGap,
  } = props;
  const workspaceHeadingId = useId();
  const composerId = useId();

  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const internalApprovalHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const announcedIdsRef = useRef<Set<string>>(new Set());

  const [decidedReceipts, setDecidedReceipts] = useState<Record<string, P10ApprovalReceipt>>({});
  const [messages, setMessages] = useState<ConversationMessage[]>(initialMessages);
  const [composerValue, setComposerValue] = useState("");
  const [localAnnouncement, setLocalAnnouncement] = useState("");

  const [uncontrolledRunning, setUncontrolledRunning] = useState(defaultRunning);
  const effectiveRunning = controlledRunning ?? uncontrolledRunning;

  const [uncontrolledReviewOpen, setUncontrolledReviewOpen] = useState(defaultReviewOpen);
  const isReviewOpen = controlledReviewOpen ?? uncontrolledReviewOpen;

  const [uncontrolledLogsOpen, setUncontrolledLogsOpen] = useState(defaultLogsOpen);
  const isLogsOpen = controlledLogsOpen ?? uncontrolledLogsOpen;
  const [logsTab, setLogsTab] = useState<LogsDrawerTab>("logs");

  const [activeHunks, setActiveHunks] = useState<FileDiffHunk[]>(() => diffHunks ?? getFallbackDiffHunks());
  const [reviewStatus, setReviewStatus] = useState<"pending" | "kept" | "reverted">("pending");
  const [logLines, setLogLines] = useState<string[]>([
    "[loopback] Seatbelt workspace isolation active · writes scoped to project root.",
  ]);
  const [terminalCommand, setTerminalCommand] = useState("");
  const [terminalRunning, setTerminalRunning] = useState(false);
  const [terminalHistory, setTerminalHistory] = useState<TerminalExecEntry[]>([]);
  const [airGapEnabled, setAirGapEnabled] = useState(defaultAirGapEnabled);
  const [egressMode, setEgressMode] = useState<EgressBarMode>(
    defaultAirGapEnabled ? "air_gapped_verified" : "unmeasured",
  );

  const undecidedProposals = useMemo(
    () => proposals.filter((p) => !decidedReceipts[p.id]),
    [decidedReceipts, proposals],
  );
  const pendingKey = undecidedProposals.map((p) => p.id).join(",");

  const [trackedPendingKey, setTrackedPendingKey] = useState(pendingKey);
  const [isPlanExpanded, setIsPlanExpanded] = useState(() => undecidedProposals.length === 0);

  if (trackedPendingKey !== pendingKey) {
    setTrackedPendingKey(pendingKey);
    if (undecidedProposals.length > 0) setIsPlanExpanded(false);
  }

  const announce = useCallback(
    (msg: string) => {
      setLocalAnnouncement(msg);
      onPoliteAnnouncement?.(msg);
    },
    [onPoliteAnnouncement],
  );

  useEffect(() => {
    const newlyArrived = undecidedProposals.filter((p) => !announcedIdsRef.current.has(p.id));
    if (newlyArrived.length === 0) return;
    for (const item of newlyArrived) announcedIdsRef.current.add(item.id);
    const latest = newlyArrived[newlyArrived.length - 1]!;
    announce(`Pending approval: ${latest.title}. Press Command+Shift+A to inspect.`);
  }, [announce, undecidedProposals]);

  const setFirstHeadingRef = useCallback(
    (node: HTMLHeadingElement | null) => {
      internalApprovalHeadingRef.current = node;
      if (typeof approvalHeadingRef === "function") {
        approvalHeadingRef(node);
      } else if (approvalHeadingRef && typeof approvalHeadingRef === "object") {
        (approvalHeadingRef as React.MutableRefObject<HTMLHeadingElement | null>).current = node;
      }
    },
    [approvalHeadingRef],
  );

  const handleStopRun = useCallback(() => {
    if (controlledRunning === undefined) setUncontrolledRunning(false);
    onStopRun?.();
    setLogLines((prev) => [...prev, "[user] Execution halted via Stop (⌘.)."]);
    announce("Active agent run stopped.");
  }, [announce, controlledRunning, onStopRun]);

  useEffect(() => {
    const handleWindowKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return;
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;

      if (!event.shiftKey && event.key === "." && effectiveRunning) {
        event.preventDefault();
        handleStopRun();
        return;
      }
      if (event.shiftKey && event.key.toLowerCase() === "a" && undecidedProposals.length > 0) {
        event.preventDefault();
        internalApprovalHeadingRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleWindowKeyDown);
    return () => window.removeEventListener("keydown", handleWindowKeyDown);
  }, [effectiveRunning, handleStopRun, undecidedProposals.length]);

  const toggleReviewPane = (next: boolean) => {
    if (controlledReviewOpen === undefined) setUncontrolledReviewOpen(next);
    onToggleReview?.(next);
  };

  const toggleLogsPane = (next: boolean) => {
    if (controlledLogsOpen === undefined) setUncontrolledLogsOpen(next);
    onToggleLogs?.(next);
  };

  const handleProposalDecision = useCallback(
    (
      proposal: P10ApprovalProposal,
      payload: P10ApprovalDecisionPayload,
    ): Promise<P10ApprovalReceipt | void> | P10ApprovalReceipt | void => {
      const fallbackReceipt: P10ApprovalReceipt = {
        proposalId: proposal.id,
        recordSeq: proposal.recordSeqCandidate ?? 1284,
        decision: payload.decision,
        summary:
          payload.decision === "deny" && payload.denyReason
            ? `${proposal.title} — ${payload.denyReason}`
            : proposal.title,
        modifiedByUser: Boolean(payload.modifiedCommand || payload.modifiedTargetPath),
        ...(payload.escalatedToNetwork ? { escalatedByEdit: true } : {}),
        decidedAt: payload.decidedAt,
        actorLabel: "you (local keyboard)",
      };

      const callerResult = onSubmitDecision?.(payload);
      if (isPromiseLike<P10ApprovalReceipt | void>(callerResult)) {
        return Promise.resolve(callerResult).then((resolved) => {
          const finalReceipt = resolved ?? fallbackReceipt;
          setDecidedReceipts((prev) => ({ ...prev, [proposal.id]: finalReceipt }));
          return finalReceipt;
        });
      }

      const finalReceipt: P10ApprovalReceipt = callerResult ?? fallbackReceipt;
      setDecidedReceipts((prev) => ({ ...prev, [proposal.id]: finalReceipt }));
      return finalReceipt;
    },
    [onSubmitDecision],
  );

  const submitComposerPrompt = () => {
    const trimmed = composerValue.trim();
    if (!runtimeReachable || trimmed.length === 0) return;
    onSendPrompt?.(trimmed);
    setMessages((prev) => [...prev, { id: `msg-${Date.now()}`, role: "user", content: trimmed }]);
    setComposerValue("");
  };

  const handleRunTerminal = (event: React.FormEvent) => {
    event.preventDefault();
    const cmd = terminalCommand.trim();
    if (!cmd || terminalRunning) return;
    setTerminalRunning(true);
    execTerminalFn(cmd)
      .then((res) => {
        setTerminalHistory((prev) => [
          ...prev,
          { id: `term-${Date.now()}`, command: cmd, stdout: res.stdout, stderr: res.stderr, exitCode: res.exitCode, durationMs: res.durationMs },
        ]);
        setLogLines((prev) => [...prev, `[sandbox] $ ${cmd} -> exit ${res.exitCode}`]);
        setTerminalCommand("");
        setTerminalRunning(false);
      })
      .catch((err: unknown) => {
        setTerminalHistory((prev) => [
          ...prev,
          { id: `term-err-${Date.now()}`, command: cmd, stdout: "", stderr: err instanceof Error ? err.message : "Sandbox execution failed.", exitCode: 1, durationMs: 0 },
        ]);
        setTerminalRunning(false);
      });
  };

  const handleToggleAirGap = () => {
    toggleAirGapFn(!airGapEnabled)
      .then((res) => {
        setAirGapEnabled(res.airGapEnabled);
        setEgressMode(res.mode);
        onEgressModeChange?.(res.mode, res.airGapEnabled);
      })
      .catch(() => {});
  };

  const completedPlanCount = planSteps.filter((s) => s.done).length;
  const firstPendingId = undecidedProposals[0]?.id;
  const isSendSoftDisabled = !runtimeReachable || composerValue.trim().length === 0;

  return (
    <div className="flex h-full min-h-0 w-full overflow-hidden bg-canvas text-fg">
      {!onPoliteAnnouncement ? (
        <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
          {localAnnouncement}
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <section aria-labelledby={workspaceHeadingId} className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
          <header className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2.5">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 id={workspaceHeadingId} className="truncate text-sm font-semibold text-fg">{taskTitle}</h1>
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-xs text-fg-muted">{workspaceBranch}</code>
              <SemanticBadge kind="opencore" detail={activeModelLabel} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {effectiveRunning ? (
                <Button size="sm" variant="danger-ghost" shortcutHint="⌘." onClick={handleStopRun}>Stop</Button>
              ) : null}
              <Button size="sm" variant="secondary" aria-expanded={isReviewOpen} onClick={() => toggleReviewPane(!isReviewOpen)}>
                {`Review changes (${activeHunks.length})`}
              </Button>
              <Button size="sm" variant="ghost" aria-expanded={isLogsOpen} onClick={() => toggleLogsPane(!isLogsOpen)}>
                Logs &amp; Terminal
              </Button>
            </div>
          </header>

          {!runtimeReachable ? (
            <CalloutBanner
              variant="runtime-unreachable"
              title="Local runtime unreachable on 127.0.0.1"
              description="Your composer draft is preserved locally. Reconnect OpenCore daemon before sending."
              className="mb-3"
            />
          ) : null}

          {planSteps.length > 0 ? (
            <div className="mb-3 rounded-sm border border-border-strong bg-surface">
              <button
                type="button"
                aria-expanded={isPlanExpanded}
                onClick={() => setIsPlanExpanded((prev) => !prev)}
                className="flex min-h-row w-full items-center justify-between gap-2 px-3 py-1.5 text-start text-xs hover:bg-surface-elevated"
              >
                <span className="font-semibold text-fg">{`Plan · ${completedPlanCount}/${planSteps.length} steps`}</span>
                <span className="text-[11px] text-fg-muted">
                  {!isPlanExpanded && undecidedProposals.length > 0
                    ? "Collapsed while approval pending · Expand"
                    : isPlanExpanded
                      ? "Collapse"
                      : "Expand"}
                </span>
              </button>
              {isPlanExpanded ? (
                <ol className="space-y-1 border-t border-border px-3 py-2 text-xs">
                  {planSteps.map((step) => (
                    <li key={step.id} className="flex items-center gap-2">
                      <span aria-hidden="true" className={`font-mono ${step.done ? "text-ok" : "text-fg-dim"}`}>
                        {step.done ? "✓" : "○"}
                      </span>
                      <span className={step.done ? "text-fg-muted" : "text-fg"}>{step.label}</span>
                    </li>
                  ))}
                </ol>
              ) : null}
            </div>
          ) : null}

          {stepReceipts.length > 0 ? (
            <div className="mb-3 space-y-1.5">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">Execution receipts</h2>
              {stepReceipts.map((item) => (
                <StepReceiptRow key={item.id} item={item} />
              ))}
            </div>
          ) : null}

          <div className="flex-1 space-y-3">
            <h2 className="sr-only">Conversation and human approvals</h2>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`rounded-sm border px-3 py-2 text-xs ${
                  msg.role === "user" ? "border-border-strong bg-surface-elevated text-fg" : "border-border bg-surface text-fg"
                }`}
              >
                <div className="mb-0.5 font-mono text-[10px] uppercase text-fg-dim">
                  {msg.role === "user" ? "You" : "Agent"}
                </div>
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}

            {proposals.map((proposal) => (
              <P10ApprovalCard
                key={proposal.id}
                proposal={proposal}
                receipt={decidedReceipts[proposal.id] ?? null}
                headingRef={proposal.id === firstPendingId ? setFirstHeadingRef : undefined}
                enableKeyboardShortcuts={proposal.id === firstPendingId}
                onSubmitDecision={(payload) => handleProposalDecision(proposal, payload)}
                onRetryPreview={onRetryPreview}
                onCreateScopedRule={onCreateScopedRule}
              />
            ))}
          </div>

          <div className="mt-4 rounded-md border border-border-strong bg-surface p-3">
            <label htmlFor={composerId} className="mb-1.5 block text-xs font-medium text-fg-muted">
              Ask agent or follow up in workspace
            </label>
            <textarea
              id={composerId}
              ref={composerRef}
              rows={2}
              value={composerValue}
              onChange={(e) => setComposerValue(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && e.key === "Enter") {
                  e.preventDefault();
                  e.stopPropagation();
                  submitComposerPrompt();
                }
              }}
              placeholder="Describe the change, cite a file, or ask a question…"
              className="w-full resize-y rounded-sm border border-border-control bg-canvas px-2.5 py-1.5 text-ui text-fg placeholder:text-fg-dim"
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-[11px] text-fg-dim">
                ⌘↵ sends prompt only · never approves pending P-10 gates
              </span>
              <Button
                size="sm"
                variant="primary"
                shortcutHint="⌘↵"
                aria-disabled={isSendSoftDisabled ? "true" : undefined}
                onClick={submitComposerPrompt}
              >
                Send
              </Button>
            </div>
          </div>
        </section>

        {!renderLogsInShell && isLogsOpen ? (
          <LogsDrawerSection
            tab={logsTab}
            onTabChange={setLogsTab}
            onClose={() => toggleLogsPane(false)}
            logLines={logLines}
            terminalCommand={terminalCommand}
            onTerminalCommandChange={setTerminalCommand}
            terminalRunning={terminalRunning}
            terminalHistory={terminalHistory}
            onRunTerminal={handleRunTerminal}
            egressMode={egressMode}
            airGapEnabled={airGapEnabled}
            onToggleAirGap={handleToggleAirGap}
          />
        ) : null}
      </div>

      {!renderReviewInShell && isReviewOpen ? (
        <aside
          aria-label="Review changes"
          tabIndex={-1}
          data-programmatic-focus="true"
          className="flex w-review shrink-0 flex-col overflow-hidden border-s border-border bg-surface"
        >
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <h2 className="text-xs font-semibold text-fg">Review changes</h2>
            <Button size="sm" variant="ghost" aria-label="Close review pane" onClick={() => toggleReviewPane(false)}>
              Close
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <ReviewChangesContent
              hunks={activeHunks}
              reviewStatus={reviewStatus}
              onKeepChanges={() => setReviewStatus("kept")}
              onRevertAll={() => {
                setActiveHunks([]);
                setReviewStatus("reverted");
              }}
              onAskForChanges={(hunk) => {
                const endLine = Math.max(hunk.newStart, hunk.newStart + Math.max(hunk.additions - 1, 0));
                setComposerValue(`Please revise ${hunk.path}:${hunk.newStart}-${endLine} — `);
                composerRef.current?.focus();
              }}
            />
          </div>
        </aside>
      ) : null}
    </div>
  );
}
