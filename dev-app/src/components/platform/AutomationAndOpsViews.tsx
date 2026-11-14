import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  BYOM_CONSUMER_COMPLIANCE_CALLOUT,
  SUBSCRIPTION_TIERS,
  validateByomCredentialClient,
  type AutomationWorkflowItem,
  type ByomValidationResult,
  type DeploymentEnvItem,
  type ExperienceMode,
  type SubscriptionTierId,
} from "@/lib/platformData";

export interface AutomationWorkspaceViewProps {
  experienceMode: ExperienceMode;
  workflows: AutomationWorkflowItem[];
  onCreateWorkflow: (spec: {
    name: string;
    triggerKind: "cron" | "webhook" | "event";
    triggerSpec: string;
    tokenBudget: number;
  }) => void;
  onRunWorkflow: (workflowId: string) => void;
  onRetryFailedNode: (workflowId: string, nodeId: string) => void;
}

export function AutomationWorkspaceView({
  experienceMode,
  workflows,
  onCreateWorkflow,
  onRunWorkflow,
  onRetryFailedNode,
}: AutomationWorkspaceViewProps): React.JSX.Element {
  const [wfName, setWfName] = useState("");
  const [triggerKind, setTriggerKind] = useState<"cron" | "webhook" | "event">("cron");
  const [triggerSpec, setTriggerSpec] = useState("0 */6 * * *");
  const [tokenBudget, setTokenBudget] = useState(25000);

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!wfName.trim()) return;
    onCreateWorkflow({
      name: wfName.trim(),
      triggerKind,
      triggerSpec: triggerSpec.trim() || "manual",
      tokenBudget,
    });
    setWfName("");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Automation · KFlow DAG &amp; Scheduled Workflows
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Automate recurring business checks, notifications, and QA steps with visual progress and one-click retry."
              : "Compile durable KFlow DAG specifications with node dependency graphs, cron/webhook triggers, and token budgets."}
          </p>
        </div>
        <SemanticBadge kind="opencore" detail={`${workflows.length} KFlow DAGs`} />
      </div>

      <form
        onSubmit={handleAdd}
        aria-label="Create automation workflow"
        className="flex flex-wrap items-end gap-2.5 rounded-md border border-border-strong bg-surface p-3"
      >
        <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-xs text-fg-muted">
          <span>Workflow name</span>
          <input
            type="text"
            aria-label="Workflow name"
            value={wfName}
            onChange={(e) => setWfName(e.target.value)}
            placeholder="e.g. Daily Invoice Reconciliation DAG"
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Trigger type</span>
          <select
            aria-label="Workflow trigger type"
            value={triggerKind}
            onChange={(e) => setTriggerKind(e.target.value as "cron" | "webhook" | "event")}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
          >
            <option value="cron">Cron schedule</option>
            <option value="webhook">Webhook</option>
            <option value="event">Workspace event</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Schedule / route</span>
          <input
            type="text"
            aria-label="Trigger schedule or route"
            value={triggerSpec}
            onChange={(e) => setTriggerSpec(e.target.value)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Token budget</span>
          <input
            type="number"
            aria-label="Workflow token budget"
            value={tokenBudget}
            onChange={(e) => setTokenBudget(Number(e.target.value) || 10000)}
            className="min-h-ctrl-sm w-28 rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
          />
        </label>
        <Button type="submit" size="sm" variant="primary">
          + Create workflow
        </Button>
      </form>

      <section aria-label="Workflow DAG pipelines" className="space-y-3">
        <h2 className="sr-only">Configured Workflows</h2>
        {workflows.map((wf) => (
          <article
            key={wf.id}
            className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-teal-accent">{wf.id}</span>
                  <h3 className="text-sm font-semibold text-fg">{wf.name}</h3>
                  <SemanticBadge
                    kind={
                      wf.lastRunStatus === "passed"
                        ? "passed"
                        : wf.lastRunStatus === "failed"
                          ? "failed"
                          : wf.lastRunStatus === "running"
                            ? "running"
                            : "ready"
                    }
                  />
                </div>
                <div className="mt-0.5 font-mono text-[11px] text-fg-dim">
                  {`Trigger: ${wf.triggerKind.toUpperCase()} (${wf.triggerSpec}) · Budget: ${wf.tokenBudget.toLocaleString()} tok`}
                </div>
              </div>
              <Button size="sm" variant="secondary" onClick={() => onRunWorkflow(wf.id)}>
                Run workflow
              </Button>
            </div>

            <div className="grid gap-2 md:grid-cols-3">
              {wf.nodes.map((node) => (
                <div
                  key={node.id}
                  className="flex flex-col justify-between gap-2 rounded-sm border border-border bg-chrome p-2.5 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-1.5">
                      <span className="font-medium text-fg">{node.label}</span>
                      <SemanticBadge
                        kind={
                          node.status === "passed"
                            ? "passed"
                            : node.status === "failed"
                              ? "failed"
                              : "ready"
                        }
                      />
                    </div>
                    <div className="font-mono text-[10px] text-fg-dim">
                      {`Agent: ${node.agentId}${node.dependsOn.length ? ` · after ${node.dependsOn.join(", ")}` : ""}`}
                    </div>
                    {node.errorDetail ? (
                      <p className="rounded-xs border border-danger/40 bg-danger-subtle px-2 py-1 text-[11px] text-danger">
                        {node.errorDetail}
                      </p>
                    ) : null}
                  </div>
                  {node.status === "failed" ? (
                    <Button
                      size="sm"
                      variant="warning-cta"
                      onClick={() => onRetryFailedNode(wf.id, node.id)}
                    >
                      Retry failed step
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}

export interface OperationsWorkspaceViewProps {
  subscriptionTier: SubscriptionTierId;
  deployments: DeploymentEnvItem[];
  onConfirmP10Rollback: (deploymentId: string) => void;
}

export function OperationsWorkspaceView({
  subscriptionTier,
  deployments,
  onConfirmP10Rollback,
}: OperationsWorkspaceViewProps): React.JSX.Element {
  const [pendingRollbackId, setPendingRollbackId] = useState<string | null>(null);
  const [byomProvider, setByomProvider] = useState("Anthropic / OpenAI");
  const [byomCredType, setByomCredType] = useState<
    "api_key" | "self_hosted_endpoint" | "consumer_subscription"
  >("api_key");
  const [byomPreview, setByomPreview] = useState("sk-authorized-org-key");
  const [byomCheck, setByomCheck] = useState<ByomValidationResult | null>(null);

  const tier = SUBSCRIPTION_TIERS[subscriptionTier];
  const dailyUsed = 42_000;
  const dailyCap =
    typeof tier.dailyOpenWeightTokens === "number" ? tier.dailyOpenWeightTokens : 2_500_000;
  const quotaPct = Math.min(100, Math.round((dailyUsed / dailyCap) * 100));

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Operations · Deployments, Cost Governance &amp; SLOs
          </h1>
          <p className="text-xs text-fg-muted">
            Monitor managed deployments, P-10 human-confirmed rollbacks, OpenCore $0.00 local inference vs BYOM spend, and TTFT latency SLOs.
          </p>
        </div>
        <SemanticBadge kind="live" labelOverride={`Active Tier · ${tier.badgeLabel}`} />
      </div>

      {/* Explicit BYOM Consumer-Subscription Compliance Callout */}
      <CalloutBanner
        variant="spend-warn"
        title="BYOM Credential & Consumer-Subscription Compliance"
        description={BYOM_CONSUMER_COMPLIANCE_CALLOUT}
        safeStateNote="Keelway charges $0.00 token markup on authorized BYOM API keys and local OpenCore weights."
      />

      {/* Cost, Quota & SLO Cards */}
      <section aria-label="Cost quota and reliability SLOs" className="grid gap-4 md:grid-cols-3">
        <h2 className="sr-only">Spend, Quotas and Reliability SLOs</h2>
        <article className="space-y-2 rounded-md border border-border-strong bg-surface p-3.5">
          <h3 className="text-xs font-semibold text-fg">OpenCore vs BYOM Spend</h3>
          <div className="font-mono text-sm font-semibold text-teal-accent">
            Local OpenCore: $0.00 / tok
          </div>
          <div className="font-mono text-xs text-fg-muted">
            Authorized BYOM API: $4.18 vendor · $0.00 Keelway markup
          </div>
        </article>

        <article className="space-y-2 rounded-md border border-border-strong bg-surface p-3.5">
          <h3 className="text-xs font-semibold text-fg">Daily Open-Weight Pool Quota</h3>
          <div className="font-mono text-xs text-fg">
            {`${dailyUsed.toLocaleString()} / ${dailyCap.toLocaleString()} tokens (${tier.rpmLimit} RPM cap)`}
          </div>
          <div
            role="progressbar"
            aria-label="Daily open-weight token quota"
            aria-valuenow={quotaPct}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 w-full overflow-hidden rounded-xs bg-chrome"
          >
            <div className="h-full bg-teal-accent" style={{ width: `${quotaPct}%` }} />
          </div>
        </article>

        <article className="space-y-2 rounded-md border border-border-strong bg-surface p-3.5">
          <h3 className="text-xs font-semibold text-fg">Reliability &amp; Latency SLOs</h3>
          <div className="font-mono text-xs text-fg">TTFT p50: 148 ms · p95: 390 ms</div>
          <div className="font-mono text-xs text-ok">Runner Availability: 99.96% (SLO Met)</div>
        </article>
      </section>

      {/* Interactive BYOM Compliance Verifier */}
      <section
        aria-label="BYOM credential compliance verifier"
        className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
      >
        <h2 className="text-sm font-semibold text-fg">BYOM Connection Compliance Check</h2>
        <div className="flex flex-wrap items-end gap-2.5">
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Provider</span>
            <input
              type="text"
              aria-label="BYOM provider"
              value={byomProvider}
              onChange={(e) => setByomProvider(e.target.value)}
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>BYOM credential type</span>
            <select
              aria-label="BYOM credential type"
              value={byomCredType}
              onChange={(e) =>
                setByomCredType(
                  e.target.value as "api_key" | "self_hosted_endpoint" | "consumer_subscription",
                )
              }
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
            >
              <option value="api_key">Authorized Vendor API Key</option>
              <option value="self_hosted_endpoint">Self-Hosted vLLM / Ollama Endpoint</option>
              <option value="consumer_subscription">Consumer ChatGPT / Claude Web Subscription</option>
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
            <span>Key prefix or endpoint preview</span>
            <input
              type="text"
              aria-label="Key prefix or endpoint preview"
              value={byomPreview}
              onChange={(e) => setByomPreview(e.target.value)}
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
            />
          </label>
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              setByomCheck(validateByomCredentialClient(byomProvider, byomCredType, byomPreview))
            }
          >
            Verify BYOM compliance
          </Button>
        </div>
        {byomCheck ? (
          <div
            role={byomCheck.valid ? "status" : "alert"}
            className={`rounded-sm border px-3 py-2 text-xs ${
              byomCheck.valid
                ? "border-ok/40 bg-ok-subtle text-fg"
                : "border-danger/50 bg-danger-subtle text-fg"
            }`}
          >
            <code className="font-mono font-semibold">{byomCheck.code}</code> — {byomCheck.message}
          </div>
        ) : null}
      </section>

      {/* Managed Deployments & P-10 Human Rollback */}
      <section aria-label="Managed deployment environments" className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">Managed Environments &amp; P-10 Rollback</h2>
        <div className="space-y-2">
          {deployments.map((dep) => {
            const isConfirming = pendingRollbackId === dep.id;
            return (
              <article
                key={dep.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface px-3.5 py-2.5"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-semibold text-fg">{dep.environment}</h3>
                    <code className="font-mono text-xs text-teal-accent">{dep.version}</code>
                    <SemanticBadge
                      kind={dep.status === "rolled_back" ? "reconfirm" : "passed"}
                      labelOverride={
                        dep.status === "rolled_back"
                          ? "Rolled back with P-10 receipt"
                          : dep.status === "staging_ready"
                            ? "Staging Verified"
                            : "Healthy"
                      }
                    />
                  </div>
                  <div className="font-mono text-[11px] text-fg-dim">
                    {`${dep.url} · Last deploy: ${dep.lastDeployedAt}${dep.rollbackReceipt ? ` · ${dep.rollbackReceipt}` : ""}`}
                  </div>
                </div>

                {dep.id === "dep-prod" ? (
                  isConfirming ? (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setPendingRollbackId(null)}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        variant="warning-cta"
                        clickOnly
                        onClick={() => {
                          onConfirmP10Rollback(dep.id);
                          setPendingRollbackId(null);
                        }}
                      >
                        Confirm human P-10 rollback
                      </Button>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setPendingRollbackId(dep.id)}
                    >
                      Request P-10 rollback
                    </Button>
                  )
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
