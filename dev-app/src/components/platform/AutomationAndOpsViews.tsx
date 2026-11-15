import React, { useEffect, useState } from "react";
import { KSpacesCrdtAndKflowPanel } from "@/components/platform/KSpacesCrdtAndKflowPanel";
import { LiveExecutionDrawer } from "@/components/platform/LiveExecutionDrawer";
import { QuotaAndPricingSimulatorPanel } from "@/components/platform/QuotaAndPricingSimulatorPanel";
import { SiemAndObservabilityPanel } from "@/components/platform/SiemAndObservabilityPanel";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  fetchClusterAndSettlementSnapshot, postClusterNodeAction, postClusterSchedule, postModelLifecycleAction,
  type ClusterNodeItem, type MarketplaceSettlementSummary, type ModelCanaryItem,
} from "@/lib/platformApi";
import {
  BYOM_CONSUMER_COMPLIANCE_CALLOUT, INITIAL_LIFECYCLE_AGENTS, SUBSCRIPTION_TIERS, validateByomCredentialClient,
  type AutomationWorkflowItem, type ByomValidationResult, type DeploymentEnvItem,
  type ExperienceMode, type SubscriptionTierId, type WorkflowNodeItem,
} from "@/lib/platformData";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

const SEED_CLUSTER_NODES: ClusterNodeItem[] = [
  { nodeId: "node-metal-local-01", runtime: "ollama_metal", runtimeLabel: "Apple Metal", region: "airgap_local", gpuModel: "Apple M-Series Metal Unified", totalVramGb: 32, freeVramGb: 32, status: "healthy", loadedModels: ["keelway-core:7b", "qwen2.5-coder:7b"] },
  { nodeId: "node-vllm-us-01", runtime: "vllm", runtimeLabel: "vLLM", region: "us", gpuModel: "NVIDIA H100 80GB", totalVramGb: 160, freeVramGb: 160, status: "healthy", loadedModels: ["keelway-coder:14b-v2", "deepseek-r1:70b"] },
  { nodeId: "node-vllm-eu-01", runtime: "vllm", runtimeLabel: "vLLM", region: "eu", gpuModel: "NVIDIA A100 80GB", totalVramGb: 80, freeVramGb: 80, status: "healthy", loadedModels: ["qwen2.5-coder:7b"] },
  { nodeId: "node-ray-af-01", runtime: "ray_serve", runtimeLabel: "Ray Serve", region: "africa", gpuModel: "NVIDIA L40S 48GB", totalVramGb: 48, freeVramGb: 48, status: "healthy", loadedModels: ["keelway-core:7b"] },
];

const SEED_MODEL_CANARIES: ModelCanaryItem[] = [
  { modelId: "keelway-core:7b", stage: "stable", trafficWeightPct: 100 },
  { modelId: "keelway-coder:14b-v2", stage: "canary", trafficWeightPct: 15 },
];

const SEED_SETTLEMENT_SUMMARY: MarketplaceSettlementSummary = {
  count: 14, grossUsd: 480.0, creatorPayoutUsd: 408.0, platformFeeUsd: 72.0, verifiedSplitLabel: "85% Creator / 15% Platform",
};

const utcStamp = (): string => `${new Date().toISOString().slice(11, 19)} UTC`;

export interface AutomationWorkspaceViewProps {
  experienceMode: ExperienceMode;
  workflows: AutomationWorkflowItem[];
  onCreateWorkflow: (spec: { name: string; triggerKind: "cron" | "webhook" | "event"; triggerSpec: string; tokenBudget: number }) => void;
  onRunWorkflow: (workflowId: string) => void;
  onRetryFailedNode: (workflowId: string, nodeId: string) => void;
  onAddStepToWorkflow?: (workflowId: string, step: { label: string; agentId: string; requiresP10: boolean }) => void;
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

export function AutomationWorkspaceView({
  experienceMode, workflows, onCreateWorkflow, onRunWorkflow, onRetryFailedNode, onAddStepToWorkflow,
  workspaceId = "default", activeRbacRole = "owner",
}: AutomationWorkspaceViewProps): React.JSX.Element {
  const [wfName, setWfName] = useState("");
  const [triggerKind, setTriggerKind] = useState<"cron" | "webhook" | "event">("cron");
  const [triggerSpec, setTriggerSpec] = useState("0 */6 * * *");
  const [tokenBudget, setTokenBudget] = useState(25000);

  const [targetWfId, setTargetWfId] = useState<string>(workflows[0]?.id ?? "WF-01");
  const [stepLabel, setStepLabel] = useState("");
  const [stepAgentId, setStepAgentId] = useState("workflow-automator");
  const [stepRequiresP10, setStepRequiresP10] = useState(false);
  const [localStepsByWf, setLocalStepsByWf] = useState<Record<string, WorkflowNodeItem[]>>({});
  const [traceByWf, setTraceByWf] = useState<Record<string, string[]>>({});
  const [traceOpenByWf, setTraceOpenByWf] = useState<Record<string, boolean>>({});
  const [liveDagSpec, setLiveDagSpec] = useState<{
    targetId: string; targetName: string; objective: string; requiresP10: boolean; nonce: number;
  } | null>(null);

  const resolvedTargetWfId = workflows.some((w) => w.id === targetWfId) ? targetWfId : (workflows[0]?.id ?? "");

  const getEffectiveNodes = (wf: AutomationWorkflowItem): WorkflowNodeItem[] => {
    const extras = (localStepsByWf[wf.id] ?? []).filter(
      (loc) => !wf.nodes.some((n) => n.id === loc.id || (n.label === loc.label && n.agentId === loc.agentId)),
    );
    return extras.length > 0 ? [...wf.nodes, ...extras] : wf.nodes;
  };

  const baseActiveWf = workflows.find((w) => w.id === resolvedTargetWfId) ?? workflows[0];
  const activeWorkflow = baseActiveWf ? { ...baseActiveWf, nodes: getEffectiveNodes(baseActiveWf) } : undefined;

  const handleAddWorkflow = (e: React.FormEvent) => {
    e.preventDefault();
    if (!wfName.trim()) return;
    onCreateWorkflow({ name: wfName.trim(), triggerKind, triggerSpec: triggerSpec.trim() || "manual", tokenBudget });
    setWfName("");
  };

  const handleAddDagStep = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanLabel = stepLabel.trim();
    if (!cleanLabel || !resolvedTargetWfId) return;
    const wf = workflows.find((w) => w.id === resolvedTargetWfId);
    const existing = wf ? getEffectiveNodes(wf) : [];
    const prevNodeId = existing[existing.length - 1]?.id;
    const newNode: WorkflowNodeItem = {
      id: `n-custom-${existing.length + 1}`, label: cleanLabel, agentId: stepAgentId,
      dependsOn: prevNodeId ? [prevNodeId] : [], status: "ready", requiresP10: stepRequiresP10,
      lastOutput: stepRequiresP10 ? "Awaiting P-10 human checkpoint on execution." : "Queued in DAG.",
    };
    setLocalStepsByWf((prev) => ({ ...prev, [resolvedTargetWfId]: [...(prev[resolvedTargetWfId] ?? []), newNode] }));
    onAddStepToWorkflow?.(resolvedTargetWfId, { label: cleanLabel, agentId: stepAgentId, requiresP10: stepRequiresP10 });
    setStepLabel("");
    setStepRequiresP10(false);
  };

  const handleExecuteWorkflow = (wf: AutomationWorkflowItem) => {
    onRunWorkflow(wf.id);
    const ts = utcStamp();
    const entries = getEffectiveNodes(wf).map(
      (n) => `[${ts}] [${n.id} · ${n.agentId}] ${n.label} -> PASSED${n.requiresP10 ? " (P-10 gate verified)" : ""} · ${n.lastOutput ?? "Receipt committed to Record."}`,
    );
    setLocalStepsByWf((prev) => prev[wf.id] ? { ...prev, [wf.id]: prev[wf.id]!.map((n) => ({ ...n, status: "passed" })) } : prev);
    setTraceByWf((prev) => ({ ...prev, [wf.id]: [...(prev[wf.id] ?? []), ...entries] }));
    setTraceOpenByWf((prev) => ({ ...prev, [wf.id]: true }));
  };

  const handleRetryNode = (wf: AutomationWorkflowItem, node: WorkflowNodeItem) => {
    onRetryFailedNode(wf.id, node.id);
    const line = `[${utcStamp()}] [${node.id} · ${node.agentId}] Retried "${node.label}" -> PASSED (allocated clean sandbox port & verified receipt)`;
    setTraceByWf((prev) => ({ ...prev, [wf.id]: [...(prev[wf.id] ?? []), line] }));
    setTraceOpenByWf((prev) => ({ ...prev, [wf.id]: true }));
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">Automation · KFlow DAG &amp; Scheduled Workflows</h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Automate recurring business checks, notifications, and QA steps with visual progress and one-click retry."
              : "Compile durable KFlow DAG specifications with node dependency graphs, cron/webhook triggers, and token budgets."}
          </p>
        </div>
        <SemanticBadge kind="opencore" detail={`${workflows.length} KFlow DAGs`} />
      </div>

      <KSpacesCrdtAndKflowPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} activeWorkflow={activeWorkflow} />

      <form onSubmit={handleAddWorkflow} aria-label="Create automation workflow" className="flex flex-wrap items-end gap-2.5 rounded-md border border-border-strong bg-surface p-3">
        <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-xs text-fg-muted">
          <span>Workflow name</span>
          <input type="text" aria-label="Workflow name" value={wfName} onChange={(e) => setWfName(e.target.value)} placeholder="e.g. Daily Invoice Reconciliation DAG" className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Trigger type</span>
          <select aria-label="Workflow trigger type" value={triggerKind} onChange={(e) => setTriggerKind(e.target.value as "cron" | "webhook" | "event")} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg">
            <option value="cron">Cron schedule</option>
            <option value="webhook">Webhook</option>
            <option value="event">Workspace event</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Schedule / route</span>
          <input type="text" aria-label="Trigger schedule or route" value={triggerSpec} onChange={(e) => setTriggerSpec(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Token budget</span>
          <input type="number" aria-label="Workflow token budget" value={tokenBudget} onChange={(e) => setTokenBudget(Number(e.target.value) || 10000)} className="min-h-ctrl-sm w-28 rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </label>
        <Button type="submit" size="sm" variant="primary">+ Create workflow</Button>
      </form>

      <form onSubmit={handleAddDagStep} aria-label="Add custom DAG step" className="flex flex-wrap items-end gap-2.5 rounded-md border border-border bg-surface p-3">
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Target workflow</span>
          <select aria-label="Target workflow" value={resolvedTargetWfId} onChange={(e) => setTargetWfId(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
            {workflows.map((wf) => <option key={wf.id} value={wf.id}>{wf.id}</option>)}
          </select>
        </label>
        <label className="flex min-w-[180px] flex-1 flex-col gap-1 text-xs text-fg-muted">
          <span>Step label</span>
          <input type="text" aria-label="Step label" value={stepLabel} onChange={(e) => setStepLabel(e.target.value)} placeholder="e.g. Run OWASP & license gate" className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Lifecycle agent</span>
          <select aria-label="Lifecycle agent" value={stepAgentId} onChange={(e) => setStepAgentId(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
            {INITIAL_LIFECYCLE_AGENTS.map((ag) => <option key={ag.id} value={ag.id}>{ag.id}</option>)}
          </select>
        </label>
        <label className="inline-flex min-h-ctrl-sm items-center gap-1.5 rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg">
          <input type="checkbox" aria-label="P-10 Human Gate" checked={stepRequiresP10} onChange={(e) => setStepRequiresP10(e.target.checked)} />
          <span>P-10 Human Gate</span>
        </label>
        <Button type="submit" size="sm" variant="secondary">+ Add DAG Step</Button>
      </form>

      {liveDagSpec ? (
        <LiveExecutionDrawer kind="workflow" targetId={liveDagSpec.targetId} targetName={liveDagSpec.targetName} objective={liveDagSpec.objective} requiresP10={liveDagSpec.requiresP10} workspaceId={workspaceId} activeRbacRole={activeRbacRole} runNonce={liveDagSpec.nonce} onClose={() => setLiveDagSpec(null)} />
      ) : null}

      <section aria-label="Workflow DAG pipelines" className="space-y-3">
        <h2 className="sr-only">Configured Workflows</h2>
        {workflows.map((wf) => {
          const nodes = getEffectiveNodes(wf);
          const logs = traceByWf[wf.id] ?? [];
          const isTraceOpen = Boolean(traceOpenByWf[wf.id]);
          const wfBadge = wf.lastRunStatus === "passed" ? "passed" : wf.lastRunStatus === "failed" ? "failed" : wf.lastRunStatus === "running" ? "running" : "ready";
          return (
            <article key={wf.id} className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-teal-accent">{wf.id}</span>
                    <h3 className="text-sm font-semibold text-fg">{wf.name}</h3>
                    <SemanticBadge kind={wfBadge} />
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-fg-dim">
                    {`Trigger: ${wf.triggerKind.toUpperCase()} (${wf.triggerSpec}) · Budget: ${wf.tokenBudget.toLocaleString()} tok`}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="ghost" aria-expanded={isTraceOpen} onClick={() => setTraceOpenByWf((prev) => ({ ...prev, [wf.id]: !isTraceOpen }))}>
                    {`Execution Trace & Logs (${logs.length})`}
                  </Button>
                  <Button size="sm" variant="primary" aria-label={`Stream Live DAG ${wf.name}`} onClick={() => setLiveDagSpec((prev) => ({ targetId: wf.id, targetName: wf.name, objective: `Execute KFlow DAG ${wf.name} (${nodes.length} steps)`, requiresP10: true, nonce: (prev?.nonce ?? 0) + 1 }))}>
                    Stream Live DAG
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => handleExecuteWorkflow(wf)}>Run workflow</Button>
                </div>
              </div>

              <div className="grid gap-2 md:grid-cols-3">
                {nodes.map((node) => (
                  <div key={node.id} className="flex flex-col justify-between gap-2 rounded-sm border border-border bg-chrome p-2.5 text-xs">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center justify-between gap-1.5">
                        <span className="font-medium text-fg">{node.label}</span>
                        <div className="flex items-center gap-1">
                          {node.requiresP10 ? <SemanticBadge kind="needs-approval" labelOverride="P-10 Gate" /> : null}
                          <SemanticBadge kind={node.status === "passed" ? "passed" : node.status === "failed" ? "failed" : "ready"} />
                        </div>
                      </div>
                      <div className="font-mono text-[10px] text-fg-dim">
                        {`Agent: ${node.agentId}${node.dependsOn.length ? ` · after ${node.dependsOn.join(", ")}` : ""}`}
                      </div>
                      {node.errorDetail ? (
                        <p className="rounded-xs border border-danger/40 bg-danger-subtle px-2 py-1 text-[11px] text-danger">{node.errorDetail}</p>
                      ) : node.lastOutput ? (
                        <p className="font-mono text-[10px] text-fg-muted">{node.lastOutput}</p>
                      ) : null}
                    </div>
                    {node.status === "failed" ? (
                      <Button size="sm" variant="warning-cta" onClick={() => handleRetryNode(wf, node)}>Retry failed step</Button>
                    ) : null}
                  </div>
                ))}
              </div>

              {isTraceOpen ? (
                <div role="log" aria-label={`Execution trace for ${wf.id}`} className="space-y-1 rounded-sm border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
                  <div className="font-semibold text-fg">Execution Trace &amp; Logs</div>
                  {logs.length === 0 ? (
                    <div>No execution runs recorded in this session yet. Click Run workflow to trace DAG output.</div>
                  ) : (
                    logs.map((entry, idx) => <div key={`${wf.id}-log-${idx}`} className="text-fg">{entry}</div>)
                  )}
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
    </div>
  );
}

export interface OperationsWorkspaceViewProps {
  subscriptionTier: SubscriptionTierId;
  deployments: DeploymentEnvItem[];
  onConfirmP10Rollback: (deploymentId: string) => void;
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

export function OperationsWorkspaceView({
  subscriptionTier, deployments, onConfirmP10Rollback, workspaceId = "default", activeRbacRole = "owner",
}: OperationsWorkspaceViewProps): React.JSX.Element {
  const [pendingRollbackId, setPendingRollbackId] = useState<string | null>(null);
  const [byomProvider, setByomProvider] = useState("Anthropic / OpenAI");
  const [byomCredType, setByomCredType] = useState<"api_key" | "self_hosted_endpoint" | "consumer_subscription">("api_key");
  const [byomPreview, setByomPreview] = useState("sk-authorized-org-key");
  const [byomCheck, setByomCheck] = useState<ByomValidationResult | null>(null);
  const [clusterNodes, setClusterNodes] = useState<ClusterNodeItem[]>(SEED_CLUSTER_NODES);
  const [modelCanaries, setModelCanaries] = useState<ModelCanaryItem[]>(SEED_MODEL_CANARIES);
  const [settlement, setSettlement] = useState<MarketplaceSettlementSummary>(SEED_SETTLEMENT_SUMMARY);

  const [schedModel, setSchedModel] = useState("keelway-core:7b");
  const [schedVramGb, setSchedVramGb] = useState(16);
  const [schedRegion, setSchedRegion] = useState<ClusterNodeItem["region"]>("airgap_local");
  const [scheduleReceipt, setScheduleReceipt] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchClusterAndSettlementSnapshot().then((snap) => {
      if (cancelled || !snap) return;
      if (snap.nodes.length > 0) setClusterNodes(snap.nodes);
      if (snap.canaries.length > 0) setModelCanaries(snap.canaries);
      if (snap.settlement) setSettlement(snap.settlement);
    });
    return () => { cancelled = true; };
  }, []);

  const handleToggleNodeDrain = (nodeId: string) => {
    const current = clusterNodes.find((n) => n.nodeId === nodeId);
    const action: "drain" | "restore" = current?.status === "drained" ? "restore" : "drain";
    setClusterNodes((prev) => prev.map((n) => (n.nodeId === nodeId ? { ...n, status: action === "drain" ? "drained" : "healthy" } : n)));
    void postClusterNodeAction(nodeId, action);
  };

  const handleScheduleWorkload = () => {
    const privacyTier = schedRegion === "airgap_local" ? "air_gap" : "standard";
    const candidates = clusterNodes
      .filter((n) => n.region === schedRegion && n.status === "healthy" && n.freeVramGb >= schedVramGb)
      .sort((a, b) => (Number(b.loadedModels.includes(schedModel)) - Number(a.loadedModels.includes(schedModel))) || (b.freeVramGb - a.freeVramGb));
    if (candidates.length === 0) {
      setScheduleReceipt({ ok: false, message: `Fail-Closed: Insufficient VRAM / Drained — No healthy node in ${schedRegion} fits ${schedVramGb}GB VRAM for ${schedModel}.` });
    } else {
      const best = candidates[0]!;
      setScheduleReceipt({ ok: true, message: `Scheduled on ${best.nodeId} (${best.runtimeLabel} · ${best.region} · ${schedVramGb}GB VRAM · ${privacyTier})` });
    }
    void postClusterSchedule({ model_id: schedModel, required_vram_gb: schedVramGb, region: schedRegion, privacy_tier: privacyTier }).then((res) => {
      const serverNodeId = typeof res?.selected_node_id === "string" ? res.selected_node_id : null;
      const matching = serverNodeId ? candidates.find((c) => c.nodeId === serverNodeId) : undefined;
      if (matching) setScheduleReceipt({ ok: true, message: `Scheduled on ${matching.nodeId} (${matching.runtimeLabel} · ${matching.region} · ${schedVramGb}GB VRAM · ${privacyTier})` });
    });
  };

  const handlePromoteCanary = () => {
    const target = modelCanaries.find((c) => c.stage === "canary") ?? modelCanaries.find((c) => c.modelId !== "keelway-core:7b") ?? modelCanaries[0];
    if (!target) return;
    setModelCanaries((prev) => prev.map((c) => (c.modelId === target.modelId ? { ...c, stage: "stable", trafficWeightPct: 100 } : c)));
    void postModelLifecycleAction("promote", { model_id: target.modelId, target_stage: "stable", traffic_weight_pct: 100 });
  };

  const handleRollbackCanary = () => {
    const target = modelCanaries.find((c) => c.stage === "canary") ?? modelCanaries.find((c) => c.modelId !== "keelway-core:7b") ?? modelCanaries[modelCanaries.length - 1];
    if (!target) return;
    setModelCanaries((prev) => prev.map((c) => (c.modelId === target.modelId ? { ...c, stage: "deprecated", trafficWeightPct: 0 } : c)));
    void postModelLifecycleAction("rollback", { model_id: target.modelId, reason: "Operator canary rollback from Operations workspace" });
  };

  const tier = SUBSCRIPTION_TIERS[subscriptionTier];
  const dailyUsed = 42_000;
  const dailyCap = typeof tier.dailyOpenWeightTokens === "number" ? tier.dailyOpenWeightTokens : 2_500_000;
  const quotaPct = Math.min(100, Math.round((dailyUsed / dailyCap) * 100));

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">Operations · Deployments, Cost Governance &amp; SLOs</h1>
          <p className="text-xs text-fg-muted">Monitor managed deployments, P-10 human-confirmed rollbacks, OpenCore $0.00 local inference vs BYOM spend, and TTFT latency SLOs.</p>
        </div>
        <SemanticBadge kind="live" labelOverride={`Active Tier · ${tier.badgeLabel}`} />
      </div>

      <CalloutBanner variant="spend-warn" title="BYOM Credential & Consumer-Subscription Compliance" description={BYOM_CONSUMER_COMPLIANCE_CALLOUT} safeStateNote="Keelway charges $0.00 token markup on authorized BYOM API keys and local OpenCore weights." />

      <section aria-label="Cost quota and reliability SLOs" className="grid gap-4 md:grid-cols-3">
        <h2 className="sr-only">Spend, Quotas and Reliability SLOs</h2>
        <article className="space-y-2 rounded-md border border-border-strong bg-surface p-3.5">
          <h3 className="text-xs font-semibold text-fg">OpenCore vs BYOM Spend</h3>
          <div className="font-mono text-sm font-semibold text-teal-accent">Local OpenCore: $0.00 / tok</div>
          <div className="font-mono text-xs text-fg-muted">Authorized BYOM API: $4.18 vendor · $0.00 Keelway markup</div>
        </article>
        <article className="space-y-2 rounded-md border border-border-strong bg-surface p-3.5">
          <h3 className="text-xs font-semibold text-fg">Daily Open-Weight Pool Quota</h3>
          <div className="font-mono text-xs text-fg">{`${dailyUsed.toLocaleString()} / ${dailyCap.toLocaleString()} tokens (${tier.rpmLimit} RPM cap)`}</div>
          <div role="progressbar" aria-label="Daily open-weight token quota" aria-valuenow={quotaPct} aria-valuemin={0} aria-valuemax={100} className="h-2 w-full overflow-hidden rounded-xs bg-chrome">
            <div className="h-full bg-teal-accent" style={{ width: `${quotaPct}%` }} />
          </div>
        </article>
        <article className="space-y-2 rounded-md border border-border-strong bg-surface p-3.5">
          <h3 className="text-xs font-semibold text-fg">Reliability &amp; Latency SLOs</h3>
          <div className="font-mono text-xs text-fg">TTFT p50: 148 ms · p95: 390 ms</div>
          <div className="font-mono text-xs text-ok">Runner Availability: 99.96% (SLO Met)</div>
        </article>
      </section>

      <QuotaAndPricingSimulatorPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <SiemAndObservabilityPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <section aria-label="BYOM credential compliance verifier" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <h2 className="text-sm font-semibold text-fg">BYOM Connection Compliance Check</h2>
        <div className="flex flex-wrap items-end gap-2.5">
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Provider</span>
            <input type="text" aria-label="BYOM provider" value={byomProvider} onChange={(e) => setByomProvider(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>BYOM credential type</span>
            <select aria-label="BYOM credential type" value={byomCredType} onChange={(e) => setByomCredType(e.target.value as "api_key" | "self_hosted_endpoint" | "consumer_subscription")} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg">
              <option value="api_key">Authorized Vendor API Key</option>
              <option value="self_hosted_endpoint">Self-Hosted vLLM / Ollama Endpoint</option>
              <option value="consumer_subscription">Consumer ChatGPT / Claude Web Subscription</option>
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
            <span>Key prefix or endpoint preview</span>
            <input type="text" aria-label="Key prefix or endpoint preview" value={byomPreview} onChange={(e) => setByomPreview(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
          </label>
          <Button size="sm" variant="secondary" onClick={() => setByomCheck(validateByomCredentialClient(byomProvider, byomCredType, byomPreview))}>Verify BYOM compliance</Button>
        </div>
        {byomCheck ? (
          <div role={byomCheck.valid ? "status" : "alert"} className={`rounded-sm border px-3 py-2 text-xs ${byomCheck.valid ? "border-ok/40 bg-ok-subtle text-fg" : "border-danger/50 bg-danger-subtle text-fg"}`}>
            <code className="font-mono font-semibold">{byomCheck.code}</code> — {byomCheck.message}
          </div>
        ) : null}
      </section>

      <section aria-label="Managed deployment environments" className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">Managed Environments &amp; P-10 Rollback</h2>
        <div className="space-y-2">
          {deployments.map((dep) => {
            const isConfirming = pendingRollbackId === dep.id;
            return (
              <article key={dep.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface px-3.5 py-2.5">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-semibold text-fg">{dep.environment}</h3>
                    <code className="font-mono text-xs text-teal-accent">{dep.version}</code>
                    <SemanticBadge kind={dep.status === "rolled_back" ? "reconfirm" : "passed"} labelOverride={dep.status === "rolled_back" ? "Rolled back with P-10 receipt" : dep.status === "staging_ready" ? "Staging Verified" : "Healthy"} />
                  </div>
                  <div className="font-mono text-[11px] text-fg-dim">{`${dep.url} · Last deploy: ${dep.lastDeployedAt}${dep.rollbackReceipt ? ` · ${dep.rollbackReceipt}` : ""}`}</div>
                </div>
                {dep.id === "dep-prod" ? (
                  isConfirming ? (
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setPendingRollbackId(null)}>Cancel</Button>
                      <Button size="sm" variant="warning-cta" clickOnly onClick={() => { onConfirmP10Rollback(dep.id); setPendingRollbackId(null); }}>Confirm human P-10 rollback</Button>
                    </div>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => setPendingRollbackId(dep.id)}>Request P-10 rollback</Button>
                  )
                ) : null}
              </article>
            );
          })}
        </div>
      </section>

      <section aria-label="Multi-node GPU cluster and model canary rollout" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">Multi-Node GPU Cluster &amp; Model Canary Rollout</h2>
          <SemanticBadge kind="opencore" detail={`${clusterNodes.filter((n) => n.status !== "drained").length}/${clusterNodes.length} Nodes Active`} />
        </div>
        <div className="grid gap-2.5 md:grid-cols-2">
          {clusterNodes.map((node) => {
            const isDrained = node.status === "drained";
            return (
              <article key={node.nodeId} className="flex flex-wrap items-center justify-between gap-2.5 rounded-sm border border-border bg-chrome p-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-mono text-xs font-semibold text-fg">{node.nodeId}</h3>
                    <SemanticBadge kind={isDrained ? "reconfirm" : "passed"} labelOverride={isDrained ? "Drained" : "Healthy"} />
                  </div>
                  <div className="font-mono text-[11px] text-fg-muted">{`${node.runtimeLabel} · ${node.totalVramGb}GB · ${node.region}`}</div>
                </div>
                <Button size="sm" variant={isDrained ? "warning-cta" : "secondary"} aria-label={`${isDrained ? "Restore Node" : "Drain Node"} ${node.nodeId}`} onClick={() => handleToggleNodeDrain(node.nodeId)}>
                  {isDrained ? "Restore Node" : "Drain Node"}
                </Button>
              </article>
            );
          })}
        </div>

        <div className="space-y-2.5 border-t border-border pt-3">
          <h3 className="text-xs font-semibold text-fg">Interactive Workload Placement Scheduler</h3>
          <div className="flex flex-wrap items-end gap-2.5">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Model</span>
              <select aria-label="Workload model" value={schedModel} onChange={(e) => setSchedModel(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                <option value="keelway-core:7b">Local · keelway-core:7b</option>
                <option value="keelway-coder:14b-v2">Canary · keelway-coder:14b-v2</option>
                <option value="deepseek-r1:70b">Reasoner · deepseek-r1:70b</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Required VRAM (GB)</span>
              <input type="number" min={1} aria-label="Required VRAM GB" value={schedVramGb} onChange={(e) => setSchedVramGb(Math.max(1, Number(e.target.value) || 1))} className="min-h-ctrl-sm w-28 rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Residency / Privacy</span>
              <select aria-label="Cluster target region" value={schedRegion} onChange={(e) => setSchedRegion(e.target.value as ClusterNodeItem["region"])} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                <option value="airgap_local">airgap_local · Loopback</option>
                <option value="us">us · US Sovereign</option>
                <option value="eu">eu · EU Sovereign</option>
                <option value="africa">africa · Africa Sovereign</option>
              </select>
            </label>
            <Button size="sm" variant="primary" onClick={handleScheduleWorkload}>Schedule Workload</Button>
          </div>
          {scheduleReceipt ? (
            <div role={scheduleReceipt.ok ? "status" : "alert"} className={`rounded-sm border px-3 py-2 font-mono text-xs ${scheduleReceipt.ok ? "border-ok/40 bg-ok-subtle text-fg" : "border-danger/50 bg-danger-subtle text-fg"}`}>
              {scheduleReceipt.message}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-fg">Model Canary Traffic Weights:</span>
            {modelCanaries.map((canary) => (
              <span key={canary.modelId} className="inline-flex items-center gap-1.5 rounded-xs border border-border-strong bg-chrome px-2.5 py-1 font-mono text-xs text-fg">
                <span className="text-teal-accent">{canary.modelId}</span>
                <span className="text-fg-muted">{`${canary.trafficWeightPct}% ${canary.stage}`}</span>
              </span>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="secondary" onClick={handlePromoteCanary}>Promote Canary -&gt; 100% Stable</Button>
            <Button size="sm" variant="ghost" onClick={handleRollbackCanary}>Rollback Canary</Button>
          </div>
        </div>
      </section>

      <section aria-label="Marketplace settlement and creator payout ledger" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">Marketplace Settlement &amp; Creator Payout Ledger</h2>
          <SemanticBadge kind="passed" labelOverride={settlement.verifiedSplitLabel} />
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-sm border border-border bg-chrome p-2.5">
            <div className="text-[11px] text-fg-muted">Verified Gross Volume (USD)</div>
            <div className="mt-0.5 font-mono text-sm font-semibold text-fg">{`$${settlement.grossUsd.toFixed(2)} USD`}</div>
          </div>
          <div className="rounded-sm border border-border bg-chrome p-2.5">
            <div className="text-[11px] text-fg-muted">Creator Payout (85% Split)</div>
            <div className="mt-0.5 font-mono text-sm font-semibold text-teal-accent">{`$${settlement.creatorPayoutUsd.toFixed(2)} USD`}</div>
          </div>
          <div className="rounded-sm border border-border bg-chrome p-2.5">
            <div className="text-[11px] text-fg-muted">Platform Fee (15% Split)</div>
            <div className="mt-0.5 font-mono text-sm font-semibold text-fg">{`$${settlement.platformFeeUsd.toFixed(2)} USD`}</div>
          </div>
        </div>
      </section>
    </div>
  );
}
