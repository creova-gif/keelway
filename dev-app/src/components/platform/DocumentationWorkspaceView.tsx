import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { SDLC_STAGES, type DocGuideItem, type ExperienceMode } from "@/lib/platformData";

export interface DocumentationWorkspaceViewProps {
  experienceMode: ExperienceMode;
  guides: DocGuideItem[];
  activePrdTitle?: string;
  onSaveDoc?: (doc: DocGuideItem & { body: string }) => void;
}

type RichDocItem = DocGuideItem & { body: string; updatedAt: string; linkedPrdId?: string };
type EditorViewMode = "split" | "preview" | "source";

const SEED_DOC_BODIES: Record<string, string> = {
  "doc-1": `# Ship Your First Governed App in 5 Minutes\n\nWelcome to the Guided Non-Coder & Builder unified studio. Follow this checklist to ship safely.\n\n- [x] Open No-Code Builder and describe your business workflow\n- [x] Review auto-generated PRD and KEEL sprint tasks\n- [ ] Approve the P-10 human checkpoint before production promotion\n\n\`\`\`bash\nkeelway record verify --workspace /workspace/keelway\n\`\`\``,
  "doc-2": `# Configure Authorized BYOM Keys & Local OpenCore\n\nConnect vendor API credentials with $0.00 Keelway markup while keeping local OpenCore models ready.\n\n- [x] Select keelway-core:7b for $0 local Seatbelt execution\n- [x] Bind authorized OpenAI, Anthropic, or Gemini API keys\n- [x] Enforce fail-closed rejection of consumer web session cookies\n\n\`\`\`json\n{\n  "routingPolicy": "4d-sovereign",\n  "localFallback": "keelway-core:7b",\n  "tokenMarkupPct": 0\n}\n\`\`\``,
  "doc-3": `# Extension SDK & keelway.package/v1 Security Spec\n\nEvery Marketplace skill, agent, and webhook plugin must declare deterministic read/write scopes.\n\n- [x] Declare explicit write_paths (wildcard "/" is blocked)\n- [x] Omit eval(), shell=True, and prompt-override directives\n- [x] Sign manifest digest with Ed25519 + SHA-256\n\n\`\`\`json\n{\n  "schema": "keelway.package/v1",\n  "write_paths": ["reports/*"],\n  "requires_p10_approval": true\n}\n\`\`\``,
  "doc-4": `# Why P-10 Human-Only Gates & Air-Gap Isolation Matter\n\nAutonomous agents accelerate delivery, while destructive mutations require cryptographic human authority.\n\n- Seatbelt sandboxing confines file mutations to the active repository root\n- Prompt-bound permission rules trigger re-confirmation on model drift\n- Every human P-10 approval appends a tamper-evident SHA-256 Record entry`,
};

function buildDefaultBody(guide: DocGuideItem): string {
  return (
    SEED_DOC_BODIES[guide.id] ??
    `# ${guide.title}\n\n${guide.summary}\n\n- [x] Verified in workspace knowledge base\n- [ ] Link acceptance criteria and runbooks\n\n\`\`\`bash\nkeelway docs check --id ${guide.id}\n\`\`\``
  );
}

function renderMarkdownPreview(markdown: string): React.ReactNode {
  const lines = markdown.split(/\r?\n/);
  const blocks: React.ReactNode[] = [];
  let idx = 0;

  while (idx < lines.length) {
    const trimmed = (lines[idx] ?? "").trim();
    if (!trimmed) {
      idx += 1;
      continue;
    }
    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim() || "text";
      const codeLines: string[] = [];
      idx += 1;
      while (idx < lines.length && !(lines[idx] ?? "").trim().startsWith("```")) {
        codeLines.push(lines[idx] ?? "");
        idx += 1;
      }
      idx += 1;
      blocks.push(
        <pre key={`code-${idx}`} data-lang={lang} className="overflow-x-auto rounded-xs border border-border bg-code p-2.5 font-mono text-[11px] text-fg">
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    if (trimmed.startsWith("# ")) {
      blocks.push(<h3 key={`h1-${idx}`} className="text-sm font-semibold text-fg">{trimmed.slice(2)}</h3>);
      idx += 1;
      continue;
    }
    if (trimmed.startsWith("## ") || trimmed.startsWith("### ")) {
      blocks.push(
        <h4 key={`h2-${idx}`} className="text-xs font-semibold text-teal-accent">
          {trimmed.replace(/^#{2,3}\s+/, "")}
        </h4>,
      );
      idx += 1;
      continue;
    }
    if (trimmed.startsWith("- ")) {
      const items: string[] = [];
      while (idx < lines.length && (lines[idx] ?? "").trim().startsWith("- ")) {
        items.push((lines[idx] ?? "").trim().slice(2));
        idx += 1;
      }
      blocks.push(
        <ul key={`ul-${idx}`} className="list-disc space-y-1 ps-4 text-xs text-fg-muted">
          {items.map((item, itemIdx) => {
            if (item.startsWith("[x] ") || item.startsWith("[ ] ")) {
              const checked = item.startsWith("[x] ");
              return (
                <li key={itemIdx} className="-ms-4 flex list-none items-center gap-2 text-fg">
                  <span aria-hidden="true" className={`font-mono text-[11px] ${checked ? "text-ok" : "text-fg-dim"}`}>
                    {checked ? "[x]" : "[ ]"}
                  </span>
                  <span>{item.slice(4)}</span>
                </li>
              );
            }
            return <li key={itemIdx}>{item}</li>;
          })}
        </ul>,
      );
      continue;
    }
    blocks.push(<p key={`p-${idx}`} className="text-xs leading-relaxed text-fg-muted">{trimmed}</p>);
    idx += 1;
  }
  return blocks;
}

export function DocumentationWorkspaceView({
  experienceMode,
  guides,
  activePrdTitle,
  onSaveDoc,
}: DocumentationWorkspaceViewProps): React.JSX.Element {
  const [docs, setDocs] = useState<RichDocItem[]>(() =>
    guides.map((g, i) => ({ ...g, body: buildDefaultBody(g), updatedAt: i === 0 ? "2m ago" : "14m ago" })),
  );
  const [quadrant, setQuadrant] = useState<"all" | DocGuideItem["quadrant"]>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDocId, setSelectedDocId] = useState<string>(() => guides[0]?.id ?? "doc-1");
  const [editorMode, setEditorMode] = useState<EditorViewMode>("split");
  const [savedDocId, setSavedDocId] = useState<string | null>(null);

  useEffect(() => {
    setDocs((prev) => {
      const existingIds = new Set(prev.map((d) => d.id));
      const incoming = guides
        .filter((g) => !existingIds.has(g.id))
        .map((g) => ({ ...g, body: buildDefaultBody(g), updatedAt: "just now" }));
      return incoming.length > 0 ? [...prev, ...incoming] : prev;
    });
  }, [guides]);

  const filteredDocs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return docs.filter((doc) => {
      if (quadrant !== "all" && doc.quadrant !== quadrant) return false;
      if (!q) return true;
      return (
        doc.title.toLowerCase().includes(q) ||
        doc.summary.toLowerCase().includes(q) ||
        doc.body.toLowerCase().includes(q)
      );
    });
  }, [docs, quadrant, searchQuery]);

  const activeDoc = useMemo(
    () => docs.find((d) => d.id === selectedDocId) ?? filteredDocs[0] ?? docs[0],
    [docs, filteredDocs, selectedDocId],
  );

  const updateActiveDoc = (patch: Partial<RichDocItem>) => {
    if (!activeDoc) return;
    setSavedDocId(null);
    setDocs((prev) => prev.map((doc) => (doc.id === activeDoc.id ? { ...doc, ...patch } : doc)));
  };

  const handleCreateNewDoc = () => {
    const nextNum = docs.length + 1;
    const newId = `doc-custom-${Date.now()}`;
    const created: RichDocItem = {
      id: newId,
      quadrant: quadrant === "all" ? "How-To" : quadrant,
      title: `Untitled Runbook #${nextNum}`,
      summary: "Workspace operational guide authored in Living Knowledge Base.",
      audience: "all",
      body: `# Untitled Runbook #${nextNum}\n\nDocument architecture decisions and verification steps.\n\n- [x] Scope workspace permissions\n- [ ] Run verification suite\n\n\`\`\`bash\n./scripts/verify_engineering_gates.sh\n\`\`\``,
      updatedAt: "just now",
    };
    setDocs((prev) => [created, ...prev]);
    setSelectedDocId(newId);
    setSavedDocId(null);
  };

  const handleSyncFromPrd = () => {
    const prdLabel = activePrdTitle?.trim() || "Security-Validated Marketplace & Unified Studio";
    const stamp = `${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC`;
    const newId = `doc-prd-sync-${Date.now()}`;
    const synced: RichDocItem = {
      id: newId,
      quadrant: "Tutorial",
      title: `Release & Onboarding Guide: ${prdLabel}`,
      summary: `Auto-synchronized from active PRD (${stamp}).`,
      audience: "all",
      linkedPrdId: "PRD-ACTIVE",
      updatedAt: `Synced ${stamp}`,
      body: `# Release & Onboarding Guide: ${prdLabel}\n\nSynchronized at ${stamp} from active workspace specifications.\n\n## Operator Checklist\n- [x] Validate PRD acceptance criteria and RICE scope\n- [x] Verify SHA-256 Record provenance and zero-CDN bundle\n- [ ] Complete P-10 human sign-off prior to rollout\n\n\`\`\`bash\nkeelway release verify --prd "${prdLabel}"\n\`\`\``,
    };
    setDocs((prev) => [synced, ...prev]);
    setQuadrant("all");
    setSelectedDocId(newId);
    setSavedDocId(newId);
    onSaveDoc?.(synced);
  };

  const handleSaveDocument = () => {
    if (!activeDoc) return;
    const firstParagraph = activeDoc.body
      .split(/\r?\n/)
      .find((line) => line.trim() && !line.trim().startsWith("#") && !line.trim().startsWith("```"));
    const updated: RichDocItem = {
      ...activeDoc,
      summary: firstParagraph?.slice(0, 140) ?? activeDoc.summary,
      updatedAt: "Saved just now",
    };
    setDocs((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
    setSavedDocId(updated.id);
    onSaveDoc?.(updated);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Documentation Knowledge Base &amp; 9-Stage SDLC
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided tutorials and plain-language explanations synced with your live project."
              : "Diataxis technical documentation + canonical cross-agent engineering contract (Antigravity · Claude Code · Devin · gstack)."}
          </p>
        </div>
        <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-2 py-1 font-mono text-[11px] text-teal-accent">
          Antigravity · Claude Code · Devin · gstack
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Diataxis quadrants" className="flex flex-wrap gap-1.5">
          {(["all", "Tutorial", "How-To", "Reference", "Explanation"] as const).map((q) => (
            <button
              key={q}
              type="button"
              aria-pressed={quadrant === q}
              onClick={() => setQuadrant(q)}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
                quadrant === q
                  ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
                  : "border-border bg-surface text-fg-muted hover:text-fg"
              }`}
            >
              {q === "all" ? "All Docs" : q}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={handleCreateNewDoc}>+ New Document</Button>
          <Button size="sm" variant="primary" onClick={handleSyncFromPrd}>Sync Doc from Active PRD</Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <section aria-label="Diataxis guides" className="space-y-2.5 lg:col-span-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-dim">
            {`Knowledge Base (${filteredDocs.length})`}
          </h2>
          <label className="block">
            <span className="sr-only">Search documentation</span>
            <input
              type="search"
              aria-label="Search documentation"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search titles, runbooks, or CLI snippets…"
              className="min-h-ctrl-sm w-full rounded-sm border border-border-control bg-surface px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim"
            />
          </label>
          <div className="space-y-2">
            {filteredDocs.map((doc) => {
              const isSelected = activeDoc?.id === doc.id;
              return (
                <button
                  key={doc.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => setSelectedDocId(doc.id)}
                  className={`w-full space-y-1 rounded-md border p-3 text-start transition-colors ${
                    isSelected ? "border-teal-accent/60 bg-teal-surface" : "border-border bg-surface hover:border-border-strong"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] uppercase text-teal-accent">{doc.quadrant}</span>
                    <span className="font-mono text-[10px] text-fg-dim">{doc.updatedAt}</span>
                  </div>
                  <div className="text-xs font-semibold text-fg">{doc.title}</div>
                  <p className="line-clamp-2 text-[11px] text-fg-muted">{doc.summary}</p>
                </button>
              );
            })}
          </div>
        </section>

        <section aria-label="Markdown knowledge studio" className="space-y-3 rounded-md border border-border-strong bg-surface p-4 lg:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
            <h2 className="text-sm font-semibold text-fg">Living Markdown Studio</h2>
            <div role="group" aria-label="Editor display mode" className="flex items-center gap-1">
              {([
                { id: "split", label: "Split Editor" },
                { id: "preview", label: "Reader Preview" },
                { id: "source", label: "Markdown Source" },
              ] as const).map((m) => (
                <button
                  key={m.id}
                  type="button"
                  aria-pressed={editorMode === m.id}
                  onClick={() => setEditorMode(m.id)}
                  className={`rounded-xs border px-2 py-1 text-[11px] font-medium ${
                    editorMode === m.id ? "border-teal-accent/50 bg-teal-surface text-teal-accent" : "border-border bg-chrome text-fg-muted hover:text-fg"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {activeDoc ? (
            <>
              <div className="flex flex-wrap items-end gap-2.5">
                <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-xs text-fg-muted">
                  <span>Document title</span>
                  <input
                    type="text"
                    aria-label="Document title"
                    value={activeDoc.title}
                    onChange={(e) => updateActiveDoc({ title: e.target.value })}
                    className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs font-medium text-fg"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-fg-muted">
                  <span>Quadrant</span>
                  <select
                    aria-label="Document quadrant"
                    value={activeDoc.quadrant}
                    onChange={(e) => updateActiveDoc({ quadrant: e.target.value as DocGuideItem["quadrant"] })}
                    className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
                  >
                    <option value="Tutorial">Tutorial</option>
                    <option value="How-To">How-To</option>
                    <option value="Reference">Reference</option>
                    <option value="Explanation">Explanation</option>
                  </select>
                </label>
                <Button size="sm" variant="primary" onClick={handleSaveDocument}>Save Document</Button>
                {savedDocId === activeDoc.id ? (
                  <span role="status" className="rounded-xs border border-ok/40 bg-ok-subtle px-2 py-1 font-mono text-[11px] text-ok">
                    Saved to Workspace
                  </span>
                ) : null}
              </div>

              <div className={`grid gap-3 ${editorMode === "split" ? "md:grid-cols-2" : "grid-cols-1"}`}>
                {editorMode !== "preview" ? (
                  <label className="flex flex-col gap-1 text-xs text-fg-muted">
                    <span className="font-mono text-[11px] text-fg-dim">Markdown Source</span>
                    <textarea
                      rows={12}
                      aria-label="Markdown document editor"
                      value={activeDoc.body}
                      onChange={(e) => updateActiveDoc({ body: e.target.value })}
                      className="min-h-[240px] rounded-sm border border-border-control bg-canvas p-2.5 font-mono text-xs text-fg"
                    />
                  </label>
                ) : null}
                {editorMode !== "source" ? (
                  <div className="flex flex-col gap-1">
                    <span className="font-mono text-[11px] text-fg-dim">Structured Preview</span>
                    <div aria-label="Rendered markdown preview" className="min-h-[240px] space-y-2.5 rounded-sm border border-border bg-chrome p-3">
                      {renderMarkdownPreview(activeDoc.body)}
                    </div>
                  </div>
                ) : null}
              </div>
            </>
          ) : null}
        </section>
      </div>

      <section aria-label="9-stage autonomous engineering workflow" className="space-y-2.5">
        <h2 className="text-sm font-semibold text-fg">9-Stage Autonomous Software Development Lifecycle</h2>
        <div className="grid gap-2 md:grid-cols-3">
          {SDLC_STAGES.map((st) => (
            <div key={st.stageNumber} className="rounded-sm border border-border bg-surface p-2.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono font-semibold text-teal-accent">{`Stage ${st.stageNumber}`}</span>
                <SemanticBadge
                  kind={st.gateStatus === "p10_human_gate" ? "needs-approval" : "passed"}
                  labelOverride={st.gateStatus === "p10_human_gate" ? "P-10 Gate" : "Verified"}
                />
              </div>
              <div className="mt-1 font-medium text-fg">{st.title}</div>
              <div className="mt-0.5 font-mono text-[10px] text-fg-dim">{`${st.leadAgent} · ${st.crossAgentHarness}`}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
