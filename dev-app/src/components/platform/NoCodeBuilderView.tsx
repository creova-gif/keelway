import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  generateLocalBlueprint,
  type ExperienceMode,
  type GeneratedProjectBlueprint,
  type PlatformViewId,
} from "@/lib/platformData";

export interface NoCodeBuilderViewProps {
  experienceMode: ExperienceMode;
  latestBlueprint: GeneratedProjectBlueprint | null;
  onGenerateBlueprint: (idea: string, templateLabel: string) => void;
  onNavigateView: (view: PlatformViewId) => void;
}

interface PreviewRecordItem {
  id: string;
  requestor: string;
  summary: string;
  extraMeta: string;
  approved: boolean;
}

const STARTER_TEMPLATES = [
  {
    id: "tpl-invoice",
    label: "Invoice Approval & Audit Portal",
    prompt: "Vendor invoice approval portal with manager sign-off, budget caps, and exportable audit receipts",
  },
  {
    id: "tpl-onboarding",
    label: "Customer Onboarding & Compliance Desk",
    prompt: "Guided customer onboarding portal with document checklist, RBAC roles, and automated review alerts",
  },
  {
    id: "tpl-inventory",
    label: "Inventory Restock & Supplier Workflow",
    prompt: "Warehouse low-stock tracker that drafts purchase requests and awaits human approval before sending",
  },
];

const INITIAL_PREVIEW_RECORDS: PreviewRecordItem[] = [
  {
    id: "REQ-901",
    requestor: "Maya Chen (Finance Ops)",
    summary: "Q4 Sovereign GPU Cluster Renewal ($18,400)",
    extraMeta: "Cost Center: INFRA-04",
    approved: false,
  },
];

export function NoCodeBuilderView({
  experienceMode,
  latestBlueprint,
  onGenerateBlueprint,
  onNavigateView,
}: NoCodeBuilderViewProps): React.JSX.Element {
  const [selectedTemplate, setSelectedTemplate] = useState(STARTER_TEMPLATES[0]!.label);
  const [ideaPrompt, setIdeaPrompt] = useState(STARTER_TEMPLATES[0]!.prompt);
  const [localBlueprint, setLocalBlueprint] = useState<GeneratedProjectBlueprint | null>(null);
  const [showStarterPreview, setShowStarterPreview] = useState(false);

  const [enableBudgetField, setEnableBudgetField] = useState(true);
  const [enableDeptField, setEnableDeptField] = useState(true);
  const [requestorName, setRequestorName] = useState("");
  const [requestSummary, setRequestSummary] = useState("");
  const [budgetCapValue, setBudgetCapValue] = useState("$4,500");
  const [deptValue, setDeptValue] = useState("SEC-OPS");
  const [previewRecords, setPreviewRecords] = useState<PreviewRecordItem[]>(INITIAL_PREVIEW_RECORDS);

  const activeBlueprint = latestBlueprint ?? localBlueprint;
  const previewVisible = Boolean(activeBlueprint) || showStarterPreview;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = ideaPrompt.trim();
    if (!clean) return;
    setLocalBlueprint(generateLocalBlueprint(clean, selectedTemplate, 0));
    onGenerateBlueprint(clean, selectedTemplate);
  };

  const handleSubmitPreviewEntry = (e: React.FormEvent) => {
    e.preventDefault();
    const req = requestorName.trim() || "Workspace Operator";
    const sum = requestSummary.trim() || "Standard governed workflow request";
    const metaParts: string[] = [];
    if (enableBudgetField && budgetCapValue.trim()) metaParts.push(`Cap: ${budgetCapValue.trim()}`);
    if (enableDeptField && deptValue.trim()) metaParts.push(`Dept: ${deptValue.trim()}`);
    setPreviewRecords((prev) => [
      {
        id: `REQ-${901 + prev.length}`,
        requestor: req,
        summary: sum,
        extraMeta: metaParts.join(" · ") || "Standard Scope",
        approved: false,
      },
      ...prev,
    ]);
    setRequestorName("");
    setRequestSummary("");
  };

  const handleApproveEntry = (id: string) => {
    setPreviewRecords((prev) => prev.map((rec) => (rec.id === id ? { ...rec, approved: true } : rec)));
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            No-Code Builder · Natural-Language Idea to Governed App
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Describe what your business needs in plain English. Keelway builds the Product Spec, Sprint Tasks, Automation Workflow, and App Preview inside the exact same governed workspace your engineers use."
              : "Fast-prototype structured PRDs, Linear-style sprint issues, KFlow DAGs, and multi-agent execution plans directly into the active workspace."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" aria-pressed={previewVisible} onClick={() => setShowStarterPreview((prev) => !prev)}>
            Preview Starter App
          </Button>
          <SemanticBadge kind="ai" detail="Shared Workspace Sync" />
        </div>
      </div>

      <section aria-label="Starter app templates" className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-dim">Starter Blueprints</h2>
        <div className="grid gap-2.5 md:grid-cols-3">
          {STARTER_TEMPLATES.map((tpl) => {
            const active = selectedTemplate === tpl.label;
            return (
              <button
                key={tpl.id}
                type="button"
                aria-pressed={active}
                onClick={() => {
                  setSelectedTemplate(tpl.label);
                  setIdeaPrompt(tpl.prompt);
                }}
                className={`rounded-md border p-3 text-start transition-colors ${
                  active ? "border-teal-accent/60 bg-teal-surface text-fg" : "border-border bg-surface text-fg-muted hover:border-border-strong hover:text-fg"
                }`}
              >
                <div className="text-xs font-semibold text-fg">{tpl.label}</div>
                <p className="mt-1 line-clamp-2 text-[11px] text-fg-muted">{tpl.prompt}</p>
              </button>
            );
          })}
        </div>
      </section>

      <form onSubmit={handleSubmit} aria-label="No-Code blueprint generator" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <label className="flex flex-col gap-1.5 text-xs font-medium text-fg">
          <span>Describe your app or workflow idea</span>
          <textarea
            rows={3}
            aria-label="Describe your app or workflow idea"
            value={ideaPrompt}
            onChange={(e) => setIdeaPrompt(e.target.value)}
            placeholder="Describe who uses the app, what approvals are needed, and what should be automated…"
            className="rounded-sm border border-border-control bg-canvas px-3 py-2 text-xs text-fg"
          />
        </label>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-[11px] text-fg-dim">
            {`Template: ${selectedTemplate} · Production publish gated by P-10 human sign-off`}
          </span>
          <Button type="submit" variant="primary">Generate Project Blueprint</Button>
        </div>
      </form>

      {activeBlueprint ? (
        <section aria-label="Generated project blueprint" className="space-y-4 rounded-md border border-teal-accent/45 bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
            <div>
              <span className="font-mono text-[11px] uppercase text-teal-accent">Committed to Shared Workspace</span>
              <h2 className="text-sm font-semibold text-fg">{activeBlueprint.prd.title}</h2>
            </div>
            <SemanticBadge kind="passed" labelOverride="Synced to Product, PM, Automation & Agents" />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">{`1. Structured PRD (${activeBlueprint.prd.id})`}</h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("product")}>Open in Product</Button>
              </div>
              <p className="text-xs text-fg-muted">{activeBlueprint.prd.problemStatement}</p>
            </article>

            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">2. Sprint Issues Created</h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("pm")}>Open in Project Manager</Button>
              </div>
              <ul className="space-y-1 text-xs text-fg-muted">
                {activeBlueprint.issues.map((iss) => (
                  <li key={iss.id}><code className="font-mono text-teal-accent">{iss.id}</code> — {iss.title}</li>
                ))}
              </ul>
            </article>

            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">{`3. Automation Workflow (${activeBlueprint.workflow.id})`}</h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("automation")}>Open in Automation</Button>
              </div>
              <div className="font-mono text-[11px] text-fg-muted">{activeBlueprint.workflow.nodes.map((n) => n.label).join(" → ")}</div>
            </article>

            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">4. Assigned Squad &amp; Governed Preview</h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("agents")}>Open in Agents</Button>
              </div>
              <div className="text-xs text-fg">{activeBlueprint.assignedTeamName}</div>
              <div className="font-mono text-[11px] text-teal-accent">{`Preview: ${activeBlueprint.previewUrl}`}</div>
              <div className="font-mono text-[10px] text-ochre">P-10 Human Approval Required before external production promotion</div>
            </article>
          </div>
        </section>
      ) : null}

      {previewVisible ? (
        <section aria-label="Interactive live app preview" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
            <div>
              <h2 className="text-sm font-semibold text-fg">
                {`Interactive Live App Preview · ${activeBlueprint?.prd.title ?? selectedTemplate}`}
              </h2>
              <p className="font-mono text-[11px] text-teal-accent">
                {activeBlueprint?.previewUrl ?? "http://127.0.0.1:7420/preview/starter-sandbox"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {([
                { view: "product", label: "Jump to Product" },
                { view: "pm", label: "Jump to Project Manager" },
                { view: "automation", label: "Jump to Automation" },
                { view: "agents", label: "Jump to Agents" },
              ] as const).map((nav) => (
                <Button key={nav.view} size="sm" variant="ghost" onClick={() => onNavigateView(nav.view)}>
                  {nav.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 rounded-xs border border-border bg-chrome px-3 py-2 text-xs text-fg">
            <span className="font-mono text-[11px] text-fg-dim">Customizable App Fields:</span>
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={enableBudgetField} onChange={(e) => setEnableBudgetField(e.target.checked)} />
              <span>Budget Cap Field</span>
            </label>
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={enableDeptField} onChange={(e) => setEnableDeptField(e.target.checked)} />
              <span>Department Cost Center</span>
            </label>
          </div>

          <form onSubmit={handleSubmitPreviewEntry} className="grid gap-2.5 md:grid-cols-4">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Requestor name</span>
              <input
                type="text"
                aria-label="Preview requestor name"
                value={requestorName}
                onChange={(e) => setRequestorName(e.target.value)}
                placeholder="e.g. Jordan Patel"
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-2">
              <span>Request summary</span>
              <input
                type="text"
                aria-label="Preview request summary"
                value={requestSummary}
                onChange={(e) => setRequestSummary(e.target.value)}
                placeholder="e.g. Approve annual SOC2 auditor access scope"
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
              />
            </label>
            {enableBudgetField ? (
              <label className="flex flex-col gap-1 text-xs text-fg-muted">
                <span>Budget cap</span>
                <input type="text" aria-label="Preview budget cap" value={budgetCapValue} onChange={(e) => setBudgetCapValue(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
              </label>
            ) : null}
            {enableDeptField ? (
              <label className="flex flex-col gap-1 text-xs text-fg-muted">
                <span>Cost center</span>
                <input type="text" aria-label="Preview cost center" value={deptValue} onChange={(e) => setDeptValue(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
              </label>
            ) : null}
            <div className="flex items-end">
              <Button type="submit" size="sm" variant="primary">Submit Test Entry</Button>
            </div>
          </form>

          <div className="overflow-x-auto rounded-xs border border-border">
            <table aria-label="Live preview records" className="w-full border-collapse text-start text-xs">
              <thead className="border-b border-border bg-chrome text-fg-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">ID</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Requestor</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Summary</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Governance Status</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-canvas">
                {previewRecords.map((rec) => (
                  <tr key={rec.id}>
                    <td className="px-3 py-2 font-mono text-teal-accent">{rec.id}</td>
                    <td className="px-3 py-2 text-fg">{rec.requestor}</td>
                    <td className="px-3 py-2 text-fg-muted">{`${rec.summary} (${rec.extraMeta})`}</td>
                    <td className="px-3 py-2 font-mono text-[11px]">
                      {rec.approved ? <span className="text-ok">Approved · Record Logged</span> : <span className="text-ochre">Pending P-10 Approval</span>}
                    </td>
                    <td className="px-3 py-2">
                      {!rec.approved ? (
                        <Button size="sm" variant="secondary" aria-label={`Approve Entry ${rec.id}`} onClick={() => handleApproveEntry(rec.id)}>
                          Approve Entry
                        </Button>
                      ) : (
                        <span className="font-mono text-[10px] text-fg-dim">Signed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
