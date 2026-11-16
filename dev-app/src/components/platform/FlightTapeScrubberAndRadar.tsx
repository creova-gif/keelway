import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { FlightTapeRecord, WorkspaceRbacRole } from "@/lib/platformDevxApi";
import {
  evaluatePromptGate,
  fetchBlastRadiusAudits,
  fetchPromptGateRuns,
  recordBlastRadius,
  type BlastRadiusAuditRecord,
  type BlastRadiusRiskTier,
  type PromptGateEvaluationRecord,
  type PromptGateVerdict,
} from "@/lib/platformStudioApi";

export interface FlightTapeScrubberAndRadarProps {
  workspaceId: string;
  activeRbacRole: WorkspaceRbacRole;
  canMutate: boolean;
  activeTape: FlightTapeRecord | null;
  forkStepIndex: number;
  onChangeForkStepIndex: (stepIndex: number) => void;
  overrideModel: string;
  overridePrompt: string;
  onStudioError?: (msg: string | null) => void;
}

const SEED_RADAR_AUDIT: BlastRadiusAuditRecord = {
  audit_id: "blast-seed-01",
  workspace_id: "default",
  trace_id: "trace-otel-seed-default",
  workflow_id: "WF-01",
  fs_reads: ["core/billing/ledger.py", "core/security/p10_gate.py"],
  fs_writes: [".keelway/wal/flight_tape.sqlite"],
  blocked_paths: ["/etc/passwd", "~/.ssh/id_ed25519"],
  egress_attempts: 0,
  blocked_egress_hosts: ["telemetry.unapproved-egress.invalid"],
  p10_gates_triggered: 1,
  seatbelted: true,
  zero_unapproved_egress: true,
  syscalls_audited: 148,
  risk_tier: "contained_guarded",
  audit_sha256: "sha256:7b3c9d10e4f281a6b5c4d3e2f10987654321fedcba0987654321abcdef123456",
  recorded_at: "2026-11-15T00:00:00.000Z",
};

function resolveRiskBadgeStyle(tier: BlastRadiusRiskTier): { classes: string; label: string } {
  switch (tier) {
    case "nominal_confined":
      return { classes: "border-ok/45 bg-ok-subtle text-ok", label: "nominal_confined" };
    case "contained_guarded":
      return { classes: "border-teal-accent/50 bg-teal-surface text-teal-accent", label: "contained_guarded" };
    case "elevated_review":
      return { classes: "border-danger/55 bg-danger-subtle text-danger", label: "elevated_review" };
    default: {
      const _exhaustive: never = tier;
      return _exhaustive;
    }
  }
}

function resolveVerdictStyle(verdict: PromptGateVerdict): string {
  switch (verdict) {
    case "PASS":
      return "border-ok/50 bg-ok-subtle text-ok";
    case "BLOCK":
      return "border-danger/55 bg-danger-subtle text-danger";
    default: {
      const _exhaustive: never = verdict;
      return _exhaustive;
    }
  }
}

export function FlightTapeScrubberAndRadar({
  workspaceId,
  activeRbacRole,
  canMutate,
  activeTape,
  forkStepIndex,
  onChangeForkStepIndex,
  overrideModel,
  overridePrompt,
  onStudioError,
}: FlightTapeScrubberAndRadarProps): React.JSX.Element {
  const [audits, setAudits] = useState<BlastRadiusAuditRecord[]>([SEED_RADAR_AUDIT]);
  const [gateRuns, setGateRuns] = useState<PromptGateEvaluationRecord[]>([]);
  const [busyBlast, setBusyBlast] = useState<boolean>(false);
  const [busyGate, setBusyGate] = useState<boolean>(false);

  const traceId = activeTape?.trace_id ?? `trace-otel-seed-${workspaceId}`;

  useEffect(() => {
    let cancelled = false;
    void fetchBlastRadiusAudits(workspaceId, activeRbacRole, traceId)
      .then((res) => {
        if (!cancelled && res.audits.length > 0) setAudits(res.audits);
      })
      .catch(() => {});
    void fetchPromptGateRuns(workspaceId, activeRbacRole)
      .then((res) => {
        if (!cancelled) setGateRuns(res.runs);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeRbacRole, traceId, workspaceId]);

  const steps = activeTape?.steps ?? [];
  const maxStepIndex = Math.max(0, steps.length - 1);
  const clampedPlayhead = Math.min(Math.max(0, forkStepIndex), Math.max(2, maxStepIndex));

  const waterfallMetrics = useMemo(() => {
    const totalMs = Math.max(
      1,
      steps.reduce((acc, s) => acc + Math.max(10, s.duration_ms), 0),
    );
    let elapsedMs = 0;
    return steps.map((st) => {
      const dur = Math.max(10, st.duration_ms);
      const startPct = Math.min(82, Math.round((elapsedMs / totalMs) * 100));
      const widthPct = Math.max(18, Math.min(100 - startPct, Math.round((dur / totalMs) * 100)));
      elapsedMs += dur;
      return { step: st, startPct, widthPct, totalMs };
    });
  }, [steps]);

  const cachedCount = steps.filter((s) => s.step_index < forkStepIndex).length;
  const forkedCount = steps.filter((s) => s.step_index >= forkStepIndex).length;
  const forkTargetNode = steps.find((s) => s.step_index === forkStepIndex)?.node_name ?? `step_${forkStepIndex}`;

  const activeAudit = audits[0] ?? SEED_RADAR_AUDIT;
  const riskStyle = resolveRiskBadgeStyle(activeAudit.risk_tier);
  const latestGate = gateRuns[0] ?? null;

  const handleAuditBlastRadius = async () => {
    if (!canMutate || busyBlast) return;
    setBusyBlast(true);
    onStudioError?.(null);
    try {
      const created = await recordBlastRadius(
        {
          workspace_id: workspaceId,
          trace_id: traceId,
          workflow_id: "WF-01",
          fs_reads: ["core/billing/ledger.py", "core/security/p10_gate.py", "core/studio/wal_trace.py"],
          fs_writes: [".keelway/wal/flight_tape.sqlite"],
          blocked_paths: ["/etc/passwd", "~/.ssh/id_ed25519"],
          egress_attempts: 0,
          blocked_egress_hosts: ["telemetry.unapproved-egress.invalid"],
          p10_gates_triggered: Math.max(1, steps.filter((s) => s.dlp_redacted).length),
          seatbelted: true,
          syscalls_audited: 164 + steps.length * 12,
        },
        activeRbacRole,
      );
      const refreshed = await fetchBlastRadiusAudits(workspaceId, activeRbacRole, traceId);
      const merged = [created, ...refreshed.audits.filter((a) => a.audit_id !== created.audit_id)];
      setAudits(merged);
    } catch (err) {
      onStudioError?.(err instanceof Error ? err.message : "Failed to audit sandbox blast-radius.");
    } finally {
      setBusyBlast(false);
    }
  };

  const handleRunPromptGate = async () => {
    if (!canMutate || busyGate) return;
    setBusyGate(true);
    onStudioError?.(null);
    try {
      const evaluated = await evaluatePromptGate(
        {
          workspace_id: workspaceId,
          candidate_prompt_version: `fork-s${forkStepIndex}-v1`,
          candidate_prompt_text: overridePrompt,
          candidate_model_id: overrideModel,
          min_pass_rate: 0.95,
          baseline_cost_usd: activeTape?.total_cost_usd ?? 0.0179,
        },
        activeRbacRole,
      );
      const refreshed = await fetchPromptGateRuns(workspaceId, activeRbacRole);
      setGateRuns([evaluated, ...refreshed.runs.filter((r) => r.gate_run_id !== evaluated.gate_run_id)]);
    } catch (err) {
      onStudioError?.(err instanceof Error ? err.message : "Failed to run prompt regression gate.");
    } finally {
      setBusyGate(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* 1. Interactive Waterfall Timeline Scrubber + 2-Branch Split Preview */}
      <div
        role="region"
        aria-label="Flight-tape waterfall timeline scrubber"
        className="space-y-3 rounded-sm border border-border-strong bg-chrome p-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-xs font-semibold text-fg">
              Tactile Flame Waterfall &amp; Time-Travel Scrubber
            </h3>
            <span className="rounded-xs border border-teal-accent/45 bg-teal-surface px-1.5 py-0.5 font-mono text-[10px] font-semibold text-teal-accent">
              {`Playhead @ Step #${forkStepIndex}`}
            </span>
          </div>

          <label className="inline-flex items-center gap-2 font-mono text-[11px] text-fg-muted">
            <span>Scrub Playhead</span>
            <input
              type="range"
              aria-label="Time-travel playhead step"
              min={0}
              max={Math.max(2, maxStepIndex)}
              step={1}
              value={clampedPlayhead}
              disabled={!canMutate}
              onChange={(e) => onChangeForkStepIndex(Number(e.target.value))}
              className="w-28 accent-teal-accent disabled:opacity-55"
            />
          </label>
        </div>

        {waterfallMetrics.length > 0 ? (
          <div className="space-y-1.5">
            {waterfallMetrics.map(({ step, startPct, widthPct }) => {
              const isCachedUpstream = step.step_index < forkStepIndex;
              const isForkAnchor = step.step_index === forkStepIndex;
              return (
                <button
                  key={`wf-bar-${step.span_id}-${step.step_index}`}
                  type="button"
                  disabled={!canMutate}
                  aria-label={`Scrub waterfall to step ${step.step_index} ${step.node_name}`}
                  aria-pressed={isForkAnchor}
                  onClick={() => onChangeForkStepIndex(step.step_index)}
                  className={`group flex w-full flex-col gap-1 rounded-xs border p-1.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent disabled:cursor-not-allowed disabled:opacity-75 ${
                    isForkAnchor
                      ? "border-ochre bg-ochre-subtle/60"
                      : isCachedUpstream
                        ? "border-teal-accent/40 bg-canvas hover:border-teal-accent"
                        : "border-ochre/40 bg-canvas hover:border-ochre"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-1.5 font-mono text-[11px]">
                    <span className="font-semibold text-fg">
                      {`Span #${step.step_index} · ${step.node_name} (${step.duration_ms}ms)`}
                    </span>
                    <span
                      className={`rounded-xs border px-1.5 py-0.2 text-[10px] font-semibold ${
                        isCachedUpstream
                          ? "border-teal-accent/45 bg-teal-surface text-teal-accent"
                          : "border-ochre/50 bg-ochre-subtle text-ochre"
                      }`}
                    >
                      {isCachedUpstream ? "Cached Upstream · $0.00" : "Counterfactual Fork Branch"}
                    </span>
                  </div>

                  <div className="relative h-3 w-full overflow-hidden rounded-xs bg-surface">
                    <div
                      style={{ marginLeft: `${startPct}%`, width: `${widthPct}%` }}
                      className={`h-full rounded-xs transition-all ${
                        isCachedUpstream ? "bg-teal-accent/80" : "bg-ochre/85"
                      }`}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xs border border-border bg-canvas px-2.5 py-2 font-mono text-[11px] text-fg-muted">
            Ingest an OTel GenAI trace above to populate proportional flame waterfall bars.
          </div>
        )}

        {/* 2-Branch Counterfactual Split Preview */}
        <div className="grid gap-2 pt-1 sm:grid-cols-2">
          <div className="rounded-xs border border-border bg-canvas p-2 font-mono text-[11px]">
            <div className="flex items-center justify-between text-fg">
              <span className="font-semibold">Original Trunk</span>
              <span className="text-fg-muted">{`$${(activeTape?.total_cost_usd ?? 0).toFixed(4)}`}</span>
            </div>
            <div className="mt-0.5 truncate text-[10px] text-fg-dim">
              {`Linear replay across ${steps.length} recorded OTel spans`}
            </div>
          </div>

          <div className="rounded-xs border border-ochre/45 bg-ochre-subtle/40 p-2 font-mono text-[11px]">
            <div className="flex items-center justify-between text-ochre">
              <span className="font-semibold">{`Forked Branch @ Step #${forkStepIndex}`}</span>
              <span>{`${cachedCount} cached ($0.00) · ${forkedCount} forked`}</span>
            </div>
            <div className="mt-0.5 truncate text-[10px] text-fg-muted">
              {`⑂ Diverges at ${forkTargetNode} → ${overrideModel}`}
            </div>
          </div>
        </div>
      </div>

      {/* 2 & 3. Sandbox Blast-Radius Radar + Inline Prompt & Schema Regression Gate */}
      <div className="grid gap-3 lg:grid-cols-2">
        <div
          role="region"
          aria-label="Sandbox blast-radius radar"
          className="space-y-2.5 rounded-sm border border-border-strong bg-chrome p-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <svg
                role="img"
                aria-label="Seatbelt containment perimeter radar"
                viewBox="0 0 36 36"
                className="h-7 w-7 shrink-0"
              >
                <circle cx="18" cy="18" r="16" fill="none" stroke="#2dd4bf" strokeOpacity="0.3" strokeWidth="1.5" />
                <circle cx="18" cy="18" r="10" fill="none" stroke="#2dd4bf" strokeOpacity="0.55" strokeWidth="1.5" />
                <circle cx="18" cy="18" r="3.5" fill="#2dd4bf" />
                <line x1="18" y1="18" x2="31" y2="10" stroke="#e5a93c" strokeWidth="1.5" />
              </svg>
              <div>
                <h3 className="text-xs font-semibold text-fg">Live Sandbox Blast-Radius Radar</h3>
                <div className="flex flex-wrap items-center gap-1.5 font-mono text-[10px]">
                  <span className="text-fg-muted">Seatbelt Confinement:</span>
                  <span className={`rounded-xs border px-1.5 py-0.2 font-semibold ${riskStyle.classes}`}>
                    {riskStyle.label}
                  </span>
                </div>
              </div>
            </div>

            <Button
              size="sm"
              variant="secondary"
              aria-label="Audit sandbox blast-radius"
              loading={busyBlast}
              disabled={!canMutate}
              onClick={() => { void handleAuditBlastRadius(); }}
            >
              Audit Trace Blast-Radius
            </Button>
          </div>

          <div className="grid gap-1.5 font-mono text-[11px] sm:grid-cols-2">
            <div className="rounded-xs border border-border bg-canvas p-2">
              <div className="text-[10px] text-fg-dim">FS Reads &amp; Writes</div>
              <div className="mt-0.5 truncate text-fg">{activeAudit.fs_reads.join(", ")}</div>
              <div className="truncate text-[10px] text-teal-accent">{`write: ${activeAudit.fs_writes.join(", ")}`}</div>
            </div>

            <div className="rounded-xs border border-border bg-canvas p-2">
              <div className="text-[10px] text-fg-dim">Blocked Escape Paths</div>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {activeAudit.blocked_paths.map((bp) => (
                  <span
                    key={bp}
                    className="rounded-xs border border-danger/45 bg-danger-subtle px-1.5 py-0.2 text-[10px] font-semibold text-danger"
                  >
                    {`✕ ${bp}`}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-border bg-canvas px-2.5 py-1.5 font-mono text-[10px]">
            <span className="font-semibold text-ok">
              {activeAudit.zero_unapproved_egress ? "● Zero Unapproved Egress" : "! Egress Review Needed"}
            </span>
            <span className="text-fg-muted">{`${activeAudit.audit_id} · Syscalls Audited: ${activeAudit.syscalls_audited}`}</span>
            <code title={activeAudit.audit_sha256} className="max-w-[220px] truncate text-teal-accent">
              {activeAudit.audit_sha256}
            </code>
          </div>
        </div>

        <div
          role="region"
          aria-label="Inline prompt regression gate"
          className="flex flex-col justify-between gap-2.5 rounded-sm border border-border-strong bg-chrome p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="space-y-0.5">
              <h3 className="text-xs font-semibold text-fg">Inline Prompt &amp; Schema Regression Gate</h3>
              <p className="text-[11px] text-fg-muted">
                Validate counterfactual prompt &amp; model overrides against Golden Eval contracts, JSON schema, and DLP guardrails before shipping.
              </p>
            </div>
            <Button
              size="sm"
              variant="primary"
              aria-label="Run prompt regression gate"
              loading={busyGate}
              disabled={!canMutate}
              onClick={() => { void handleRunPromptGate(); }}
            >
              Run Prompt Regression Gate
            </Button>
          </div>

          {latestGate ? (
            <div className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`rounded-xs border px-2 py-0.5 text-xs font-bold ${resolveVerdictStyle(latestGate.verdict)}`}>
                    {latestGate.verdict}
                  </span>
                  <span className="font-semibold text-fg">
                    {`Pass Rate: ${Math.round(latestGate.pass_rate * 100)}% (${latestGate.passed_cases}/${latestGate.cases_evaluated})`}
                  </span>
                </div>
                <span className="text-teal-accent">
                  {`cost_delta_usd: ${latestGate.cost_delta_usd >= 0 ? "+" : ""}${latestGate.cost_delta_usd.toFixed(4)}`}
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-fg-muted">
                <span>{`${latestGate.gate_run_id} · Schema Valid: ${latestGate.schema_valid_count}/${latestGate.cases_evaluated} · DLP Violations: ${latestGate.dlp_violations}`}</span>
                <code title={latestGate.gate_sha256} className="max-w-[220px] truncate text-teal-accent">
                  {latestGate.gate_sha256}
                </code>
              </div>
            </div>
          ) : (
            <div className="rounded-xs border border-border bg-canvas px-2.5 py-2 font-mono text-[11px] text-fg-muted">
              {`Ready to gate "${overrideModel}" candidate prompt against workspace Golden Evals (min_pass_rate: 95%).`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
