import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacRecordKbrainFact,
  canRbacResolveKbrainConflict,
  recordKbrainFact,
  resolveKbrainFact,
  searchKbrainFacts,
  type KbrainMemoryFact,
  type KbrainMemoryScope,
  type WorkspaceRbacRole,
} from "@/lib/platformKbrainApi";

export interface KBrainMemoryGraphPanelProps {
  workspaceId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

const KBRAIN_SCOPES: ReadonlyArray<KbrainMemoryScope> = [
  "local_session",
  "project",
  "team",
  "org",
];

export function KBrainMemoryGraphPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: KBrainMemoryGraphPanelProps): React.JSX.Element {
  const canRecord = canRbacRecordKbrainFact(activeRbacRole);
  const canResolveP10 = canRbacResolveKbrainConflict(activeRbacRole);

  const [factKey, setFactKey] = useState("arch.storage_engine");
  const [factScope, setFactScope] = useState<KbrainMemoryScope>("project");
  const [factStatement, setFactStatement] = useState("");
  const [recordBusy, setRecordBusy] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [maxScope, setMaxScope] = useState<KbrainMemoryScope>("org");
  const [searchBusy, setSearchBusy] = useState(false);
  const [resolveBusyId, setResolveBusyId] = useState<string | null>(null);

  const [facts, setFacts] = useState<KbrainMemoryFact[]>([]);
  const [alertMessage, setAlertMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAlertMessage(null);
    setStatusMessage(null);
    void searchKbrainFacts(workspaceId, "", maxScope, true, activeRbacRole)
      .then((res) => {
        if (!cancelled) setFacts(res.results);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setAlertMessage(err instanceof Error ? err.message : "Failed to load KBrain memory graph.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeRbacRole, maxScope, workspaceId]);

  const handleRecordFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canRecord) {
      setAlertMessage(`RBAC Denied (${activeRbacRole}): Viewer role cannot record KBrain memory facts.`);
      return;
    }
    const cleanKey = factKey.trim();
    const cleanStatement = factStatement.trim();
    if (!cleanKey || !cleanStatement) {
      setAlertMessage("Both KBrain fact key and statement are required before recording memory.");
      return;
    }
    setRecordBusy(true);
    setAlertMessage(null);
    setStatusMessage(null);
    try {
      const created = await recordKbrainFact(
        {
          workspace_id: workspaceId,
          key: cleanKey,
          statement: cleanStatement,
          scope: factScope,
        },
        activeRbacRole,
      );
      setFacts((prev) => [created, ...prev.filter((f) => f.id !== created.id)]);
      setFactStatement("");
      if (created.status === "conflict") {
        setAlertMessage(
          `Conflict detected on "${created.key}" (${created.scope}): Existing statement diverges — P-10 human conflict resolution required.`,
        );
      } else {
        setStatusMessage(`Recorded ${created.key} (${created.scope}) · ${created.status}`);
      }
    } catch (err) {
      setAlertMessage(err instanceof Error ? err.message : "Failed to record KBrain memory fact.");
    } finally {
      setRecordBusy(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setSearchBusy(true);
    setAlertMessage(null);
    try {
      const res = await searchKbrainFacts(workspaceId, searchQuery.trim(), maxScope, true, activeRbacRole);
      setFacts(res.results);
    } catch (err) {
      setAlertMessage(err instanceof Error ? err.message : "Failed to query KBrain hybrid search.");
    } finally {
      setSearchBusy(false);
    }
  };

  const handleResolveConflict = async (fact: KbrainMemoryFact) => {
    if (!canResolveP10) {
      setAlertMessage(
        `RBAC Denied (${activeRbacRole}): Only owner or operator can sign P-10 conflict resolutions.`,
      );
      return;
    }
    setResolveBusyId(fact.id);
    setAlertMessage(null);
    try {
      const resolved = await resolveKbrainFact(workspaceId, fact.id, "approve", activeRbacRole);
      setFacts((prev) =>
        prev
          .map((item) => {
            if (item.id === fact.id) return resolved;
            if (item.key === fact.key && item.scope === fact.scope && item.status !== "withdrawn") {
              return { ...item, status: "corrected" as const };
            }
            return item;
          })
          .filter((item) => item.status !== "corrected" && item.status !== "withdrawn"),
      );
      setStatusMessage(`P-10 Conflict Resolved · Approved "${resolved.key}" (rev ${resolved.revision})`);
    } catch (err) {
      setAlertMessage(err instanceof Error ? err.message : "Failed to resolve KBrain conflict.");
    } finally {
      setResolveBusyId(null);
    }
  };

  const conflictCount = facts.filter((f) => f.status === "conflict").length;

  return (
    <section
      aria-label="KBrain scope-governed memory graph and hybrid BM25 search"
      className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">
            KBrain Scope-Governed Memory Graph &amp; Hybrid BM25 + 3-Gram Search
          </h2>
          <p className="text-xs text-fg-muted">
            Enforce hierarchical ACL boundaries (local_session &rarr; project &rarr; team &rarr; org), pre-storage DLP secret blocking, and P-10 conflict resolution.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <SemanticBadge kind="opencore" detail={`Workspace · ${workspaceId}`} />
          <SemanticBadge
            kind={conflictCount > 0 ? "needs-approval" : "passed"}
            labelOverride={conflictCount > 0 ? `${conflictCount} Conflict Pending P-10` : `${facts.length} Scoped Facts`}
          />
        </div>
      </div>

      {alertMessage ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          {alertMessage}
        </div>
      ) : null}

      {statusMessage && !alertMessage ? (
        <div role="status" className="rounded-xs border border-ok/40 bg-ok-subtle px-3 py-2 font-mono text-xs text-fg">
          {statusMessage}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">Record Scope-Governed Memory Fact (DLP Protected)</h3>
              <p className="font-mono text-[11px] text-fg-muted">
                Scans for raw secrets (sk- / ghp_) &amp; detects same-key statement drift
              </p>
            </div>
            <SemanticBadge kind="passed" labelOverride="DLP Guard Active" />
          </div>

          <form onSubmit={(e) => { void handleRecordFact(e); }} className="space-y-2.5">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
                <span>Fact key</span>
                <input
                  type="text"
                  aria-label="KBrain fact key"
                  value={factKey}
                  onChange={(e) => setFactKey(e.target.value)}
                  className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
                <span>Memory scope</span>
                <select
                  aria-label="KBrain memory scope"
                  value={factScope}
                  onChange={(e) => setFactScope(e.target.value as KbrainMemoryScope)}
                  className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
                >
                  {KBRAIN_SCOPES.map((sc) => (
                    <option key={sc} value={sc}>{sc}</option>
                  ))}
                </select>
              </label>
            </div>

            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Fact statement</span>
              <textarea
                rows={3}
                aria-label="KBrain fact statement"
                value={factStatement}
                onChange={(e) => setFactStatement(e.target.value)}
                placeholder="e.g. All sovereign tables enforce SQLite WAL and SHA-256 provenance."
                className="rounded-sm border border-border-control bg-canvas px-2.5 py-1.5 font-mono text-xs text-fg placeholder:text-fg-muted"
              />
            </label>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-[10px] text-fg-muted">
                {canRecord
                  ? `Active author role: ${activeRbacRole}`
                  : `RBAC Lock (${activeRbacRole}): Viewer role is read-only`}
              </span>
              <Button type="submit" size="sm" variant="primary" loading={recordBusy} disabled={!canRecord}>
                Record Memory Fact
              </Button>
            </div>
          </form>
        </div>

        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">Hybrid BM25 + 3-Gram Semantic Retrieval</h3>
              <p className="font-mono text-[11px] text-fg-muted">
                Lexical BM25 + character 3-gram similarity gated by max scope ACL
              </p>
            </div>
            <SemanticBadge kind="live" labelOverride={`Max Scope · ${maxScope}`} />
          </div>

          <form onSubmit={(e) => { void handleSearch(e); }} className="grid gap-2 sm:grid-cols-12">
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted sm:col-span-7">
              <span>Hybrid query</span>
              <input
                type="search"
                aria-label="KBrain hybrid search query"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search workspace facts (BM25 + 3-gram)..."
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg placeholder:text-fg-muted"
              />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted sm:col-span-5">
              <span>Max retrieval scope</span>
              <select
                aria-label="Max retrieval scope"
                value={maxScope}
                onChange={(e) => setMaxScope(e.target.value as KbrainMemoryScope)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              >
                {KBRAIN_SCOPES.map((sc) => (
                  <option key={sc} value={sc}>{sc}</option>
                ))}
              </select>
            </label>
            <div className="flex items-center justify-between gap-2 sm:col-span-12">
              <span className="font-mono text-[10px] text-fg-muted">
                {`${facts.length} matching fact${facts.length === 1 ? "" : "s"}`}
              </span>
              <Button type="submit" size="sm" variant="secondary" loading={searchBusy}>
                Search KBrain Memory
              </Button>
            </div>
          </form>

          <ul aria-label="KBrain retrieved memory facts" className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 text-xs">
            {facts.length === 0 ? (
              <li className="font-mono text-[11px] text-fg-muted">
                No KBrain memory facts matched within scope &ldquo;{maxScope}&rdquo;.
              </li>
            ) : (
              facts.map((fact) => {
                const isConflict = fact.status === "conflict";
                return (
                  <li
                    key={fact.id}
                    className="space-y-1.5 rounded-xs border border-border bg-surface p-2.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex flex-wrap items-center gap-1.5 font-mono">
                        <span className="font-semibold text-accent">{fact.key}</span>
                        <span className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 text-[10px] text-fg-muted">
                          {fact.scope}
                        </span>
                        <SemanticBadge
                          kind={isConflict ? "needs-approval" : fact.status === "approved" ? "passed" : "ready"}
                          labelOverride={fact.status}
                        />
                      </div>
                      <span className="font-mono text-[11px] text-fg-muted">
                        {`score: ${fact.hybrid_score.toFixed(2)}`}
                      </span>
                    </div>

                    <p className="text-xs text-fg">{fact.statement}</p>

                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-1.5">
                      <code
                        className="max-w-[220px] truncate font-mono text-[11px] text-accent"
                        title={fact.fact_sha256}
                      >
                        {fact.fact_sha256}
                      </code>
                      {isConflict ? (
                        <Button
                          size="sm"
                          variant="warning-cta"
                          clickOnly
                          loading={resolveBusyId === fact.id}
                          disabled={!canResolveP10}
                          onClick={() => {
                            void handleResolveConflict(fact);
                          }}
                        >
                          Resolve Conflict (P-10 Approve)
                        </Button>
                      ) : null}
                    </div>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
