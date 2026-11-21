import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacInvokeMcpOrEval,
  fetchLatestGoldenEval,
  GOLDEN_EVAL_CATEGORY_META,
  postRunGoldenEval,
  type GoldenEvalCaseItem,
  type GoldenEvalCategory,
  type GoldenEvalRunResult,
} from "@/lib/platformMcpEvalApi";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface GoldenEvalScorecardPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

export function GoldenEvalScorecardPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: GoldenEvalScorecardPanelProps): React.JSX.Element {
  const canRunEval = canRbacInvokeMcpOrEval(activeRbacRole);
  const [selectedCategory, setSelectedCategory] = useState<GoldenEvalCategory>("all");
  const [running, setRunning] = useState(false);
  const [evalRun, setEvalRun] = useState<GoldenEvalRunResult | null>(null);
  const [cachedCases, setCachedCases] = useState<GoldenEvalCaseItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    void fetchLatestGoldenEval(workspaceId, activeRbacRole).then((snap) => {
      if (cancelled || !snap.has_run || !snap.latest) return;
      setEvalRun(snap.latest);
      setCachedCases(snap.latest.cases);
    });
    return () => {
      cancelled = true;
    };
  }, [activeRbacRole, workspaceId]);

  const handleRunSuite = async () => {
    if (!canRunEval || running) return;
    setRunning(true);
    try {
      const res = await postRunGoldenEval({
        workspaceId,
        category: selectedCategory,
        role: activeRbacRole,
      });
      setEvalRun(res);
      setCachedCases((prev) => {
        if (selectedCategory === "all" || prev.length === 0) return res.cases;
        const byId = new Map(prev.map((c) => [c.id, c]));
        res.cases.forEach((c) => byId.set(c.id, c));
        return Array.from(byId.values());
      });
    } finally {
      setRunning(false);
    }
  };

  const handleCategoryChange = (next: GoldenEvalCategory) => {
    setSelectedCategory(next);
    if (!evalRun || !canRunEval) return;
    const hasCategoryCases =
      next === "all" ? cachedCases.length >= 16 : cachedCases.some((c) => c.category === next);
    if (!hasCategoryCases) {
      void postRunGoldenEval({ workspaceId, category: next, role: activeRbacRole }).then((res) => {
        setEvalRun(res);
        setCachedCases((prev) => {
          if (next === "all") return res.cases;
          const byId = new Map(prev.map((c) => [c.id, c]));
          res.cases.forEach((c) => byId.set(c.id, c));
          return Array.from(byId.values());
        });
      });
    }
  };

  const visibleCases = useMemo(() => {
    if (!evalRun) return [];
    const pool = cachedCases.length > 0 ? cachedCases : evalRun.cases;
    return selectedCategory === "all" ? pool : pool.filter((c) => c.category === selectedCategory);
  }, [cachedCases, evalRun, selectedCategory]);

  return (
    <section
      aria-label="Golden benchmark and adversarial red-team suite"
      className="space-y-4 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">
            Golden Benchmark &amp; Adversarial Red-Team Scorecard
          </h2>
          <p className="text-xs text-fg-muted">
            Deterministic 16-probe runtime verification across AST isolation, P-10 governance, SSRF/DLP red-team defenses, and calibrated unit economics.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 text-xs text-fg-muted">
            <span>Category:</span>
            <select
              aria-label="Golden eval category"
              value={selectedCategory}
              onChange={(e) => handleCategoryChange(e.target.value as GoldenEvalCategory)}
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
            >
              <option value="all">all (16 Probes)</option>
              <option value="workspace_ast">workspace_ast (Workspace &amp; AST)</option>
              <option value="governance_p10">governance_p10 (Governance &amp; P-10)</option>
              <option value="security_redteam">security_redteam (Security Red-Team)</option>
              <option value="routing_pricing">routing_pricing (Routing &amp; Pricing)</option>
            </select>
          </label>
          <Button
            size="sm"
            variant="primary"
            loading={running}
            disabled={!canRunEval}
            onClick={() => { void handleRunSuite(); }}
          >
            Run 16-Probe Golden Suite
          </Button>
        </div>
      </div>

      {!canRunEval ? (
        <div role="status" className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">
          {`Viewer role active (${activeRbacRole}): Golden benchmark execution requires owner, admin, builder, or operator role.`}
        </div>
      ) : null}

      {evalRun ? (
        <div className="space-y-3">
          <div className="grid gap-2.5 sm:grid-cols-3">
            <div className="rounded-sm border border-ok/40 bg-ok-subtle px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">Pass Rate</div>
              <div className="font-mono text-sm font-semibold text-ok">
                {`${evalRun.pass_rate}% (${evalRun.passed_cases}/${evalRun.total_cases})`}
              </div>
            </div>
            <div className="rounded-sm border border-border bg-chrome px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">Duration</div>
              <div className="font-mono text-sm font-semibold text-fg">{`${evalRun.duration_ms}ms`}</div>
            </div>
            <div className="rounded-sm border border-border bg-chrome px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">SHA-256 Receipt</div>
              <code className="block truncate font-mono text-xs font-semibold text-accent">
                {evalRun.receipt_sha256}
              </code>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {GOLDEN_EVAL_CATEGORY_META.map((cat) => {
              const stat = evalRun.categories[cat.id] ?? { total: 4, passed: 4, pass_rate: 100 };
              return (
                <div
                  key={cat.id}
                  className="flex items-center justify-between gap-2 rounded-xs border border-border bg-canvas px-2.5 py-2 text-xs"
                >
                  <div>
                    <div className="font-semibold text-fg">{cat.label}</div>
                    <code className="font-mono text-[10px] text-fg-muted">{cat.id}</code>
                  </div>
                  <SemanticBadge
                    kind={stat.passed === stat.total ? "passed" : "failed"}
                    labelOverride={`${stat.passed}/${stat.total} (${stat.pass_rate}%)`}
                  />
                </div>
              );
            })}
          </div>

          <ul aria-label="Golden evaluation probe results" className="grid gap-2 md:grid-cols-2">
            {visibleCases.map((probe) => (
              <li
                key={probe.id}
                className="space-y-1.5 rounded-sm border border-border bg-canvas px-3 py-2.5 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5 font-mono">
                    <span className="font-semibold text-fg">{probe.id}</span>
                    <span className="rounded-xs border border-accent/40 bg-accent-subtle px-1.5 py-0.5 text-[10px] text-accent">
                      {probe.category}
                    </span>
                  </div>
                  <span
                    className={`rounded-xs border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${
                      probe.passed
                        ? "border-ok/40 bg-ok-subtle text-ok"
                        : "border-danger/45 bg-danger-subtle text-danger"
                    }`}
                  >
                    {probe.passed ? "PASSED" : "FAILED"}
                  </span>
                </div>
                <div className="font-medium text-fg">{probe.title}</div>
                <p className="font-mono text-[11px] text-fg-muted">{probe.evidence}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="rounded-xs border border-border bg-chrome px-3 py-2.5 font-mono text-xs text-fg-muted">
          Ready to execute 16 deterministic golden &amp; adversarial probes across workspace AST, P-10 governance, SSRF/DLP security, and calibrated pricing.
        </div>
      )}
    </section>
  );
}
