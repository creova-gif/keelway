import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import {
  canRbacRunCyclicKflow, DEFAULT_CYCLIC_NODES, executeCyclicKflow,
  listCyclicKflowRuns, listKflowAutopilotSimulations, PlatformCyclicHttpError,
  simulateKflowAutopilot, validateCyclicKflow,
  type AutopilotPrivacyPolicy, type AutopilotSimulationRecord, type CyclicKflowRunRecord,
  type CyclicLoopEdgeSpec, type CyclicNodeSpec, type CyclicRunStatus,
  type CyclicValidationResult, type WorkspaceRbacRole,
} from "@/lib/platformCyclicApi";

export interface CyclicKflowAndAutopilotPanelProps {
  workspaceId?: string;
  workflowId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

const PRIVACY_POLICIES: ReadonlyArray<AutopilotPrivacyPolicy> = ["hybrid_balanced", "airgap_strict", "eu_residency"];

function resolveCyclicStatusBadge(status: CyclicRunStatus | "IDLE"): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "CONVERGED": return { kind: "passed", labelOverride: "CONVERGED" };
    case "COMPENSATED": return { kind: "failed", labelOverride: "COMPENSATED" };
    case "HELD_P10": return { kind: "needs-approval", labelOverride: "HELD_P10" };
    case "IDLE": return { kind: "ready", labelOverride: "BOUNDED" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

function formatPrivacyPolicyOption(policy: AutopilotPrivacyPolicy): string {
  switch (policy) {
    case "hybrid_balanced": return "hybrid_balanced — Hybrid Frontier + P95 Budget Guard";
    case "airgap_strict": return "airgap_strict — Zero-Egress Local OpenCore Only";
    case "eu_residency": return "eu_residency — EU Sovereign Local Checkpoints";
    default: { const _exhaustive: never = policy; return _exhaustive; }
  }
}

function buildRewrittenNodes(sim: AutopilotSimulationRecord): CyclicNodeSpec[] {
  const planByNode = new Map(sim.node_plan.map((item) => [item.node_id, item]));
  return DEFAULT_CYCLIC_NODES.map((base) => {
    const planned = planByNode.get(base.id);
    if (!planned) return { ...base, depends_on: [...base.depends_on] };
    return {
      ...base, depends_on: [...base.depends_on], model: planned.selected_model,
      base_cost_usd: planned.p50_cost_usd, ttft_ms: planned.rewritten ? 135 : base.ttft_ms,
    };
  });
}

interface ReflectionColumnProps {
  maxIterationsInput: string; criticThresholdInput: string; shardsInput: string;
  busyAction: string | null; validation: CyclicValidationResult | null; activeRun: CyclicKflowRunRecord | null;
  onChangeMaxIterations: (val: string) => void; onChangeCriticThreshold: (val: string) => void;
  onChangeShards: (val: string) => void; onValidate: () => void; onExecuteLoop: (simulateTimeout: boolean) => void;
}

function CyclicReflectionColumn({
  maxIterationsInput, criticThresholdInput, shardsInput, busyAction, validation, activeRun,
  onChangeMaxIterations, onChangeCriticThreshold, onChangeShards, onValidate, onExecuteLoop,
}: ReflectionColumnProps): React.JSX.Element {
  return (
    <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
      <h3 className="text-xs font-semibold text-fg">Bounded Reflection Loops, Map-Reduce &amp; Saga Compensation</h3>

      <div className="grid gap-2 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Max loop iterations</span>
          <input type="number" aria-label="Max loop iterations" value={maxIterationsInput} onChange={(e) => onChangeMaxIterations(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Critic convergence threshold</span>
          <input type="number" step="0.05" aria-label="Critic convergence threshold" value={criticThresholdInput} onChange={(e) => onChangeCriticThreshold(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Map-reduce shards</span>
          <input type="number" aria-label="Map-reduce shards" value={shardsInput} onChange={(e) => onChangeShards(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" loading={busyAction === "validate"} onClick={onValidate}>
          Validate Cyclic Graph
        </Button>
        <Button type="button" size="sm" variant="primary" loading={busyAction === "execute"} onClick={() => onExecuteLoop(false)}>
          Execute Reflection Loop
        </Button>
        <Button type="button" size="sm" variant="warning-cta" loading={busyAction === "compensate"} onClick={() => onExecuteLoop(true)}>
          Trigger Saga Compensation
        </Button>
      </div>

      {validation ? (
        <div className="rounded-xs border border-border bg-canvas px-2.5 py-1.5 font-mono text-[11px] text-fg-muted">
          <span className="font-semibold text-teal-accent">Graph Verified:</span>{" "}
          {`${validation.topological_spine.join(" -> ")} · max steps ${validation.max_worst_case_steps} · handlers [${validation.compensation_handlers.join(", ")}]`}
        </div>
      ) : null}

      <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
        {activeRun ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg">
                {`Iterations: ${activeRun.iterations_executed}/${activeRun.max_iterations} · Final Critic: ${activeRun.final_critic_score.toFixed(2)} · Shards: ${activeRun.fan_out_shards}`}
              </span>
              <span className="text-teal-accent">
                {`map_reduce (${activeRun.fan_out_shards}sh) · $${activeRun.total_cost_usd.toFixed(3)} · ${activeRun.total_latency_ms}ms`}
              </span>
            </div>

            <ol aria-label="Cyclic reflection iteration trace" className="space-y-1 border-t border-border pt-1.5">
              {activeRun.iteration_trace.map((step, idx) => (
                <li key={`${step.iteration}-${step.node_id}-${idx}`} className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-fg">
                  <span>{`[iter ${step.iteration}] ${step.node_id} (${step.model ?? step.agent_id}) · ${step.shard_count}sh`}</span>
                  <span className="text-fg-muted">{`critic ${step.critic_score.toFixed(2)} · ${step.status}`}</span>
                </li>
              ))}
            </ol>

            {activeRun.compensation_log.length > 0 ? (
              <div className="space-y-1 border-t border-danger/40 pt-1.5">
                <div className="text-[10px] font-semibold text-danger">Saga Reverse-Order Compensation Rollback</div>
                <ul aria-label="Saga compensation rollback log" className="space-y-1">
                  {activeRun.compensation_log.map((comp, idx) => (
                    <li key={`${comp.node_id}-${comp.handler}-${idx}`} className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-danger/35 bg-danger-subtle px-2 py-1 text-[10px] text-fg">
                      <span className="font-semibold">{`${comp.node_id} -> ${comp.handler}`}</span>
                      <span className="text-danger">{`${comp.reason} · ${comp.status}`}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : (
          <div className="text-fg-muted">
            Validate bounded back-edges or click Execute Reflection Loop to trace critic convergence and map-reduce shards.
          </div>
        )}
      </div>
    </div>
  );
}

interface AutopilotColumnProps {
  privacyPolicy: AutopilotPrivacyPolicy; budgetCapInput: string; busyAction: string | null;
  simulation: AutopilotSimulationRecord | null;
  onChangePrivacyPolicy: (policy: AutopilotPrivacyPolicy) => void;
  onChangeBudgetCap: (val: string) => void; onSimulate: () => void; onApplyAndRun: () => void;
}

function AutopilotPlannerColumn({
  privacyPolicy, budgetCapInput, busyAction, simulation,
  onChangePrivacyPolicy, onChangeBudgetCap, onSimulate, onApplyAndRun,
}: AutopilotColumnProps): React.JSX.Element {
  return (
    <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
      <h3 className="text-xs font-semibold text-fg">Pre-Run Hybrid Cost &amp; 4D Privacy Autopilot</h3>

      <div className="grid gap-2 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs text-fg-muted sm:col-span-2">
          <span>4D Privacy boundary policy</span>
          <select aria-label="4D Privacy boundary policy" value={privacyPolicy} onChange={(e) => onChangePrivacyPolicy(e.target.value as AutopilotPrivacyPolicy)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
            {PRIVACY_POLICIES.map((pol) => (
              <option key={pol} value={pol}>{formatPrivacyPolicyOption(pol)}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>P95 budget cap (USD)</span>
          <input type="number" step="0.05" aria-label="P95 budget cap (USD)" value={budgetCapInput} onChange={(e) => onChangeBudgetCap(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" loading={busyAction === "simulate"} onClick={onSimulate}>
          Simulate Pre-Run Blast &amp; Autopilot
        </Button>
        <Button type="button" size="sm" variant="primary" loading={busyAction === "apply_autopilot"} onClick={onApplyAndRun}>
          Apply Autopilot Route &amp; Run
        </Button>
      </div>

      {simulation ? (
        <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
          <div className="grid gap-2 sm:grid-cols-3">
            <div>
              <div className="text-[10px] text-fg-muted">Baseline P95 vs Autopilot P95</div>
              <div className="font-semibold text-fg">{`$${simulation.baseline_p95_usd.toFixed(3)} -> $${simulation.optimized_p95_usd.toFixed(3)}`}</div>
            </div>
            <div>
              <div className="text-[10px] text-fg-muted">Savings % &amp; Violations Resolved</div>
              <div className="font-semibold text-teal-accent">{`${simulation.savings_pct.toFixed(1)}% saved · ${simulation.violations_resolved} resolved`}</div>
            </div>
            <div>
              <div className="text-[10px] text-fg-muted">Expected TTFT</div>
              <div className="font-semibold text-fg">{`${simulation.baseline_ttft_ms}ms -> ${simulation.optimized_ttft_ms}ms`}</div>
            </div>
          </div>

          <ul aria-label="Autopilot node routing plan" className="space-y-1.5 border-t border-border pt-2">
            {simulation.node_plan.map((item) => (
              <li key={item.node_id} className="rounded-xs border border-border bg-chrome px-2 py-1.5">
                <div className="flex flex-wrap items-center justify-between gap-1.5">
                  <span className="font-semibold text-fg">{`${item.node_id}: ${item.original_model} -> ${item.selected_model}`}</span>
                  <SemanticBadge kind={item.rewritten ? "opencore" : "ready"} labelOverride={item.rewritten ? "REWRITTEN" : "RETAINED"} />
                </div>
                <div className="mt-0.5 text-[10px] text-fg-muted">{`${item.data_boundary} · $${item.p95_cost_usd.toFixed(2)} egress · ${item.reason}`}</div>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
          Run Simulate Pre-Run Blast &amp; Autopilot to forecast P50/P95 loop spend and enforce 4D zero-egress OpenCore routing.
        </div>
      )}
    </div>
  );
}

export function CyclicKflowAndAutopilotPanel({
  workspaceId = "default", workflowId = "WF-CYCLIC-01", activeRbacRole = "owner",
}: CyclicKflowAndAutopilotPanelProps): React.JSX.Element {
  const canMutate = canRbacRunCyclicKflow(activeRbacRole);
  const [maxIterationsInput, setMaxIterationsInput] = useState<string>("3");
  const [criticThresholdInput, setCriticThresholdInput] = useState<string>("0.85");
  const [shardsInput, setShardsInput] = useState<string>("3");
  const [privacyPolicy, setPrivacyPolicy] = useState<AutopilotPrivacyPolicy>("hybrid_balanced");
  const [budgetCapInput, setBudgetCapInput] = useState<string>("0.15");
  const [validation, setValidation] = useState<CyclicValidationResult | null>(null);
  const [activeRun, setActiveRun] = useState<CyclicKflowRunRecord | null>(null);
  const [simulation, setSimulation] = useState<AutopilotSimulationRecord | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorAlert, setErrorAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listCyclicKflowRuns(workspaceId, workflowId, activeRbacRole).then((runs) => { if (!cancelled && runs.length > 0) setActiveRun(runs[0] ?? null); }).catch(() => {});
    void listKflowAutopilotSimulations(workspaceId, workflowId, activeRbacRole).then((sims) => { if (!cancelled && sims.length > 0) setSimulation(sims[0] ?? null); }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeRbacRole, workflowId, workspaceId]);

  const formatError = (err: unknown, fallback: string): string =>
    err instanceof PlatformCyclicHttpError ? `HTTP ${err.status} · ${err.message}` : err instanceof Error ? err.message : fallback;

  const parseLoopControls = () => {
    const maxIterations = Number.parseInt(maxIterationsInput, 10);
    const criticThreshold = Number.parseFloat(criticThresholdInput);
    const shards = Number.parseInt(shardsInput, 10);
    const effMax = Number.isFinite(maxIterations) ? maxIterations : 0;
    const effThr = Number.isFinite(criticThreshold) ? criticThreshold : -1;
    const loopEdges: CyclicLoopEdgeSpec[] = [
      { from_node: "critic_verify", to_node: "draft_patch", condition: "critic_score_lt", threshold: effThr, max_iterations: effMax },
    ];
    return { maxIterations: effMax, criticThreshold: effThr, shards: Number.isFinite(shards) ? shards : 0, loopEdges };
  };

  const handleValidate = async () => {
    setBusyAction("validate");
    setErrorAlert(null);
    try {
      const { loopEdges } = parseLoopControls();
      setValidation(await validateCyclicKflow({ workspace_id: workspaceId, workflow_id: workflowId, loop_edges: loopEdges }, activeRbacRole));
    } catch (err) {
      setErrorAlert(formatError(err, "Failed to validate cyclic KFlow graph."));
    } finally {
      setBusyAction(null);
    }
  };

  const handleExecuteLoop = async (simulateTimeout: boolean, customNodes?: CyclicNodeSpec[]) => {
    setBusyAction(simulateTimeout ? "compensate" : "execute");
    setErrorAlert(null);
    try {
      const { maxIterations, criticThreshold, shards, loopEdges } = parseLoopControls();
      const run = await executeCyclicKflow(
        { workspace_id: workspaceId, workflow_id: workflowId, nodes: customNodes, loop_edges: loopEdges, max_iterations_override: maxIterations, critic_threshold: criticThreshold, fan_out_shards: shards, simulate_timeout: simulateTimeout },
        activeRbacRole,
      );
      setActiveRun(run);
    } catch (err) {
      setErrorAlert(formatError(err, "Failed to execute cyclic KFlow reflection loop."));
    } finally {
      setBusyAction(null);
    }
  };

  const handleSimulateAutopilot = async () => {
    setBusyAction("simulate");
    setErrorAlert(null);
    try {
      const parsedCap = Number.parseFloat(budgetCapInput);
      const sim = await simulateKflowAutopilot(
        { workspace_id: workspaceId, workflow_id: workflowId, privacy_policy: privacyPolicy, budget_cap_usd: Number.isFinite(parsedCap) ? parsedCap : -1 },
        activeRbacRole,
      );
      setSimulation(sim);
    } catch (err) {
      setErrorAlert(formatError(err, "Failed to simulate pre-run cost/privacy autopilot."));
    } finally {
      setBusyAction(null);
    }
  };

  const handleApplyAutopilotAndRun = async () => {
    setBusyAction("apply_autopilot");
    setErrorAlert(null);
    try {
      const parsedCap = Number.parseFloat(budgetCapInput);
      const targetCap = Number.isFinite(parsedCap) ? parsedCap : 0.15;
      const activeSim =
        simulation && simulation.privacy_policy === privacyPolicy && simulation.budget_cap_usd === targetCap
          ? simulation
          : await simulateKflowAutopilot({ workspace_id: workspaceId, workflow_id: workflowId, privacy_policy: privacyPolicy, budget_cap_usd: targetCap }, activeRbacRole);
      setSimulation(activeSim);
      const { maxIterations, criticThreshold, shards, loopEdges } = parseLoopControls();
      const run = await executeCyclicKflow(
        { workspace_id: workspaceId, workflow_id: workflowId, nodes: buildRewrittenNodes(activeSim), loop_edges: loopEdges, max_iterations_override: maxIterations, critic_threshold: criticThreshold, fan_out_shards: shards, simulate_timeout: false },
        activeRbacRole,
      );
      setActiveRun(run);
    } catch (err) {
      setErrorAlert(formatError(err, "Failed to apply autopilot route and run cyclic KFlow."));
    } finally {
      setBusyAction(null);
    }
  };

  const badgeSpec = resolveCyclicStatusBadge(activeRun?.status ?? "IDLE");

  return (
    <section id="cyclic-kflow-autopilot-panel" aria-label="Bounded Cyclic KFlow and Cost Privacy Autopilot" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Bounded Cyclic KFlow &amp; Cost/Privacy Autopilot</h2>
            <SemanticBadge kind={badgeSpec.kind} labelOverride={badgeSpec.labelOverride} />
            {!canMutate ? (
              <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                {`RBAC: ${activeRbacRole} (read-only)`}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-fg-muted">
            Bounded critic reflection loops, dynamic map-reduce shards, reverse-order saga compensation, and pre-run 4D cost/privacy autopilot.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-xs border border-teal-accent/45 bg-teal-surface px-2 py-1 font-mono text-[11px]">
            <span className="text-fg-muted">run_sha256:</span>
            <code data-testid="cyclic-run-sha256" title={activeRun?.run_sha256 ?? "awaiting-run"} className="max-w-[160px] truncate font-semibold text-teal-accent">
              {activeRun?.run_sha256 ?? "awaiting-run"}
            </code>
          </div>
          <div className="flex items-center gap-1.5 rounded-xs border border-border-strong bg-chrome px-2 py-1 font-mono text-[11px]">
            <span className="text-fg-muted">simulation_sha256:</span>
            <code data-testid="autopilot-simulation-sha256" title={simulation?.simulation_sha256 ?? "awaiting-simulation"} className="max-w-[160px] truncate font-semibold text-teal-accent">
              {simulation?.simulation_sha256 ?? "awaiting-simulation"}
            </code>
          </div>
        </div>
      </div>

      {errorAlert ? (
        <div role="alert" className="rounded-xs border border-danger/55 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{errorAlert}</span>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <CyclicReflectionColumn
          maxIterationsInput={maxIterationsInput} criticThresholdInput={criticThresholdInput} shardsInput={shardsInput}
          busyAction={busyAction} validation={validation} activeRun={activeRun}
          onChangeMaxIterations={setMaxIterationsInput} onChangeCriticThreshold={setCriticThresholdInput} onChangeShards={setShardsInput}
          onValidate={() => { void handleValidate(); }} onExecuteLoop={(timeout) => { void handleExecuteLoop(timeout); }}
        />
        <AutopilotPlannerColumn
          privacyPolicy={privacyPolicy} budgetCapInput={budgetCapInput} busyAction={busyAction} simulation={simulation}
          onChangePrivacyPolicy={setPrivacyPolicy} onChangeBudgetCap={setBudgetCapInput}
          onSimulate={() => { void handleSimulateAutopilot(); }} onApplyAndRun={() => { void handleApplyAutopilotAndRun(); }}
        />
      </div>
    </section>
  );
}
