import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type {
  ExperienceMode,
  LifecycleAgentItem,
  PmIssueItem,
  PmIssuePriority,
  PmIssueStatus,
  ProductPrdItem,
  UserFeedbackItem,
} from "@/lib/platformData";

export interface ProjectManagerViewProps {
  experienceMode: ExperienceMode;
  issues: PmIssueItem[];
  agents: LifecycleAgentItem[];
  onCreateIssue: (issue: { title: string; priority: PmIssuePriority; assignedAgentId: string }) => void;
  onUpdateIssueStatus: (issueId: string, status: PmIssueStatus) => void;
  onDelegateIssueToAgent: (issueId: string) => void;
}

export function ProjectManagerView({
  experienceMode,
  issues,
  agents,
  onCreateIssue,
  onUpdateIssueStatus,
  onDelegateIssueToAgent,
}: ProjectManagerViewProps): React.JSX.Element {
  const [statusFilter, setStatusFilter] = useState<PmIssueStatus | "all">("all");
  const [newTitle, setNewTitle] = useState("");
  const [newPriority, setNewPriority] = useState<PmIssuePriority>("high");
  const [newAgent, setNewAgent] = useState(agents[0]?.id ?? "feature-coder");

  const visibleIssues = issues.filter((iss) =>
    statusFilter === "all" ? true : iss.status === statusFilter,
  );

  const handleSubmitIssue = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    onCreateIssue({
      title: newTitle.trim(),
      priority: newPriority,
      assignedAgentId: newAgent,
    });
    setNewTitle("");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Project Manager · Linear-Style Issues &amp; Sprints
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Track every milestone in plain English and click 'Delegate to Agent' to assign work automatically."
              : "Shared issue board synchronized with PRDs, git branches, lifecycle agents, and P-10 verification gates."}
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-fg-muted">
          <span className="rounded-xs border border-border bg-surface px-2 py-1">
            Sprint 14 · Sovereign Platform
          </span>
          <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-2 py-1 text-teal-accent">
            Milestone: v1.1 Unified GA
          </span>
        </div>
      </div>

      {/* Filter Strip & Create Issue Form */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Filter issues by status" className="flex flex-wrap gap-1">
          {(["all", "backlog", "todo", "in_progress", "in_review", "done"] as const).map((st) => (
            <button
              key={st}
              type="button"
              aria-pressed={statusFilter === st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium capitalize ${
                statusFilter === st
                  ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
                  : "border-border bg-surface text-fg-muted hover:text-fg"
              }`}
            >
              {st.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <form
        onSubmit={handleSubmitIssue}
        aria-label="Create sprint issue"
        className="flex flex-wrap items-end gap-2.5 rounded-md border border-border-strong bg-surface p-3"
      >
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-xs text-fg-muted">
          <span>New issue title</span>
          <input
            type="text"
            aria-label="New issue title"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Add Linear-style issue to active sprint…"
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Priority</span>
          <select
            aria-label="New issue priority"
            value={newPriority}
            onChange={(e) => setNewPriority(e.target.value as PmIssuePriority)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
          >
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Assign lifecycle agent</span>
          <select
            aria-label="Assign lifecycle agent"
            value={newAgent}
            onChange={(e) => setNewAgent(e.target.value)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" size="sm" variant="primary">
          + Create issue
        </Button>
      </form>

      {/* Issues List */}
      <section aria-label="Sprint issues list" className="space-y-2">
        <h2 className="sr-only">Active Sprint Issues</h2>
        {visibleIssues.map((issue) => (
          <article
            key={issue.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface px-3.5 py-2.5"
          >
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold text-teal-accent">{issue.id}</span>
                <h3 className="text-xs font-semibold text-fg">{issue.title}</h3>
                <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] uppercase text-fg-muted">
                  {issue.priority}
                </span>
                {issue.status === "in_progress" ? (
                  <SemanticBadge kind="running" labelOverride="Delegated · In Progress" />
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-fg-dim">
                <span>{issue.sprint}</span>
                <span aria-hidden="true">·</span>
                <span>{issue.milestone}</span>
                {issue.assignedAgentId ? (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="text-fg-muted">{`Agent: ${issue.assignedAgentId}`}</span>
                  </>
                ) : null}
                {issue.dependencies.length > 0 ? (
                  <span className="rounded-xs border border-warning/40 bg-warning-subtle px-1.5 py-0.5 text-[10px] text-warning">
                    {`Depends on ${issue.dependencies.join(", ")}`}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <select
                aria-label={`Status for ${issue.id}`}
                value={issue.status}
                onChange={(e) => onUpdateIssueStatus(issue.id, e.target.value as PmIssueStatus)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
              >
                <option value="backlog">Backlog</option>
                <option value="todo">Todo</option>
                <option value="in_progress">In Progress</option>
                <option value="in_review">In Review</option>
                <option value="done">Done</option>
              </select>
              <Button
                size="sm"
                variant="secondary"
                aria-label={`Delegate to Agent for ${issue.id}`}
                onClick={() => onDelegateIssueToAgent(issue.id)}
              >
                Delegate to Agent
              </Button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}

export interface ProductWorkspaceViewProps {
  experienceMode: ExperienceMode;
  prds: ProductPrdItem[];
  feedback: UserFeedbackItem[];
  onToggleCriterion: (prdId: string, criterionId: string) => void;
  onJumpToPm: () => void;
}

export function ProductWorkspaceView({
  experienceMode,
  prds,
  feedback,
  onToggleCriterion,
  onJumpToPm,
}: ProductWorkspaceViewProps): React.JSX.Element {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Product Discovery, PRDs &amp; Release Plans
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Review product goals, check off acceptance criteria, and see which sprint tasks deliver each feature."
              : "Structured PRDs with RICE prioritization, executable acceptance criteria, user feedback evidence, and linked KEEL sprint issues."}
          </p>
        </div>
        <SemanticBadge kind="live" labelOverride={`${prds.length} Active PRDs`} />
      </div>

      {/* PRDs Grid */}
      <section aria-label="Product requirement documents" className="grid gap-4 lg:grid-cols-2">
        <h2 className="sr-only">Structured PRDs</h2>
        {prds.map((prd) => (
          <article
            key={prd.id}
            className="flex flex-col justify-between gap-3 rounded-md border border-border-strong bg-surface p-4"
          >
            <div className="space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs font-semibold text-teal-accent">{prd.id}</span>
                <div className="flex items-center gap-1.5">
                  <span className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg">
                    {`RICE ${prd.riceScore}`}
                  </span>
                  <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-1.5 py-0.5 font-mono text-[10px] uppercase text-teal-accent">
                    {prd.releaseStage.replace("_", " ")}
                  </span>
                </div>
              </div>
              <h3 className="text-sm font-semibold text-fg">{prd.title}</h3>
              <p className="text-xs text-fg-muted">{prd.problemStatement}</p>

              <div className="space-y-1.5 pt-1">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-fg-dim">
                  Acceptance Criteria
                </div>
                {prd.acceptanceCriteria.map((ac) => (
                  <label key={ac.id} className="flex items-start gap-2 text-xs text-fg">
                    <input
                      type="checkbox"
                      checked={ac.met}
                      onChange={() => onToggleCriterion(prd.id, ac.id)}
                      className="mt-0.5"
                    />
                    <span>{ac.text}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2.5">
              <div className="flex flex-wrap items-center gap-1">
                <span className="text-[11px] text-fg-dim">Linked issues:</span>
                {prd.linkedIssueIds.map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={onJumpToPm}
                    className="rounded-xs border border-border-control bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-teal-accent hover:bg-surface-elevated"
                  >
                    {id}
                  </button>
                ))}
              </div>
            </div>
          </article>
        ))}
      </section>

      {/* User Feedback & Prioritization Log */}
      <section aria-label="User feedback log" className="space-y-2.5">
        <h2 className="text-sm font-semibold text-fg">Customer Discovery &amp; Feedback Log</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {feedback.map((item) => (
            <article key={item.id} className="rounded-md border border-border bg-surface p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-fg">{item.persona}</span>
                <span className="font-mono text-[11px] text-teal-accent">
                  {`Impact ${item.impactScore}/10 · ${item.linkedPrdId}`}
                </span>
              </div>
              <p className="mt-1.5 text-xs text-fg-muted">{`“${item.quote}”`}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
