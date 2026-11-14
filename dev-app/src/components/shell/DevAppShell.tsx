import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import * as Tabs from "@radix-ui/react-tabs";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import type { EgressTelemetryState, RailSection, SidebarTaskItem, TaskStatus } from "@/lib/types";

export type LogsDrawerTab = "logs" | "terminal" | "network";
export type CompanionTab = "approvals" | "tasks" | "record" | "status";

export interface DevAppShellProps {
  activeSection: RailSection;
  onSelectSection: (section: RailSection) => void;
  tasks?: SidebarTaskItem[];
  activeTaskId?: string;
  onSelectTask?: (taskId: string) => void;
  onNewTask?: () => void;
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

export function formatEgressBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isTabMap(v: DevAppShellProps["logsDrawerContent"]): v is Partial<Record<LogsDrawerTab, React.ReactNode>> {
  return typeof v === "object" && v !== null && !React.isValidElement(v) && ("logs" in v || "terminal" in v || "network" in v);
}

interface StatusBarEgressProps {
  egress: EgressTelemetryState;
  offlineSetting: boolean;
  deployPending: boolean;
  onSwitchToLocalModel?: () => void;
  onGoOffline?: () => void;
}

function StatusBarEgress({ egress, offlineSetting, deployPending, onSwitchToLocalModel, onGoOffline }: StatusBarEgressProps): React.JSX.Element {
  const egressPopoverHeadingId = useId();

  if (egress.mode === "measured_offline") {
    const suffix = egress.lastCheckedAt ? ` (${egress.lastCheckedAt})` : "";
    return (
      <div className="flex items-center gap-2">
        <span className="text-ok">{`Offline · verified${suffix}`}</span>
        <span aria-hidden="true" className="text-fg-dim">·</span>
        <span className="font-mono tabular-nums text-fg-muted">0 B sent</span>
        <SemanticBadge kind="live" />
      </div>
    );
  }
  if (egress.mode === "air_gapped_verified") {
    const suffix = egress.lastCheckedAt ? ` (${egress.lastCheckedAt})` : "";
    return (
      <div className="flex items-center gap-2">
        <span className="text-teal-accent">{`Air-gapped · verified${suffix}`}</span>
        <span aria-hidden="true" className="text-fg-dim">·</span>
        <span className="font-mono text-fg-muted">sent: unmeasured</span>
        <SemanticBadge kind="locked" />
      </div>
    );
  }
  if (egress.mode === "unknown_probe_failed") {
    return (
      <div className="flex items-center gap-2">
        <span className="text-warning">Network: unknown (probe failed)</span>
        <span aria-hidden="true" className="text-fg-dim">·</span>
        <span className="font-mono text-fg-muted">sent: unmeasured</span>
        <SemanticBadge kind="unmeasured" />
      </div>
    );
  }

  if (egress.mode === "connected_warning") {
    const bytesText =
      egress.bytesSent !== null ? `${formatEgressBytes(egress.bytesSent)} sent` : "sent: unmeasured";
    return (
      <div className="flex items-center gap-2">
        <span className="text-fg-muted">Connected</span>
        <span aria-hidden="true" className="text-fg-dim">·</span>
        <span className="font-medium text-warning">{`Cloud used (${egress.cloudCallsCount})`}</span>
        <span aria-hidden="true" className="text-fg-dim">·</span>
        <span className="font-mono tabular-nums text-fg">{bytesText}</span>
        <SemanticBadge kind="live" />
        <Popover.Root>
          <Popover.Trigger asChild>
            <button
              type="button"
              className="rounded-xs border border-border-control bg-surface-elevated px-1.5 py-0 font-sans text-[11px] font-medium text-fg hover:border-fg-muted"
            >
              Details
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              side="top"
              align="end"
              sideOffset={6}
              aria-labelledby={egressPopoverHeadingId}
              className="z-50 w-80 rounded-md border border-border-strong bg-surface p-3 text-ui text-fg shadow-popover"
            >
              <div className="space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <h2 id={egressPopoverHeadingId} className="text-xs font-semibold text-fg">
                    Data sent this session
                  </h2>
                  <SemanticBadge kind="live" />
                </div>
                {egress.endpoints.length > 0 ? (
                  <ul className="divide-y divide-border rounded-sm border border-border bg-canvas/60">
                    {egress.endpoints.map((ep) => (
                      <li
                        key={`${ep.host}-${ep.purpose}`}
                        className="flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs"
                      >
                        <div className="min-w-0">
                          <div className="truncate font-mono text-fg">
                            <code dir="ltr" className="unicode-bidi-isolate">{ep.host}</code>
                          </div>
                          <div className="truncate text-[11px] text-fg-muted">
                            {ep.purpose}
                            {ep.modelId ? (
                              <>
                                {" · "}
                                <code dir="ltr" className="unicode-bidi-isolate">{ep.modelId}</code>
                              </>
                            ) : null}
                          </div>
                        </div>
                        <div className="shrink-0 text-end font-mono text-[11px] tabular-nums text-fg-muted">
                          <div>{`${ep.calls} ${ep.calls === 1 ? "call" : "calls"}`}</div>
                          <div>{ep.bytesSent !== null ? formatEgressBytes(ep.bytesSent) : "unmeasured"}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p className="text-[11px] text-fg-muted">Every request is also a Record entry.</p>
                <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                  <Button size="sm" variant="primary" onClick={() => onSwitchToLocalModel?.()}>
                    Switch to local model
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => onGoOffline?.()}>
                    Go offline
                  </Button>
                </div>
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
    );
  }

  const label = deployPending
    ? "Network: deploy pending, nothing sent yet"
    : offlineSetting === false
      ? "Connected"
      : "Offline (setting)";

  return (
    <div className="flex items-center gap-2">
      <span className="text-fg-muted">{label}</span>
      <span aria-hidden="true" className="text-fg-dim">·</span>
      <span className="font-mono text-fg-muted">sent: unmeasured</span>
      <SemanticBadge kind="unmeasured" />
    </div>
  );
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

export function DevAppShell(props: DevAppShellProps): React.JSX.Element {
  const {
    activeSection, onSelectSection, tasks = [], activeTaskId, onSelectTask, onNewTask,
    pendingApprovalCount, onJumpToApprovalHeading, contextSidebarContent, contextSidebarLabel,
    reviewDrawerOpen = false, onToggleReviewDrawer, reviewDrawerContent, reviewDrawerTitle = "Review",
    logsDrawerOpen: controlledLogsOpen, defaultLogsDrawerOpen = false, onToggleLogsDrawer,
    logsTab: controlledLogsTab, onSelectLogsTab, logsDrawerContent, egress = DEFAULT_EGRESS,
    offlineSetting = true, deployPending = false, onSwitchToLocalModel, onGoOffline,
    onOpenCommandPalette, workspaceBranch, activeModelLabel, recordSeqLatest,
    mainAriaLabel = "Agent workspace", politeAnnouncement, isDesktopApp = false, isMobileCompanion,
    activeCompanionTab = "tasks", onSelectCompanionTab, children,
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
    activeSection !== "record" &&
    (activeSection === "tasks" || contextSidebarContent !== undefined);

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
              <TasksQueueList
                tasks={sortedTasks}
                activeTaskId={activeTaskId}
                onSelectTask={onSelectTask}
                onNewTask={onNewTask}
              />
            )}
          </aside>
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
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
              Local · <code dir="ltr" className="unicode-bidi-isolate">{activeModelLabel}</code>
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
            onSwitchToLocalModel={onSwitchToLocalModel}
            onGoOffline={onGoOffline}
          />
        </div>
      </footer>
    </div>
  );
}
