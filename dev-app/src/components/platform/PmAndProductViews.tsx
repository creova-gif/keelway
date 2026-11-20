import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
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
  prds?: ProductPrdItem[];
  onCreateIssue: (issue: { title: string; priority: PmIssuePriority; assignedAgentId: string }) => void;
  onUpdateIssueStatus: (issueId: string, status: PmIssueStatus) => void;
  onDelegateIssueToAgent: (issueId: string) => void;
  onUpdateIssueDetails?: (
    issueId: string,
    updates: { description?: string; dependencies?: string[]; linkedPrdId?: string },
  ) => void;
  onOpenInIde?: (prefill: string) => void;
}

interface LocalIssuePatch {
  description?: string;
  dependencies?: string[];
  linkedPrdId?: string;
}

const CTRL_CLS = "min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg";
const KANBAN_COLUMNS: ReadonlyArray<{ id: PmIssueStatus; label: string }> = [
  { id: "backlog", label: "Backlog" },
  { id: "todo", label: "Todo" },
  { id: "in_progress", label: "In Progress" },
  { id: "in_review", label: "In Review" },
  { id: "done", label: "Done" },
];

export function ProjectManagerView({
  experienceMode,
  issues,
  agents,
  prds,
  onCreateIssue,
  onUpdateIssueStatus,
  onDelegateIssueToAgent,
  onUpdateIssueDetails,
  onOpenInIde,
}: ProjectManagerViewProps): React.JSX.Element {
  const [layout, setLayout] = useState<"list" | "kanban">("list");
  const [statusFilter, setStatusFilter] = useState<PmIssueStatus | "all">("all");
  const [localIssues, setLocalIssues] = useState<PmIssueItem[]>(issues);
  const [patchesById, setPatchesById] = useState<Record<string, LocalIssuePatch>>({});
  const [inspectedIssueId, setInspectedIssueId] = useState<string | null>(null);
  const [ideDispatchedId, setIdeDispatchedId] = useState<string | null>(null);
  const [savedInspectId, setSavedInspectId] = useState<string | null>(null);

  const [newTitle, setNewTitle] = useState("");
  const [newPriority, setNewPriority] = useState<PmIssuePriority>("high");
  const [newAgent, setNewAgent] = useState(agents[0]?.id ?? "feature-coder");

  const [draftDesc, setDraftDesc] = useState("");
  const [draftDeps, setDraftDeps] = useState("");
  const [draftPrd, setDraftPrd] = useState("PRD-01");

  useEffect(() => {
    setLocalIssues(issues);
  }, [issues]);

  const enrichedIssues = useMemo(
    () =>
      localIssues.map((iss) => {
        const p = patchesById[iss.id];
        return {
          ...iss,
          dependencies: p?.dependencies ?? iss.dependencies,
          linkedPrdId: p?.linkedPrdId ?? iss.linkedPrdId,
          description: p?.description ?? `Deliver ${iss.title} under Seatbelt isolation with SHA-256 Record provenance.`,
        };
      }),
    [localIssues, patchesById],
  );

  const visibleIssues = useMemo(
    () => enrichedIssues.filter((iss) => (statusFilter === "all" ? true : iss.status === statusFilter)),
    [enrichedIssues, statusFilter],
  );

  const doneCount = useMemo(() => enrichedIssues.filter((iss) => iss.status === "done").length, [enrichedIssues]);
  const totalCount = enrichedIssues.length;
  const velocityPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;
  const inspectedIssue = useMemo(() => enrichedIssues.find((i) => i.id === inspectedIssueId) ?? null, [enrichedIssues, inspectedIssueId]);

  const knownPrdIds = useMemo(() => {
    const set = new Set<string>(["PRD-01", "PRD-02"]);
    prds?.forEach((p) => set.add(p.id));
    enrichedIssues.forEach((i) => { if (i.linkedPrdId) set.add(i.linkedPrdId); });
    return Array.from(set);
  }, [enrichedIssues, prds]);

  const openInspector = (iss: (typeof enrichedIssues)[number]) => {
    if (inspectedIssueId === iss.id) {
      setInspectedIssueId(null);
      return;
    }
    setInspectedIssueId(iss.id);
    setDraftDesc(iss.description);
    setDraftDeps(iss.dependencies.join(", "));
    setDraftPrd(iss.linkedPrdId ?? "PRD-01");
    setSavedInspectId(null);
  };

  const handleSaveInspector = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inspectedIssue) return;
    const deps = draftDeps.split(",").map((d) => d.trim()).filter(Boolean);
    const updates: LocalIssuePatch = { description: draftDesc, dependencies: deps, linkedPrdId: draftPrd.trim() || undefined };
    setPatchesById((prev) => ({ ...prev, [inspectedIssue.id]: updates }));
    setSavedInspectId(inspectedIssue.id);
    onUpdateIssueDetails?.(inspectedIssue.id, updates);
  };

  const handleSubmitIssue = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = newTitle.trim();
    if (!clean) return;
    setLocalIssues((prev) => [
      {
        id: `KEEL-${105 + prev.length}`,
        title: clean,
        status: "todo",
        priority: newPriority,
        sprint: "Sprint 14 · Sovereign Platform",
        milestone: "v1.1 Unified GA",
        dependencies: [],
        assignedAgentId: newAgent,
      },
      ...prev,
    ]);
    onCreateIssue({ title: clean, priority: newPriority, assignedAgentId: newAgent });
    setNewTitle("");
  };

  const handleStatusChange = (issueId: string, nextStatus: PmIssueStatus) => {
    setLocalIssues((prev) => prev.map((iss) => (iss.id === issueId ? { ...iss, status: nextStatus } : iss)));
    onUpdateIssueStatus(issueId, nextStatus);
  };

  const handleDelegate = (issueId: string) => {
    setLocalIssues((prev) =>
      prev.map((iss) => (iss.id === issueId ? { ...iss, status: "in_progress", assignedAgentId: iss.assignedAgentId ?? "feature-coder" } : iss)),
    );
    onDelegateIssueToAgent(issueId);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">Project Manager · Linear-Style Issues &amp; Sprints</h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Track every milestone in plain English and click 'Delegate to Agent' to assign work automatically."
              : "Shared issue board synchronized with PRDs, git branches, lifecycle agents, and P-10 verification gates."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-fg-muted">
          <span className="rounded-xs border border-border bg-surface px-2 py-1">Sprint 14 · Sovereign Platform</span>
          <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-2 py-1 text-teal-accent">Milestone: v1.1 Unified GA</span>
        </div>
      </div>

      <section aria-label="Sprint velocity and milestone progress" className="space-y-2 rounded-md border border-border bg-surface p-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <span className="font-semibold text-fg">Sprint Velocity &amp; Milestone Completion</span>
          <span className="font-mono text-teal-accent">{`${doneCount} / ${totalCount} issues (${velocityPct}%)`}</span>
        </div>
        <div role="progressbar" aria-label="Sprint milestone completion" aria-valuenow={velocityPct} aria-valuemin={0} aria-valuemax={100} className="h-2 w-full overflow-hidden rounded-xs bg-chrome">
          <div className="h-full bg-teal-accent transition-all" style={{ width: `${velocityPct}%` }} />
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Filter issues by status" className="flex flex-wrap gap-1">
          {(["all", "backlog", "todo", "in_progress", "in_review", "done"] as const).map((st) => (
            <button
              key={st}
              type="button"
              aria-pressed={statusFilter === st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium capitalize ${
                statusFilter === st ? "border-teal-accent/50 bg-teal-surface text-teal-accent" : "border-border bg-surface text-fg-muted hover:text-fg"
              }`}
            >
              {st.replace("_", " ")}
            </button>
          ))}
        </div>

        <div role="group" aria-label="Project Manager layout" className="flex items-center gap-1">
          {([
            { id: "list", label: "List View" },
            { id: "kanban", label: "Kanban Board" },
          ] as const).map((mode) => (
            <button
              key={mode.id}
              type="button"
              aria-pressed={layout === mode.id}
              onClick={() => setLayout(mode.id)}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
                layout === mode.id ? "border-teal-accent/50 bg-teal-surface text-teal-accent" : "border-border bg-surface text-fg-muted hover:text-fg"
              }`}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmitIssue} aria-label="Create sprint issue" className="flex flex-wrap items-end gap-2.5 rounded-md border border-border-strong bg-surface p-3">
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-xs text-fg-muted">
          <span>New issue title</span>
          <input type="text" aria-label="New issue title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Add Linear-style issue to active sprint…" className={CTRL_CLS} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Priority</span>
          <select aria-label="New issue priority" value={newPriority} onChange={(e) => setNewPriority(e.target.value as PmIssuePriority)} className={CTRL_CLS}>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-fg-muted">
          <span>Assign lifecycle agent</span>
          <select aria-label="Assign lifecycle agent" value={newAgent} onChange={(e) => setNewAgent(e.target.value)} className={`${CTRL_CLS} font-mono`}>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>
        <Button type="submit" size="sm" variant="primary">+ Create issue</Button>
      </form>

      {inspectedIssue ? (
        <section aria-label={`Issue detail inspector for ${inspectedIssue.id}`} className="space-y-3 rounded-md border border-teal-accent/50 bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
            <h2 className="text-sm font-semibold text-fg">{`Issue Detail Inspector · ${inspectedIssue.id}: ${inspectedIssue.title}`}</h2>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  onOpenInIde?.(`Implement ${inspectedIssue.id} (${inspectedIssue.title}): ${draftDesc}`);
                  setIdeDispatchedId(inspectedIssue.id);
                }}
              >
                Open in IDE
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setInspectedIssueId(null)}>Close</Button>
            </div>
          </div>

          <form onSubmit={handleSaveInspector} className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
              <span>Description &amp; implementation notes</span>
              <textarea rows={2} aria-label="Issue description" value={draftDesc} onChange={(e) => setDraftDesc(e.target.value)} className="rounded-sm border border-border-control bg-canvas p-2 text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Blocking dependencies (comma-separated)</span>
              <input type="text" aria-label="Issue dependencies" value={draftDeps} onChange={(e) => setDraftDeps(e.target.value)} placeholder="e.g. KEEL-101" className={`${CTRL_CLS} font-mono`} />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Linked PRD</span>
              <select aria-label="Linked PRD" value={draftPrd} onChange={(e) => setDraftPrd(e.target.value)} className={`${CTRL_CLS} font-mono`}>
                {knownPrdIds.map((pid) => <option key={pid} value={pid}>{pid}</option>)}
              </select>
            </label>
            <div className="flex items-center gap-2 md:col-span-2">
              <Button type="submit" size="sm" variant="primary">Save Issue Details</Button>
              {savedInspectId === inspectedIssue.id ? <span role="status" className="font-mono text-xs text-ok">Issue details updated</span> : null}
              {ideDispatchedId === inspectedIssue.id ? <span role="status" className="font-mono text-xs text-teal-accent">Queued in IDE Composer</span> : null}
            </div>
          </form>
        </section>
      ) : null}

      {layout === "list" ? (
        <section aria-label="Sprint issues list" className="space-y-2">
          <h2 className="sr-only">Active Sprint Issues</h2>
          {visibleIssues.map((issue) => (
            <article key={issue.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface px-3.5 py-2.5">
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-teal-accent">{issue.id}</span>
                  <h3 className="text-xs font-semibold text-fg">{issue.title}</h3>
                  <span className="font-mono text-[10px] uppercase text-fg-dim">{issue.priority}</span>
                  {issue.status === "in_progress" ? (
                    <span className="inline-flex items-center gap-1.5 text-[11px] text-running">
                      <span aria-hidden="true" className="inline-block h-1.5 w-1.5 rounded-full bg-running" />
                      Delegated · In Progress
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-fg-dim">
                  <span>{issue.sprint}</span>
                  <span aria-hidden="true">·</span>
                  <span>{issue.milestone}</span>
                  {issue.linkedPrdId ? <span className="text-teal-accent">{`· ${issue.linkedPrdId}`}</span> : null}
                  {issue.assignedAgentId ? <span className="text-fg-muted">{`· Agent: ${issue.assignedAgentId}`}</span> : null}
                  {issue.dependencies.length > 0 ? (
                    <span className="rounded-xs border border-warning/40 bg-warning-subtle px-1.5 py-0.5 text-[10px] text-warning">
                      {`Depends on ${issue.dependencies.join(", ")}`}
                    </span>
                  ) : null}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="ghost" aria-expanded={inspectedIssueId === issue.id} aria-label={`Inspect ${issue.id}`} onClick={() => openInspector(issue)}>
                  Inspect
                </Button>
                <select aria-label={`Status for ${issue.id}`} value={issue.status} onChange={(e) => handleStatusChange(issue.id, e.target.value as PmIssueStatus)} className={CTRL_CLS}>
                  {KANBAN_COLUMNS.map((col) => <option key={col.id} value={col.id}>{col.label}</option>)}
                </select>
                <Button size="sm" variant="secondary" aria-label={`Delegate to Agent for ${issue.id}`} onClick={() => handleDelegate(issue.id)}>
                  Delegate to Agent
                </Button>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section aria-label="Kanban sprint board" className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          {KANBAN_COLUMNS.map((col) => {
            const colIssues = visibleIssues.filter((iss) => iss.status === col.id);
            return (
              <div key={col.id} className="flex flex-col gap-2 rounded-md border border-border-strong bg-chrome p-2.5">
                <div className="flex items-center justify-between border-b border-border pb-1.5">
                  <h2 className="text-xs font-semibold text-fg">{col.label}</h2>
                  <span className="rounded-xs bg-surface px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">{colIssues.length}</span>
                </div>
                <div className="space-y-2">
                  {colIssues.map((issue) => (
                    <article key={issue.id} className="space-y-2 rounded-sm border border-border bg-surface p-2.5 text-xs">
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-mono font-semibold text-teal-accent">{issue.id}</span>
                        <span className="font-mono text-[10px] uppercase text-fg-dim">{issue.priority}</span>
                      </div>
                      <h3 className="font-medium text-fg">{issue.title}</h3>
                      <select aria-label={`Status for ${issue.id}`} value={issue.status} onChange={(e) => handleStatusChange(issue.id, e.target.value as PmIssueStatus)} className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-1.5 py-0.5 text-[11px] text-fg">
                        {KANBAN_COLUMNS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                      </select>
                      <div className="flex items-center justify-between gap-1 pt-1">
                        <Button size="sm" variant="ghost" aria-label={`Inspect ${issue.id}`} onClick={() => openInspector(issue)}>Inspect</Button>
                        <Button size="sm" variant="secondary" aria-label={`Delegate to Agent for ${issue.id}`} onClick={() => handleDelegate(issue.id)}>Delegate to Agent</Button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}

export interface ProductWorkspaceViewProps {
  experienceMode: ExperienceMode;
  prds: ProductPrdItem[];
  feedback: UserFeedbackItem[];
  onToggleCriterion: (prdId: string, criterionId: string) => void;
  onJumpToPm: () => void;
  onCreatePrd?: (prd: ProductPrdItem) => void;
  onGenerateIssuesFromPrd?: (prd: ProductPrdItem) => void;
  onCreateFeedback?: (entry: UserFeedbackItem) => void;
}

export function ProductWorkspaceView({
  experienceMode,
  prds,
  feedback,
  onToggleCriterion,
  onJumpToPm,
  onCreatePrd,
  onGenerateIssuesFromPrd,
  onCreateFeedback,
}: ProductWorkspaceViewProps): React.JSX.Element {
  const [localPrds, setLocalPrds] = useState<ProductPrdItem[]>(prds);
  const [localFeedback, setLocalFeedback] = useState<UserFeedbackItem[]>(feedback);
  const [generatedIssuePrdIds, setGeneratedIssuePrdIds] = useState<Record<string, string[]>>({});

  const [prdTitle, setPrdTitle] = useState("");
  const [prdProblem, setPrdProblem] = useState("");
  const [prdStage, setPrdStage] = useState<ProductPrdItem["releaseStage"]>("discovery");
  const [prdCriteriaRaw, setPrdCriteriaRaw] = useState("Pass WCAG 2.2 AA accessibility\nRequire P-10 approval on mutations");
  const [riceReach, setRiceReach] = useState(600);
  const [riceImpact, setRiceImpact] = useState(3);
  const [riceConfidence, setRiceConfidence] = useState(90);
  const [riceEffort, setRiceEffort] = useState(18);

  const [fbPersona, setFbPersona] = useState("");
  const [fbQuote, setFbQuote] = useState("");
  const [fbImpact, setFbImpact] = useState(9.2);
  const [fbPrdId, setFbPrdId] = useState(prds[0]?.id ?? "PRD-01");

  useEffect(() => {
    setLocalPrds((prev) => {
      const incomingIds = new Set(prds.map((p) => p.id));
      return [...prev.filter((p) => !incomingIds.has(p.id)), ...prds];
    });
  }, [prds]);

  useEffect(() => {
    setLocalFeedback((prev) => {
      const incomingIds = new Set(feedback.map((f) => f.id));
      return [...prev.filter((f) => !incomingIds.has(f.id)), ...feedback];
    });
  }, [feedback]);

  const computedRice = useMemo(() => {
    const safeEffort = Math.max(1, riceEffort);
    const clampedConf = Math.min(100, Math.max(0, riceConfidence));
    return Math.round((Math.max(0, riceReach) * Math.max(0, riceImpact) * (clampedConf / 100)) / safeEffort);
  }, [riceConfidence, riceEffort, riceImpact, riceReach]);

  const handleAuthorPrd = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = prdTitle.trim();
    if (!cleanTitle) return;
    const id = `PRD-0${localPrds.length + 1}`;
    const criteriaLines = prdCriteriaRaw.split(/\n|,/).map((s) => s.trim()).filter(Boolean);
    const created: ProductPrdItem = {
      id,
      title: cleanTitle,
      problemStatement: prdProblem.trim() || `Deliver ${cleanTitle} with verified acceptance gates.`,
      riceScore: computedRice,
      releaseStage: prdStage,
      linkedIssueIds: [`KEEL-${300 + localPrds.length}`],
      acceptanceCriteria: (criteriaLines.length > 0 ? criteriaLines : [`Verify ${cleanTitle} end-to-end`]).map(
        (text, idx) => ({ id: `${id}-ac-${idx + 1}`, text, met: false }),
      ),
    };
    setLocalPrds((prev) => [created, ...prev]);
    setFbPrdId(created.id);
    setPrdTitle("");
    setPrdProblem("");
    onCreatePrd?.(created);
  };

  const handleToggleLocalCriterion = (prdId: string, criterionId: string) => {
    setLocalPrds((prev) =>
      prev.map((p) =>
        p.id === prdId
          ? { ...p, acceptanceCriteria: p.acceptanceCriteria.map((ac) => (ac.id === criterionId ? { ...ac, met: !ac.met } : ac)) }
          : p,
      ),
    );
    onToggleCriterion(prdId, criterionId);
  };

  const handleGenerateIssues = (prd: ProductPrdItem) => {
    const nextId = `KEEL-${401 + Object.keys(generatedIssuePrdIds).length * 2}`;
    setGeneratedIssuePrdIds((prev) => ({ ...prev, [prd.id]: [...(prev[prd.id] ?? []), nextId] }));
    onGenerateIssuesFromPrd?.(prd);
  };

  const handleLogFeedback = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanPersona = fbPersona.trim();
    const cleanQuote = fbQuote.trim();
    if (!cleanPersona || !cleanQuote) return;
    const entry: UserFeedbackItem = {
      id: `fb-local-${Date.now()}`,
      persona: cleanPersona,
      quote: cleanQuote,
      impactScore: Number(fbImpact) || 9.0,
      linkedPrdId: fbPrdId,
    };
    setLocalFeedback((prev) => [entry, ...prev]);
    setFbPersona("");
    setFbQuote("");
    onCreateFeedback?.(entry);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">Product Discovery, PRDs &amp; Release Plans</h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided mode: Review product goals, check off acceptance criteria, and see which sprint tasks deliver each feature."
              : "Structured PRDs with RICE prioritization, executable acceptance criteria, user feedback evidence, and linked KEEL sprint issues."}
          </p>
        </div>
        <span className="font-mono text-[11px] text-fg-muted">{`${localPrds.length} Active PRDs`}</span>
      </div>

      <section aria-label="Author new PRD and RICE calculator" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">+ Author New PRD &amp; RICE Prioritization Calculator</h2>
          <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-2 py-0.5 font-mono text-xs font-semibold text-teal-accent">
            {`RICE: ${computedRice}`}
          </span>
        </div>

        <form onSubmit={handleAuthorPrd} className="grid gap-3 md:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
            <span>PRD title</span>
            <input type="text" aria-label="PRD title" value={prdTitle} onChange={(e) => setPrdTitle(e.target.value)} placeholder="e.g. Zero-Trust Webhook Relay & Audit Vault" className={CTRL_CLS} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
            <span>Release stage</span>
            <select aria-label="PRD release stage" value={prdStage} onChange={(e) => setPrdStage(e.target.value as ProductPrdItem["releaseStage"])} className={CTRL_CLS}>
              <option value="discovery">Discovery</option>
              <option value="in_delivery">In Delivery</option>
              <option value="beta">Beta</option>
              <option value="ga">GA</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
            <span>Problem statement</span>
            <textarea rows={2} aria-label="PRD problem statement" value={prdProblem} onChange={(e) => setPrdProblem(e.target.value)} placeholder="What customer problem does this solve?" className="rounded-sm border border-border-control bg-canvas p-2 text-xs text-fg" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
            <span>Acceptance criteria (newline or comma separated)</span>
            <textarea rows={2} aria-label="PRD acceptance criteria" value={prdCriteriaRaw} onChange={(e) => setPrdCriteriaRaw(e.target.value)} className="rounded-sm border border-border-control bg-canvas p-2 text-xs text-fg" />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Reach (users/qtr)</span>
            <input type="number" aria-label="RICE reach" value={riceReach} onChange={(e) => setRiceReach(Number(e.target.value))} className={`${CTRL_CLS} font-mono`} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Impact (0.5–3)</span>
            <input type="number" step="0.5" aria-label="RICE impact" value={riceImpact} onChange={(e) => setRiceImpact(Number(e.target.value))} className={`${CTRL_CLS} font-mono`} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Confidence %</span>
            <input type="number" aria-label="RICE confidence" value={riceConfidence} onChange={(e) => setRiceConfidence(Number(e.target.value))} className={`${CTRL_CLS} font-mono`} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Effort (person-wks)</span>
            <input type="number" min="1" aria-label="RICE effort" value={riceEffort} onChange={(e) => setRiceEffort(Number(e.target.value))} className={`${CTRL_CLS} font-mono`} />
          </label>
          <div className="md:col-span-4">
            <Button type="submit" size="sm" variant="primary">+ Author New PRD</Button>
          </div>
        </form>
      </section>

      <section aria-label="Product requirement documents" className="grid gap-4 lg:grid-cols-2">
        <h2 className="sr-only">Structured PRDs</h2>
        {localPrds.map((prd) => {
          const extraIssues = generatedIssuePrdIds[prd.id] ?? [];
          const allIssueIds = Array.from(new Set([...prd.linkedIssueIds, ...extraIssues]));
          return (
            <article key={prd.id} className="flex flex-col justify-between gap-3 rounded-md border border-border-strong bg-surface p-4">
              <div className="space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-teal-accent">{prd.id}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg">{`RICE ${prd.riceScore}`}</span>
                    <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-1.5 py-0.5 font-mono text-[10px] uppercase text-teal-accent">
                      {prd.releaseStage.replace("_", " ")}
                    </span>
                  </div>
                </div>
                <h3 className="text-sm font-semibold text-fg">{prd.title}</h3>
                <p className="text-xs text-fg-muted">{prd.problemStatement}</p>
                <div className="space-y-1.5 pt-1">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-fg-dim">Acceptance Criteria</div>
                  {prd.acceptanceCriteria.map((ac) => (
                    <label key={ac.id} className="flex items-start gap-2 text-xs text-fg">
                      <input type="checkbox" checked={ac.met} onChange={() => handleToggleLocalCriterion(prd.id, ac.id)} className="mt-0.5" />
                      <span>{ac.text}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2.5">
                <div className="flex flex-wrap items-center gap-1">
                  <span className="text-[11px] text-fg-dim">Linked issues:</span>
                  {allIssueIds.map((id) => (
                    <button key={id} type="button" onClick={onJumpToPm} className="rounded-xs border border-border-control bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-teal-accent hover:bg-surface-elevated">
                      {id}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  {extraIssues.length > 0 ? <span role="status" className="font-mono text-[10px] text-ok">Sprint Issues Synced</span> : null}
                  <Button size="sm" variant="secondary" aria-label={`Generate Sprint Issues for ${prd.id}`} onClick={() => handleGenerateIssues(prd)}>
                    Generate Sprint Issues
                  </Button>
                </div>
              </div>
            </article>
          );
        })}
      </section>

      <section aria-label="User feedback log" className="space-y-3">
        <h2 className="text-sm font-semibold text-fg">Customer Discovery &amp; Feedback Log</h2>
        <form onSubmit={handleLogFeedback} aria-label="Log customer feedback" className="grid gap-2.5 rounded-md border border-border-strong bg-surface p-3 md:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Customer persona</span>
            <input type="text" aria-label="Customer persona" value={fbPersona} onChange={(e) => setFbPersona(e.target.value)} placeholder="e.g. FinTech Staff Engineer" className={CTRL_CLS} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
            <span>Feedback quote</span>
            <input type="text" aria-label="Customer feedback quote" value={fbQuote} onChange={(e) => setFbQuote(e.target.value)} placeholder="Direct customer evidence or discovery note…" className={CTRL_CLS} />
          </label>
          <div className="flex items-end gap-2">
            <label className="flex w-20 flex-col gap-1 text-xs text-fg-muted">
              <span>Impact</span>
              <input type="number" step="0.1" min="1" max="10" aria-label="Feedback impact score" value={fbImpact} onChange={(e) => setFbImpact(Number(e.target.value))} className={`${CTRL_CLS} font-mono`} />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
              <span>PRD</span>
              <select aria-label="Feedback linked PRD" value={fbPrdId} onChange={(e) => setFbPrdId(e.target.value)} className={`${CTRL_CLS} font-mono`}>
                {localPrds.map((p) => <option key={p.id} value={p.id}>{p.id}</option>)}
              </select>
            </label>
          </div>
          <div className="md:col-span-4">
            <Button type="submit" size="sm" variant="secondary">+ Log Customer Feedback</Button>
          </div>
        </form>

        <div className="grid gap-3 md:grid-cols-2">
          {localFeedback.map((item) => (
            <article key={item.id} className="rounded-md border border-border bg-surface p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-fg">{item.persona}</span>
                <span className="font-mono text-[11px] text-teal-accent">{`Impact ${item.impactScore}/10 · ${item.linkedPrdId}`}</span>
              </div>
              <p className="mt-1.5 text-xs text-fg-muted">{`“${item.quote}”`}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
