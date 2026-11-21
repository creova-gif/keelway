import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateDevx, DEFAULT_LANGGRAPH_PYTHON_SOURCE, migrateLanggraphSource,
  type LangGraphMigrationResult, type LangGraphSourceLanguage, type WorkspaceRbacRole,
} from "@/lib/platformDevxApi";

export interface LangGraphMigratorPanelProps {
  workspaceId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

export function LangGraphMigratorPanel({
  workspaceId = "default", activeRbacRole = "owner",
}: LangGraphMigratorPanelProps): React.JSX.Element {
  const canMutate = canRbacMutateDevx(activeRbacRole);
  const [sourceCode, setSourceCode] = useState<string>(DEFAULT_LANGGRAPH_PYTHON_SOURCE);
  const [sourceLanguage, setSourceLanguage] = useState<LangGraphSourceLanguage>("python");
  const [workflowName, setWorkflowName] = useState<string>("migrated-release-review-kflow");
  const [migrating, setMigrating] = useState<boolean>(false);
  const [result, setResult] = useState<LangGraphMigrationResult | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const handleMigrate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canMutate || migrating) return;
    setMigrating(true);
    setErrorBanner(null);
    try {
      const migrated = await migrateLanggraphSource(
        workspaceId, sourceCode, sourceLanguage, workflowName.trim() || "migrated-release-review-kflow", activeRbacRole,
      );
      setResult(migrated);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to migrate LangGraph source to KFlow.");
    } finally {
      setMigrating(false);
    }
  };

  const maxIter = result?.bounded_loop_policies[0]?.max_iterations ?? 5;

  return (
    <section aria-label="LangGraph to KFlow static AST migrator" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold text-fg">
            LangGraph / LangChain Static AST Importer (<code>keelway migrate</code>)
          </h2>
          <p className="text-xs text-fg-muted">
            Zero-<code>eval</code> static AST parser converting <code>StateGraph</code> nodes, conditional cycles, and <code>interrupt()</code> pauses into bounded KFlow + P-10 human-gated blueprints.
          </p>
        </div>
        <SemanticBadge kind="opencore" labelOverride="Zero-Eval Static AST" />
      </div>

      {!canMutate ? (
        <div className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">
          {`Migrator Read-Only Mode (${activeRbacRole}): Static AST conversion to KFlow blueprints is disabled for viewer role.`}
        </div>
      ) : null}

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{errorBanner}</span>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <form onSubmit={(e) => { void handleMigrate(e); }} className="space-y-2.5 rounded-sm border border-border bg-chrome p-3">
          <div className="grid gap-2.5 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Source language</span>
              <select aria-label="LangGraph source language" value={sourceLanguage} onChange={(e) => setSourceLanguage(e.target.value as LangGraphSourceLanguage)} disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                <option value="python">python (ast.parse)</option>
                <option value="typescript">typescript (StateGraph)</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Target KFlow name</span>
              <input type="text" aria-label="Target KFlow workflow name" value={workflowName} onChange={(e) => setWorkflowName(e.target.value)} disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
          </div>

          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>StateGraph / LangChain source snippet</span>
            <textarea
              rows={9}
              aria-label="LangGraph source code"
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
              disabled={!canMutate}
              className="rounded-sm border border-border-control bg-canvas p-2.5 font-mono text-[11px] text-fg"
            />
          </label>

          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[11px] text-fg-muted">Extracts interrupt() -&gt; p10_human_gate &amp; cyclic max_iterations</span>
            <Button type="submit" size="sm" variant="primary" loading={migrating} disabled={!canMutate}>
              Convert LangGraph to KFlow
            </Button>
          </div>
        </form>

        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold text-fg">KFlow Blueprint &amp; Static AST Diagnostics</h3>
            {result ? (
              <code title={result.migration_sha256} className="max-w-[240px] truncate rounded-xs border border-border bg-canvas px-2 py-0.5 font-mono text-[11px] text-accent">
                {result.migration_sha256}
              </code>
            ) : null}
          </div>

          {result ? (
            <div role="status" className="space-y-2.5 text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <SemanticBadge kind="passed" labelOverride={`${result.nodes.length} Nodes · ${result.edges.length} Edges`} />
                {result.p10_gates_injected.length > 0 ? (
                  <SemanticBadge kind="needs-approval" labelOverride={`p10_human_gate · ${result.p10_gates_injected.join(", ")}`} />
                ) : null}
                {result.cycles_detected > 0 ? (
                  <SemanticBadge kind="opencore" labelOverride={`Bounded Cycle · max_iterations: ${maxIter}`} />
                ) : null}
              </div>

              <div className="flex flex-wrap gap-1.5 font-mono text-[11px]">
                {result.nodes.map((n) => (
                  <span key={n.id} className="rounded-xs border border-border bg-canvas px-2 py-0.5 text-fg">
                    {`${n.id} (${n.kind})`}
                  </span>
                ))}
              </div>

              {result.legacy_warnings.length > 0 ? (
                <ul aria-label="Legacy LangChain deprecation advisories" className="space-y-1 rounded-xs border border-warning/45 bg-warning-subtle px-2.5 py-1.5 font-mono text-[11px] text-fg">
                  {result.legacy_warnings.map((w, idx) => (
                    <li key={`warn-${idx}`}>{`Advisory: ${w}`}</li>
                  ))}
                </ul>
              ) : null}

              <pre className="max-h-52 overflow-auto rounded-xs border border-border bg-code p-2.5 font-mono text-[11px] text-fg">
                <code>{result.kflow_sdk_code}</code>
              </pre>
            </div>
          ) : (
            <p className="rounded-xs border border-border bg-canvas px-3 py-4 text-xs text-fg-muted">
              Click <strong>Convert LangGraph to KFlow</strong> to statically analyze <code>StateGraph</code> nodes, inject P-10 checkpoints for <code>interrupt()</code> calls, bound cyclic edges with <code>max_iterations</code>, and emit KFlow SDK code.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
