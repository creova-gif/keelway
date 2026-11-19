import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import {
  formatEgressBytes,
  resolveEgressDisplay,
  StatusBarEgress,
} from "@/components/shell/StatusBarEgress";
import { BrandMark } from "@/components/ui/BrandMark";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import type { EgressTelemetryState, RailSection, SidebarAgentItem, SidebarTaskItem, TaskStatus } from "@/lib/types";
import { subscribeApiErrors, subscribeDataFallbacks, type ApiRequestError } from "@/lib/api";

export { formatEgressBytes, resolveEgressDisplay };

export type LogsDrawerTab = "logs" | "terminal" | "network";
export type CompanionTab = "approvals" | "tasks" | "record" | "status";

export interface DevAppShellProps {
  activeSection: RailSection;
  onSelectSection: (section: RailSection) => void;
  tasks?: SidebarTaskItem[];
  activeTaskId?: string;
  onSelectTask?: (taskId: string) => void;
  onNewTask?: () => void;
  agents?: SidebarAgentItem[];
  onSelectAgent?: () => void;
  pendingApprovalCount?: number;
  onJumpToApprovalHeading?: () => void;
  contextSidebarContent?: React.ReactNode;
  contextSidebarLabel?: string;
  reviewDrawerOpen?: boolean;
  onToggleReviewDrawer?: (open: boolean) => void;
  reviewDrawerContent?: React.ReactNode;
  reviewDrawerTitle?: string;
  logsDrawerOpen?: boolean;
  defaultLogsDrawerOpen?: boolean;
  onToggleLogsDrawer?: (open: boolean) => void;
  logsTab?: LogsDrawerTab;
  onSelectLogsTab?: (tab: LogsDrawerTab) => void;
  logsDrawerContent?: React.ReactNode | Partial<Record<LogsDrawerTab, React.ReactNode>>;
  egress?: EgressTelemetryState;
  offlineSetting?: boolean;
  deployPending?: boolean;
  onSwitchToLocalModel?: () => void;
  onGoOffline?: () => void;
  onOpenCommandPalette?: () => void;
  workspaceBranch?: string;
  activeModelLabel?: string;
  recordSeqLatest?: number;
  mainAriaLabel?: string;
  politeAnnouncement?: string;
  isDesktopApp?: boolean;
  isMobileCompanion?: boolean;
  activeCompanionTab?: CompanionTab;
  onSelectCompanionTab?: (tab: CompanionTab) => void;
  topWorkspaceBar?: React.ReactNode;
  hideSidebar?: boolean;
  children: React.ReactNode;
}

const DEFAULT_EGRESS: EgressTelemetryState = {
  mode: "unmeasured", cloudCallsCount: 0, bytesSent: null, airGapLocked: false, endpoints: [],
};

const TASK_STATUS_PRIORITY: Record<TaskStatus, number> = {
  needs_approval: 0, running: 1, queued: 2, ready: 3, failed: 4, done: 5,
};

const TASK_STATUS_TO_BADGE: Record<TaskStatus, SemanticBadgeKind> = {
  needs_approval: "needs-approval", running: "running", queued: "queued",
  done: "done", ready: "ready", failed: "failed",
};

const RAIL_ITEMS: Array<{ section: RailSection; label: string; glyph: string }> = [
  { section: "tasks", label: "Tasks", glyph: "◈" },
  { section: "files", label: "Files", glyph: "▤" },
  { section: "record", label: "Record", glyph: "⛓" },
  { section: "settings", label: "Settings", glyph: "⚙" },
];

function isTabMap(v: DevAppShellProps["logsDrawerContent"]): v is Partial<Record<LogsDrawerTab, React.ReactNode>> {
  return typeof v === "object" && v !== null && !React.isValidElement(v) && ("logs" in v || "terminal" in v || "network" in v);
}

interface TasksQueueListProps {
  tasks: SidebarTaskItem[];
  activeTaskId?: string;
  onSelectTask?: (taskId: string) => void;
  onNewTask?: () => void;
}

function TasksQueueList({
  tasks,
  activeTaskId,
  onSelectTask,
  onNewTask,
}: TasksQueueListProps): React.JSX.Element {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-muted">Tasks</span>
        {onNewTask ? (
          <Button size="sm" variant="secondary" onClick={onNewTask}>
            New task
          </Button>
        ) : null}
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {tasks.length === 0 ? (
          <p className="px-2 py-4 text-xs text-fg-muted">No tasks in this workspace yet.</p>
        ) : (
          tasks.map((task) => {
            const isPending = task.status === "needs_approval";
            const isSelected = task.id === activeTaskId;
            return (
              <button
                key={task.id}
                type="button"
                aria-current={isSelected ? "true" : undefined}
                onClick={() => onSelectTask?.(task.id)}
                className={`flex min-h-task-row w-full flex-col gap-1 rounded-sm border px-2.5 py-2 text-start transition-colors ${
                  isPending
                    ? "border-s-2 border-ochre bg-ochre-subtle/30 hover:bg-ochre-subtle/50"
                    : isSelected
                      ? "border-teal-accent/45 bg-surface-elevated"
                      : "border-transparent hover:border-border-strong hover:bg-surface"
                }`}
              >
                <span className="line-clamp-2 text-xs font-medium text-fg">{task.title}</span>
                <div className="flex w-full flex-wrap items-center justify-between gap-1.5">
                  <SemanticBadge kind={TASK_STATUS_TO_BADGE[task.status]} />
                  <span className="font-mono text-[10px] text-fg-dim">{task.updatedAt}</span>
                </div>
                {task.branch ? (
                  <div className="truncate font-mono text-[10px] text-fg-muted">
                    <code dir="ltr" className="unicode-bidi-isolate">{task.branch}</code>
                  </div>
                ) : null}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

interface AgentsRailListProps {
  agents: SidebarAgentItem[];
  onSelectAgent?: () => void;
}

const AGENT_STATUS_DOT: Record<TaskStatus, { label: string; dot: string } | null> = {
  needs_approval: { label: "Needs approval", dot: "bg-ochre" },
  running: { label: "Running", dot: "bg-running" },
  queued: { label: "Queued", dot: "bg-fg-dim" },
  ready: null,
  done: { label: "Done", dot: "bg-fg-muted" },
  failed: { label: "Failed", dot: "bg-danger" },
};

function AgentsRailList({ agents, onSelectAgent }: AgentsRailListProps): React.JSX.Element {
  const [collapsed, setCollapsed] = useState(false);
  const attentionCount = agents.filter((a) => AGENT_STATUS_DOT[a.status] !== null).length;
  return (
    <section aria-label="Agents" className="flex max-h-[45%] shrink-0 flex-col border-t border-border">
      <button
        type="button"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center justify-between gap-2 border-b border-border px-3 py-2 text-start transition-colors hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-teal-accent"
      >
        <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-fg-muted">
          <span aria-hidden="true" className={`font-mono text-[9px] transition-transform ${collapsed ? "" : "rotate-90"}`}>▸</span>
          Agents
        </span>
        <span className="font-mono text-[10px] text-fg-dim">
          {attentionCount > 0 ? `${attentionCount} need attention · ` : ""}
          {agents.length} registered
        </span>
      </button>
      {!collapsed ? (
        <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {agents.map((agent) => {
            const status = AGENT_STATUS_DOT[agent.status];
            return (
              <button
                key={agent.id}
                type="button"
                onClick={onSelectAgent}
                className="flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-start transition-colors hover:bg-surface"
              >
                <span className="flex min-w-0 flex-col">
                  <code className="truncate font-mono text-[11px] font-medium text-fg">{agent.name}</code>
                  <span className="truncate text-[10px] text-fg-dim">{agent.roleTitle}</span>
                </span>
                {status ? (
                  <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-fg-muted">
                    <span aria-hidden="true" className={`inline-block h-1.5 w-1.5 rounded-full ${status.dot}`} />
                    {status.label}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

export function DevAppShell(props: DevAppShellProps): React.JSX.Element {
  const {
    activeSection, onSelectSection, tasks = [], activeTaskId, onSelectTask, onNewTask,
    agents = [], onSelectAgent,
    pendingApprovalCount, onJumpToApprovalHeading, contextSidebarContent, contextSidebarLabel,
    reviewDrawerOpen = false, onToggleReviewDrawer, reviewDrawerContent, reviewDrawerTitle = "Review",
    logsDrawerOpen: controlledLogsOpen, defaultLogsDrawerOpen = false, onToggleLogsDrawer,
    logsTab: controlledLogsTab, onSelectLogsTab, logsDrawerContent, egress = DEFAULT_EGRESS,
    offlineSetting = true, deployPending = false, onSwitchToLocalModel, onGoOffline,
    onOpenCommandPalette, workspaceBranch, activeModelLabel, recordSeqLatest,
    mainAriaLabel = "Agent workspace", politeAnnouncement, isDesktopApp = false, isMobileCompanion,
    activeCompanionTab = "tasks", onSelectCompanionTab, topWorkspaceBar, hideSidebar = false, children,
  } = props;

  const [uncontrolledLogsOpen, setUncontrolledLogsOpen] = useState(defaultLogsDrawerOpen);
  const [uncontrolledLogsTab, setUncontrolledLogsTab] = useState<LogsDrawerTab>("logs");
  const [isNarrowViewport, setIsNarrowViewport] = useState<boolean>(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 767px)").matches
      : false,
  );
  const isLogsOpen = controlledLogsOpen ?? uncontrolledLogsOpen;
  const currentLogsTab = controlledLogsTab ?? uncontrolledLogsTab;
  const effectiveMobileCompanion = isMobileCompanion ?? isNarrowViewport;
  const [fallbackResponseCount, setFallbackResponseCount] = useState(0);
  const [lastApiError, setLastApiError] = useState<ApiRequestError | null>(null);

  useEffect(() => subscribeDataFallbacks(setFallbackResponseCount), []);
  useEffect(() => subscribeApiErrors(setLastApiError), []);

  useEffect(() => {
    if (
      isMobileCompanion !== undefined ||
      typeof window === "undefined" ||
      typeof window.matchMedia !== "function"
    ) {
      return;
    }
    const mql = window.matchMedia("(max-width: 767px)");
    setIsNarrowViewport(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setIsNarrowViewport(e.matches);
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    mql.addListener?.(onChange);
    return () => mql.removeListener?.(onChange);
  }, [isMobileCompanion]);

  const primaryRailRef = useRef<HTMLElement | null>(null);
  const sidebarRef = useRef<HTMLElement | null>(null);
  const mainRef = useRef<HTMLElement | null>(null);
  const reviewRef = useRef<HTMLElement | null>(null);
  const logsRef = useRef<HTMLElement | null>(null);
  const statusBarRef = useRef<HTMLElement | null>(null);

  const sortedTasks = useMemo(
    () =>
      tasks
        .map((item, idx) => ({ item, idx }))
        .sort((a, b) => {
          const diff = TASK_STATUS_PRIORITY[a.item.status] - TASK_STATUS_PRIORITY[b.item.status];
          return diff !== 0 ? diff : a.idx - b.idx;
        })
        .map(({ item }) => item),
    [tasks],
  );

  const effectivePendingCount = useMemo(
    () =>
      typeof pendingApprovalCount === "number"
        ? pendingApprovalCount
        : tasks.filter((t) => t.status === "needs_approval").length,
    [pendingApprovalCount, tasks],
  );

  const setLogsOpen = useCallback(
    (next: boolean) => {
      if (controlledLogsOpen === undefined) setUncontrolledLogsOpen(next);
      onToggleLogsDrawer?.(next);
    },
    [controlledLogsOpen, onToggleLogsDrawer],
  );

  const handleTabChange = useCallback(
    (value: string) => {
      const nextTab = value as LogsDrawerTab;
      if (controlledLogsTab === undefined) setUncontrolledLogsTab(nextTab);
      onSelectLogsTab?.(nextTab);
    },
    [controlledLogsTab, onSelectLogsTab],
  );

  const shouldRenderSidebar =
    !effectiveMobileCompanion &&
    !hideSidebar &&
    activeSection !== "record";

  const resolvedSidebarLabel =
    contextSidebarLabel ??
    (activeSection === "tasks" ? "Tasks" : activeSection === "files" ? "Files" : "Settings");

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (document.querySelector('[role="dialog"]')) return;
      if (event.key === "F6") {
        event.preventDefault();
        const slots = [
          {
            target: sidebarRef.current ?? primaryRailRef.current,
            contains: (el: Element | null) =>
              Boolean(el && (primaryRailRef.current?.contains(el) || sidebarRef.current?.contains(el))),
          },
          { target: mainRef.current, contains: (el: Element | null) => Boolean(el && mainRef.current?.contains(el)) },
          ...(reviewDrawerOpen && reviewRef.current
            ? [{ target: reviewRef.current, contains: (el: Element | null) => Boolean(el && reviewRef.current?.contains(el)) }]
            : []),
          ...(isLogsOpen && logsRef.current
            ? [{ target: logsRef.current, contains: (el: Element | null) => Boolean(el && logsRef.current?.contains(el)) }]
            : []),
          { target: statusBarRef.current, contains: (el: Element | null) => Boolean(el && statusBarRef.current?.contains(el)) },
        ].filter((s) => s.target !== null);
        if (slots.length === 0) return;
        const idx = slots.findIndex((s) => s.contains(document.activeElement));
        const nextIdx =
          idx === -1
            ? event.shiftKey ? slots.length - 1 : 0
            : event.shiftKey ? (idx - 1 + slots.length) % slots.length : (idx + 1) % slots.length;
        slots[nextIdx]?.target?.focus();
        return;
      }

      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const lowerKey = event.key.toLowerCase();
      if (event.shiftKey && lowerKey === "r") {
        if (isDesktopApp) {
          event.preventDefault();
          onSelectSection("record");
        }
        return;
      }
      if (event.shiftKey && lowerKey === "a") {
        if (effectivePendingCount > 0 && onJumpToApprovalHeading) {
          event.preventDefault();
          onJumpToApprovalHeading();
        }
        return;
      }
      if (event.shiftKey) return;
      if (event.key === "1") {
        event.preventDefault();
        (sidebarRef.current ?? primaryRailRef.current)?.focus();
      } else if (event.key === "2") {
        event.preventDefault();
        mainRef.current?.focus();
      } else if (event.key === "3" && reviewDrawerOpen && reviewRef.current) {
        event.preventDefault();
        reviewRef.current.focus();
      } else if (lowerKey === "j") {
        event.preventDefault();
        setLogsOpen(!isLogsOpen);
      } else if (lowerKey === "k" && onOpenCommandPalette) {
        event.preventDefault();
        onOpenCommandPalette();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    effectivePendingCount, isDesktopApp, isLogsOpen, onJumpToApprovalHeading,
    onOpenCommandPalette, onSelectSection, reviewDrawerOpen, setLogsOpen,
  ]);

  const renderLogsTabBody = (tab: LogsDrawerTab): React.ReactNode => {
    if (isTabMap(logsDrawerContent) && logsDrawerContent[tab] !== undefined) {
      return logsDrawerContent[tab];
    }
    if (!isTabMap(logsDrawerContent) && logsDrawerContent !== undefined && tab === currentLogsTab) {
      return logsDrawerContent;
    }
    if (tab === "logs") {
      return (
        <div className="font-mono text-xs text-fg-muted">
          [loopback] Seatbelt workspace isolation active · awaiting stream events.
        </div>
      );
    }
    if (tab === "terminal") {
      return (
        <div className="font-mono text-xs text-fg-muted">
          Sandboxed workspace shell (<code dir="ltr" className="unicode-bidi-isolate">/v1/terminal/exec</code>) ready.
        </div>
      );
    }
    return (
      <div className="font-mono text-xs text-fg-muted">
        Egress monitor mode: <code dir="ltr" className="unicode-bidi-isolate">{egress.mode}</code>
      </div>
    );
  };

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-canvas text-fg">
      <div className="flex items-center gap-2">
        <a
          href="#kw-main-workspace"
          onClick={(e) => {
            e.preventDefault();
            mainRef.current?.focus();
          }}
          className="sr-only focus:not-sr-only focus:fixed focus:start-2 focus:top-2 focus:z-50 focus:rounded-sm focus:border focus:border-border-focus focus:bg-surface-elevated focus:px-3 focus:py-1.5 focus:text-xs focus:font-semibold focus:text-fg"
        >
          Skip to Agent workspace
        </a>
        {effectivePendingCount > 0 ? (
          <button
            type="button"
            onClick={() => onJumpToApprovalHeading?.()}
            className="sr-only focus:not-sr-only focus:fixed focus:start-48 focus:top-2 focus:z-50 focus:rounded-sm focus:border focus:border-ochre focus:bg-surface-elevated focus:px-3 focus:py-1.5 focus:text-xs focus:font-semibold focus:text-ochre"
          >
            {`Jump to pending approval (${effectivePendingCount})`}
          </button>
        ) : null}
      </div>

      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        data-testid="shell-polite-announcer"
      >
        {politeAnnouncement}
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {!effectiveMobileCompanion ? (
          <nav
            ref={primaryRailRef}
            aria-label="Primary navigation"
            tabIndex={-1}
            data-programmatic-focus="true"
            className="flex w-rail shrink-0 flex-col items-center justify-between border-e border-border bg-chrome py-2"
          >
            <div className="flex w-full flex-col items-center gap-1.5">
              <div className="mb-0.5 flex h-9 w-9 items-center justify-center rounded-sm text-fg">
                <BrandMark size={20} showWordmark={false} />
              </div>
              {RAIL_ITEMS.map((item) => {
                const isActive = activeSection === item.section;
                const showBadge = item.section === "tasks" && effectivePendingCount > 0;
                return (
                  <button
                    key={item.section}
                    type="button"
                    aria-label={item.label}
                    aria-current={isActive ? "page" : undefined}
                    title={item.label}
                    onClick={() => onSelectSection(item.section)}
                    className={`relative flex h-9 w-9 items-center justify-center rounded-sm border transition-colors ${
                      isActive
                        ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
                        : "border-transparent text-fg-muted hover:bg-surface-elevated hover:text-fg"
                    }`}
                  >
                    <span aria-hidden="true" className="font-mono text-sm leading-none">{item.glyph}</span>
                    {showBadge ? (
                      <span
                        aria-hidden="true"
                        className="absolute -end-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-ochre px-1 font-mono text-[10px] font-bold leading-none text-ochre-ink"
                      >
                        {effectivePendingCount}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            {onOpenCommandPalette ? (
              <button
                type="button"
                aria-label="Open command palette"
                title="Command palette (⌘K)"
                onClick={onOpenCommandPalette}
                className="flex h-8 w-8 items-center justify-center rounded-sm border border-border-control/60 bg-surface text-fg-muted hover:border-fg-muted hover:text-fg"
              >
                <span aria-hidden="true" className="font-mono text-[10px]">⌘K</span>
              </button>
            ) : null}
          </nav>
        ) : null}

        {shouldRenderSidebar ? (
          <aside
            ref={sidebarRef}
            aria-label={resolvedSidebarLabel}
            tabIndex={-1}
            data-programmatic-focus="true"
            className="flex w-sidebar shrink-0 flex-col overflow-hidden border-e border-border bg-chrome"
          >
            {contextSidebarContent !== undefined ? (
              contextSidebarContent
            ) : (
              <div className="flex h-full flex-col overflow-hidden">
                <div className="min-h-0 flex-1">
                  <TasksQueueList
                    tasks={sortedTasks}
                    activeTaskId={activeTaskId}
                    onSelectTask={onSelectTask}
                    onNewTask={onNewTask}
                  />
                </div>
                {agents.length > 0 ? (
                  <AgentsRailList agents={agents} onSelectAgent={onSelectAgent} />
                ) : null}
              </div>
            )}
          </aside>
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {!effectiveMobileCompanion && topWorkspaceBar ? topWorkspaceBar : null}
          <main
            id="kw-main-workspace"
            ref={mainRef}
            aria-label={mainAriaLabel}
            tabIndex={-1}
            data-programmatic-focus="true"
            className="min-h-0 flex-1 overflow-y-auto bg-canvas"
          >
            {children}
          </main>

          {isLogsOpen ? (
            <section
              ref={logsRef}
              aria-label="Logs and terminal"
              tabIndex={-1}
              data-programmatic-focus="true"
              className="flex h-[300px] shrink-0 flex-col border-t border-border-strong bg-chrome"
            >
              <Tabs.Root value={currentLogsTab} onValueChange={handleTabChange} className="flex min-h-0 flex-1 flex-col">
                <div className="flex items-center justify-between border-b border-border px-3 py-1">
                  <Tabs.List aria-label="Workspace output tabs" className="flex items-center gap-1">
                    {(["logs", "terminal", "network"] as const).map((tab) => (
                      <Tabs.Trigger
                        key={tab}
                        value={tab}
                        className="rounded-xs px-2.5 py-1 text-xs font-medium capitalize text-fg-muted data-[state=active]:bg-surface-elevated data-[state=active]:text-fg"
                      >
                        {tab}
                      </Tabs.Trigger>
                    ))}
                  </Tabs.List>
                  <Button size="sm" variant="ghost" aria-label="Close logs drawer" onClick={() => setLogsOpen(false)}>
                    Close
                  </Button>
                </div>
                {(["logs", "terminal", "network"] as const).map((tab) => (
                  <Tabs.Content key={tab} value={tab} className="min-h-0 flex-1 overflow-y-auto bg-code p-3">
                    {renderLogsTabBody(tab)}
                  </Tabs.Content>
                ))}
              </Tabs.Root>
            </section>
          ) : null}
        </div>

        {!effectiveMobileCompanion && reviewDrawerOpen ? (
          <aside
            ref={reviewRef}
            aria-label={reviewDrawerTitle}
            tabIndex={-1}
            data-programmatic-focus="true"
            className="flex w-review shrink-0 flex-col overflow-hidden border-s border-border bg-surface"
          >
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <span className="text-xs font-semibold text-fg">{reviewDrawerTitle}</span>
              {onToggleReviewDrawer ? (
                <Button size="sm" variant="ghost" aria-label="Close review drawer" onClick={() => onToggleReviewDrawer(false)}>
                  Close
                </Button>
              ) : null}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-3">{reviewDrawerContent}</div>
          </aside>
        ) : null}
      </div>

      {effectiveMobileCompanion ? (
        <nav aria-label="Companion navigation" className="grid grid-cols-4 gap-1 border-t border-border bg-chrome px-2 py-1">
          {(
            [
              { tab: "approvals", label: "Approvals", section: "tasks" as RailSection },
              { tab: "tasks", label: "Tasks", section: "tasks" as RailSection },
              { tab: "record", label: "Record", section: "record" as RailSection },
              { tab: "status", label: "Status", section: "settings" as RailSection },
            ] as const
          ).map((item) => {
            const isCurrent = activeCompanionTab === item.tab;
            return (
              <button
                key={item.tab}
                type="button"
                aria-current={isCurrent ? "page" : undefined}
                onClick={() => {
                  onSelectCompanionTab?.(item.tab);
                  onSelectSection(item.section);
                  if (item.tab === "approvals") onJumpToApprovalHeading?.();
                }}
                className={`flex min-h-11 min-w-11 items-center justify-center gap-1.5 rounded-sm px-2 text-xs font-medium ${
                  isCurrent ? "bg-teal-surface text-teal-accent" : "text-fg-muted hover:bg-surface-elevated hover:text-fg"
                }`}
              >
                <span>{item.label}</span>
                {item.tab === "approvals" && effectivePendingCount > 0 ? (
                  <span aria-hidden="true" className="rounded-full bg-ochre px-1.5 py-0.5 font-mono text-[10px] font-bold leading-none text-ochre-ink">
                    {effectivePendingCount}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>
      ) : null}

      <footer
        id="keelway-status-bar"
        ref={statusBarRef}
        role="contentinfo"
        aria-label="Workspace status bar"
        aria-live="polite"
        aria-atomic="false"
        tabIndex={-1}
        data-programmatic-focus="true"
        className="flex h-statusbar min-h-statusbar shrink-0 items-center justify-between gap-3 border-t border-border bg-chrome px-3 text-[11px] leading-none"
      >
        <div className="flex min-w-0 items-center gap-3">
          {workspaceBranch ? (
            <span className="truncate font-mono text-fg-muted">
              <span aria-hidden="true" className="me-1">⎇</span>
              <code dir="ltr" className="unicode-bidi-isolate">{workspaceBranch}</code>
            </span>
          ) : null}
          {activeModelLabel ? (
            <span className="truncate font-mono text-fg-muted">
              {/^(local|cloud)\b/i.test(activeModelLabel)
                ? ""
                : egress.mode === "connected_warning" || offlineSetting === false
                  ? "Model · "
                  : "Local · "}
              <code dir="ltr" className="unicode-bidi-isolate">{activeModelLabel}</code>
            </span>
          ) : null}
          {typeof recordSeqLatest === "number" ? (
            <span className="font-mono tabular-nums text-fg-dim">{`Record #${recordSeqLatest}`}</span>
          ) : null}
          <button
            type="button"
            aria-expanded={isLogsOpen}
            onClick={() => setLogsOpen(!isLogsOpen)}
            className="rounded-xs px-1.5 py-0.5 font-mono text-[11px] text-fg-muted hover:bg-surface-elevated hover:text-fg"
          >
            Logs (⌘J)
          </button>
        </div>
        <div className="shrink-0">
          <StatusBarEgress
            egress={egress}
            offlineSetting={offlineSetting}
            deployPending={deployPending}
            fallbackResponseCount={fallbackResponseCount}
            apiError={lastApiError}
            onSwitchToLocalModel={onSwitchToLocalModel}
            onGoOffline={onGoOffline}
          />
        </div>
      </footer>
    </div>
  );
}
