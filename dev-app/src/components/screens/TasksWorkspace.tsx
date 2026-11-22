import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { LogsDrawerTab } from "@/components/shell/DevAppShell";
import { AgentComposer, type ComposerPreflight } from "@/components/screens/AgentComposer";
import { P10ApprovalCard } from "@/components/screens/P10ApprovalCard";
import {
  buildLogsDrawerTabPanels,
  LogsDrawerSection,
  ReviewChangesContent,
  type LogsDrawerPanelsProps,
  type ReviewChangesContentProps,
  type TerminalExecEntry,
} from "@/components/screens/TasksDrawers";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import { execSandboxTerminal, explainRouting, toggleAirGap } from "@/lib/api";
import {
  approveAgentStep,
  cancelAgentTask,
  defaultStepArgs,
  mapEventsToReceipts,
  pendingToProposal,
  runAgentTask,
  STEPABLE_TOOLS,
  stepAgentTool,
  type AgentRunState,
} from "@/lib/agentLoopApi";
import { getFallbackDiffHunks } from "@/lib/apiFallbacks";
import type {
  EgressBarMode,
  FileDiffHunk,
  P10ApprovalDecisionPayload,
  P10ApprovalProposal,
  P10ApprovalReceipt,
  P10ScopedRuleSpec,
  StepReceiptItem,
} from "@/lib/types";

export {
  buildLogsDrawerTabPanels,
  LogsDrawerSection,
  ReviewChangesContent,
  type LogsDrawerPanelsProps,
  type ReviewChangesContentProps,
  type TerminalExecEntry,
};

function isPromiseLike<T>(value: unknown): value is PromiseLike<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { then?: unknown }).then === "function"
  );
}

export interface PlanStepItem {
  id: string;
  label: string;
  done: boolean;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp?: string;
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
    <div
      data-testid={`step-receipt-${item.id}`}
      className="rounded-sm border border-border bg-surface text-xs"
    >
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

export interface TasksWorkspaceProps {
  taskId?: string;
  taskTitle?: string;
  workspaceBranch?: string;
  activeModelLabel?: string;
  planSteps?: PlanStepItem[];
  stepReceipts?: StepReceiptItem[];
  proposals?: P10ApprovalProposal[];
  receipts?: Record<string, P10ApprovalReceipt>;
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
  isCompanion?: boolean;
  onSelectActiveModel?: (modelId: string, modelLabel: string) => void;
  defaultLogsOpen?: boolean;
  logsOpen?: boolean;
  onToggleLogs?: (open: boolean) => void;
  renderLogsInShell?: boolean;
  defaultAirGapEnabled?: boolean;
  composerValue?: string;
  onComposerValueChange?: (value: string) => void;
  composerTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
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
    taskId = "task-default",
    taskTitle = "Active workspace task",
    workspaceBranch = "feat/unified-dev-app",
    activeModelLabel = "coder-7b v2.5.1",
    planSteps = DEFAULT_PLAN_STEPS,
    stepReceipts = [],
    proposals = [],
    receipts,
    initialMessages = [],
    diffHunks,
    runtimeReachable = true,
    defaultRunning = false,
    isRunning: controlledRunning,
    onStopRun,
    defaultReviewOpen = false,
    reviewOpen: controlledReviewOpen,
    onToggleReview,
    renderReviewInShell = false,
    isCompanion = false,
    onSelectActiveModel,
    defaultLogsOpen = false,
    logsOpen: controlledLogsOpen,
    onToggleLogs,
    renderLogsInShell = false,
    defaultAirGapEnabled = false,
    composerValue: controlledComposerValue,
    onComposerValueChange,
    composerTextareaRef,
    approvalHeadingRef,
    onPoliteAnnouncement,
    onSendPrompt,
    onSubmitDecision,
    onRetryPreview,
    onCreateScopedRule,
    onEgressModeChange,
    execTerminalFn = execSandboxTerminal,
    toggleAirGapFn = toggleAirGap,
  } = props;
  const workspaceHeadingId = useId();

  const internalComposerRef = useRef<HTMLTextAreaElement | null>(null);
  const activeComposerRef = composerTextareaRef ?? internalComposerRef;
  const internalApprovalHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const announcedIdsRef = useRef<Set<string>>(new Set());
  const seqRef = useRef(0);

  const [trackedTaskId, setTrackedTaskId] = useState(taskId);
  const [trackedDiffHunks, setTrackedDiffHunks] = useState(diffHunks);
  const [decidedReceipts, setDecidedReceipts] = useState<Record<string, P10ApprovalReceipt>>({});
  const [focusedPendingId, setFocusedPendingId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>(initialMessages);
  const [uncontrolledComposerValue, setUncontrolledComposerValue] = useState("");
  const effectiveComposerValue = controlledComposerValue ?? uncontrolledComposerValue;
  const [localAnnouncement, setLocalAnnouncement] = useState("");

  const [uncontrolledRunning, setUncontrolledRunning] = useState(defaultRunning);
  const effectiveRunning = controlledRunning ?? uncontrolledRunning;

  const [uncontrolledReviewOpen, setUncontrolledReviewOpen] = useState(defaultReviewOpen);
  const isReviewOpen = controlledReviewOpen ?? uncontrolledReviewOpen;

  const [uncontrolledLogsOpen, setUncontrolledLogsOpen] = useState(defaultLogsOpen);
  const isLogsOpen = controlledLogsOpen ?? uncontrolledLogsOpen;
  const [logsTab, setLogsTab] = useState<LogsDrawerTab>("logs");

  const [activeHunks, setActiveHunks] = useState<FileDiffHunk[]>(
    () => diffHunks ?? getFallbackDiffHunks(),
  );
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

  // Live governed agent run (`/v1/agent/*`). The loop is operator-stepped:
  // every action returns full agent_state, so no polling is required.
  const [liveRun, setLiveRun] = useState<{
    taskId: string;
    goal: string;
    state: AgentRunState;
  } | null>(null);
  const [liveRunBusy, setLiveRunBusy] = useState(false);
  const [stepTool, setStepTool] = useState<string>(STEPABLE_TOOLS[0]);
  const [stepArgsText, setStepArgsText] = useState("{}");

  const livePlanSteps = useMemo<PlanStepItem[]>(
    () =>
      liveRun
        ? liveRun.state.plan.map((s) => ({
            id: s.id,
            label: s.observation ? `${s.description} — ${s.observation}` : s.description,
            done: s.status === "completed",
          }))
        : planSteps,
    [liveRun, planSteps],
  );
  const liveReceipts = useMemo<StepReceiptItem[]>(
    () => (liveRun ? mapEventsToReceipts(liveRun.state.recent_events) : stepReceipts),
    [liveRun, stepReceipts],
  );
  const livePending = liveRun?.state.pending_approval ?? null;
  const liveQuorumPending = livePending?.requires_quorum === true ? livePending : null;
  const liveProposals = useMemo<P10ApprovalProposal[]>(
    () =>
      livePending && !livePending.requires_quorum
        ? [pendingToProposal(livePending, { modelId: activeModelLabel })]
        : [],
    [livePending, activeModelLabel],
  );
  const effectiveProposals = useMemo(
    () => [...proposals, ...liveProposals],
    [proposals, liveProposals],
  );

  if (trackedTaskId !== taskId) {
    setTrackedTaskId(taskId);
    setTrackedDiffHunks(diffHunks);
    setMessages(initialMessages);
    setActiveHunks(diffHunks ?? getFallbackDiffHunks());
    setReviewStatus("pending");
    setFocusedPendingId(null);
  } else if (trackedDiffHunks !== diffHunks) {
    setTrackedDiffHunks(diffHunks);
    setActiveHunks(diffHunks ?? getFallbackDiffHunks());
  }

  const updateComposerValue = useCallback(
    (next: string) => {
      if (controlledComposerValue === undefined) {
        setUncontrolledComposerValue(next);
      }
      onComposerValueChange?.(next);
    },
    [controlledComposerValue, onComposerValueChange],
  );

  const undecidedProposals = useMemo(
    () => effectiveProposals.filter((p) => !receipts?.[p.id] && !decidedReceipts[p.id]),
    [decidedReceipts, effectiveProposals, receipts],
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

  const toggleReviewPane = useCallback(
    (next: boolean) => {
      if (controlledReviewOpen === undefined) setUncontrolledReviewOpen(next);
      onToggleReview?.(next);
    },
    [controlledReviewOpen, onToggleReview],
  );

  const toggleLogsPane = useCallback(
    (next: boolean) => {
      if (controlledLogsOpen === undefined) setUncontrolledLogsOpen(next);
      onToggleLogs?.(next);
    },
    [controlledLogsOpen, onToggleLogs],
  );

  useEffect(() => {
    const handleWindowKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return;
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;

      if (!event.shiftKey && event.key === "." && effectiveRunning) {
        event.preventDefault();
        handleStopRun();
        return;
      }
      if (
        !event.shiftKey &&
        event.key.toLowerCase() === "j" &&
        !renderLogsInShell &&
        !document.getElementById("kw-main-workspace")
      ) {
        event.preventDefault();
        toggleLogsPane(!isLogsOpen);
        return;
      }
      if (event.shiftKey && event.key.toLowerCase() === "a" && undecidedProposals.length > 0) {
        event.preventDefault();
        internalApprovalHeadingRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleWindowKeyDown);
    return () => window.removeEventListener("keydown", handleWindowKeyDown);
  }, [
    effectiveRunning,
    handleStopRun,
    isLogsOpen,
    renderLogsInShell,
    toggleLogsPane,
    undecidedProposals.length,
  ]);

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

      if (liveRun && proposal.id.startsWith("live-") && livePending) {
        const approved = payload.decision !== "deny";
        const remember = payload.scopedRule
          ? {
              scope: payload.scopedRule.scopePattern,
              model_id: payload.scopedRule.modelId || undefined,
              prompt_version: payload.scopedRule.promptVersion || undefined,
            }
          : undefined;
        return Promise.resolve(
          approveAgentStep(liveRun.taskId, { approved, remember }),
        ).then((res) => {
          if (!res.ok) {
            setLogLines((prev) => [
              ...prev,
              `[agent] approve rejected: ${res.detail ?? `HTTP ${res.status}`}`,
            ]);
            return fallbackReceipt;
          }
          if (res.data?.agent_state) {
            setLiveRun((prev) =>
              prev ? { ...prev, state: res.data!.agent_state! } : prev,
            );
          }
          const callerResult = onSubmitDecision?.(payload);
          if (isPromiseLike<P10ApprovalReceipt | void>(callerResult)) {
            return callerResult.then((resolved) => {
              const finalReceipt = resolved ?? fallbackReceipt;
              setDecidedReceipts((prev) => ({ ...prev, [proposal.id]: finalReceipt }));
              return finalReceipt;
            });
          }
          const finalReceipt = (callerResult as P10ApprovalReceipt | void) ?? fallbackReceipt;
          setDecidedReceipts((prev) => ({ ...prev, [proposal.id]: finalReceipt }));
          return finalReceipt;
        });
      }

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
    [livePending, liveRun, onSubmitDecision],
  );

  const [composerPreflight, setComposerPreflight] = useState<ComposerPreflight | null>(null);

  const submitComposerPrompt = async () => {
    const trimmed = effectiveComposerValue.trim();
    if (!runtimeReachable || trimmed.length === 0 || liveRunBusy) return;
    onSendPrompt?.(trimmed);
    setMessages((prev) => [
      ...prev,
      { id: `msg-${++seqRef.current}`, role: "user", content: trimmed },
    ]);
    updateComposerValue("");

    // Paper 19.2 pre-flight honesty: simulate routing before the run launches.
    try {
      const route = await explainRouting({
        taskKind: "agent_run",
        privacy: airGapEnabled ? "private" : "standard",
        maxLatencyMs: 30_000,
        maxCostUsd: 1.0,
      });
      setComposerPreflight({ status: "simulated", result: route });
    } catch {
      setComposerPreflight({ status: "unavailable" });
    }

    setLiveRunBusy(true);
    void runAgentTask({ goal: trimmed, modelId: activeModelLabel })
      .then((res) => {
        if (!res.ok || !res.data) {
          setLogLines((prev) => [
            ...prev,
            `[agent] run rejected: ${res.detail ?? `HTTP ${res.status}`}`,
          ]);
          return;
        }
        const state = res.data.state;
        if (state) {
          const taskId = res.data.task_id;
          setLiveRun({ taskId, goal: trimmed, state });
          setLogLines((prev) => [
            ...prev,
            `[agent] run ${taskId} started · ${state.plan.length} steps (keyword-planned, policy: ${state.policy})`,
          ]);
          setMessages((prev) => [
            ...prev,
            {
              id: `msg-${++seqRef.current}`,
              role: "agent",
              content: `Governed run started (${taskId}). Plan has ${state.plan.length} steps — keyword-planned, not model-driven. Step tools below; mutating tools gate for approval.`,
            },
          ]);
        }
      })
      .finally(() => setLiveRunBusy(false));
  };

  const handleStepTool = () => {
    if (!liveRun || liveRunBusy) return;
    let parsed: Record<string, unknown>;
    try {
      const raw = JSON.parse(stepArgsText || "{}") as unknown;
      parsed = raw !== null && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
    } catch {
      setLogLines((prev) => [...prev, "[agent] step args are not valid JSON — step not sent"]);
      return;
    }
    setLiveRunBusy(true);
    void stepAgentTool(liveRun.taskId, { toolName: stepTool, arguments: parsed })
      .then((res) => {
        if (!res.ok || !res.data) {
          setLogLines((prev) => [
            ...prev,
            `[agent] step ${stepTool} rejected: ${res.detail ?? `HTTP ${res.status}`}`,
          ]);
          return;
        }
        setLiveRun((prev) =>
          prev ? { ...prev, state: res.data!.agent_state } : prev,
        );
        const status = res.data.step_result?.status;
        setLogLines((prev) => [
          ...prev,
          `[agent] step ${stepTool} → ${typeof status === "string" ? status : "executed"}`,
        ]);
      })
      .finally(() => setLiveRunBusy(false));
  };

  const handleCancelRun = () => {
    if (!liveRun || liveRunBusy) return;
    setLiveRunBusy(true);
    void cancelAgentTask(liveRun.taskId)
      .then((res) => {
        setLogLines((prev) => [
          ...prev,
          res.ok ? `[agent] run ${liveRun.taskId} cancelled` : `[agent] cancel rejected: HTTP ${res.status}`,
        ]);
        if (res.ok && res.data?.agent_state) {
          setLiveRun((prev) => (prev ? { ...prev, state: res.data!.agent_state! } : prev));
        }
      })
      .finally(() => setLiveRunBusy(false));
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
          {
            id: `term-${++seqRef.current}`,
            command: cmd,
            stdout: res.stdout,
            stderr: res.stderr,
            exitCode: res.exitCode,
            durationMs: res.durationMs,
          },
        ]);
        setLogLines((prev) => [...prev, `[sandbox] $ ${cmd} -> exit ${res.exitCode}`]);
        setTerminalCommand("");
        setTerminalRunning(false);
      })
      .catch((err: unknown) => {
        setTerminalHistory((prev) => [
          ...prev,
          {
            id: `term-err-${++seqRef.current}`,
            command: cmd,
            stdout: "",
            stderr: err instanceof Error ? err.message : "Sandbox execution failed.",
            exitCode: 1,
            durationMs: 0,
          },
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
      .catch((err: unknown) => {
        setLogLines((prev) => [
          ...prev,
          `[network] Air-Gap toggle error: ${err instanceof Error ? err.message : "request failed"}`,
        ]);
      });
  };

  const completedPlanCount = livePlanSteps.filter((s) => s.done).length;
  const firstPendingId = undecidedProposals[0]?.id;
  const activeShortcutProposalId = undecidedProposals.some((p) => p.id === focusedPendingId)
    ? focusedPendingId
    : firstPendingId;

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-canvas text-fg md:flex-row">
      {!onPoliteAnnouncement ? (
        <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
          {localAnnouncement}
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <section
          aria-labelledby={workspaceHeadingId}
          className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4"
        >
          <header className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2.5">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 id={workspaceHeadingId} className="truncate text-sm font-semibold text-fg">
                {taskTitle}
              </h1>
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-xs text-fg-muted">
                {workspaceBranch}
              </code>
              <SemanticBadge kind="opencore" detail={activeModelLabel} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {effectiveRunning ? (
                <Button size="sm" variant="danger-ghost" shortcutHint="⌘." onClick={handleStopRun}>
                  Stop
                </Button>
              ) : null}
              <Button
                size="sm"
                variant="secondary"
                aria-expanded={isReviewOpen}
                onClick={() => toggleReviewPane(!isReviewOpen)}
              >
                {`Review changes (${activeHunks.length})`}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                shortcutHint="⌘J"
                aria-expanded={isLogsOpen}
                onClick={() => toggleLogsPane(!isLogsOpen)}
              >
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

          {liveRun ? (
            <div
              data-testid="live-agent-run"
              className="mb-3 rounded-sm border border-accent-border bg-accent-subtle/40 px-3 py-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs">
                  <span className="font-semibold text-fg">Live agent run</span>
                  <code dir="ltr" className="unicode-bidi-isolate font-mono text-[11px] text-fg-muted">
                    {liveRun.taskId}
                  </code>
                  <span className="rounded-xs border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase text-fg-muted">
                    {liveRun.state.status}
                  </span>
                  <span className="text-[11px] text-fg-muted">
                    {`${liveRun.state.events_count} events · policy ${liveRun.state.policy}`}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="danger-ghost"
                  disabled={liveRunBusy || liveRun.state.status === "cancelled" || liveRun.state.status === "completed"}
                  onClick={handleCancelRun}
                >
                  Cancel run
                </Button>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border/60 pt-2">
                <label htmlFor="live-step-tool" className="text-[11px] font-medium text-fg-muted">
                  Step tool
                </label>
                <select
                  id="live-step-tool"
                  value={stepTool}
                  onChange={(e) => {
                    const tool = e.target.value;
                    setStepTool(tool);
                    setStepArgsText(JSON.stringify(defaultStepArgs(tool, liveRun.goal)));
                  }}
                  className="rounded-xs border border-border bg-surface px-1.5 py-1 font-mono text-[11px] text-fg"
                >
                  {STEPABLE_TOOLS.map((tool) => (
                    <option key={tool} value={tool}>{tool}</option>
                  ))}
                </select>
                <label htmlFor="live-step-args" className="sr-only">
                  Tool arguments (JSON)
                </label>
                <input
                  id="live-step-args"
                  value={stepArgsText}
                  onChange={(e) => setStepArgsText(e.target.value)}
                  spellCheck={false}
                  className="min-w-40 flex-1 rounded-xs border border-border bg-surface px-1.5 py-1 font-mono text-[11px] text-fg"
                />
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={liveRunBusy || liveRun.state.status === "cancelled" || liveRun.state.status === "completed"}
                  onClick={handleStepTool}
                >
                  Run step
                </Button>
              </div>
              {liveQuorumPending ? (
                <p className="mt-2 text-[11px] text-warning" role="note">
                  {`Pending action requires ${liveQuorumPending.required_roles?.join(" + ") ?? "multi-role"} quorum approval — single-approver card hidden.`}
                </p>
              ) : null}
            </div>
          ) : null}

          {livePlanSteps.length > 0 ? (
            <div className="mb-3 rounded-sm border border-border-strong bg-surface">
              <button
                type="button"
                aria-expanded={isPlanExpanded}
                onClick={() => setIsPlanExpanded((prev) => !prev)}
                className="flex min-h-row w-full items-center justify-between gap-2 px-3 py-1.5 text-start text-xs hover:bg-surface-elevated"
              >
                <span className="font-semibold text-fg">
                  {`Plan · ${completedPlanCount}/${livePlanSteps.length} steps`}
                </span>
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
                  {livePlanSteps.map((step) => (
                    <li key={step.id} className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className={`font-mono ${step.done ? "text-ok" : "text-fg-dim"}`}
                      >
                        {step.done ? "✓" : "○"}
                      </span>
                      <span className={step.done ? "text-fg-muted" : "text-fg"}>{step.label}</span>
                    </li>
                  ))}
                </ol>
              ) : null}
            </div>
          ) : null}

          {liveReceipts.length > 0 ? (
            <div className="mb-3 space-y-1.5">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
                {liveRun ? "Live execution events" : "Execution receipts"}
              </h2>
              {liveReceipts.map((item) => (
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
                  msg.role === "user"
                    ? "border-border-strong bg-surface-elevated text-fg"
                    : "border-border bg-surface text-fg"
                }`}
              >
                <div className="mb-0.5 font-mono text-[10px] uppercase text-fg-dim">
                  {msg.role === "user" ? "You" : "Agent"}
                </div>
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}

            {effectiveProposals.map((proposal) => {
              const effectiveReceipt =
                receipts?.[proposal.id] ?? decidedReceipts[proposal.id] ?? null;
              return (
                <P10ApprovalCard
                  key={proposal.id}
                  proposal={proposal}
                  receipt={effectiveReceipt}
                  headingRef={proposal.id === firstPendingId ? setFirstHeadingRef : undefined}
                  enableKeyboardShortcuts={proposal.id === activeShortcutProposalId}
                  onFocusCapture={
                    !effectiveReceipt ? () => setFocusedPendingId(proposal.id) : undefined
                  }
                  onSubmitDecision={(payload) => handleProposalDecision(proposal, payload)}
                  onRetryPreview={onRetryPreview}
                  onCreateScopedRule={onCreateScopedRule}
                />
              );
            })}
          </div>

          {isCompanion ? (
            <p className="border-t border-border px-2 py-2 text-[11px] text-fg-dim">
              Authoring stays on the desktop — the watch is for gates and reads.
            </p>
          ) : (
            <AgentComposer
              value={effectiveComposerValue}
              onChange={updateComposerValue}
              onSubmitPrompt={() => void submitComposerPrompt()}
              runtimeReachable={runtimeReachable}
              textareaRef={activeComposerRef}
              activeModelLabel={activeModelLabel}
              onSelectActiveModel={onSelectActiveModel}
              preflight={composerPreflight}
            />
          )}
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
          className="flex w-review max-md:w-full shrink-0 flex-col overflow-hidden border-t border-border bg-surface md:border-s md:border-t-0"
        >
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <h2 className="text-xs font-semibold text-fg">Review changes</h2>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Close review pane"
              onClick={() => toggleReviewPane(false)}
            >
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
                const endLine = Math.max(
                  hunk.newStart,
                  hunk.newStart + Math.max(hunk.additions - 1, 0),
                );
                updateComposerValue(`Please revise ${hunk.path}:${hunk.newStart}-${endLine} — `);
                activeComposerRef.current?.focus();
              }}
            />
          </div>
        </aside>
      ) : null}
    </div>
  );
}
