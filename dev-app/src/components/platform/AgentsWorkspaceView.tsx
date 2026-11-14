import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type {
  ExperienceMode,
  LifecycleAgentItem,
  MultiAgentTeamItem,
} from "@/lib/platformData";

export interface AgentsWorkspaceViewProps {
  experienceMode: ExperienceMode;
  agents: LifecycleAgentItem[];
  teams: MultiAgentTeamItem[];
  onCreateCustomAgent: (agent: LifecycleAgentItem) => void;
  onDispatchTeam: (teamId: string) => void;
  onUpdateAgentModel: (agentId: string, modelId: string) => void;
  onJumpToIdeTask: (promptPrefill: string) => void;
}

export function AgentsWorkspaceView({
  experienceMode,
  agents,
  teams,
  onCreateCustomAgent,
  onDispatchTeam,
  onUpdateAgentModel,
  onJumpToIdeTask,
}: AgentsWorkspaceViewProps): React.JSX.Element {
  const [customName, setCustomName] = useState("");
  const [customRole, setCustomRole] = useState("");
  const [customInstructions, setCustomInstructions] = useState(
    "Review database migrations and require human P-10 approval before destructive DDL.",
  );
  const [customTools, setCustomTools] = useState("read_file, ast_graph, run_tests");
  const [customModel, setCustomModel] = useState("keelway-reasoner:14b");
  const [customP10, setCustomP10] = useState(true);
  const [searchFilter, setSearchFilter] = useState("");

  const filteredAgents = agents.filter((a) => {
    const q = searchFilter.trim().toLowerCase();
    if (!q) return true;
    return (
      a.name.toLowerCase().includes(q) ||
      a.roleTitle.toLowerCase().includes(q) ||
      a.stage.toLowerCase().includes(q)
    );
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = customName.trim();
    const cleanRole = customRole.trim();
    if (!cleanName || !cleanRole) return;
    const slug = cleanName.toLowerCase().replace(/[^a-z0-9-]+/g, "-");
    onCreateCustomAgent({
      id: `custom-${slug}-${Date.now()}`,
      name: cleanName,
      roleTitle: cleanRole,
      plainSummary: customInstructions.trim() || cleanRole,
      stage: "Custom Lifecycle",
      defaultModel: customModel,
      tools: customTools
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      requiresP10: customP10,
      promptVersion: "p-14",
      status: "ready",
      isCustom: true,
      instructions: customInstructions.trim(),
    });
    setCustomName("");
    setCustomRole("");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Specialized Lifecycle Agents &amp; Coordinated Teams
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Pick a ready-made specialist squad below to plan, build, test, and document your project with human approval safety."
              : "Builder mode: 12 built-in keelway.agent/v1 lifecycle agents + coordinated multi-agent swarms with scoped tool envelopes and P-10 gates."}
          </p>
        </div>
        <SemanticBadge kind="opencore" detail={`${agents.length} agents registered`} />
      </div>

      {/* Coordinated Multi-Agent Teams */}
      <section aria-label="Coordinated multi-agent teams" className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">Coordinated Multi-Agent Teams</h2>
        <div className="grid gap-3 lg:grid-cols-3">
          {teams.map((team) => (
            <article
              key={team.id}
              className="flex flex-col justify-between gap-3 rounded-md border border-border-strong bg-surface p-3.5"
            >
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
                    <span
                      key={m}
                      className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-teal-accent"
                    >
                      {m}
                    </span>
                  ))}
                </div>
                <div className="rounded-xs border border-ochre/35 bg-ochre-subtle/30 px-2 py-1 font-mono text-[10px] text-ochre">
                  {team.p10CheckpointLabel}
                </div>
                <ol className="space-y-1 pt-1 text-[11px] text-fg-muted">
                  {team.executionSteps.map((step) => (
                    <li key={step.id} className="flex items-center justify-between gap-2">
                      <span className="truncate">
                        <code className="font-mono text-fg">{step.agentId}</code>: {step.action}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] uppercase text-fg-dim">
                        {step.status.replace("_", " ")}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
              <div className="flex items-center justify-between gap-2 border-t border-border pt-2.5">
                <Button
                  size="sm"
                  variant="primary"
                  aria-label={`Dispatch team ${team.name}`}
                  onClick={() => onDispatchTeam(team.id)}
                >
                  Dispatch team
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => onJumpToIdeTask(`Coordinate ${team.name} on current branch: `)}
                >
                  Open in IDE
                </Button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* 12 Specialized Lifecycle Agents */}
      <section aria-label="Lifecycle agents catalog" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">
            {`Lifecycle Agents (${filteredAgents.length})`}
          </h2>
          <input
            type="search"
            aria-label="Filter lifecycle agents"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Filter by agent, role, or SDLC stage…"
            className="min-h-ctrl-sm w-64 rounded-sm border border-border-control bg-surface px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim"
          />
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filteredAgents.map((agent) => (
            <article
              key={agent.id}
              className="flex flex-col justify-between gap-2.5 rounded-md border border-border bg-surface p-3"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-mono text-xs font-semibold text-fg">{agent.name}</h3>
                  <SemanticBadge
                    kind={agent.status === "needs_approval" ? "needs-approval" : "ready"}
                  />
                </div>
                <div className="text-xs font-medium text-teal-accent">{agent.roleTitle}</div>
                <p className="text-xs text-fg-muted">{agent.plainSummary}</p>
                {experienceMode === "builder" ? (
                  <div className="flex flex-wrap gap-1 pt-0.5">
                    <span className="rounded-xs bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-dim">
                      {agent.stage}
                    </span>
                    <span className="rounded-xs bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-dim">
                      {`prompt:${agent.promptVersion}`}
                    </span>
                    {agent.tools.map((tool) => (
                      <code
                        key={tool}
                        className="rounded-xs border border-border px-1 py-0.5 font-mono text-[10px] text-fg-muted"
                      >
                        {tool}
                      </code>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
                <select
                  aria-label={`Model route for ${agent.name}`}
                  value={agent.defaultModel}
                  onChange={(e) => onUpdateAgentModel(agent.id, e.target.value)}
                  className="rounded-xs border border-border-control bg-canvas px-1.5 py-0.5 font-mono text-[11px] text-fg"
                >
                  <option value="keelway-core:7b">keelway-core:7b (Local)</option>
                  <option value="keelway-reasoner:14b">keelway-reasoner:14b (Local)</option>
                  <option value="byom:authorized-api">byom:authorized-api (0% Markup)</option>
                </select>
                <span className="font-mono text-[10px] text-fg-dim">
                  {agent.requiresP10 ? "P-10 Human Gate" : "Read/Plan Scope"}
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Custom Agent Forge Form */}
      <section
        aria-label="Create custom lifecycle agent"
        className="rounded-md border border-border-strong bg-surface p-4"
      >
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
                <option value="keelway-core:7b">keelway-core:7b</option>
                <option value="keelway-reasoner:14b">keelway-reasoner:14b</option>
              </select>
            </label>
            <label className="inline-flex items-center gap-1.5 text-xs text-fg">
              <input
                type="checkbox"
                checked={customP10}
                onChange={(e) => setCustomP10(e.target.checked)}
              />
              <span>Require P-10 human gate on mutations</span>
            </label>
            <Button type="submit" size="sm" variant="primary">
              Create custom agent
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}
