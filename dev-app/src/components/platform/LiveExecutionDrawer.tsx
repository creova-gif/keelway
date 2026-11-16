import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacApproveP10,
  postExecutionP10Decision,
  startExecutionRunStream,
  type LiveExecutionEvent,
  type LiveExecutionStatus,
  type RbacRoleId,
} from "@/lib/platformRuntimeApi";

export interface LiveExecutionDrawerProps {
  kind: "agent" | "workflow";
  targetId: string;
  targetName: string;
  objective: string;
  requiresP10?: boolean;
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
  runNonce?: number;
  onClose?: () => void;
}

function formatEventTag(ev: LiveExecutionEvent): string {
  if (ev.type === "run.completed") {
    return `[run.completed · ${ev.receiptSha256 ?? "sha256:verified"}]`;
  }
  return `[${ev.type}]`;
}

export function LiveExecutionDrawer({
  kind,
  targetId,
  targetName,
  objective,
  requiresP10 = true,
  workspaceId = "default",
  activeRbacRole = "owner",
  runNonce = 1,
  onClose,
}: LiveExecutionDrawerProps): React.JSX.Element {
  const [runId, setRunId] = useState<string>("");
  const [status, setStatus] = useState<LiveExecutionStatus>("streaming");
  const [events, setEvents] = useState<LiveExecutionEvent[]>([]);
  const [resolvingP10, setResolvingP10] = useState(false);

  const canApprove = canRbacApproveP10(activeRbacRole);
  const rbacTooltip = canApprove
    ? undefined
    : `RBAC Policy: role "${activeRbacRole}" cannot resolve P-10 human checkpoints (requires owner, admin, or operator).`;

  const roleAtLaunchRef = useRef<RbacRoleId>(activeRbacRole);
  roleAtLaunchRef.current = activeRbacRole;

  const launchStream = useCallback(async () => {
    setEvents([]);
    setStatus("streaming");
    const result = await startExecutionRunStream({
      kind,
      targetId,
      targetName,
      objective,
      requiresP10,
      workspaceId,
      role: roleAtLaunchRef.current,
      onEvent: (ev) => {
        setEvents((prev) => [...prev, ev]);
      },
    });
    setRunId(result.runId);
    setStatus(result.status);
  }, [kind, objective, requiresP10, targetId, targetName, workspaceId]);

  useEffect(() => {
    void launchStream();
  }, [launchStream, runNonce]);

  const handleP10Decision = async (decision: "approve" | "deny") => {
    if (!canApprove || !runId || status !== "awaiting_p10_approval") return;
    setResolvingP10(true);
    try {
      const outcome = await postExecutionP10Decision({
        runId,
        decision,
        workspaceId,
        role: activeRbacRole,
      });
      setEvents((prev) => {
        const seen = new Set(prev.map((p) => p.seq));
        return [...prev, ...outcome.events.filter((e) => !seen.has(e.seq))];
      });
      setStatus(outcome.status);
    } finally {
      setResolvingP10(false);
    }
  };

  const badgeKind =
    status === "awaiting_p10_approval"
      ? "needs-approval"
      : status === "completed"
        ? "passed"
        : status === "aborted"
          ? "failed"
          : "running";

  const badgeLabel =
    status === "awaiting_p10_approval"
      ? "Held · P-10 Human Gate"
      : status === "completed"
        ? "Completed · Receipt Signed"
        : status === "aborted"
          ? "Aborted by Operator"
          : "Streaming SSE";

  return (
    <section
      aria-label="Live streaming execution console"
      className="space-y-3 rounded-md border border-teal-accent/50 bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2.5">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">
              {`Live SSE Execution Stream · ${targetName}`}
            </h2>
            <SemanticBadge kind={badgeKind} labelOverride={badgeLabel} />
            {runId ? <code className="font-mono text-[11px] text-fg-muted">{runId}</code> : null}
          </div>
          <p className="text-xs text-fg-muted">
            {`Workspace: ${workspaceId} · Active RBAC: ${activeRbacRole} · Objective: ${objective}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => { void launchStream(); }}>
            Re-run SSE Stream
          </Button>
          {onClose ? (
            <Button size="sm" variant="ghost" onClick={onClose}>
              Close Stream
            </Button>
          ) : null}
        </div>
      </div>

      <div
        role="log"
        aria-live="polite"
        aria-label="Live execution SSE event log"
        className="rounded-sm border border-border bg-canvas p-3 font-mono text-xs"
      >
        <ol className="space-y-1.5">
          {events.map((ev, idx) => {
            const isP10Held = ev.type === "p10.held";
            const isApprovedOrDone = ev.type === "p10.approved" || ev.type === "run.completed";
            const isAborted = ev.type === "p10.denied" || ev.type === "run.aborted";
            const rowTone = isP10Held
              ? "border-ochre/45 bg-ochre-subtle text-fg"
              : isApprovedOrDone
                ? "border-ok/40 bg-ok-subtle text-fg"
                : isAborted
                  ? "border-danger/45 bg-danger-subtle text-fg"
                  : "border-border bg-chrome text-fg";
            return (
              <li key={`${ev.runId}-${ev.seq}-${idx}`} className={`rounded-xs border px-2.5 py-1.5 ${rowTone}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold">
                    <span className={isP10Held ? "text-ochre" : isApprovedOrDone ? "text-ok" : isAborted ? "text-danger" : "text-teal-accent"}>
                      {formatEventTag(ev)}
                    </span>{" "}
                    <span>{ev.label}</span>
                  </span>
                  <span className="text-[10px] text-fg-muted">{ev.timestamp}</span>
                </div>
                <div className="mt-0.5 font-sans text-[11px] text-fg-muted">{ev.detail}</div>
              </li>
            );
          })}
        </ol>
      </div>

      {status === "awaiting_p10_approval" ? (
        <div className="space-y-2 rounded-sm border border-ochre/45 bg-ochre-subtle p-3">
          <div className="text-xs font-semibold text-fg">
            P-10 Human-Only Checkpoint Active — Explicit pointer/touch confirmation required to mutate workspace or resume DAG.
          </div>
          {!canApprove ? (
            <div role="status" className="font-mono text-[11px] text-fg-muted">
              {rbacTooltip}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="warning-cta"
              clickOnly
              loading={resolvingP10}
              disabled={!canApprove}
              title={rbacTooltip ?? "Explicit human P-10 approval"}
              onClick={() => { void handleP10Decision("approve"); }}
            >
              Approve P-10 &amp; Resume Stream
            </Button>
            <Button
              size="sm"
              variant="danger"
              clickOnly
              disabled={!canApprove || resolvingP10}
              title={rbacTooltip ?? "Explicit human P-10 denial"}
              onClick={() => { void handleP10Decision("deny"); }}
            >
              Deny &amp; Abort Run
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
