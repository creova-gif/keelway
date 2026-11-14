import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  type ExportBundleReceipt,
  RecordChainCallouts,
  RecordEntryInspector,
  RecordOutcomeBadge,
  type RecordEntryInspectorProps,
} from "@/components/screens/RecordEntryInspector";
import { Button } from "@/components/ui/Button";
import {
  exportAuditBundle,
  fetchAuditEntries,
  fetchAuditMerkleProof,
  verifyAuditChain,
} from "@/lib/api";
import type {
  ChainVerificationState,
  RecordActorKind,
  RecordLedgerEntry,
  RecordOutcomeKind,
} from "@/lib/types";

export { RecordEntryInspector, type RecordEntryInspectorProps };

export interface RecordAuditLedgerProps {
  initialEntries?: RecordLedgerEntry[];
  initialChainState?: ChainVerificationState;
  selectedSeq?: number | null;
  initialSelectedSeq?: number | null;
  defaultInspectorOpen?: boolean;
  loading?: boolean;
  error?: string | null;
  onSelectSeq?: (seq: number | null) => void;
  onOpenDiffInReview?: (diffPath: string, seq: number) => void;
  fetchEntriesFn?: typeof fetchAuditEntries;
  verifyChainFn?: typeof verifyAuditChain;
  fetchMerkleProofFn?: typeof fetchAuditMerkleProof;
  exportBundleFn?: typeof exportAuditBundle;
}

const ACTOR_OPTIONS: ReadonlyArray<{ value: "all" | RecordActorKind; label: string }> = [
  { value: "all", label: "All actors" },
  { value: "human", label: "Human" },
  { value: "agent", label: "Agent" },
  { value: "policy", label: "Policy" },
  { value: "system", label: "System" },
];

const OUTCOME_OPTIONS: ReadonlyArray<{ value: "all" | RecordOutcomeKind; label: string }> = [
  { value: "all", label: "All outcomes" },
  { value: "passed", label: "Passed" },
  { value: "ready", label: "Ready" },
  { value: "allowed", label: "Allowed" },
  { value: "denied", label: "Denied" },
  { value: "blocked", label: "Blocked" },
  { value: "failed", label: "Failed" },
];

function buildDistinctOptions(
  allLabel: string,
  values: string[],
): Array<{ value: string; label: string }> {
  return [
    { value: "all", label: allLabel },
    ...Array.from(new Set(values)).filter(Boolean).map((v) => ({ value: v, label: v })),
  ];
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ReadonlyArray<{ value: string; label: string }>;
  onChange: (next: string) => void;
}): React.JSX.Element {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] font-medium text-fg-muted">{label}</label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-ctrl-sm rounded-xs border border-border-control bg-surface px-2 py-1 text-xs text-fg"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}

function triggerSafeBrowserDownload(filename: string, content: string): void {
  if (
    typeof window === "undefined" ||
    typeof document === "undefined" ||
    typeof navigator === "undefined" ||
    /jsdom/i.test(navigator.userAgent ?? "") ||
    typeof URL === "undefined" ||
    typeof URL.createObjectURL !== "function"
  ) {
    return;
  }
  try {
    const objectUrl = URL.createObjectURL(new Blob([content], { type: "application/json;charset=utf-8" }));
    const anchor = Object.assign(document.createElement("a"), {
      href: objectUrl,
      download: filename,
      rel: "noopener",
    });
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  } catch {
    // Non-fatal in sandboxed webviews
  }
}

export function RecordAuditLedger({
  initialEntries,
  initialChainState,
  selectedSeq,
  initialSelectedSeq,
  defaultInspectorOpen = true,
  loading: loadingProp,
  error: errorProp,
  onSelectSeq,
  onOpenDiffInReview,
  fetchEntriesFn = fetchAuditEntries,
  verifyChainFn = verifyAuditChain,
  fetchMerkleProofFn = fetchAuditMerkleProof,
  exportBundleFn = exportAuditBundle,
}: RecordAuditLedgerProps): React.JSX.Element {
  const [entries, setEntries] = useState<RecordLedgerEntry[]>(() => initialEntries ?? []);
  const [isLoading, setIsLoading] = useState<boolean>(
    () => loadingProp ?? initialEntries === undefined,
  );
  const [loadError, setLoadError] = useState<string | null>(() => errorProp ?? null);
  const [chainState, setChainState] = useState<ChainVerificationState>(
    () =>
      initialChainState ?? {
        status: initialEntries ? "verified" : "checking",
        totalEntries: initialEntries?.length ?? 0,
      },
  );
  const [isVerifying, setIsVerifying] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportReceipt, setExportReceipt] = useState<ExportBundleReceipt | null>(null);

  const initialResolvedSeq =
    selectedSeq !== undefined
      ? selectedSeq
      : initialSelectedSeq !== undefined
        ? initialSelectedSeq
        : defaultInspectorOpen && initialEntries && initialEntries.length > 0
          ? initialEntries[0].seq
          : null;

  const [internalSelectedSeq, setInternalSelectedSeq] = useState<number | null>(initialResolvedSeq);
  const [inspectorOpen, setInspectorOpen] = useState<boolean>(initialResolvedSeq !== null);
  const [missingPrevSeq, setMissingPrevSeq] = useState<number | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [targetFilter, setTargetFilter] = useState("all");
  const [actorFilter, setActorFilter] = useState<"all" | RecordActorKind>("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [modelFilter, setModelFilter] = useState("all");
  const [outcomeFilter, setOutcomeFilter] = useState<"all" | RecordOutcomeKind>("all");
  const [dateFilter, setDateFilter] = useState("all");

  const searchId = useId();
  const rowButtonRefs = useRef<Record<number, HTMLButtonElement | null>>({});
  const fetchEntriesRef = useRef(fetchEntriesFn);
  fetchEntriesRef.current = fetchEntriesFn;
  const verifyChainRef = useRef(verifyChainFn);
  verifyChainRef.current = verifyChainFn;
  const exportBundleRef = useRef(exportBundleFn);
  exportBundleRef.current = exportBundleFn;
  const onSelectSeqRef = useRef(onSelectSeq);
  onSelectSeqRef.current = onSelectSeq;

  useEffect(() => {
    if (initialEntries !== undefined) {
      setEntries(initialEntries);
      setIsLoading(false);
    }
  }, [initialEntries]);

  useEffect(() => {
    if (initialChainState !== undefined) {
      setChainState(initialChainState);
    }
  }, [initialChainState]);

  useEffect(() => {
    if (selectedSeq !== undefined) {
      setInternalSelectedSeq(selectedSeq);
      setInspectorOpen(selectedSeq !== null);
      setMissingPrevSeq(null);
    }
  }, [selectedSeq]);

  const executeLedgerLoad = useCallback(
    async (
      shouldFetchEntries: boolean,
      shouldVerifyChain: boolean,
      isCancelled?: () => boolean,
    ) => {
      if (!shouldFetchEntries && !shouldVerifyChain) return;
      if (shouldFetchEntries) setIsLoading(true);
      setLoadError(null);

      try {
        const [loadedEntries, verifiedState] = await Promise.all([
          shouldFetchEntries ? fetchEntriesRef.current() : Promise.resolve(null),
          shouldVerifyChain ? verifyChainRef.current() : Promise.resolve(null),
        ]);
        if (isCancelled?.()) return;

        if (loadedEntries !== null) {
          setEntries(loadedEntries);
          if (
            selectedSeq === undefined &&
            initialSelectedSeq === undefined &&
            defaultInspectorOpen &&
            loadedEntries.length > 0
          ) {
            setInternalSelectedSeq((prev) => prev ?? loadedEntries[0].seq);
            setInspectorOpen(true);
          }
        }
        if (verifiedState !== null) {
          setChainState(verifiedState);
        }
      } catch (err: unknown) {
        if (isCancelled?.()) return;
        setLoadError(
          err instanceof Error ? err.message : "Local audit ledger endpoint did not respond.",
        );
      } finally {
        if (!isCancelled?.() && shouldFetchEntries) {
          setIsLoading(false);
        }
      }
    },
    [defaultInspectorOpen, initialSelectedSeq, selectedSeq],
  );

  useEffect(() => {
    let cancelled = false;
    void executeLedgerLoad(
      initialEntries === undefined,
      initialChainState === undefined,
      () => cancelled,
    );
    return () => {
      cancelled = true;
    };
  }, [executeLedgerLoad, initialChainState, initialEntries]);

  const closeInspector = useCallback(() => {
    setInspectorOpen(false);
    setMissingPrevSeq(null);
    onSelectSeqRef.current?.(null);
  }, []);

  useEffect(() => {
    if (!inspectorOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeInspector();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeInspector, inspectorOpen]);

  const clearFilters = useCallback(() => {
    setSearchQuery("");
    setTargetFilter("all");
    setActorFilter("all");
    setActionFilter("all");
    setModelFilter("all");
    setOutcomeFilter("all");
    setDateFilter("all");
  }, []);

  const handleSelectSeq = useCallback((seq: number) => {
    setInternalSelectedSeq(seq);
    setInspectorOpen(true);
    setMissingPrevSeq(null);
    onSelectSeqRef.current?.(seq);
  }, []);

  const targetOptions = useMemo(() => buildDistinctOptions("All targets", entries.map((e) => e.target)), [entries]);
  const actionOptions = useMemo(() => buildDistinctOptions("All actions", entries.map((e) => e.action)), [entries]);
  const modelOptions = useMemo(() => buildDistinctOptions("All models", entries.map((e) => e.modelId)), [entries]);
  const dateOptions = useMemo(
    () =>
      buildDistinctOptions(
        "All dates",
        entries.map((e) => e.timestampEt.slice(0, 10)).filter((d) => d.length >= 8),
      ),
    [entries],
  );

  const hasActiveFilters =
    searchQuery.trim().length > 0 ||
    [targetFilter, actorFilter, actionFilter, modelFilter, outcomeFilter, dateFilter].some(
      (f) => f !== "all",
    );

  const filteredEntries = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const qBareSeq = q.startsWith("#") ? q.slice(1) : q;

    return entries.filter((entry) => {
      if (targetFilter !== "all" && entry.target !== targetFilter) return false;
      if (actorFilter !== "all" && entry.actorKind !== actorFilter) return false;
      if (actionFilter !== "all" && entry.action !== actionFilter) return false;
      if (modelFilter !== "all" && entry.modelId !== modelFilter) return false;
      if (outcomeFilter !== "all" && entry.outcome !== outcomeFilter) return false;
      if (dateFilter !== "all" && entry.timestampEt.slice(0, 10) !== dateFilter) return false;
      if (!q) return true;

      const haystack = [
        `#${entry.seq}`,
        String(entry.seq),
        entry.action,
        entry.target,
        entry.hash,
        entry.prevHash,
        entry.actorLabel,
        entry.modelId,
        entry.approvalLabel,
      ]
        .join(" ")
        .toLowerCase();
      return String(entry.seq).includes(qBareSeq) || haystack.includes(q);
    });
  }, [actionFilter, actorFilter, dateFilter, entries, modelFilter, outcomeFilter, searchQuery, targetFilter]);

  const selectedEntry = useMemo(
    () =>
      internalSelectedSeq !== null
        ? entries.find((entry) => entry.seq === internalSelectedSeq) ?? null
        : null,
    [entries, internalSelectedSeq],
  );

  const handleVerifyChain = async () => {
    setIsVerifying(true);
    try {
      setChainState(await verifyChainRef.current());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Chain verification request failed.");
    } finally {
      setIsVerifying(false);
    }
  };

  const handleExportBundle = async () => {
    setIsExporting(true);
    try {
      const bundle = await exportBundleRef.current();
      const jsonlLines = bundle.jsonl.split(/\r?\n/).filter((l) => l.trim().length > 0).length;
      const csvRows = Math.max(
        0,
        bundle.csv.split(/\r?\n/).filter((l) => l.trim().length > 0).length - 1,
      );
      setExportReceipt({
        format: bundle.format,
        generatedAt: bundle.generatedAt,
        jsonlLines,
        csvRows,
        hasPythonVerifier: bundle.verifierScript.trim().length > 0,
        chainStatus: bundle.chainStatus,
      });
      triggerSafeBrowserDownload(
        `keelway-record-bundle-${bundle.chainStatus}.json`,
        JSON.stringify(bundle, null, 2),
      );
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Unable to export forensic audit bundle.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleOpenBrokenEntry = (brokenSeq: number) => {
    if (!filteredEntries.some((entry) => entry.seq === brokenSeq) && hasActiveFilters) {
      clearFilters();
    }
    handleSelectSeq(brokenSeq);
    rowButtonRefs.current[brokenSeq]?.focus();
  };

  const handleJumpToPrevSeq = (prevSeq: number) => {
    if (!entries.some((entry) => entry.seq === prevSeq)) {
      setMissingPrevSeq(prevSeq);
      return;
    }
    if (!filteredEntries.some((entry) => entry.seq === prevSeq) && hasActiveFilters) {
      clearFilters();
    }
    handleSelectSeq(prevSeq);
  };

  const handleRowButtonKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    rowIndex: number,
  ) => {
    const delta = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0;
    if (delta === 0) return;
    event.preventDefault();
    const neighbor = filteredEntries[rowIndex + delta];
    if (neighbor) {
      rowButtonRefs.current[neighbor.seq]?.focus();
      if (inspectorOpen) handleSelectSeq(neighbor.seq);
    }
  };

  const effectiveLoading = loadingProp ?? isLoading;
  const effectiveError = errorProp ?? loadError;

  return (
    <div className="flex h-full min-h-[480px] w-full overflow-hidden bg-canvas text-ui text-fg">
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-chrome px-4 py-2.5">
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-fg">Record</h1>
            <p className="text-xs text-fg-muted">
              Append-only SHA-256 hash-chained audit ledger · local P-10 & 4D routing provenance
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button size="sm" variant="secondary" loading={isVerifying} onClick={() => void handleVerifyChain()}>
              Verify chain
            </Button>
            <Button size="sm" variant="secondary" loading={isExporting} onClick={() => void handleExportBundle()}>
              Export…
            </Button>
          </div>
        </header>

        <RecordChainCallouts
          chainState={chainState}
          totalLoadedEntries={entries.length}
          effectiveError={effectiveError}
          isExporting={isExporting}
          exportReceipt={exportReceipt}
          onRetry={() => void executeLedgerLoad(true, true)}
          onOpenBrokenEntry={handleOpenBrokenEntry}
          onExportBundle={() => void handleExportBundle()}
          onDismissExportReceipt={() => setExportReceipt(null)}
        />

        <section
          aria-label="Filter Record entries"
          className="flex flex-wrap items-end gap-2.5 border-b border-border bg-chrome/60 px-4 py-2"
        >
          <div className="flex min-w-[180px] flex-1 flex-col gap-1">
            <label htmlFor={searchId} className="text-[11px] font-medium text-fg-muted">
              Search <span className="sr-only">Record entries</span>
            </label>
            <input
              id={searchId}
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search #seq, action, target, hash, actor, model…"
              className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-surface px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim"
            />
          </div>

          <FilterSelect label="Target" value={targetFilter} options={targetOptions} onChange={setTargetFilter} />
          <FilterSelect
            label="Who"
            value={actorFilter}
            options={ACTOR_OPTIONS}
            onChange={(v) => setActorFilter(v as "all" | RecordActorKind)}
          />
          <FilterSelect label="Action" value={actionFilter} options={actionOptions} onChange={setActionFilter} />
          <FilterSelect label="Model" value={modelFilter} options={modelOptions} onChange={setModelFilter} />
          <FilterSelect
            label="Outcome"
            value={outcomeFilter}
            options={OUTCOME_OPTIONS}
            onChange={(v) => setOutcomeFilter(v as "all" | RecordOutcomeKind)}
          />
          <FilterSelect label="Date" value={dateFilter} options={dateOptions} onChange={setDateFilter} />

          <div className="ms-auto flex items-center gap-2 self-end pb-0.5">
            {hasActiveFilters ? (
              <Button size="sm" variant="ghost" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : null}
            <span className="font-mono text-xs tabular-nums text-fg-muted">
              {`Showing ${filteredEntries.length} of ${entries.length} entries`}
            </span>
          </div>
        </section>

        <div className="min-h-0 flex-1 overflow-auto bg-canvas">
          {effectiveLoading ? (
            <div aria-busy="true" className="space-y-2 p-4">
              <p className="font-mono text-xs text-fg-muted">Loading SHA-256 Record entries…</p>
              {[0, 1, 2, 3].map((rowIdx) => (
                <div key={rowIdx} className="h-table-row w-full rounded-xs border border-border bg-surface-elevated" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
              <p className="text-sm font-medium text-fg">No entries recorded yet</p>
              <p className="max-w-md text-xs text-fg-muted">
                Approved P-10 actions, sandbox test runs, and 4D routing decisions are appended here with SHA-256 chain links.
              </p>
            </div>
          ) : filteredEntries.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2.5 py-12 text-center">
              <p className="text-sm font-medium text-fg">No Record entries match the current filters</p>
              <Button size="sm" variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          ) : (
            <table
              aria-label="Record SHA-256 audit ledger"
              className="w-full border-collapse text-start text-xs tabular-nums"
            >
              <thead className="sticky top-0 z-10 border-b border-border-strong bg-chrome text-fg-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap">When (ET)</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap">Who</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">What</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap">Model</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap">Approval</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap">Outcome</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold whitespace-nowrap">Integrity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredEntries.map((entry, rowIndex) => {
                  const isSelected = inspectorOpen && selectedEntry?.seq === entry.seq;
                  const isTamperedHere = chainState.status === "broken" && chainState.brokenAtSeq === entry.seq;
                  const isUntrustedAfterBreak =
                    chainState.status === "broken" &&
                    typeof chainState.brokenAtSeq === "number" &&
                    entry.seq > chainState.brokenAtSeq;

                  return (
                    <tr
                      key={entry.seq}
                      data-selected={isSelected ? "true" : undefined}
                      onClick={() => handleSelectSeq(entry.seq)}
                      className={`min-h-table-row cursor-pointer transition-colors ${
                        isSelected
                          ? "border-s-2 border-s-teal-accent bg-teal-surface/40"
                          : isTamperedHere
                            ? "bg-danger-subtle/40 hover:bg-danger-subtle/60"
                            : "hover:bg-surface-elevated/70"
                      }`}
                    >
                      <td className="px-3 py-2 font-mono whitespace-nowrap text-fg-muted">
                        {entry.timestampEt}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-fg">{entry.actorLabel}</span>
                          <span className="rounded-xs border border-border-control/50 bg-surface-elevated px-1 py-0 font-mono text-[10px] text-fg-muted">
                            {entry.actorKind}
                          </span>
                        </div>
                      </td>
                      <td className="max-w-[280px] px-3 py-2">
                        <div className="flex flex-wrap items-baseline gap-1.5">
                          <span className="font-medium text-fg">{entry.action}</span>
                          <code
                            dir="ltr"
                            className="unicode-bidi-isolate truncate rounded-xs border border-border bg-code px-1.5 py-0.5 font-mono text-[11px] text-fg-muted"
                          >
                            {entry.target}
                          </code>
                        </div>
                      </td>
                      <td className="px-3 py-2 font-mono whitespace-nowrap text-fg">
                        {`${entry.modelId} ${entry.modelVersion} · ${entry.promptVersion}`}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 text-fg">
                          {entry.approvedByHuman ? (
                            <span aria-hidden="true" className="font-mono text-[11px] font-bold text-teal-accent">
                              ✓
                            </span>
                          ) : null}
                          <span>{entry.approvalLabel}</span>
                        </span>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <RecordOutcomeBadge outcome={entry.outcome} />
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <button
                          ref={(el) => {
                            rowButtonRefs.current[entry.seq] = el;
                          }}
                          type="button"
                          aria-current={isSelected ? "true" : undefined}
                          aria-expanded={isSelected ? "true" : "false"}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectSeq(entry.seq);
                          }}
                          onKeyDown={(e) => handleRowButtonKeyDown(e, rowIndex)}
                          className={`inline-flex items-center gap-1.5 rounded-xs border px-2 py-0.5 font-mono text-[11px] transition-colors ${
                            isTamperedHere
                              ? "border-danger/60 bg-danger-subtle font-semibold text-danger"
                              : isUntrustedAfterBreak
                                ? "border-warning/50 bg-warning-subtle text-warning"
                                : isSelected
                                  ? "border-teal-accent/60 bg-teal-surface font-semibold text-teal-accent"
                                  : "border-border-control/70 bg-surface-elevated text-fg hover:border-fg-muted"
                          }`}
                        >
                          {isTamperedHere ? (
                            <span aria-hidden="true">✕</span>
                          ) : isUntrustedAfterBreak ? (
                            <span aria-hidden="true">!</span>
                          ) : null}
                          <span>{`#${entry.seq}`}</span>
                          <span aria-hidden="true" className="text-fg-dim">·</span>
                          <code dir="ltr" className="unicode-bidi-isolate">
                            {`${entry.hash.slice(0, 8)}…`}
                          </code>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {inspectorOpen && selectedEntry ? (
        <RecordEntryInspector
          entry={selectedEntry}
          chainState={chainState}
          missingPrevSeq={missingPrevSeq}
          onSelectPrevSeq={handleJumpToPrevSeq}
          onClose={closeInspector}
          onOpenDiffInReview={onOpenDiffInReview}
          fetchMerkleProofFn={fetchMerkleProofFn}
        />
      ) : null}
    </div>
  );
}
