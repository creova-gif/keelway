import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateDebugger, deleteDebuggerBreakpoint, getDebuggerCodeLens,
  listDebuggerBreakpoints, listDebuggerSessions, PlatformDebuggerHttpError,
  setDebuggerBreakpoint, startDebuggerSession, stepDebuggerSession,
  type DebuggerBreakpoint, type DebuggerCodeLensItem, type DebuggerConditionType,
  type DebuggerSession, type DebuggerSessionStatus, type DebuggerStepAction, type WorkspaceRbacRole,
} from "@/lib/platformDebuggerApi";

export interface StepDebuggerAndBridgePanelProps {
  workspaceId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

const CONDITION_OPTIONS: ReadonlyArray<DebuggerConditionType> = [
  "cost_usd_gt", "hybrid_score_lt", "before_shell_tool", "before_p10_gate", "always", "line_match",
];

function formatConditionOptionLabel(cond: DebuggerConditionType): string {
  switch (cond) {
    case "cost_usd_gt": return "cost_usd_gt — Step spend exceeds USD threshold";
    case "hybrid_score_lt": return "hybrid_score_lt — Hybrid confidence below threshold";
    case "before_shell_tool": return "before_shell_tool — Before Seatbelt shell_exec call";
    case "before_p10_gate": return "before_p10_gate — Before P-10 human approval gate";
    case "always": return "always — Unconditional step boundary";
    case "line_match": return "line_match — AST source line / node match";
    default: { const _exhaustive: never = cond; return _exhaustive; }
  }
}

function formatActionSummary(action: DebuggerStepAction): string {
  switch (action) {
    case "step_over": return "Step Over (F10)";
    case "step_into": return "Step Into (F11)";
    case "continue": return "Continue (F5)";
    case "mutate_state": return "Apply State Patch";
    default: { const _exhaustive: never = action; return _exhaustive; }
  }
}

function resolveSessionBadge(status: DebuggerSessionStatus): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "PAUSED": return { kind: "needs-approval", labelOverride: "PAUSED" };
    case "COMPLETED": return { kind: "passed", labelOverride: "COMPLETED" };
    case "READY": return { kind: "ready", labelOverride: "READY" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

export function StepDebuggerAndBridgePanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: StepDebuggerAndBridgePanelProps): React.JSX.Element {
  const canMutate = canRbacMutateDebugger(activeRbacRole);
  const [breakpoints, setBreakpoints] = useState<DebuggerBreakpoint[]>([]);
  const [session, setSession] = useState<DebuggerSession | null>(null);
  const [lenses, setLenses] = useState<DebuggerCodeLensItem[]>([]);
  const [cursorAttachUri, setCursorAttachUri] = useState<string>(
    `cursor://keelway.vscode-keelway/attach?workspace=${encodeURIComponent(workspaceId)}&port=7420`,
  );
  const [vscodeAttachUri, setVscodeAttachUri] = useState<string>(
    `vscode://keelway.vscode-keelway/attach?workspace=${encodeURIComponent(workspaceId)}&port=7420`,
  );
  const [conditionType, setConditionType] = useState<DebuggerConditionType>("cost_usd_gt");
  const [thresholdInput, setThresholdInput] = useState<string>("0.25");
  const [varKey, setVarKey] = useState<string>("override_route");
  const [varValue, setVarValue] = useState<string>("keelway-core:7b");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorAlert, setErrorAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listDebuggerBreakpoints(workspaceId, activeRbacRole).then((bps) => { if (!cancelled) setBreakpoints(bps); }).catch(() => {});
    void listDebuggerSessions(workspaceId, activeRbacRole).then((s) => { if (!cancelled && s.length > 0) setSession(s[0] ?? null); }).catch(() => {});
    void getDebuggerCodeLens(workspaceId, activeRbacRole).then((res) => {
      if (cancelled) return;
      setLenses(res.lenses ?? []);
      if (res.cursor_attach_uri) setCursorAttachUri(res.cursor_attach_uri);
      if (res.vscode_attach_uri) setVscodeAttachUri(res.vscode_attach_uri);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const formatErrorMessage = (err: unknown, fallback: string): string =>
    err instanceof PlatformDebuggerHttpError
      ? `HTTP ${err.status} · ${err.message}`
      : err instanceof Error ? err.message : fallback;

  const handleAddBreakpoint = async () => {
    setBusyAction("add_bp");
    setErrorAlert(null);
    try {
      const parsed = Number.parseFloat(thresholdInput);
      const created = await setDebuggerBreakpoint(
        { workspace_id: workspaceId, condition_type: conditionType, threshold: Number.isFinite(parsed) ? parsed : 0.25 },
        activeRbacRole,
      );
      setBreakpoints((prev) => [...prev.filter((b) => b.breakpoint_id !== created.breakpoint_id), created]);
    } catch (err) {
      setErrorAlert(formatErrorMessage(err, "Failed to add conditional breakpoint."));
    } finally {
      setBusyAction(null);
    }
  };

  const handleRemoveBreakpoint = async (bp: DebuggerBreakpoint) => {
    setBusyAction(`del_${bp.breakpoint_id}`);
    setErrorAlert(null);
    try {
      await deleteDebuggerBreakpoint(bp.breakpoint_id, workspaceId, activeRbacRole);
      setBreakpoints((prev) => prev.filter((item) => item.breakpoint_id !== bp.breakpoint_id));
    } catch (err) {
      setErrorAlert(formatErrorMessage(err, "Failed to remove breakpoint."));
    } finally {
      setBusyAction(null);
    }
  };

  const handleStartSession = async () => {
    setBusyAction("start");
    setErrorAlert(null);
    try {
      const started = await startDebuggerSession({ workspace_id: workspaceId }, activeRbacRole);
      setSession(started);
    } catch (err) {
      setErrorAlert(formatErrorMessage(err, "Failed to start debug session."));
    } finally {
      setBusyAction(null);
    }
  };

  const handleStepAction = async (action: DebuggerStepAction, statePatch?: Record<string, unknown>) => {
    setBusyAction(action);
    setErrorAlert(null);
    try {
      const targetId = session?.session_id ?? `dbg-pending-${workspaceId}`;
      const updated = await stepDebuggerSession(targetId, { workspace_id: workspaceId, action, state_patch: statePatch }, activeRbacRole);
      setSession(updated);
    } catch (err) {
      setErrorAlert(formatErrorMessage(err, `Failed to execute ${formatActionSummary(action)}.`));
    } finally {
      setBusyAction(null);
    }
  };

  const handleApplyPatch = async () => {
    await handleStepAction("mutate_state", { [varKey.trim() || "override_route"]: varValue });
  };

  const handleTestSecretDlp = async () => {
    const sampleSecret = "sk-live-secret999999999";
    setVarValue(sampleSecret);
    await handleStepAction("mutate_state", { [varKey.trim() || "override_route"]: sampleSecret });
  };

  const sessionStatus: DebuggerSessionStatus = session?.status ?? "READY";
  const badgeSpec = resolveSessionBadge(sessionStatus);
  const isPaused = sessionStatus === "PAUSED";
  const activeFrame = session?.active_frame ?? null;
  const callStack = session?.call_stack ?? [];
  const activeSessionQuery = session?.session_id ? `&session=${encodeURIComponent(session.session_id)}` : "";
  const effectiveCursorUri = `${cursorAttachUri}${activeSessionQuery}`;
  const effectiveVscodeUri = `${vscodeAttachUri}${activeSessionQuery}`;

  return (
    <section
      id="step-debugger-bridge-panel"
      aria-label="Live Step-Through Debugger and VS Code Cursor Bridge"
      className="space-y-4 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Live Step-Through Debugger &amp; VS Code / Cursor Bridge</h2>
            <SemanticBadge kind={badgeSpec.kind} labelOverride={badgeSpec.labelOverride} />
            {!canMutate ? (
              <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                {`RBAC: ${activeRbacRole} (read-only)`}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-fg-muted">
            Conditional gutter breakpoints, F10/F11/F5 frame stepping, DLP-guarded state mutation, and 4D CodeLens IDE attach.
          </p>
        </div>

        <div className="flex items-center gap-1.5 rounded-xs border border-teal-accent/45 bg-teal-surface px-2 py-1 font-mono text-[11px]">
          <span className="text-fg-muted">frame_sha256:</span>
          <code
            data-testid="debugger-frame-sha256"
            title={session?.frame_sha256 ?? "awaiting-session"}
            className="max-w-[220px] truncate font-semibold text-teal-accent"
          >
            {session?.frame_sha256 ?? "awaiting-session"}
          </code>
        </div>
      </div>

      {errorAlert ? (
        <div role="alert" className="rounded-xs border border-danger/55 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{errorAlert}</span>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
          <h3 className="text-xs font-semibold text-fg">Conditional Gutter Breakpoints &amp; Execution Controls</h3>

          <div className="grid gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-fg-muted sm:col-span-2">
              <span>Condition type</span>
              <select
                aria-label="Breakpoint condition type"
                value={conditionType}
                onChange={(e) => setConditionType(e.target.value as DebuggerConditionType)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              >
                {CONDITION_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{formatConditionOptionLabel(opt)}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Threshold</span>
              <input
                type="number"
                step="0.05"
                aria-label="Breakpoint threshold"
                value={thresholdInput}
                onChange={(e) => setThresholdInput(e.target.value)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono text-[11px] text-fg-muted">{`Active Breakpoints (${breakpoints.length})`}</span>
            <Button type="button" size="sm" variant="secondary" loading={busyAction === "add_bp"} onClick={() => { void handleAddBreakpoint(); }}>
              Add Conditional Breakpoint
            </Button>
          </div>

          <ul aria-label="Active conditional breakpoints" className="space-y-1.5 text-xs">
            {breakpoints.map((bp) => (
              <li key={bp.breakpoint_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-border bg-canvas px-2.5 py-1.5 font-mono text-[11px]">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-danger" aria-hidden="true">●</span>
                  <span className="font-semibold text-fg">{bp.condition_type}</span>
                  <span className="text-fg-muted">{bp.label}</span>
                </div>
                <Button type="button" size="sm" variant="ghost" aria-label={`Remove breakpoint ${bp.label}`} onClick={() => { void handleRemoveBreakpoint(bp); }}>
                  ×
                </Button>
              </li>
            ))}
          </ul>

          <div role="toolbar" aria-label="Step debugger execution controls" className="flex flex-wrap items-center gap-2 border-t border-border pt-2.5">
            <Button type="button" size="sm" variant="primary" loading={busyAction === "start"} onClick={() => { void handleStartSession(); }}>
              Start Debug Session
            </Button>
            <Button type="button" size="sm" variant="secondary" disabled={!isPaused || busyAction !== null} onClick={() => { void handleStepAction("step_over"); }}>
              Step Over (F10)
            </Button>
            <Button type="button" size="sm" variant="secondary" disabled={!isPaused || busyAction !== null} onClick={() => { void handleStepAction("step_into"); }}>
              Step Into (F11)
            </Button>
            <Button type="button" size="sm" variant="secondary" disabled={!isPaused || busyAction !== null} onClick={() => { void handleStepAction("continue"); }}>
              Continue (F5)
            </Button>
          </div>

          <div className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            {session && activeFrame ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-fg">{`Step ${session.current_step_index + 1}/${session.total_steps} · Depth ${session.step_depth}`}</span>
                  <span className="text-teal-accent">{`${activeFrame.node_id} · ${activeFrame.tool_name} · ${activeFrame.agent_id} ($${activeFrame.cost_usd.toFixed(2)})`}</span>
                </div>
                <div className="text-fg-muted">{`Hit Reason: ${session.hit_reason ?? "Execution completed cleanly"}`}</div>
                <ol aria-label="Debugger call stack" className="space-y-1 border-t border-border pt-1.5">
                  {callStack.map((entry) => (
                    <li key={`${entry.frame_index}-${entry.depth}-${entry.node_id}`} className="flex items-center justify-between gap-2 text-[10px] text-fg">
                      <span>{`[depth ${entry.depth}] ${entry.node_id} (${entry.tool_name})`}</span>
                      <span className="text-fg-muted">{entry.agent_id}</span>
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <div className="text-fg-muted">Click Start Debug Session to launch workflow trace and pause on matching gutter breakpoints.</div>
            )}
          </div>
        </div>

        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold text-fg">In-Place Variable Mutator (DLP-Guarded)</h3>
            <span className="rounded-xs border border-border-strong bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-teal-accent">
              {`Mutations: ${session?.mutation_count ?? 0}`}
            </span>
          </div>

          <pre className="max-h-28 overflow-auto rounded-xs border border-border bg-code p-2 font-mono text-[11px] text-fg">
            <code>{JSON.stringify(session?.variables ?? { route_mode: "hybrid_4d", claim_amount_usd: 1420 }, null, 2)}</code>
          </pre>

          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Variable key</span>
              <input type="text" aria-label="State variable key" value={varKey} onChange={(e) => setVarKey(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Variable value</span>
              <input type="text" aria-label="State variable value" value={varValue} onChange={(e) => setVarValue(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="primary" loading={busyAction === "mutate_state"} onClick={() => { void handleApplyPatch(); }}>
              Apply State Patch
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={() => { void handleTestSecretDlp(); }}>
              Test Secret DLP Block
            </Button>
          </div>

          <div className="space-y-2 border-t border-border pt-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-semibold text-fg">4D Routing CodeLens &amp; IDE Bridge</h3>
              <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
                <a href={effectiveCursorUri} className="rounded-xs border border-teal-accent/50 bg-teal-surface px-2 py-0.5 font-semibold text-teal-accent hover:underline">
                  Attach in Cursor
                </a>
                <a href={effectiveVscodeUri} className="rounded-xs border border-border-strong bg-canvas px-2 py-0.5 font-semibold text-fg hover:underline">
                  Attach in VS Code
                </a>
              </div>
            </div>

            <ul aria-label="4D routing CodeLens items" className="space-y-1.5">
              {lenses.map((lens) => (
                <li key={`${lens.file_path}:${lens.symbol}`} className="rounded-xs border border-border bg-canvas px-2.5 py-1.5 font-mono text-[11px]">
                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                    <span className="font-semibold text-fg">{lens.symbol}</span>
                    <span className="text-teal-accent">{`${lens.model_checkpoint} · P50 ${lens.p50_latency_ms}ms · $${lens.avg_cost_usd.toFixed(2)}`}</span>
                  </div>
                  <div className="mt-0.5 truncate text-[10px] text-fg-muted">{lens.provenance_4d}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
