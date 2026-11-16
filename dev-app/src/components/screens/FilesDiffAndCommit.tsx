import React, { useEffect, useId, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { createGitCommit, fetchGitProposal } from "@/lib/api";
import type {
  FileDiffHunk,
  GitCommitProposal,
  GitCommitResult,
  P10DiffLine,
} from "@/lib/types";

export type DiffDisplayMode = "unified" | "split";

interface SplitDiffRow {
  kind: "hunk" | "pair";
  hunkText?: string;
  before?: P10DiffLine;
  after?: P10DiffLine;
}

function buildSplitRows(lines: P10DiffLine[]): SplitDiffRow[] {
  const rows: SplitDiffRow[] = [];
  let idx = 0;

  while (idx < lines.length) {
    const current = lines[idx];
    if (current.type === "hunk") {
      rows.push({ kind: "hunk", hunkText: current.content });
      idx += 1;
      continue;
    }
    if (current.type === "context") {
      rows.push({ kind: "pair", before: current, after: current });
      idx += 1;
      continue;
    }

    const dels: P10DiffLine[] = [];
    while (idx < lines.length && lines[idx].type === "del") {
      dels.push(lines[idx]);
      idx += 1;
    }
    const adds: P10DiffLine[] = [];
    while (idx < lines.length && lines[idx].type === "add") {
      adds.push(lines[idx]);
      idx += 1;
    }

    const maxLen = Math.max(dels.length, adds.length);
    for (let k = 0; k < maxLen; k += 1) {
      rows.push({ kind: "pair", before: dels[k], after: adds[k] });
    }
  }

  return rows;
}

export interface FilesDiffViewProps {
  mode: DiffDisplayMode;
  hunks: FileDiffHunk[];
  activePath: string;
}

export function FilesDiffView({
  mode,
  hunks,
  activePath,
}: FilesDiffViewProps): React.JSX.Element {
  const displayedHunks = useMemo(() => {
    const matching = hunks.filter((h) => h.path === activePath);
    return matching.length > 0 ? matching : hunks;
  }, [activePath, hunks]);

  if (displayedHunks.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center bg-code p-6 text-xs text-fg-muted">
        No uncommitted diff hunks in working tree.
      </div>
    );
  }

  return (
    <div
      data-testid={`files-diff-${mode}`}
      className="min-h-0 flex-1 space-y-4 overflow-auto bg-code p-3 font-mono text-code"
    >
      {displayedHunks.map((hunk) => {
        const splitRows = mode === "split" ? buildSplitRows(hunk.lines) : [];
        return (
          <section
            key={`${hunk.path}-${hunk.oldStart}-${hunk.newStart}`}
            aria-label={`Diff for ${hunk.path}`}
            className="overflow-hidden rounded-sm border border-border-strong bg-canvas"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-elevated px-3 py-1.5 font-sans text-xs">
              <div className="flex min-w-0 items-center gap-2">
                <code dir="ltr" className="unicode-bidi-isolate truncate font-mono text-fg">
                  {hunk.path}
                </code>
                {typeof hunk.aiRecordSeq === "number" ? (
                  <SemanticBadge kind="ai" detail={`#${hunk.aiRecordSeq}`} />
                ) : null}
              </div>
              <div className="flex items-center gap-2 font-mono tabular-nums">
                <span className="text-ok">{`+${hunk.additions}`}</span>
                <span className="text-danger">{`-${hunk.deletions}`}</span>
              </div>
            </div>

            {mode === "unified" ? (
              <div className="divide-y divide-border/40 bg-code">
                {hunk.lines.map((line, lineIdx) => {
                  const isAdd = line.type === "add";
                  const isDel = line.type === "del";
                  const isHunk = line.type === "hunk";
                  const sign = isAdd ? "+" : isDel ? "-" : isHunk ? "" : " ";
                  const lineStyle: React.CSSProperties | undefined = isAdd
                    ? { backgroundColor: "var(--diff-add-bg)" }
                    : isDel
                      ? { backgroundColor: "var(--diff-del-bg)" }
                      : undefined;

                  return (
                    <div
                      key={`${lineIdx}-${line.type}`}
                      data-diff-line={line.type}
                      style={lineStyle}
                      className={`flex items-start gap-2 px-2 py-0.5 ${
                        isHunk ? "bg-surface/60 text-fg-dim" : "text-fg"
                      }`}
                    >
                      <span className="w-8 shrink-0 select-none text-end tabular-nums text-fg-dim">
                        {line.oldLine ?? ""}
                      </span>
                      <span className="w-8 shrink-0 select-none text-end tabular-nums text-fg-dim">
                        {line.newLine ?? ""}
                      </span>
                      <span className="w-16 shrink-0 select-none truncate text-[10px] text-teal-accent">
                        {isAdd && typeof hunk.aiRecordSeq === "number"
                          ? `AI #${hunk.aiRecordSeq}`
                          : ""}
                      </span>
                      <span
                        data-diff-sign={sign.trim() || undefined}
                        className={`w-4 shrink-0 select-none text-center font-bold ${
                          isAdd ? "text-ok" : isDel ? "text-danger" : "text-fg-dim"
                        }`}
                      >
                        {sign}
                      </span>
                      <code
                        dir="ltr"
                        className="unicode-bidi-isolate min-w-0 flex-1 whitespace-pre-wrap break-all"
                      >
                        {line.content}
                      </code>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="bg-code">
                <div className="grid grid-cols-2 border-b border-border bg-surface text-[11px] font-medium text-fg-muted">
                  <div className="border-e border-border px-2.5 py-1">Before (HEAD)</div>
                  <div className="px-2.5 py-1">After (Working tree)</div>
                </div>
                <div className="divide-y divide-border/40">
                  {splitRows.map((row, rowIdx) => {
                    if (row.kind === "hunk") {
                      return (
                        <div
                          key={`hunk-${rowIdx}`}
                          data-diff-line="hunk"
                          className="bg-surface/60 px-2.5 py-0.5 text-fg-dim"
                        >
                          <code dir="ltr" className="unicode-bidi-isolate">
                            {row.hunkText}
                          </code>
                        </div>
                      );
                    }

                    const beforeIsDel = row.before?.type === "del";
                    const afterIsAdd = row.after?.type === "add";

                    return (
                      <div key={`pair-${rowIdx}`} className="grid grid-cols-2">
                        <div
                          data-split-side="before"
                          data-diff-line={beforeIsDel ? "del" : row.before ? "context" : "empty"}
                          style={
                            beforeIsDel ? { backgroundColor: "var(--diff-del-bg)" } : undefined
                          }
                          className="flex min-w-0 items-start gap-1.5 border-e border-border px-2 py-0.5"
                        >
                          <span className="w-7 shrink-0 select-none text-end tabular-nums text-fg-dim">
                            {row.before?.oldLine ?? ""}
                          </span>
                          <span
                            className={`w-3.5 shrink-0 select-none text-center font-bold ${
                              beforeIsDel ? "text-danger" : "text-fg-dim"
                            }`}
                          >
                            {beforeIsDel ? "-" : row.before ? " " : ""}
                          </span>
                          <code
                            dir="ltr"
                            className="unicode-bidi-isolate min-w-0 flex-1 whitespace-pre-wrap break-all"
                          >
                            {row.before?.content ?? ""}
                          </code>
                        </div>

                        <div
                          data-split-side="after"
                          data-diff-line={afterIsAdd ? "add" : row.after ? "context" : "empty"}
                          style={
                            afterIsAdd ? { backgroundColor: "var(--diff-add-bg)" } : undefined
                          }
                          className="flex min-w-0 items-start gap-1.5 px-2 py-0.5"
                        >
                          <span className="w-7 shrink-0 select-none text-end tabular-nums text-fg-dim">
                            {row.after?.newLine ?? ""}
                          </span>
                          <span className="w-14 shrink-0 select-none truncate text-[10px] text-teal-accent">
                            {afterIsAdd && typeof hunk.aiRecordSeq === "number"
                              ? `AI #${hunk.aiRecordSeq}`
                              : ""}
                          </span>
                          <span
                            className={`w-3.5 shrink-0 select-none text-center font-bold ${
                              afterIsAdd ? "text-ok" : "text-fg-dim"
                            }`}
                          >
                            {afterIsAdd ? "+" : row.after ? " " : ""}
                          </span>
                          <code
                            dir="ltr"
                            className="unicode-bidi-isolate min-w-0 flex-1 whitespace-pre-wrap break-all"
                          >
                            {row.after?.content ?? ""}
                          </code>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

export interface FilesCommitModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fetchProposalFn?: typeof fetchGitProposal;
  commitFn?: typeof createGitCommit;
  onCommitted?: (result: GitCommitResult) => void;
}

export function FilesCommitModal({
  open,
  onOpenChange,
  fetchProposalFn = fetchGitProposal,
  commitFn = createGitCommit,
  onCommitted,
}: FilesCommitModalProps): React.JSX.Element {
  const [proposal, setProposal] = useState<GitCommitProposal | null>(null);
  const [loadingProposal, setLoadingProposal] = useState(false);
  const [commitMessage, setCommitMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const baseId = useId();
  const descId = `${baseId}-commit-desc`;
  const msgInputId = `${baseId}-commit-msg`;

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    setLoadingProposal(true);
    setErrorText(null);

    fetchProposalFn()
      .then((res) => {
        if (!cancelled) {
          setProposal(res);
          setCommitMessage(res.proposedMessage || res.proposedTitle || "");
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorText(err instanceof Error ? err.message : "Failed to load Git commit proposal.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingProposal(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fetchProposalFn, open]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting || loadingProposal) return;
    const trimmed = commitMessage.trim();
    if (!trimmed) {
      setErrorText("Commit message is required.");
      return;
    }
    setSubmitting(true);
    setErrorText(null);
    try {
      const filesList = proposal?.files.map((f) => f.path);
      const res = await commitFn(trimmed, filesList && filesList.length > 0 ? filesList : undefined);
      if (!res.ok) {
        setErrorText("Git commit did not complete.");
        return;
      }
      onCommitted?.(res);
      onOpenChange(false);
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Git commit failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/65" />
        <Dialog.Content
          aria-describedby={descId}
          className="fixed start-1/2 top-[12%] z-50 flex w-full max-w-lg -translate-x-1/2 flex-col overflow-hidden rounded-md border border-border-strong bg-surface text-fg shadow-modal rtl:translate-x-1/2"
        >
          <div className="border-b border-border bg-chrome px-4 py-3">
            <Dialog.Title className="text-sm font-semibold text-fg">
              Commit workspace changes
            </Dialog.Title>
            <Dialog.Description id={descId} className="mt-0.5 text-xs text-fg-muted">
              Review proposed commit message and staged files on local branch before recording commit.
            </Dialog.Description>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3 p-4">
            {proposal ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-border bg-canvas/70 px-2.5 py-1.5 font-mono text-xs text-fg-muted">
                <span>
                  Branch:{" "}
                  <code dir="ltr" className="unicode-bidi-isolate text-fg">
                    {proposal.branch}
                  </code>
                </span>
                <span>{`Patch #${proposal.patchHash}`}</span>
              </div>
            ) : null}

            {proposal && proposal.files.length > 0 ? (
              <ul
                aria-label="Staged files"
                className="max-h-28 divide-y divide-border overflow-y-auto rounded-sm border border-border bg-canvas/60 text-xs"
              >
                {proposal.files.map((file) => (
                  <li key={file.path} className="flex items-center justify-between gap-2 px-2.5 py-1">
                    <code dir="ltr" className="unicode-bidi-isolate truncate font-mono text-fg">
                      {file.path}
                    </code>
                    <span className="rounded-xs border border-border-control/60 bg-surface-elevated px-1.5 py-0 font-mono text-[10px] font-semibold text-fg-muted">
                      {file.status}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="space-y-1">
              <label htmlFor={msgInputId} className="block text-xs font-semibold text-fg">
                Commit message
              </label>
              <textarea
                id={msgInputId}
                dir="ltr"
                rows={4}
                value={commitMessage}
                disabled={loadingProposal}
                onChange={(e) => setCommitMessage(e.target.value)}
                className="unicode-bidi-isolate w-full rounded-sm border border-border-control bg-canvas px-3 py-2 font-mono text-xs text-fg"
              />
            </div>

            {errorText ? (
              <p role="alert" className="text-xs text-danger">
                {errorText}
              </p>
            ) : null}

            <div className="flex items-center justify-end gap-2 pt-1">
              <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                variant="primary"
                loading={submitting || loadingProposal}
              >
                Commit changes
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
