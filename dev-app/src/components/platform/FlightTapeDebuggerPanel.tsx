import React, { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  buildSampleOtelTracePayload, canRbacMutateDevx, fetchEvalDatasetCases, fetchFlightTapes,
  ingestOtelTrace, promoteTraceToEval, replayFlightTape,
  type EvalDatasetCaseRecord, type FlightTapeRecord, type ReplayFlightTapeResponse, type WorkspaceRbacRole,
} from "@/lib/platformDevxApi";

export interface FlightTapeDebuggerPanelProps {
  workspaceId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

const DEFAULT_OVERRIDE_PROMPT = "Synthesize concise root-cause resolution strictly from cached tool evidence.";

export function FlightTapeDebuggerPanel({
  workspaceId = "default", activeRbacRole = "owner",
}: FlightTapeDebuggerPanelProps): React.JSX.Element {
  const canMutate = canRbacMutateDevx(activeRbacRole);
  const [tapes, setTapes] = useState<FlightTapeRecord[]>([]);
  const [listSource, setListSource] = useState<"live" | "local_fallback">("local_fallback");
  const [selectedTraceId, setSelectedTraceId] = useState<string>("");
  const [evalCases, setEvalCases] = useState<EvalDatasetCaseRecord[]>([]);
  const [forkStepIndex, setForkStepIndex] = useState<number>(1);
  const [overrideModel, setOverrideModel] = useState<string>("keelway-core:7b");
  const [overridePrompt, setOverridePrompt] = useState<string>(DEFAULT_OVERRIDE_PROMPT);
  const [busyAction, setBusyAction] = useState<"ingest" | "replay" | "promote" | null>(null);
  const [replayReceipt, setReplayReceipt] = useState<ReplayFlightTapeResponse | null>(null);
  const [promotedCase, setPromotedCase] = useState<EvalDatasetCaseRecord | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const inflightIngestRef = useRef<Promise<FlightTapeRecord> | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchFlightTapes(workspaceId, activeRbacRole)
      .then((res) => {
        if (cancelled) return;
        setListSource(res.source);
        setTapes(res.tapes);
        setSelectedTraceId((prev) => res.tapes.some((t) => t.trace_id === prev) ? prev : (res.tapes[0]?.trace_id ?? ""));
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorBanner(err instanceof Error ? err.message : "Failed to load flight-tapes.");
      });
    void fetchEvalDatasetCases(workspaceId, activeRbacRole)
      .then((res) => { if (!cancelled) setEvalCases(res.cases); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const activeTape = useMemo(
    () => tapes.find((t) => t.trace_id === selectedTraceId) ?? tapes[0] ?? null,
    [tapes, selectedTraceId],
  );
  const totalDlpRedactions = useMemo(() => tapes.reduce((acc, t) => acc + t.dlp_redactions, 0), [tapes]);
  const stepOptions = useMemo(() => {
    const count = Math.max(3, activeTape?.steps.length ?? 3);
    return Array.from({ length: count }, (_, idx) => {
      const st = activeTape?.steps[idx];
      return { index: idx, label: st ? `Step ${idx} · ${st.node_name} (${st.model_id})` : `Step ${idx}` };
    });
  }, [activeTape]);

  const runIngestSample = async (): Promise<FlightTapeRecord> => {
    const created = await ingestOtelTrace(buildSampleOtelTracePayload(workspaceId), activeRbacRole);
    setTapes((prev) => [created, ...prev.filter((t) => t.trace_id !== created.trace_id)]);
    setSelectedTraceId(created.trace_id);
    return created;
  };

  const handleIngestTrace = async () => {
    if (!canMutate || busyAction) return;
    setBusyAction("ingest");
    setErrorBanner(null);
    const p = runIngestSample();
    inflightIngestRef.current = p;
    try {
      await p;
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to ingest OTel GenAI trace.");
    } finally {
      inflightIngestRef.current = null;
      setBusyAction(null);
    }
  };

  const handleReplayFork = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canMutate || busyAction) return;
    setBusyAction("replay");
    setErrorBanner(null);
    try {
      const target = inflightIngestRef.current ? await inflightIngestRef.current : (activeTape ?? await runIngestSample());
      const res = await replayFlightTape(
        workspaceId, target.trace_id,
        { from_step_index: forkStepIndex, override_model: overrideModel, override_prompt: overridePrompt },
        activeRbacRole,
      );
      setTapes((prev) => [res.tape, ...prev.filter((t) => t.trace_id !== res.tape.trace_id)]);
      setSelectedTraceId(res.tape.trace_id);
      setReplayReceipt(res);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to replay counterfactual fork.");
    } finally {
      setBusyAction(null);
    }
  };

  const handlePromoteEval = async () => {
    if (!canMutate || busyAction) return;
    setBusyAction("promote");
    setErrorBanner(null);
    try {
      const target = inflightIngestRef.current ? await inflightIngestRef.current : (activeTape ?? await runIngestSample());
      const createdCase = await promoteTraceToEval(workspaceId, target.trace_id, `Golden Eval · ${target.title}`, activeRbacRole);
      setPromotedCase(createdCase);
      setEvalCases((prev) => [createdCase, ...prev.filter((c) => c.case_id !== createdCase.case_id)]);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to promote trace to Golden Eval.");
    } finally {
      setBusyAction(null);
    }
  };

  const forkBadgeId = replayReceipt ? (replayReceipt.fork_trace_id.startsWith("fork-") ? replayReceipt.fork_trace_id : `fork-${replayReceipt.fork_trace_id}`) : "";
  const evalBadgeId = promotedCase ? (promotedCase.case_id.startsWith("evalcase-") ? promotedCase.case_id : `evalcase-${promotedCase.case_id}`) : "";

  return (
    <section aria-label="Flight-tape time-travel debugger and OTel trace evaluator" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-fg">Flight-Tape Time-Travel Debugger &amp; OTel GenAI Trace Wedge</h2>
          <p className="text-xs text-fg-muted">
            Ingest zero-cost OpenTelemetry GenAI traces into local SQLite WAL with automatic DLP secret scrubbing, fork counterfactual steps reusing cached upstream work at $0, and promote traces to Golden Evals.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <SemanticBadge kind="opencore" labelOverride="$0 Local SQLite WAL Traces" />
          <SemanticBadge kind={totalDlpRedactions > 0 ? "reconfirm" : "passed"} labelOverride={totalDlpRedactions > 0 ? `DLP Scrubbed · ${totalDlpRedactions}` : "DLP Verified Clean"} />
          <SemanticBadge kind="live" labelOverride={`${tapes.length} Tapes · ${evalCases.length} Eval Cases`} />
        </div>
      </div>

      {!canMutate ? (
        <div className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">
          {`Flight-Tape Read-Only Mode (${activeRbacRole}): Trace inspection is enabled; OTel ingest, counterfactual replay, and eval promotion are locked for viewer role.`}
        </div>
      ) : null}

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{errorBanner}</span>
        </div>
      ) : null}

      <div className="flex flex-wrap items-end justify-between gap-3 rounded-sm border border-border bg-chrome p-3">
        <div className="flex flex-wrap items-end gap-2.5">
          <Button size="sm" variant="primary" loading={busyAction === "ingest"} disabled={!canMutate} onClick={() => { void handleIngestTrace(); }}>
            Ingest OTel GenAI Trace
          </Button>
          {tapes.length > 0 ? (
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Active Flight-Tape</span>
              <select aria-label="Active flight-tape trace" value={activeTape?.trace_id ?? ""} onChange={(e) => setSelectedTraceId(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                {tapes.map((t) => (
                  <option key={t.trace_id} value={t.trace_id}>{`${t.trace_id} · ${t.title} ($${t.total_cost_usd.toFixed(4)})`}</option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {activeTape ? (
            <code title={activeTape.tape_sha256} className="max-w-[240px] truncate rounded-xs border border-border bg-canvas px-2 py-0.5 font-mono text-[11px] text-teal-accent">
              {activeTape.tape_sha256}
            </code>
          ) : null}
          <Button size="sm" variant="secondary" loading={busyAction === "promote"} disabled={!canMutate} onClick={() => { void handlePromoteEval(); }}>
            Promote Trace to Golden Eval
          </Button>
        </div>
      </div>

      {tapes.length === 0 && listSource === "live" ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-canvas px-3 py-2.5 text-xs text-fg-muted">
          <span>No Flight-Tape traces recorded in SQLite WAL for this workspace yet.</span>
          <Button size="sm" variant="secondary" disabled={!canMutate || busyAction === "ingest"} onClick={() => { void handleIngestTrace(); }}>
            Ingest Sample OTel Trace
          </Button>
        </div>
      ) : null}

      {replayReceipt || promotedCase ? (
        <div role="status" className="space-y-1.5 rounded-sm border border-ok/40 bg-ok-subtle px-3 py-2 font-mono text-xs text-fg">
          {replayReceipt ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{`Counterfactual Fork Ready: ${forkBadgeId} · cached_steps_reused: ${replayReceipt.cached_steps_reused} · cost_delta_usd: ${replayReceipt.cost_delta_usd >= 0 ? "+" : ""}${replayReceipt.cost_delta_usd.toFixed(4)}`}</span>
              <code className="max-w-[240px] truncate text-[11px] text-teal-accent">{replayReceipt.tape_sha256}</code>
            </div>
          ) : null}
          {promotedCase ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{`Promoted Golden Eval Case: ${evalBadgeId} · source: ${promotedCase.trace_id} (${promotedCase.step_count} steps)`}</span>
              <code className="max-w-[240px] truncate text-[11px] text-teal-accent">{promotedCase.case_sha256}</code>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2.5">
          <h3 className="text-xs font-semibold text-fg">{`Step Timeline (${activeTape?.steps.length ?? 0} spans)`}</h3>
          <ol aria-label="Flight-tape execution steps" className="space-y-2 text-xs">
            {(activeTape?.steps ?? []).map((st) => (
              <li key={`${activeTape?.trace_id}-${st.step_index}`} className="space-y-1 rounded-sm border border-border bg-chrome p-2.5">
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <div className="flex flex-wrap items-center gap-1.5 font-mono">
                    <span className="rounded-xs border border-border bg-canvas px-1.5 py-0.5 text-[10px] text-fg">{`#${st.step_index}`}</span>
                    <span className="font-semibold text-fg">{st.node_name}</span>
                    <span className="text-[11px] text-teal-accent">{`${st.span_kind} · ${st.model_id}`}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                    {st.cached_reuse ? <SemanticBadge kind="passed" labelOverride="Cached Upstream · $0" /> : <span className="text-fg-muted">{`$${st.cost_usd.toFixed(4)}`}</span>}
                    {st.dlp_redacted ? <SemanticBadge kind="reconfirm" labelOverride="DLP Scrubbed" /> : null}
                  </div>
                </div>
                <p className="truncate font-mono text-[11px] text-fg-muted">{st.prompt}</p>
                <div className="flex items-center justify-between gap-2 font-mono text-[10px] text-fg-muted">
                  <span>{`${st.duration_ms}ms · ${st.input_tokens + st.output_tokens} tok`}</span>
                  <code title={st.step_sha256} className="max-w-[240px] truncate text-teal-accent">{st.step_sha256}</code>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="space-y-3">
          <form onSubmit={(e) => { void handleReplayFork(e); }} className="space-y-2.5 rounded-sm border border-border bg-chrome p-3">
            <h3 className="text-xs font-semibold text-fg">Counterfactual Time-Travel Fork</h3>
            <div className="grid gap-2.5 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs text-fg-muted">
                <span>Fork from step index</span>
                <select aria-label="Counterfactual fork step index" value={forkStepIndex} onChange={(e) => setForkStepIndex(Number(e.target.value))} disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                  {stepOptions.map((opt) => <option key={opt.index} value={opt.index}>{opt.label}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-fg-muted">
                <span>Override model</span>
                <input type="text" aria-label="Counterfactual override model" value={overrideModel} onChange={(e) => setOverrideModel(e.target.value)} disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Counterfactual prompt override</span>
              <input type="text" aria-label="Counterfactual prompt override" value={overridePrompt} onChange={(e) => setOverridePrompt(e.target.value)} disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <div className="flex items-center justify-between gap-2 pt-0.5">
              <span className="font-mono text-[11px] text-fg-muted">Upstream steps &lt; fork index reuse cached outputs at $0</span>
              <Button type="submit" size="sm" variant="primary" loading={busyAction === "replay"} disabled={!canMutate}>Replay Counterfactual Fork</Button>
            </div>
          </form>

          {evalCases.length > 0 ? (
            <div className="space-y-1.5 rounded-sm border border-border bg-chrome p-3">
              <h3 className="text-xs font-semibold text-fg">{`Promoted Golden Eval Dataset (${evalCases.length})`}</h3>
              <ul aria-label="Promoted golden eval dataset cases" className="space-y-1 font-mono text-[11px]">
                {evalCases.slice(0, 4).map((c) => (
                  <li key={c.case_id} className="flex items-center justify-between gap-2 rounded-xs border border-border bg-canvas px-2 py-1 text-fg">
                    <span className="truncate">{`${c.case_id} · ${c.title}`}</span>
                    <code title={c.case_sha256} className="max-w-[240px] truncate text-[10px] text-teal-accent">{c.case_sha256}</code>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
