import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type {
  ExperienceMode,
  GeneratedProjectBlueprint,
  PlatformViewId,
} from "@/lib/platformData";

export interface NoCodeBuilderViewProps {
  experienceMode: ExperienceMode;
  latestBlueprint: GeneratedProjectBlueprint | null;
  onGenerateBlueprint: (idea: string, templateLabel: string) => void;
  onNavigateView: (view: PlatformViewId) => void;
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

export function NoCodeBuilderView({
  experienceMode,
  latestBlueprint,
  onGenerateBlueprint,
  onNavigateView,
}: NoCodeBuilderViewProps): React.JSX.Element {
  const [selectedTemplate, setSelectedTemplate] = useState(STARTER_TEMPLATES[0]!.label);
  const [ideaPrompt, setIdeaPrompt] = useState(STARTER_TEMPLATES[0]!.prompt);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ideaPrompt.trim()) return;
    onGenerateBlueprint(ideaPrompt.trim(), selectedTemplate);
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
        <SemanticBadge kind="ai" detail="Shared Workspace Sync" />
      </div>

      {/* Starter Templates */}
      <section aria-label="Starter app templates" className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-dim">
          Starter Blueprints
        </h2>
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
                  active
                    ? "border-teal-accent/60 bg-teal-surface text-fg"
                    : "border-border bg-surface text-fg-muted hover:border-border-strong hover:text-fg"
                }`}
              >
                <div className="text-xs font-semibold text-fg">{tpl.label}</div>
                <p className="mt-1 line-clamp-2 text-[11px] text-fg-muted">{tpl.prompt}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Natural-Language Prompt Studio */}
      <form
        onSubmit={handleSubmit}
        aria-label="No-Code blueprint generator"
        className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
      >
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
          <Button type="submit" variant="primary">
            Generate Project Blueprint
          </Button>
        </div>
      </form>

      {/* Live Generated Blueprint Artifacts */}
      {latestBlueprint ? (
        <section
          aria-label="Generated project blueprint"
          className="space-y-4 rounded-md border border-teal-accent/45 bg-surface p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
            <div>
              <span className="font-mono text-[11px] uppercase text-teal-accent">
                Committed to Shared Workspace
              </span>
              <h2 className="text-sm font-semibold text-fg">{latestBlueprint.prd.title}</h2>
            </div>
            <SemanticBadge kind="passed" labelOverride="Synced to Product, PM, Automation & Agents" />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {/* 1. PRD Card */}
            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">
                  {`1. Structured PRD (${latestBlueprint.prd.id})`}
                </h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("product")}>
                  Open in Product
                </Button>
              </div>
              <p className="text-xs text-fg-muted">{latestBlueprint.prd.problemStatement}</p>
            </article>

            {/* 2. Sprint Issues Card */}
            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">2. Sprint Issues Created</h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("pm")}>
                  Open in Project Manager
                </Button>
              </div>
              <ul className="space-y-1 text-xs text-fg-muted">
                {latestBlueprint.issues.map((iss) => (
                  <li key={iss.id}>
                    <code className="font-mono text-teal-accent">{iss.id}</code> — {iss.title}
                  </li>
                ))}
              </ul>
            </article>

            {/* 3. Automation Workflow Card */}
            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">
                  {`3. Automation Workflow (${latestBlueprint.workflow.id})`}
                </h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("automation")}>
                  Open in Automation
                </Button>
              </div>
              <div className="font-mono text-[11px] text-fg-muted">
                {latestBlueprint.workflow.nodes.map((n) => n.label).join(" → ")}
              </div>
            </article>

            {/* 4. Agent Squad & Governed Deployment Preview */}
            <article className="space-y-2 rounded-sm border border-border bg-chrome p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-fg">
                  4. Assigned Squad &amp; Governed Preview
                </h3>
                <Button size="sm" variant="ghost" onClick={() => onNavigateView("agents")}>
                  Open in Agents
                </Button>
              </div>
              <div className="text-xs text-fg">{latestBlueprint.assignedTeamName}</div>
              <div className="font-mono text-[11px] text-teal-accent">
                {`Preview: ${latestBlueprint.previewUrl}`}
              </div>
              <div className="font-mono text-[10px] text-ochre">
                P-10 Human Approval Required before external production promotion
              </div>
            </article>
          </div>
        </section>
      ) : null}
    </div>
  );
}
