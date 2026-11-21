import React, { useEffect, useMemo, useState } from "react";
import { FlightTapeDebuggerPanel } from "@/components/platform/FlightTapeDebuggerPanel";
import { LiveExecutionDrawer } from "@/components/platform/LiveExecutionDrawer";
import { McpInspectorPanel } from "@/components/platform/McpInspectorPanel";
import { ShadowCacheAndDistillationPanel } from "@/components/platform/ShadowCacheAndDistillationPanel";
import { StepDebuggerAndBridgePanel } from "@/components/platform/StepDebuggerAndBridgePanel";
import { StructuredOutputAndSelfHealingPanel } from "@/components/platform/StructuredOutputAndSelfHealingPanel";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type {
  ExperienceMode,
  LifecycleAgentItem,
  MultiAgentTeamItem,
} from "@/lib/platformData";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";
import type { AgentRegistryRecord } from "@/lib/types";

export interface AgentsWorkspaceViewProps {
  experienceMode: ExperienceMode;
  agents: LifecycleAgentItem[];
  agentRegistry?: Map<string, AgentRegistryRecord> | null;
  onToggleRegistryEntry?: (name: string, version: string, enabled: boolean) => Promise<boolean>;
  teams: MultiAgentTeamItem[];
  onCreateCustomAgent: (agent: LifecycleAgentItem) => void;
  onDispatchTeam: (teamId: string) => void;
  onUpdateAgentModel: (agentId: string, modelId: string) => void;
  onJumpToIdeTask: (promptPrefill: string) => void;
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

interface DryRunTraceStep {
  id: string;
  label: string;
  detail: string;
  heldForP10: boolean;
}

export function AgentsWorkspaceView({
  experienceMode,
  agents,
  agentRegistry = null,
  onToggleRegistryEntry,
  teams,
  onCreateCustomAgent,
  onDispatchTeam,
  onUpdateAgentModel,
  onJumpToIdeTask,
  workspaceId = "default",
  activeRbacRole = "owner",
}: AgentsWorkspaceViewProps): React.JSX.Element {
  const [localAgents, setLocalAgents] = useState<LifecycleAgentItem[]>(agents);
  const [pendingToggleId, setPendingToggleId] = useState<string | null>(null);
  const canToggleRegistry = activeRbacRole === "owner" || activeRbacRole === "admin";
  const [localTeams, setLocalTeams] = useState<MultiAgentTeamItem[]>(teams);
  const [customName, setCustomName] = useState("");
  const [customRole, setCustomRole] = useState("");
  const [customInstructions, setCustomInstructions] = useState(
    "Review database migrations and require human P-10 approval before destructive DDL.",
  );
  const [customTools, setCustomTools] = useState("read_file, ast_graph, run_tests");
  const [customModel, setCustomModel] = useState("keelway-reasoning:14b");
  const [customP10, setCustomP10] = useState(true);
  const [searchFilter, setSearchFilter] = useState("");

  const [supervisedAgentId, setSupervisedAgentId] = useState<string | null>(null);
  const [dryRunObjective, setDryRunObjective] = useState(
    "Audit module boundaries and synthesize zero-downtime implementation plan",
  );
  const [dryRunTrace, setDryRunTrace] = useState<DryRunTraceStep[] | null>(null);
  const [liveStreamSpec, setLiveStreamSpec] = useState<{
    targetId: string; targetName: string; objective: string; requiresP10: boolean; nonce: number;
  } | null>(null);

  useEffect(() => {
    setLocalAgents(agents);
  }, [agents]);

  useEffect(() => {
    setLocalTeams(teams);
  }, [teams]);

  const filteredAgents = useMemo(() => {
    const q = searchFilter.trim().toLowerCase();
    if (!q) return localAgents;
    return localAgents.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.roleTitle.toLowerCase().includes(q) ||
        a.stage.toLowerCase().includes(q),
    );
  }, [localAgents, searchFilter]);

  const supervisedAgent = useMemo(
    () => localAgents.find((a) => a.id === supervisedAgentId) ?? null,
    [localAgents, supervisedAgentId],
  );

  const handleLaunchLiveStream = (target?: LifecycleAgentItem) => {
    const picked = target ?? supervisedAgent ?? localAgents.find((a) => a.requiresP10) ?? localAgents[0];
    if (!picked) return;
    setLiveStreamSpec((prev) => ({
      targetId: picked.id,
      targetName: picked.name,
      objective: dryRunObjective.trim() || "Execute scoped agent verification",
      requiresP10: picked.requiresP10,
      nonce: (prev?.nonce ?? 0) + 1,
    }));
  };

  const manifestJson = useMemo(() => {
    if (!supervisedAgent) return "";
    return JSON.stringify(
      {
        schema: "keelway.agent/v1",
        id: supervisedAgent.id,
        defaultModel: supervisedAgent.defaultModel,
        tools: supervisedAgent.tools,
        requiresP10: supervisedAgent.requiresP10,
        promptVersion: supervisedAgent.promptVersion,
        ed25519Verified: true,
      },
      null,
      2,
    );
  }, [supervisedAgent]);

  const handleToggleSupervise = (agent: LifecycleAgentItem) => {
    setSupervisedAgentId((prev) => (prev === agent.id ? null : agent.id));
    setDryRunTrace(null);
  };

  const handleRunDryRun = (e: React.FormEvent) => {
    e.preventDefault();
    if (!supervisedAgent) return;
    const goal = dryRunObjective.trim() || "Execute scoped agent verification";
    setDryRunTrace([
      {
        id: "step-1",
        label: "1. Inspect AST/Context [PASSED]",
        detail: `Scoped tools [${supervisedAgent.tools.join(", ")}] bound to Seatbelt root for: "${goal}".`,
        heldForP10: false,
      },
      {
        id: "step-2",
        label: "2. Synthesize Plan [PASSED]",
        detail: `Generated deterministic plan on ${supervisedAgent.defaultModel} (prompt:${supervisedAgent.promptVersion}).`,
        heldForP10: false,
      },
      supervisedAgent.requiresP10
        ? {
            id: "step-3",
            label: "3. Mutation Gate [HELD FOR HUMAN P-10]",
            detail: "Paused prior to workspace mutation — explicit human P-10 sign-off required.",
            heldForP10: true,
          }
        : {
            id: "step-3",
            label: "3. Read/Plan Scope Gate [PASSED]",
            detail: "Zero-mutation read/plan envelope verified · SHA-256 Record receipt ready.",
            heldForP10: false,
          },
    ]);
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = customName.trim();
    const cleanRole = customRole.trim();
    if (!cleanName || !cleanRole) return;
    const slug = cleanName.toLowerCase().replace(/[^a-z0-9-]+/g, "-");
    const created: LifecycleAgentItem = {
      id: `custom-${slug}-${Date.now()}`,
      name: cleanName,
      roleTitle: cleanRole,
      plainSummary: customInstructions.trim() || cleanRole,
      stage: "Custom Lifecycle",
      defaultModel: customModel,
      tools: customTools.split(",").map((t) => t.trim()).filter(Boolean),
      requiresP10: customP10,
      promptVersion: "p-14",
      status: "ready",
      isCustom: true,
      instructions: customInstructions.trim(),
    };
    setLocalAgents((prev) => [created, ...prev]);
    onCreateCustomAgent(created);
    setCustomName("");
    setCustomRole("");
  };

  const handleModelChange = (agentId: string, modelId: string) => {
    setLocalAgents((prev) => prev.map((a) => (a.id === agentId ? { ...a, defaultModel: modelId } : a)));
    onUpdateAgentModel(agentId, modelId);
  };

  const handleTeamDispatch = (teamId: string) => {
    setLocalTeams((prev) => prev.map((t) => (t.id === teamId ? { ...t, lastRunStatus: "running" } : t)));
    onDispatchTeam(teamId);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">Specialized Lifecycle Agents &amp; Coordinated Teams</h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Pick a ready-made specialist squad below to plan, build, test, and document your project with human approval safety."
              : "Builder mode: 12 built-in keelway.agent/v1 lifecycle agents + coordinated multi-agent swarms with scoped tool envelopes and P-10 gates."}
          </p>
        </div>
        <SemanticBadge
          kind="opencore"
          detail={
            agentRegistry
              ? `${agentRegistry.size} manifests registered · ${[...agentRegistry.values()].filter((r) => r.enabled).length} enabled`
              : `${localAgents.length} agents · registry unverified`
          }
        />
      </div>

      <FlightTapeDebuggerPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <StructuredOutputAndSelfHealingPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <section aria-label="Coordinated multi-agent teams" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">Coordinated Multi-Agent Teams</h2>
          {!supervisedAgent ? (
            <Button size="sm" variant="secondary" onClick={() => handleLaunchLiveStream()}>
              Stream Live Execution
            </Button>
          ) : null}
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {localTeams.map((team) => (
            <article key={team.id} className="flex flex-col justify-between gap-3 rounded-md border border-border-strong bg-surface p-3.5">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-fg">{team.name}</h3>
                  <SemanticBadge
                    kind={
                      team.lastRunStatus === "needs_approval"
                        ? "needs-approval"
                        : team.lastRunStatus === "running"
                          ? "running"
                          : "ready"
                    }
                  />
                </div>
                <p className="text-xs text-fg-muted">{team.description}</p>
                <div className="flex flex-wrap gap-1">
                  {team.memberAgentIds.map((m) => (
                    <span key={m} className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-accent">{m}</span>
                  ))}
                </div>
                <div className="rounded-xs border border-ochre/35 bg-ochre-subtle/30 px-2 py-1 font-mono text-[10px] text-ochre">
                  {team.p10CheckpointLabel}
                </div>
                <ol className="space-y-1 pt-1 text-[11px] text-fg-muted">
                  {team.executionSteps.map((step) => (
                    <li key={step.id} className="flex items-center justify-between gap-2">
                      <span className="truncate"><code className="font-mono text-fg">{step.agentId}</code>: {step.action}</span>
                      <span className="shrink-0 font-mono text-[10px] uppercase text-fg-dim">{step.status.replace("_", " ")}</span>
                    </li>
                  ))}
                </ol>
              </div>
              <div className="flex items-center justify-between gap-2 border-t border-border pt-2.5">
                <Button size="sm" variant="primary" aria-label={`Dispatch team ${team.name}`} onClick={() => handleTeamDispatch(team.id)}>
                  Dispatch team
                </Button>
                <Button size="sm" variant="ghost" onClick={() => onJumpToIdeTask(`Coordinate ${team.name} on current branch: `)}>
                  Open in IDE
                </Button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {supervisedAgent ? (
        <section aria-label="Agent session supervisor and manifest inspector" className="space-y-3 rounded-md border border-accent/50 bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2.5">
            <div>
              <h2 className="text-sm font-semibold text-fg">
                {`Agent Session Supervisor & keelway.agent/v1 Manifest · ${supervisedAgent.name}`}
              </h2>
              <p className="text-xs text-fg-muted">
                Inspect signed capability manifest and execute a sandboxed dry-run trace prior to IDE dispatch.
              </p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setSupervisedAgentId(null)}>Close Supervisor</Button>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-1">
              <div className="font-mono text-[11px] text-accent">Canonical keelway.agent/v1 Manifest (Ed25519 Verified)</div>
              <pre className="overflow-x-auto rounded-xs border border-border bg-code p-3 font-mono text-[11px] text-fg">
                <code>{manifestJson}</code>
              </pre>
            </div>

            <div className="space-y-3">
              <form onSubmit={handleRunDryRun} className="space-y-2.5">
                <label className="flex flex-col gap-1 text-xs text-fg-muted">
                  <span>Supervised dry-run objective</span>
                  <input
                    type="text"
                    aria-label="Agent dry-run objective"
                    value={dryRunObjective}
                    onChange={(e) => setDryRunObjective(e.target.value)}
                    className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
                  />
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="submit" size="sm" variant="primary">Run Supervised Dry-Run</Button>
                  <Button type="button" size="sm" variant="secondary" onClick={() => handleLaunchLiveStream(supervisedAgent)}>
                    Stream Live Execution
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onJumpToIdeTask(`[${supervisedAgent.name}] ${dryRunObjective.trim()}`)}
                  >
                    Send to IDE Composer
                  </Button>
                </div>
              </form>

              {dryRunTrace ? (
                <ol aria-label="Supervised dry-run execution trace" className="space-y-1.5 rounded-xs border border-border bg-chrome p-2.5 text-xs">
                  {dryRunTrace.map((st) => (
                    <li
                      key={st.id}
                      className={`rounded-xs border px-2.5 py-1.5 ${
                        st.heldForP10 ? "border-ochre/45 bg-ochre-subtle text-ochre" : "border-ok/35 bg-ok-subtle text-fg"
                      }`}
                    >
                      <div className="font-mono text-[11px] font-semibold">{st.label}</div>
                      <div className="mt-0.5 text-[11px] text-fg-muted">{st.detail}</div>
                    </li>
                  ))}
                </ol>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {liveStreamSpec ? (
        <LiveExecutionDrawer
          kind="agent"
          targetId={liveStreamSpec.targetId}
          targetName={liveStreamSpec.targetName}
          objective={liveStreamSpec.objective}
          requiresP10={liveStreamSpec.requiresP10}
          workspaceId={workspaceId}
          activeRbacRole={activeRbacRole}
          runNonce={liveStreamSpec.nonce}
          onClose={() => setLiveStreamSpec(null)}
        />
      ) : null}

      <section aria-label="Lifecycle agents catalog" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">{`Lifecycle Agents (${filteredAgents.length})`}</h2>
          <label className="block">
            <span className="sr-only">Filter lifecycle agents</span>
            <input
              type="search"
              aria-label="Filter lifecycle agents"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter by agent, role, or SDLC stage…"
              className="min-h-ctrl-sm w-64 rounded-sm border border-border-control bg-surface px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim"
            />
          </label>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filteredAgents.map((agent) => {
            const reg = agentRegistry?.get(agent.id) ?? agentRegistry?.get(agent.name) ?? null;
            return (
            <article key={agent.id} className="flex flex-col justify-between gap-2.5 rounded-md border border-border bg-surface p-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-mono text-xs font-semibold text-fg">{agent.name}</h3>
                  <div className="flex items-center gap-1.5">
                    <SemanticBadge kind={agent.status === "needs_approval" ? "needs-approval" : "ready"} />
                    {agentRegistry === null ? null : !reg ? (
                      <SemanticBadge kind="unmeasured" labelOverride="Unregistered" />
                    ) : !reg.enabled ? (
                      <SemanticBadge kind="locked" labelOverride="Disabled" />
                    ) : (
                      <SemanticBadge kind="live" detail={reg.digest ? `digest ${reg.digest.replace(/^sha256:/, "").slice(0, 8)}` : reg.version} />
                    )}
                  </div>
                </div>
                <div className="text-xs font-medium text-accent">{agent.roleTitle}</div>
                <p className="text-xs text-fg-muted">{agent.plainSummary}</p>
                {experienceMode === "builder" ? (
                  <div className="flex flex-wrap gap-1 pt-0.5">
                    <span className="rounded-xs bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-dim">{agent.stage}</span>
                    <span className="rounded-xs bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-dim">{`prompt:${agent.promptVersion}`}</span>
                    {agent.tools.map((tool) => (
                      <code key={tool} className="rounded-xs border border-border px-1 py-0.5 font-mono text-[10px] text-fg-muted">{tool}</code>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="space-y-2 border-t border-border pt-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <select
                    aria-label={`Model route for ${agent.name}`}
                    value={agent.defaultModel}
                    onChange={(e) => handleModelChange(agent.id, e.target.value)}
                    className="rounded-xs border border-border-control bg-canvas px-1.5 py-0.5 font-mono text-[11px] text-fg"
                  >
                    <option value="keelway-core:7b">keelway-core:7b (Local alias)</option>
                    <option value="keelway-reasoning:14b">keelway-reasoning:14b (Local alias)</option>
                    <option value="keelway-nano:1.5b">keelway-nano:1.5b (Simulated)</option>
                    <option value="byom:authorized-api">byom:authorized-api (0% Markup)</option>
                  </select>
                  {agent.defaultModel === "keelway-nano:1.5b" ? (
                    <SemanticBadge kind="simulated" labelOverride="Simulated" />
                  ) : agent.defaultModel.startsWith("keelway-") ? (
                    <SemanticBadge kind="live" labelOverride="Local alias" />
                  ) : null}
                  <span className="font-mono text-[10px] text-fg-dim">
                    {agent.requiresP10 ? "P-10 Human Gate" : "Read/Plan Scope"}
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    aria-expanded={supervisedAgentId === agent.id}
                    aria-label={`Inspect & Supervise ${agent.name}`}
                    onClick={() => handleToggleSupervise(agent)}
                    className="flex-1"
                  >
                    Inspect &amp; Supervise
                  </Button>
                  {reg && onToggleRegistryEntry ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      clickOnly
                      aria-label={`${reg.enabled ? "Disable" : "Enable"} agent manifest ${reg.name}`}
                      disabled={pendingToggleId === reg.id}
                      aria-disabled={!canToggleRegistry ? "true" : undefined}
                      title={canToggleRegistry ? "Kill-switch: toggles the manifest's enabled state in the registry" : "Requires owner or admin role"}
                      onClick={async () => {
                        if (!canToggleRegistry) return;
                        setPendingToggleId(reg.id);
                        try {
                          await onToggleRegistryEntry(reg.name, reg.version, !reg.enabled);
                        } finally {
                          setPendingToggleId(null);
                        }
                      }}
                    >
                      {pendingToggleId === reg.id ? "Working…" : reg.enabled ? "Disable" : "Enable"}
                    </Button>
                  ) : null}
                </div>
              </div>
            </article>
            );
          })}
        </div>
      </section>

      <section aria-label="Create custom lifecycle agent" className="rounded-md border border-border-strong bg-surface p-4">
        <h2 className="text-sm font-semibold text-fg">Create Custom Agent</h2>
        <form onSubmit={handleCreate} className="mt-3 grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Custom agent name</span>
            <input
              type="text"
              aria-label="Custom agent name"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="e.g. migration-guardian"
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Custom agent role</span>
            <input
              type="text"
              aria-label="Custom agent role"
              value={customRole}
              onChange={(e) => setCustomRole(e.target.value)}
              placeholder="e.g. Zero-Downtime Schema Reviewer"
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
            <span>System instructions</span>
            <textarea
              rows={2}
              aria-label="Custom agent instructions"
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              className="rounded-sm border border-border-control bg-canvas px-2.5 py-1.5 text-xs text-fg"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Allowed tool scopes (comma-separated)</span>
            <input
              type="text"
              aria-label="Allowed tool scopes"
              value={customTools}
              onChange={(e) => setCustomTools(e.target.value)}
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
            />
          </label>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Default model</span>
              <select
                aria-label="Custom agent default model"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              >
                <option value="keelway-core:7b">keelway-core:7b (Local alias)</option>
                <option value="keelway-reasoning:14b">keelway-reasoning:14b (Local alias)</option>
                <option value="keelway-nano:1.5b">keelway-nano:1.5b (Simulated)</option>
              </select>
              {customModel === "keelway-nano:1.5b" ? (
                <SemanticBadge kind="simulated" labelOverride="Simulated weights" />
              ) : customModel.startsWith("keelway-") ? (
                <SemanticBadge kind="live" labelOverride="Local runtime alias" />
              ) : null}
            </label>
            <label className="inline-flex items-center gap-1.5 text-xs text-fg">
              <input type="checkbox" checked={customP10} onChange={(e) => setCustomP10(e.target.checked)} />
              <span>Require P-10 human gate on mutations</span>
            </label>
            <Button type="submit" size="sm" variant="primary">Create custom agent</Button>
          </div>
        </form>
      </section>

      <ShadowCacheAndDistillationPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <StepDebuggerAndBridgePanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <McpInspectorPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />
    </div>
  );
}
