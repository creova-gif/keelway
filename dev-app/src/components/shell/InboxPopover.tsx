import React, { useEffect, useId, useRef, useState } from "react";
import { fetchAuditEntries } from "@/lib/api";
import type { RecordLedgerEntry, SidebarTaskItem } from "@/lib/types";

const DENIAL_ACTION_MARKER = /denied|rejected|blocked|refused/i;
const DENIAL_ROW_LIMIT = 4;

export function isDenialEntry(entry: RecordLedgerEntry): boolean {
  return entry.outcome === "denied" || DENIAL_ACTION_MARKER.test(entry.action);
}

export interface InboxPopoverProps {
  tasks: SidebarTaskItem[];
  onSelectTask?: (taskId: string) => void;
  onJumpToApprovalHeading?: () => void;
  onOpenRecord?: () => void;
  fetchAuditEntriesFn?: () => Promise<RecordLedgerEntry[]>;
}

export function InboxPopover({
  tasks,
  onSelectTask,
  onJumpToApprovalHeading,
  onOpenRecord,
  fetchAuditEntriesFn = fetchAuditEntries,
}: InboxPopoverProps): React.JSX.Element {
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [denials, setDenials] = useState<RecordLedgerEntry[] | null>(null);
  const [denialsError, setDenialsError] = useState(false);

  const pendingApprovals = tasks.filter((t) => t.status === "needs_approval");
  const runOutcomes = tasks.filter((t) => t.status === "done" || t.status === "failed");
  const unreadCount = pendingApprovals.length;

  useEffect(() => {
    if (!open || denials !== null || denialsError) return;
    let mounted = true;
    fetchAuditEntriesFn()
      .then((entries) => {
        if (!mounted) return;
        setDenials(
          entries
            .filter(isDenialEntry)
            .sort((a, b) => b.seq - a.seq)
            .slice(0, DENIAL_ROW_LIMIT),
        );
      })
      .catch(() => {
        if (mounted) setDenialsError(true);
      });
    return () => {
      mounted = false;
    };
  }, [open, denials, denialsError, fetchAuditEntriesFn]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && event.target instanceof Node && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={unreadCount > 0 ? `Inbox — ${unreadCount} pending approval${unreadCount === 1 ? "" : "s"}` : "Inbox — nothing pending"}
        onClick={() => setOpen((v) => !v)}
        className="relative inline-flex items-center gap-1.5 rounded-xs px-1.5 py-0.5 font-mono text-[10px] font-semibold text-fg-muted hover:bg-surface hover:text-fg focus:outline-none focus-visible:underline"
      >
        Inbox
        {unreadCount > 0 ? (
          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-ochre" />
        ) : null}
      </button>
      {open ? (
        <div
          id={panelId}
          role="dialog"
          aria-label="Inbox — what needs you"
          className="absolute end-0 top-full z-50 mt-1 w-80 rounded-md border border-border-strong bg-surface text-xs text-fg shadow-modal"
        >
          <div className="flex items-baseline justify-between gap-2 border-b border-border px-3 py-2">
            <span className="font-semibold text-fg">Inbox — what needs you</span>
            <span className="font-mono text-[10px] text-fg-dim">rail button, unread dot only</span>
          </div>
          {pendingApprovals.length === 0 && runOutcomes.length === 0 && (denials ?? []).length === 0 ? (
            <p className="px-3 py-3 text-fg-muted">
              Nothing needs you — no pending gates, finished runs, or denied actions on the tape.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {pendingApprovals.map((task) => (
                <li key={`approval-${task.id}`} className="flex items-center justify-between gap-2 px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-ochre" />
                      <span className="truncate font-semibold text-fg">{`P-10 · ${task.title}`}</span>
                    </div>
                    <p className="mt-0.5 truncate font-mono text-[10px] text-fg-dim">
                      {task.branch ? `${task.branch} · ` : ""}human gate — never auto-approved
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onSelectTask?.(task.id);
                      onJumpToApprovalHeading?.();
                      setOpen(false);
                    }}
                    className="shrink-0 rounded-xs border border-ochre/60 px-2 py-0.5 font-mono text-[10px] font-semibold text-ochre hover:bg-ochre-subtle"
                  >
                    Review
                  </button>
                </li>
              ))}
              {runOutcomes.map((task) => (
                <li key={`run-${task.id}`} className="flex items-center justify-between gap-2 px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span
                        aria-hidden="true"
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${task.status === "done" ? "bg-success" : "bg-danger"}`}
                      />
                      <span className="truncate font-semibold text-fg">
                        {`${task.status === "done" ? "Run finished" : "Run failed"} — ${task.title}`}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate font-mono text-[10px] text-fg-dim">
                      {task.modelLabel ? `${task.modelLabel} · ` : ""}{task.updatedAt}
                    </p>
                  </div>
                  {onOpenRecord ? (
                    <button
                      type="button"
                      onClick={() => {
                        onOpenRecord();
                        setOpen(false);
                      }}
                      className="shrink-0 rounded-xs px-1.5 py-0.5 font-mono text-[10px] font-semibold text-fg-muted hover:bg-canvas hover:text-fg"
                    >
                      Tape ↗
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {denials && denials.length > 0 ? (
            <div className="border-t border-border">
              <div className="px-3 pt-2 font-mono text-[10px] uppercase tracking-wide text-fg-dim">
                Security events — from the Record
              </div>
              <ul className="divide-y divide-border">
                {denials.map((entry) => (
                  <li key={`denial-${entry.seq}`} className="flex items-center justify-between gap-2 px-3 py-2.5">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-danger" />
                        <span className="truncate font-semibold text-fg">{`${entry.action} — ${entry.target}`}</span>
                      </div>
                      <p className="mt-0.5 truncate font-mono text-[10px] text-fg-dim">
                        {`Record #${entry.seq} · ${entry.actorLabel} · ${entry.timestampEt}`}
                      </p>
                    </div>
                    {onOpenRecord ? (
                      <button
                        type="button"
                        onClick={() => {
                          onOpenRecord();
                          setOpen(false);
                        }}
                        className="shrink-0 rounded-xs px-1.5 py-0.5 font-mono text-[10px] font-semibold text-fg-muted hover:bg-canvas hover:text-fg"
                      >
                        Tape ↗
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : denialsError ? (
            <p className="border-t border-border px-3 py-2 text-[10px] text-fg-dim">
              Security events unavailable — Record endpoint unreachable.
            </p>
          ) : null}
          <p className="border-t border-border px-3 py-2 text-[10px] text-fg-dim">
            P-10 requests (actionable), run outcomes and denied actions (tape links). No marketing pings, ever.
          </p>
        </div>
      ) : null}
    </div>
  );
}
