import React from "react";
import type { SidebarTaskItem, TaskStatus } from "@/lib/types";

export interface ChatWorkspaceViewProps {
  tasks: SidebarTaskItem[];
  activeTaskId: string;
  onSelectTask: (taskId: string) => void;
  children: React.ReactNode;
}

const SESSION_STATUS_LABEL: Record<TaskStatus, string> = {
  needs_approval: "P-10 pending",
  running: "Running",
  queued: "Queued",
  done: "Done",
  ready: "Ready",
  failed: "Failed",
};

const SESSION_STATUS_CLASS: Record<TaskStatus, string> = {
  needs_approval: "border-ochre/60 text-ochre",
  running: "border-status-running/60 text-status-running",
  queued: "border-border-strong text-fg-muted",
  done: "border-status-ok/60 text-status-ok",
  ready: "border-border-strong text-fg-muted",
  failed: "border-red-danger/60 text-red-danger",
};

export function ChatWorkspaceView({
  tasks,
  activeTaskId,
  onSelectTask,
  children,
}: ChatWorkspaceViewProps): React.JSX.Element {
  return (
    <div className="flex h-full min-h-0 overflow-hidden" data-chat-view="true">
      <nav
        aria-label="Chat sessions"
        className="flex w-56 shrink-0 flex-col overflow-hidden border-e border-border bg-chrome max-md:w-40"
      >
        <p className="border-b border-border px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-dim">
          Sessions
        </p>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-1.5" role="listbox" aria-label="Agent sessions">
          {tasks.map((task) => {
            const isActive = task.id === activeTaskId;
            return (
              <button
                key={task.id}
                type="button"
                role="option"
                aria-selected={isActive}
                title={task.title}
                onClick={() => onSelectTask(task.id)}
                className={`flex w-full flex-col gap-1 rounded-xs border-s-2 px-2 py-1.5 text-start transition-colors duration-fast ease-state focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${
                  isActive
                    ? "border-s-accent bg-surface text-fg"
                    : "border-s-transparent text-fg-muted hover:bg-surface hover:text-fg"
                }`}
              >
                <span className="w-full truncate text-xs font-medium">{task.title}</span>
                <span className="flex items-center justify-between gap-2">
                  <span
                    className={`rounded-xs border px-1 py-px font-mono text-[9px] uppercase tracking-wide ${SESSION_STATUS_CLASS[task.status]}`}
                  >
                    {SESSION_STATUS_LABEL[task.status]}
                  </span>
                  <span className="font-mono text-[9px] text-fg-dim">{task.updatedAt}</span>
                </span>
              </button>
            );
          })}
        </div>
      </nav>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
