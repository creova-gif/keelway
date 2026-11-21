import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type {
  AuditMerkleProof,
  ChainVerificationState,
  RecordLedgerEntry,
  RecordOutcomeKind,
} from "@/lib/types";

export interface ExportBundleReceipt {
  format: string;
  generatedAt: string;
  jsonlLines: number;
  csvRows: number;
  hasPythonVerifier: boolean;
  chainStatus: "verified" | "broken";
}

export function RecordChainCallouts({
  chainState,
  totalLoadedEntries,
  effectiveError,
  isExporting,
  exportReceipt,
  onRetry,
  onOpenBrokenEntry,
  onExportBundle,
  onDismissExportReceipt,
}: {
  chainState: ChainVerificationState;
  totalLoadedEntries: number;
  effectiveError: string | null;
  isExporting: boolean;
  exportReceipt: ExportBundleReceipt | null;
  onRetry: () => void;
  onOpenBrokenEntry: (brokenSeq: number) => void;
  onExportBundle: () => void;
  onDismissExportReceipt: () => void;
}): React.JSX.Element {
  const brokenSeq = chainState.brokenAtSeq ?? 0;
  const verifiedTotal = (chainState.totalEntries || totalLoadedEntries).toLocaleString("en-US");

  return (
    <div className="space-y-2 border-b border-border bg-canvas px-4 py-2.5">
      {effectiveError ? (
        <CalloutBanner
          variant="runtime-unreachable"
          title="Record audit ledger unreachable"
          description={effectiveError}
          safeStateNote="Append-only SQLite WAL ledger on disk has not been modified."
          actions={
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          }
        />
      ) : chainState.status === "broken" ? (
        <CalloutBanner
          variant="chain-broken"
          title={`Chain broken at entry #${brokenSeq}: hash doesn't match the previous entry`}
          description={`Entries after #${brokenSeq} can't be trusted.`}
          safeStateNote={
            chainState.expectedPrevHash && chainState.actualPrevHash
              ? `Expected prev ${chainState.expectedPrevHash.slice(0, 12)}… · recorded ${chainState.actualPrevHash.slice(0, 12)}…`
              : undefined
          }
          actions={
            <>
              <Button size="sm" variant="danger" onClick={() => onOpenBrokenEntry(brokenSeq)}>
                {`Open entry #${brokenSeq}`}
              </Button>
              <Button size="sm" variant="secondary" loading={isExporting} onClick={onExportBundle}>
                Export report
              </Button>
            </>
          }
        />
      ) : chainState.status === "verified" ? (
        <CalloutBanner
          variant="chain-verified"
          title={`Chain verified · ${verifiedTotal} entries · no gaps`}
          description={
            chainState.merkleRoot ? (
              <span>
                Merkle root{" "}
                <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">
                  {`${chainState.merkleRoot.slice(0, 16)}…`}
                </code>
              </span>
            ) : undefined
          }
          safeStateNote={chainState.verifiedAt ? `Verified at ${chainState.verifiedAt}` : undefined}
        />
      ) : (
        <div className="rounded-md border border-border-strong bg-surface px-3.5 py-2 font-mono text-xs text-fg-muted">
          Checking SHA-256 chain continuity across local ledger…
        </div>
      )}

      {exportReceipt ? (
        <section
          aria-label="Forensic export bundle receipt"
          className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border-strong bg-surface-elevated px-3 py-2 text-xs"
        >
          <div className="min-w-0 space-y-0.5">
            <div className="font-medium text-fg">
              Forensic bundle prepared ·{" "}
              <code dir="ltr" className="unicode-bidi-isolate font-mono">
                {exportReceipt.format}
              </code>
            </div>
            <div className="font-mono text-[11px] tabular-nums text-fg-muted">
              {`JSONL (${exportReceipt.jsonlLines} lines) + CSV (${exportReceipt.csvRows} rows) + standalone Python SHA-256 verifier · chain=${exportReceipt.chainStatus} · ${exportReceipt.generatedAt}`}
            </div>
          </div>
          <Button size="sm" variant="ghost" onClick={onDismissExportReceipt}>
            Dismiss receipt
          </Button>
        </section>
      ) : null}
    </div>
  );
}

export function RecordOutcomeBadge({
  outcome,
}: {
  outcome: RecordOutcomeKind;
}): React.JSX.Element {
  const spec =
    outcome === "passed"
      ? { dot: "bg-ok", text: "text-ok", label: "Passed" }
      : outcome === "ready"
        ? { dot: "bg-fg-muted", text: "text-fg-muted", label: "Ready" }
        : outcome === "allowed"
          ? { dot: "bg-fg-muted", text: "text-fg", label: "Allowed" }
          : { dot: "bg-danger", text: "text-danger", label: outcome === "denied" ? "Denied" : outcome === "blocked" ? "Blocked" : "Failed" };
  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-[11px] ${spec.text}`}>
      <span aria-hidden="true" className={`inline-block h-1.5 w-1.5 rounded-full ${spec.dot}`} />
      {spec.label}
    </span>
  );
}

export interface RecordEntryInspectorProps {
  entry: RecordLedgerEntry;
  chainState: ChainVerificationState;
  missingPrevSeq?: number | null;
  inspectorRef?: React.Ref<HTMLElement>;
  onSelectPrevSeq: (prevSeq: number) => void;
  onClose: () => void;
  onOpenDiffInReview?: (diffPath: string, seq: number) => void;
  fetchMerkleProofFn: (seq: number) => Promise<AuditMerkleProof>;
}

export function RecordEntryInspector({
  entry,
  chainState,
  missingPrevSeq = null,
  inspectorRef,
  onSelectPrevSeq,
  onClose,
  onOpenDiffInReview,
  fetchMerkleProofFn,
}: RecordEntryInspectorProps): React.JSX.Element {
  const [proofState, setProofState] = useState<{
    seq: number;
    status: "loading" | "ready" | "error";
    proof: AuditMerkleProof | null;
  }>(() => ({ seq: entry.seq, status: "loading", proof: null }));

  const fetchProofRef = useRef(fetchMerkleProofFn);
  fetchProofRef.current = fetchMerkleProofFn;

  useEffect(() => {
    let cancelled = false;
    const targetSeq = entry.seq;
    setProofState({ seq: targetSeq, status: "loading", proof: null });

    Promise.resolve()
      .then(() => fetchProofRef.current(targetSeq))
      .then((proof) => {
        if (!cancelled) {
          setProofState({ seq: targetSeq, status: "ready", proof });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProofState({ seq: targetSeq, status: "error", proof: null });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [entry.seq]);

  const effectiveProofStatus =
    proofState.seq !== entry.seq ? "loading" : proofState.status;
  const effectiveProof = proofState.seq === entry.seq ? proofState.proof : null;

  const isBrokenAtEntry =
    chainState.status === "broken" && chainState.brokenAtSeq === entry.seq;
  const isAfterBrokenEntry =
    chainState.status === "broken" &&
    typeof chainState.brokenAtSeq === "number" &&
    entry.seq > chainState.brokenAtSeq;

  const route = entry.fourDRoute;
  const { prevSeq } = entry;

  return (
    <aside
      ref={inspectorRef}
      aria-label={`Entry #${entry.seq} details`}
      className="flex w-inspector shrink-0 flex-col overflow-hidden border-s border-border bg-surface text-ui text-fg"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-chrome px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate font-mono text-sm font-semibold tabular-nums text-fg">
            {`Entry #${entry.seq}`}
          </h2>
          <RecordOutcomeBadge outcome={entry.outcome} />
        </div>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Close entry inspector"
          onClick={onClose}
        >
          <span aria-hidden="true">Close</span>
        </Button>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 text-xs">
        {isBrokenAtEntry ? (
          <div className="rounded-sm border border-danger bg-danger-subtle p-2.5 text-fg">
            <div className="font-semibold text-danger">
              {`✕ Hash chain broken at #${entry.seq}`}
            </div>
            <p className="mt-0.5 text-fg-muted">
              Previous hash link does not match the preceding ledger entry.
            </p>
            {chainState.expectedPrevHash || chainState.actualPrevHash ? (
              <div className="mt-1.5 space-y-1 font-mono text-[11px] text-fg-dim">
                {chainState.expectedPrevHash ? (
                  <div>
                    Expected prev:{" "}
                    <code dir="ltr" className="unicode-bidi-isolate text-fg">
                      {chainState.expectedPrevHash}
                    </code>
                  </div>
                ) : null}
                {chainState.actualPrevHash ? (
                  <div>
                    Recorded prev:{" "}
                    <code dir="ltr" className="unicode-bidi-isolate text-danger">
                      {chainState.actualPrevHash}
                    </code>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : isAfterBrokenEntry ? (
          <div className="rounded-sm border border-warning bg-warning-subtle p-2.5 text-fg">
            <div className="font-semibold text-warning">
              {`! Untrusted chain segment (after #${chainState.brokenAtSeq})`}
            </div>
            <p className="mt-0.5 text-fg-muted">
              {`Entries after #${chainState.brokenAtSeq} can't be trusted until tampering is resolved.`}
            </p>
          </div>
        ) : null}

        <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-2.5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
            Event & P-10 Provenance
          </h3>
          <dl className="space-y-1">
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-fg-dim">When (ET)</dt>
              <dd className="font-mono tabular-nums text-fg">{entry.timestampEt}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-fg-dim">Who</dt>
              <dd className="text-end text-fg">
                <span>{entry.actorLabel}</span>{" "}
                <span className="rounded-xs border border-border-control bg-surface-elevated px-1 font-mono text-[10px] text-fg-muted">
                  {entry.actorKind}
                </span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-fg-dim">Action</dt>
              <dd className="text-end font-medium text-fg">{entry.action}</dd>
            </div>
            <div className="space-y-0.5 pt-0.5">
              <dt className="text-fg-dim">Target</dt>
              <dd>
                <code
                  dir="ltr"
                  className="unicode-bidi-isolate block break-all rounded-xs border border-border bg-code px-2 py-1 font-mono text-[11px] text-fg"
                >
                  {entry.target}
                </code>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2 pt-0.5">
              <dt className="text-fg-dim">Approval</dt>
              <dd className="text-end text-fg">
                <span className="font-medium">{entry.approvalLabel}</span>
                <span className="ms-1.5 font-mono text-[10px] text-fg-muted">
                  {entry.approvedByHuman ? "· Human P-10" : "· Policy"}
                </span>
              </dd>
            </div>
          </dl>
        </div>

        <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-2.5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
            Model & Prompt Provenance
          </h3>
          <div className="font-mono text-xs tabular-nums text-fg">
            {`${entry.modelId} ${entry.modelVersion} · prompt ${entry.promptVersion}`}
          </div>
          <div className="space-y-0.5">
            <div className="text-[11px] text-fg-dim">System prompt hash</div>
            <code
              dir="ltr"
              className="unicode-bidi-isolate block break-all rounded-xs border border-border bg-code px-2 py-1 font-mono text-[11px] text-fg"
            >
              {entry.systemPromptHash}
            </code>
          </div>
        </div>

        <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-2.5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
            4D Route
          </h3>
          {route ? (
            <dl className="space-y-1">
              <div className="flex items-baseline justify-between gap-2">
                <dt className="text-fg-dim">Privacy</dt>
                <dd className="font-mono text-fg">{route.privacy}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-2">
                <dt className="text-fg-dim">Provider</dt>
                <dd className="font-mono text-fg">{route.selectedProvider}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-2">
                <dt className="text-fg-dim">Selected model</dt>
                <dd>
                  <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">
                    {route.selectedModel}
                  </code>
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-2">
                <dt className="text-fg-dim">Data boundary</dt>
                <dd>
                  <code
                    dir="ltr"
                    className={`unicode-bidi-isolate rounded-xs border px-1.5 py-0.5 font-mono text-[11px] ${
                      route.dataBoundary === "local_loopback"
                        ? "border-accent bg-accent-subtle text-accent"
                        : route.dataBoundary === "external_vendor_api"
                          ? "border-warning bg-warning-subtle text-warning"
                          : "border-border-control bg-surface-elevated text-fg"
                    }`}
                  >
                    {route.dataBoundary}
                  </code>
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-2">
                <dt className="text-fg-dim">Latency / Cost cap</dt>
                <dd className="font-mono tabular-nums text-fg">
                  {`${route.latencyTier} · $${route.costCapUsd.toFixed(2)} · ${route.taskComplexity}`}
                </dd>
              </div>
              <div className="space-y-0.5 pt-1">
                <dt className="text-fg-dim">Reason</dt>
                <dd className="text-fg-muted">{route.reason}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-fg-muted">No 4D routing tuple attached to this entry.</p>
          )}
        </div>

        <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-2.5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
            SHA-256 Hash Chain
          </h3>
          <div className="space-y-0.5">
            <div className="font-mono text-[11px] text-fg-dim">hash</div>
            <code
              dir="ltr"
              className="unicode-bidi-isolate block break-all rounded-xs border border-border bg-code px-2 py-1 font-mono text-[11px] text-fg"
            >
              {entry.hash}
            </code>
          </div>
          <div className="space-y-1 pt-0.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] text-fg-dim">prev</span>
              {prevSeq !== null ? (
                <button
                  type="button"
                  onClick={() => onSelectPrevSeq(prevSeq)}
                  className="rounded-xs border border-border-control bg-surface-elevated px-1.5 py-0.5 font-mono text-[11px] font-semibold tabular-nums text-accent transition-colors duration-fast ease-state hover:border-accent"
                >
                  {`(#${prevSeq})`}
                </button>
              ) : (
                <span className="font-mono text-[11px] text-fg-dim">(genesis)</span>
              )}
            </div>
            <code
              dir="ltr"
              className="unicode-bidi-isolate block break-all rounded-xs border border-border bg-code px-2 py-1 font-mono text-[11px] text-fg-muted"
            >
              {entry.prevHash}
            </code>
            {missingPrevSeq !== null ? (
              <p className="font-mono text-[11px] text-fg-muted">
                {`Entry #${missingPrevSeq} is outside the loaded ledger window.`}
              </p>
            ) : null}
          </div>
        </div>

        <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-2.5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-fg-muted">
              Merkle Inclusion Proof
            </h3>
            {effectiveProofStatus === "ready" && effectiveProof ? (
              effectiveProof.verified ? (
                <SemanticBadge kind="passed" labelOverride="Verified" />
              ) : (
                <SemanticBadge kind="failed" labelOverride="Unverified" />
              )
            ) : null}
          </div>

          {effectiveProofStatus === "loading" ? (
            <p className="font-mono text-[11px] text-fg-muted">
              Verifying Merkle inclusion path…
            </p>
          ) : effectiveProofStatus === "error" || !effectiveProof ? (
            <p className="font-mono text-[11px] text-warning">
              Unable to load Merkle inclusion proof.
            </p>
          ) : (
            <div className="space-y-1.5">
              <div className="space-y-0.5">
                <div className="text-[11px] text-fg-dim">Merkle root</div>
                <code
                  dir="ltr"
                  className="unicode-bidi-isolate block break-all rounded-xs border border-border bg-code px-2 py-1 font-mono text-[11px] text-fg"
                >
                  {effectiveProof.merkleRoot}
                </code>
              </div>
              <div className="font-mono text-[11px] tabular-nums text-fg-muted">
                {`${effectiveProof.siblings.length} sibling ${
                  effectiveProof.siblings.length === 1 ? "hash" : "hashes"
                }`}
              </div>
              {effectiveProof.siblings.length > 0 ? (
                <ul className="space-y-1">
                  {effectiveProof.siblings.map((sibling, idx) => (
                    <li
                      key={`${sibling.position}-${sibling.hash}-${idx}`}
                      className="flex items-center justify-between gap-2 rounded-xs border border-border bg-code px-2 py-1 font-mono text-[11px]"
                    >
                      <span className="text-fg-dim">{`${idx + 1}. ${sibling.position}`}</span>
                      <code dir="ltr" className="unicode-bidi-isolate text-fg-muted">
                        {`${sibling.hash.slice(0, 16)}…`}
                      </code>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 space-y-1 border-t border-border bg-chrome px-3 py-2.5">
        <Button
          size="sm"
          variant="secondary"
          className="w-full"
          disabled={!entry.diffPath}
          onClick={() => {
            if (entry.diffPath) {
              onOpenDiffInReview?.(entry.diffPath, entry.seq);
            }
          }}
        >
          Open diff in Review
        </Button>
        <div className="truncate text-center font-mono text-[11px] text-fg-dim">
          {entry.diffPath ? (
            <code dir="ltr" className="unicode-bidi-isolate">
              {entry.diffPath}
            </code>
          ) : (
            "No file diff attached to this entry"
          )}
        </div>
      </div>
    </aside>
  );
}
