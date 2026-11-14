"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Bot, BookOpen, CheckCircle2, Code2, FileText, Gauge, Kanban,
  Package, Play, ShieldCheck, Sparkles, UserCheck, Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

export type ExperienceMode = "builder" | "non_coder";
export type UnifiedViewId =
  | "nocode" | "agents" | "ide" | "pm" | "product"
  | "automation" | "marketplace" | "security" | "docs" | "operations";

interface BlueprintPreset {
  id: string;
  idea: string;
  slug: string;
  stack: string;
  prdSummary: string;
  acceptance: string[];
  issues: { id: string; title: string; agent: string; priority: string }[];
  diffPath: string;
  diffAdded: string[];
  dagNodes: { step: string; role: string; gate?: boolean }[];
}

const PRESETS: BlueprintPreset[] = [
  {
    id: "hipaa-intake",
    idea: "HIPAA-ready patient intake & triage portal",
    slug: "hipaa-intake-portal",
    stack: "FastAPI + React 19 + Zero-Egress OpenCore 7B",
    prdSummary: "Zero-egress patient intake workflow with pre-persistence PHI scrubbing, clinical urgency triage, and P-10 clinician sign-off.",
    acceptance: [
      "Scrub 18 HIPAA identifiers via redact_text() prior to SQLite WAL storage",
      "Route triage classification exclusively to local keelway-core:7b ($0.00/tok)",
      "Require explicit human P-10 approval before exporting HL7/FHIR referral bundle",
    ],
    issues: [
      { id: "KW-201", title: "Define PHI intake schema & zero-egress policy", agent: "code-architect", priority: "Urgent" },
      { id: "KW-202", title: "Build accessible intake form & urgency classifier", agent: "nocode-app-builder", priority: "High" },
      { id: "KW-203", title: "Add HIPAA redaction & P-10 export gate tests", agent: "security-auditor", priority: "High" },
    ],
    diffPath: "app/intake/phi_triage_router.py",
    diffAdded: [
      "+ @router.post('/v1/intake/triage', dependencies=[Depends(enforce_local_airgap)])",
      "+ def submit_intake(payload: PatientIntake, gate: P10Gate = Depends()):",
      "+     sanitized = redact_text(payload.notes, profile='hipaa_safe_harbor')",
      "+     return run_local_model('keelway-core:7b', sanitized, zero_egress=True)",
    ],
    dagNodes: [
      { step: "1. Patient Form Webhook", role: "issue-triager" },
      { step: "2. Local PHI Redaction", role: "security-auditor" },
      { step: "3. OpenCore 7B Triage", role: "feature-coder" },
      { step: "4. P-10 Clinician Sign-Off", role: "human-operator", gate: true },
    ],
  },
  {
    id: "soc2-release",
    idea: "Automated PR security & SOC2 release pipeline",
    slug: "soc2-release-gate",
    stack: "Keelway CLI + GitHub Webhook + CycloneDX 1.5 SBOM",
    prdSummary: "Autonomous pull-request security audit, AST regression verification, CycloneDX SBOM generation, and dual-human release sign-off.",
    acceptance: [
      "Block shell=True, eval(), and unscoped wildcard permissions on every PR diff",
      "Emit genesis-anchored SHA-256 FlightRecorder receipt per CI test shard",
      "Hold production deployment until human operator approves P-10 release gate",
    ],
    issues: [
      { id: "KW-301", title: "Wire AST diff scanner & secret leak tripwire", agent: "security-auditor", priority: "Urgent" },
      { id: "KW-302", title: "Execute deterministic pytest & Vitest verification", agent: "qa-ci-runner", priority: "High" },
      { id: "KW-303", title: "Generate CycloneDX 1.5 SBOM & release runbook", agent: "devops-sre", priority: "Medium" },
    ],
    diffPath: "pipelines/soc2_release_gate.py",
    diffAdded: [
      "+ def verify_release_candidate(pr_sha: str) -> ReleaseAttestation:",
      "+     scan = MarketplaceSecurityScanner().scan_diff(pr_sha)",
      "+     assert scan.passed, f'Blocked by policy: {scan.findings}'",
      "+     return await_p10_human_approval(action='prod.deploy', commit=pr_sha)",
    ],
    dagNodes: [
      { step: "1. PR Diff Trigger", role: "pr-reviewer" },
      { step: "2. Static & Secret Audit", role: "security-auditor" },
      { step: "3. Sandbox Test Shards", role: "qa-ci-runner" },
      { step: "4. P-10 Prod Release Gate", role: "human-operator", gate: true },
    ],
  },
  {
    id: "fintech-recon",
    idea: "Multi-currency fintech invoice reconciliation workflow",
    slug: "fintech-invoice-recon",
    stack: "Python SDK + KFlow Cron DAG + Hybrid BYOM Router",
    prdSummary: "Multi-currency ledger matching across NGN, KES, EUR, and USD settlements with spend-capped hybrid routing and audit proofs.",
    acceptance: [
      "Reconcile CSV/ERP settlement lines deterministically with <1% variance threshold",
      "Auto-downgrade to keelway-core:7b ($0.00) if monthly BYOM cloud cap reaches 100%",
      "Require P-10 treasury controller approval on adjustments exceeding $5,000",
    ],
    issues: [
      { id: "KW-401", title: "Normalize FX settlement parsers (NGN/KES/EUR/USD)", agent: "feature-coder", priority: "Urgent" },
      { id: "KW-402", title: "Configure KFlow nightly reconciliation DAG", agent: "workflow-automator", priority: "High" },
      { id: "KW-403", title: "Enforce P-10 treasury threshold & audit export", agent: "product-strategist", priority: "High" },
    ],
    diffPath: "workflows/fx_reconciliation.py",
    diffAdded: [
      "+ def reconcile_batch(settlement: BatchLedger) -> ReconReceipt:",
      "+     matched = match_fx_entries(settlement, model='keelway-core:7b')",
      "+     if matched.adjustment_usd > 5000:",
      "+         require_p10_approval(reason='Treasury threshold > $5,000')",
    ],
    dagNodes: [
      { step: "1. 02:00 UTC Ledger Ingest", role: "workflow-automator" },
      { step: "2. FX Line Matching (7B)", role: "feature-coder" },
      { step: "3. P-10 Variance Approval", role: "human-operator", gate: true },
      { step: "4. Signed Audit Ledger Sync", role: "devops-sre" },
    ],
  },
];

const UNIFIED_VIEWS: { id: UnifiedViewId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "nocode", label: "No-Code Builder", icon: Sparkles },
  { id: "product", label: "Product", icon: FileText },
  { id: "pm", label: "Project Manager", icon: Kanban },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "ide", label: "IDE", icon: Code2 },
  { id: "automation", label: "Automation", icon: Workflow },
  { id: "marketplace", label: "Marketplace", icon: Package },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "docs", label: "Documentation", icon: BookOpen },
  { id: "operations", label: "Operations", icon: Gauge },
];

const INITIAL_MARKETPLACE = [
  { id: "pkg-linear", name: "Linear Sprint Triager", kind: "agent_skill", split: "85% Creator / 15% Platform", installed: true },
  { id: "pkg-hipaa", name: "Safe-Harbor PII/PHI Guard", kind: "plugin_extension", split: "100% First-Party OSS", installed: true },
  { id: "pkg-sbom", name: "CycloneDX 1.5 Attester", kind: "dev_tool", split: "85% Creator / 15% Platform", installed: false },
];

export function UnifiedPlatformPlayground() {
  const [mode, setMode] = useState<ExperienceMode>("builder");
  const [activeView, setActiveView] = useState<UnifiedViewId>("nocode");
  const [selectedPresetId, setSelectedPresetId] = useState(PRESETS[0].id);
  const [ideaInput, setIdeaInput] = useState(PRESETS[0].idea);
  const [compiledIdea, setCompiledIdea] = useState(PRESETS[0].idea);
  const [compileCount, setCompileCount] = useState(1);
  const [p10Approved, setP10Approved] = useState(false);
  const [doneIssues, setDoneIssues] = useState<string[]>(["KW-201"]);
  const [packages, setPackages] = useState(INITIAL_MARKETPLACE);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const qMode = params.get("mode");
    if (qMode === "noncoder" || qMode === "non_coder") {
      setMode("non_coder");
    } else if (qMode === "builder") {
      setMode("builder");
    }
    const qView = params.get("view") as UnifiedViewId | null;
    if (qView && UNIFIED_VIEWS.some((v) => v.id === qView)) {
      setActiveView(qView);
    }
  }, []);

  const activeBlueprint = useMemo(() => {
    const matched = PRESETS.find((p) => p.id === selectedPresetId) ?? PRESETS[0];
    if (compiledIdea.trim() && compiledIdea.trim() !== matched.idea) {
      const slug = compiledIdea.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 28) || "custom-sovereign-app";
      return {
        ...matched,
        idea: compiledIdea.trim(),
        slug,
        prdSummary: `Sovereign blueprint compiled for "${compiledIdea.trim()}" with zero-egress OpenCore routing, linked sprint issues, and P-10 human approval checkpoints.`,
      };
    }
    return matched;
  }, [selectedPresetId, compiledIdea]);

  const handleSelectPreset = (preset: BlueprintPreset) => {
    setSelectedPresetId(preset.id);
    setIdeaInput(preset.idea);
    setCompiledIdea(preset.idea);
    setP10Approved(false);
    setDoneIssues([preset.issues[0].id]);
    trackEvent("playground_blueprint_compiled", { preset: preset.id });
  };

  const handleCompileBlueprint = (e: React.FormEvent) => {
    e.preventDefault();
    const nextIdea = ideaInput.trim() || PRESETS[0].idea;
    setCompiledIdea(nextIdea);
    setCompileCount((c) => c + 1);
    setP10Approved(false);
    setActiveView("product");
    trackEvent("playground_blueprint_compiled", { custom: nextIdea !== PRESETS[0].idea });
  };

  return (
    <div className="overflow-hidden rounded-lg border border-border-strong bg-surface shadow-xl">
      <div className="flex flex-col justify-between gap-4 border-b border-border-strong bg-surface-elevated px-4 py-3.5 sm:px-6 lg:flex-row lg:items-center">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <span className="chip-teal rounded-sm px-2 py-0.5">WORKSPACE: {activeBlueprint.slug}</span>
          <span className="chip-neutral rounded-sm px-2 py-0.5">keelway-core:7b ($0.00/tok)</span>
          <span className={cn("rounded-sm px-2 py-0.5", p10Approved ? "chip-teal" : "chip-amber")}>
            {p10Approved ? "P-10 Gate: Approved" : "P-10 Gate: 1 Pending Human"}
          </span>
        </div>

        <div role="group" aria-label="Workspace experience mode" className="inline-flex flex-wrap rounded-sm border border-border-strong bg-canvas p-0.5">
          {(
            [
              ["builder", "Builder Mode"],
              ["non_coder", "Guided Non-Coder Mode"],
            ] as const
          ).map(([val, label]) => (
            <button
              key={val}
              type="button"
              onClick={() => {
                setMode(val);
                trackEvent("playground_mode_switched", { mode: val });
              }}
              className={cn(
                "min-h-[38px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors",
                mode === val ? "bg-teal-accent text-teal-ink" : "text-fg-muted hover:text-fg"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div role="tablist" aria-label="10 Unified Keelway Platform Views" className="flex items-center gap-1 overflow-x-auto border-b border-border-subtle bg-canvas px-3 py-2">
        {UNIFIED_VIEWS.map((v) => {
          const Icon = v.icon;
          const active = activeView === v.id;
          return (
            <button
              key={v.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => {
                setActiveView(v.id);
                trackEvent("playground_view_selected", { view: v.id, mode });
              }}
              className={cn(
                "inline-flex min-h-[40px] shrink-0 items-center gap-1.5 rounded-sm px-3 font-mono text-xs font-medium transition-colors",
                active
                  ? "border border-teal-accent/60 bg-teal-surface font-semibold text-teal-accent"
                  : "border border-transparent text-fg-muted hover:bg-surface hover:text-fg"
              )}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{v.label}</span>
            </button>
          );
        })}
      </div>

      <div className="p-5 sm:p-6">
        {activeView === "nocode" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <form onSubmit={handleCompileBlueprint} className="space-y-4 lg:col-span-7">
              <div>
                <span className="font-mono text-xs font-semibold uppercase text-teal-accent">
                  {mode === "non_coder" ? "Guided Idea-to-App Studio (Zero Coding Required)" : "Blueprint Compiler -> Shared Workspace Context"}
                </span>
                <h2 className="mt-1 text-xl font-bold text-fg">Describe what you want to ship; Keelway wires all 10 views</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleSelectPreset(p)}
                    className={cn(
                      "min-h-[38px] rounded-sm border px-3 text-left font-mono text-xs transition-colors",
                      selectedPresetId === p.id && ideaInput === p.idea
                        ? "border-teal-accent bg-teal-surface font-semibold text-teal-accent"
                        : "border-border-strong bg-canvas text-fg-muted hover:text-fg"
                    )}
                  >
                    {p.idea}
                  </button>
                ))}
              </div>
              <div>
                <label htmlFor="blueprint-idea-input" className="block font-mono text-[11px] uppercase text-fg-muted">
                  Natural-Language Product or Workflow Brief
                </label>
                <textarea
                  id="blueprint-idea-input"
                  rows={3}
                  value={ideaInput}
                  onChange={(e) => setIdeaInput(e.target.value)}
                  className="mt-1.5 w-full rounded-md border border-border-strong bg-canvas p-3 text-sm text-fg focus:border-teal-accent"
                />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button type="submit" className="kw-btn kw-btn-primary">
                  <Play className="h-4 w-4" aria-hidden="true" />
                  <span>Compile Blueprint</span>
                </button>
                <span className="font-mono text-xs text-fg-muted">
                  Revision #{compileCount} · Populates Product, PM, Agents, IDE &amp; DAG
                </span>
              </div>
            </form>

            <div className="rounded-md border border-border-strong bg-canvas p-4 lg:col-span-5">
              <div className="font-mono text-xs font-bold uppercase text-teal-accent">Generated Shared Artifacts</div>
              <p className="mt-1.5 text-xs text-fg-muted">Stack: <strong className="text-fg">{activeBlueprint.stack}</strong></p>
              <div className="mt-3 grid grid-cols-2 gap-2.5 font-mono text-xs">
                {(
                  [
                    ["Product PRD", "product", "3 Acceptance Gates"],
                    ["Sprint Board", "pm", `${activeBlueprint.issues.length} Linked Issues`],
                    ["Agent Squad", "agents", "4 Lifecycle Roles"],
                    ["Governed Diff", "ide", "P-10 Human Checkpoint"],
                  ] as const
                ).map(([title, targetView, sub]) => (
                  <button
                    key={title}
                    type="button"
                    onClick={() => setActiveView(targetView)}
                    className="rounded-sm border border-border-strong bg-surface p-3 text-left transition-colors hover:border-teal-accent"
                  >
                    <div className="font-bold text-fg">{title}</div>
                    <div className="mt-1 text-[11px] text-teal-accent">{sub} →</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeView === "product" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xl font-bold text-fg">Live PRD: {activeBlueprint.idea}</h2>
              <span className="chip-teal rounded-sm px-2.5 py-1">RICE Priority: 94 · Linked to {activeBlueprint.issues.length} PM Issues</span>
            </div>
            <p className="text-sm leading-relaxed text-fg-muted">{activeBlueprint.prdSummary}</p>
            <div className="rounded-md border border-border-strong bg-canvas p-4">
              <div className="font-mono text-xs font-bold uppercase text-fg-muted">Executable Acceptance Criteria</div>
              <ul className="mt-3 space-y-2 text-xs text-fg">
                {activeBlueprint.acceptance.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {activeView === "pm" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-fg">Linear-Style Sprint Issues &amp; Agent Assignments</h2>
              <span className="font-mono text-xs text-teal-accent">{doneIssues.length}/{activeBlueprint.issues.length} Completed</span>
            </div>
            <div className="divide-y divide-border-subtle rounded-md border border-border-strong bg-canvas">
              {activeBlueprint.issues.map((iss) => {
                const isDone = doneIssues.includes(iss.id);
                return (
                  <div key={iss.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setDoneIssues((prev) => (prev.includes(iss.id) ? prev.filter((x) => x !== iss.id) : [...prev, iss.id]))}
                        className={cn(
                          "min-h-[34px] rounded-sm border px-2.5 font-mono font-semibold",
                          isDone ? "border-teal-accent bg-teal-surface text-teal-accent" : "border-border-strong bg-surface text-fg-muted"
                        )}
                      >
                        {isDone ? "DONE" : "IN PROGRESS"}
                      </button>
                      <div>
                        <div className="font-semibold text-fg"><span className="mr-2 font-mono text-teal-accent">{iss.id}</span>{iss.title}</div>
                        <div className="font-mono text-[11px] text-fg-muted">Assigned Agent: <code>{iss.agent}</code> · Priority: {iss.priority}</div>
                      </div>
                    </div>
                    <button type="button" onClick={() => setActiveView("ide")} className="font-mono text-xs text-teal-accent hover:underline">
                      Inspect Diff in IDE →
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {activeView === "agents" && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {[
              { role: "code-architect", model: "keelway-core:7b", scope: "ast:read, prd:link", desc: "Designs typed interfaces and shared infrastructure boundaries." },
              { role: "feature-coder", model: "qwen2.5-coder:14b", scope: "fs:patch_jailed", desc: "Implements vertical slices inside Seatbelt workspace containment." },
              { role: "security-auditor", model: "keelway-core:7b", scope: "redact:verify, sbom:scan", desc: "Enforces pre-egress secret hygiene and blocks shell/injection sinks." },
              { role: "qa-ci-runner", model: "keelway-core:7b", scope: "pytest:isolated", desc: "Runs deterministic test gates prior to human P-10 checkpoint." },
            ].map((ag) => (
              <div key={ag.role} className="rounded-md border border-border-strong bg-canvas p-4">
                <div className="flex items-center justify-between font-mono text-xs">
                  <span className="font-bold text-teal-accent">{ag.role}</span>
                  <span className="chip-neutral rounded-sm px-2 py-0.5">{ag.model}</span>
                </div>
                <p className="mt-2 text-xs text-fg-muted">{ag.desc}</p>
                {mode === "builder" && <div className="mt-2 font-mono text-[11px] text-fg-dim">Manifest Scopes: <code>{ag.scope}</code></div>}
              </div>
            ))}
          </div>
        )}

        {activeView === "ide" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-fg">
                  {mode === "builder" ? `Governed Split Diff: ${activeBlueprint.diffPath}` : "Visual Change Preview & Human Safety Sign-Off"}
                </h2>
                <p className="text-xs text-fg-muted">Agents propose verified patches; only a human operator can approve P-10 high-impact gates.</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setP10Approved(true);
                  trackEvent("playground_workflow_completed", { slug: activeBlueprint.slug });
                }}
                disabled={p10Approved}
                className="kw-btn kw-btn-primary text-xs disabled:opacity-60"
              >
                <UserCheck className="h-4 w-4" aria-hidden="true" />
                <span>{p10Approved ? "P-10 Human Gate Approved" : "Approve P-10 Gate (Human Only)"}</span>
              </button>
            </div>
            <pre className="overflow-x-auto rounded-md border border-border-strong bg-canvas p-4 font-mono text-xs leading-relaxed text-teal-accent">
              {activeBlueprint.diffAdded.join("\n")}
            </pre>
          </div>
        )}

        {activeView === "automation" && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {activeBlueprint.dagNodes.map((n) => (
              <div key={n.step} className={cn("rounded-md border p-4 font-mono text-xs", n.gate ? "border-amber-alert bg-amber-surface text-fg" : "border-border-strong bg-canvas text-fg")}>
                <div className="font-bold">{n.step}</div>
                <div className="mt-1 text-[11px] text-fg-muted">Actor: {n.role}</div>
                <div className="mt-2 text-[11px] text-teal-accent">{n.gate ? (p10Approved ? "Signed Off" : "Awaiting Human P-10") : "Verified Ready"}</div>
              </div>
            ))}
          </div>
        )}

        {activeView === "marketplace" && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {packages.map((pkg) => (
              <div key={pkg.id} className="flex flex-col justify-between rounded-md border border-border-strong bg-canvas p-4">
                <div>
                  <span className="chip-teal rounded-sm px-2 py-0.5">{pkg.kind}</span>
                  <h3 className="mt-2 font-bold text-fg">{pkg.name}</h3>
                  <p className="mt-1 font-mono text-[11px] text-fg-muted">{pkg.split}</p>
                  <p className="mt-1 font-mono text-[11px] text-teal-accent">SHA-256 Pre-Publish Verified</p>
                </div>
                <button
                  type="button"
                  onClick={() => setPackages((prev) => prev.map((p) => (p.id === pkg.id ? { ...p, installed: !p.installed } : p)))}
                  className="kw-btn kw-btn-secondary mt-4 w-full text-xs"
                >
                  {pkg.installed ? "Installed in Workspace ✓" : "Install Extension"}
                </button>
              </div>
            ))}
          </div>
        )}

        {activeView === "security" && (
          <div className="space-y-2 rounded-md border border-border-strong bg-canvas p-4 font-mono text-xs">
            <div className="font-bold text-teal-accent">SHA-256 FlightRecorder &amp; Sovereign Containment Posture</div>
            <div>Sandbox: macOS Seatbelt / Linux Landlock · Network: Loopback Air-Gap Ready</div>
            <div>
              P-10 Receipt Status:{" "}
              <strong className={p10Approved ? "text-teal-accent" : "text-amber-alert"}>
                {p10Approved ? "SIGNED BY HUMAN OPERATOR (sha256:9f4c2e1b…88a0d4)" : "HELD — High-impact actions cannot self-approve"}
              </strong>
            </div>
          </div>
        )}

        {activeView === "docs" && (
          <div className="space-y-2 rounded-md border border-border-strong bg-canvas p-4 text-xs">
            <div className="font-mono font-bold uppercase text-teal-accent">Living Product &amp; Engineering Knowledge Base</div>
            <p className="text-fg-muted">
              Automatically keeps onboarding guides, architecture runbooks, customer help docs, and API references synchronized whenever PRDs, workflows, or approved code changes ship.
            </p>
          </div>
        )}

        {activeView === "operations" && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-md border border-border-strong bg-canvas p-4 font-mono">
              <div className="text-xs text-fg-muted">OpenCore Local Inference</div>
              <div className="mt-1 text-2xl font-extrabold text-teal-accent">$0.00 / tok</div>
              <div className="mt-1 text-[11px] text-fg-muted">keelway-core:7b · Metal / CUDA</div>
            </div>
            <div className="rounded-md border border-border-strong bg-canvas p-4 font-mono">
              <div className="text-xs text-fg-muted">BYOM Cloud Proxy Markup</div>
              <div className="mt-1 text-2xl font-extrabold text-fg">0% Fee</div>
              <div className="mt-1 text-[11px] text-fg-muted">Authorized API Keys · Auto-Fallback</div>
            </div>
            <div className="rounded-md border border-border-strong bg-canvas p-4 font-mono">
              <div className="text-xs text-fg-muted">Median Local TTFT SLO</div>
              <div className="mt-1 text-2xl font-extrabold text-teal-accent">140 ms</div>
              <div className="mt-1 text-[11px] text-fg-muted">100% Loopback Availability</div>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-strong bg-surface px-5 py-4 text-xs">
        <span className="font-medium text-fg-muted">Ready to run this workspace locally or deploy for your team?</span>
        <div className="flex flex-wrap gap-2.5">
          <Link href="/#quickstart" className="kw-btn kw-btn-primary text-xs">Install Free CLI</Link>
          <Link href="/marketplace" className="kw-btn kw-btn-secondary text-xs">Browse Marketplace</Link>
          <Link href="/pricing" className="kw-btn kw-btn-secondary text-xs">Compare Plans</Link>
        </div>
      </div>
    </div>
  );
}
