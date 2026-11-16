import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  isTrustedUserEvent,
  type P10ApprovalDecisionPayload,
  type P10ApprovalProposal,
  type P10ApprovalReceipt,
  type P10DecisionAction,
  type P10DiffLine,
  type P10ScopedRuleSpec,
} from "@/lib/types";

export const P10_GOVERNANCE_FOOTER_COPY =
  "Only you can approve. Agent output never counts as confirmation, and the agent can't approve for you.";

export const NETWORK_ESCALATION_PATTERN =
  /\b(curl|wget|ssh|scp|rsync|nc|ncat|git\s+push|npm\s+publish|vercel\s+deploy)\b/i;

export interface P10ApprovalCardProps {
  proposal: P10ApprovalProposal;
  isDomainRegulated?: boolean;
  initialReceipt?: P10ApprovalReceipt | null;
  receipt?: P10ApprovalReceipt | null;
  headingRef?: React.Ref<HTMLHeadingElement>;
  enableKeyboardShortcuts?: boolean;
  onFocusCapture?: React.FocusEventHandler<HTMLElement>;
  onSubmitDecision?: (
    payload: P10ApprovalDecisionPayload,
  ) => Promise<P10ApprovalReceipt | void> | P10ApprovalReceipt | void;
  onRetryPreview?: (proposalId: string) => void;
  onCreateScopedRule?: (rule: P10ScopedRuleSpec) => void;
}

function isPromiseLike<T>(value: unknown): value is PromiseLike<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    "then" in value &&
    typeof (value as { then?: unknown }).then === "function"
  );
}

function defaultScopeForProposal(proposal: P10ApprovalProposal): string {
  if (proposal.kind === "command") return proposal.command?.trim() || "npm test";
  if (proposal.kind === "file_edit") return proposal.targetPath?.trim() || "src/**";
  return "";
}

export function DiffLinesView({ lines }: { lines: P10DiffLine[] }): React.JSX.Element {
  return (
    <div className="max-h-48 overflow-auto rounded-sm border border-border bg-code p-2 font-mono text-code">
      {lines.map((line, index) => {
        const prefix =
          line.type === "add" ? "+" : line.type === "del" ? "-" : line.type === "hunk" ? "" : " ";
        const rowTone =
          line.type === "add"
            ? "bg-ok-subtle text-fg"
            : line.type === "del"
              ? "bg-danger-subtle text-fg"
              : line.type === "hunk"
                ? "text-fg-dim"
                : "text-fg-muted";
        return (
          <div key={`${index}-${line.type}`} className={`flex gap-2 px-1.5 py-0.5 ${rowTone}`}>
            <span className="w-8 shrink-0 select-none text-end tabular-nums text-fg-dim">
              {line.newLine ?? line.oldLine ?? ""}
            </span>
            <code dir="ltr" className="unicode-bidi-isolate whitespace-pre-wrap break-all">
              {`${prefix}${line.content}`}
            </code>
          </div>
        );
      })}
    </div>
  );
}

function ProposalPreviewBox({
  proposal,
  effectiveCommand,
  effectiveTargetPath,
  onRetryPreview,
}: {
  proposal: P10ApprovalProposal;
  effectiveCommand: string;
  effectiveTargetPath: string;
  onRetryPreview?: (proposalId: string) => void;
}): React.JSX.Element {
  if (proposal.previewStatus === "loading") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-sm border border-border bg-code p-3 font-mono text-xs text-fg-muted"
      >
        Loading preview from local workspace sandbox…
      </div>
    );
  }

  if (proposal.previewStatus === "failed") {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-danger/45 bg-danger-subtle p-3 text-xs text-fg">
        <span>{proposal.previewError ?? "Preview failed to load from workspace sandbox."}</span>
        <Button size="sm" variant="secondary" onClick={() => onRetryPreview?.(proposal.id)}>
          Retry preview
        </Button>
      </div>
    );
  }

  if (proposal.diffLines && proposal.diffLines.length > 0) {
    return <DiffLinesView lines={proposal.diffLines} />;
  }

  if (proposal.kind === "network_deploy") {
    return (
      <div className="space-y-1 rounded-sm border border-border bg-code p-2.5 font-mono text-xs text-fg">
        <div>
          <span className="text-fg-muted">Destination: </span>
          <code dir="ltr" className="unicode-bidi-isolate">
            {proposal.destinationHost ?? "external-endpoint"}
          </code>
        </div>
        {typeof proposal.payloadBytesEstimate === "number" ? (
          <div className="tabular-nums text-fg-muted">
            {`Estimated outbound payload: ${proposal.payloadBytesEstimate} B`}
          </div>
        ) : null}
        {effectiveCommand ? (
          <div>
            <span className="text-fg-muted">Command: </span>
            <code dir="ltr" className="unicode-bidi-isolate">{effectiveCommand}</code>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-1 rounded-sm border border-border bg-code p-2.5 font-mono text-xs text-fg">
      {effectiveCommand ? (
        <div>
          <span className="select-none text-fg-dim">$ </span>
          <code dir="ltr" className="unicode-bidi-isolate">{effectiveCommand}</code>
        </div>
      ) : null}
      {effectiveTargetPath ? (
        <div>
          <span className="text-fg-muted">Target: </span>
          <code dir="ltr" className="unicode-bidi-isolate">{effectiveTargetPath}</code>
        </div>
      ) : null}
      {proposal.workingDir ? (
        <div className="text-fg-muted">
          <span>cwd: </span>
          <code dir="ltr" className="unicode-bidi-isolate">{proposal.workingDir}</code>
        </div>
      ) : null}
    </div>
  );
}

function ScopedRulePopover({
  proposal,
  open,
  onOpenChange,
  scopePattern,
  onScopePatternChange,
  expiresAfterSession,
  onExpiresChange,
  previewLocked,
  lockReasonId,
  onSave,
}: {
  proposal: P10ApprovalProposal;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scopePattern: string;
  onScopePatternChange: (val: string) => void;
  expiresAfterSession: boolean;
  onExpiresChange: (val: boolean) => void;
  previewLocked: boolean;
  lockReasonId: string;
  onSave: (event: React.MouseEvent<HTMLButtonElement>) => void;
}): React.JSX.Element {
  const titleId = useId();
  const inputId = useId();
  const sessionCheckboxId = useId();

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>
        <Button size="md" variant="secondary" previewLocked={previewLocked} lockReasonId={lockReasonId}>
          Allow always (scoped)
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={6}
          aria-labelledby={titleId}
          className="z-50 w-80 rounded-md border border-border-strong bg-surface p-3 text-ui text-fg shadow-popover"
        >
          <div className="space-y-2.5">
            <h2 id={titleId} className="text-xs font-semibold text-fg">
              Allow always in scope
            </h2>
            <p className="text-[11px] text-fg-muted">
              Bound to{" "}
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">{proposal.modelId}</code>{" "}
              and prompt{" "}
              <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">{proposal.promptVersion}</code>.
              Model or prompt drift forces re-confirmation.
            </p>
            <div className="space-y-1">
              <label htmlFor={inputId} className="block text-xs font-medium text-fg">
                Scope pattern
              </label>
              <input
                id={inputId}
                type="text"
                dir="ltr"
                value={scopePattern}
                onChange={(e) => onScopePatternChange(e.target.value)}
                className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-code px-2 py-1 font-mono text-xs text-fg"
              />
            </div>
            <label htmlFor={sessionCheckboxId} className="flex items-center gap-2 text-xs text-fg-muted">
              <input
                id={sessionCheckboxId}
                type="checkbox"
                checked={expiresAfterSession}
                onChange={(e) => onExpiresChange(e.target.checked)}
                className="rounded-xs border-border-control"
              />
              <span>Expire when session closes</span>
            </label>
            <div className="flex items-center justify-end gap-2 pt-1">
              <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button size="sm" variant="primary" onClick={onSave}>
                Save scoped rule
              </Button>
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function P10ApprovalCard({
  proposal,
  isDomainRegulated = false,
  initialReceipt = null,
  receipt: controlledReceipt,
  headingRef,
  enableKeyboardShortcuts = true,
  onFocusCapture,
  onSubmitDecision,
  onRetryPreview,
  onCreateScopedRule,
}: P10ApprovalCardProps): React.JSX.Element {
  const headingId = useId();
  const lockReasonId = useId();
  const editFieldId = useId();
  const denyReasonId = useId();
  const confirmRegionHeadingId = useId();

  const articleRef = useRef<HTMLElement | null>(null);
  const allowOnceBtnRef = useRef<HTMLButtonElement | null>(null);
  const cancelConfirmBtnRef = useRef<HTMLButtonElement | null>(null);
  const latestProposalIdRef = useRef(proposal.id);
  latestProposalIdRef.current = proposal.id;

  const [trackedProposalId, setTrackedProposalId] = useState(proposal.id);
  const [editedCommand, setEditedCommand] = useState(proposal.command ?? "");
  const [editedTargetPath, setEditedTargetPath] = useState(proposal.targetPath ?? "");
  const [isEditing, setIsEditing] = useState(false);
  const [denyReason, setDenyReason] = useState("");
  const [scopeOpen, setScopeOpen] = useState(false);
  const [scopePattern, setScopePattern] = useState(() => defaultScopeForProposal(proposal));
  const [expiresAfterSession, setExpiresAfterSession] = useState(false);
  const [confirmExternalOpen, setConfirmExternalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [internalReceipt, setInternalReceipt] = useState<P10ApprovalReceipt | null>(initialReceipt);

  if (trackedProposalId !== proposal.id) {
    setTrackedProposalId(proposal.id);
    setEditedCommand(proposal.command ?? "");
    setEditedTargetPath(proposal.targetPath ?? "");
    setIsEditing(false);
    setDenyReason("");
    setScopeOpen(false);
    setScopePattern(defaultScopeForProposal(proposal));
    setExpiresAfterSession(false);
    setConfirmExternalOpen(false);
    setSubmitting(false);
    setSubmitError(null);
    setInternalReceipt(initialReceipt);
  }

  const setMergedHeadingRef = useCallback(
    (node: HTMLHeadingElement | null) => {
      if (typeof headingRef === "function") {
        headingRef(node);
      } else if (headingRef && typeof headingRef === "object") {
        (headingRef as React.MutableRefObject<HTMLHeadingElement | null>).current = node;
      }
    },
    [headingRef],
  );

  const activeReceipt = controlledReceipt !== undefined ? controlledReceipt : internalReceipt;
  const isCommandProposal = proposal.kind !== "file_edit";
  const hasCommandModified =
    isCommandProposal && editedCommand.trim() !== (proposal.command ?? "").trim();
  const hasTargetModified =
    !isCommandProposal && editedTargetPath.trim() !== (proposal.targetPath ?? "").trim();
  const isModified = hasCommandModified || hasTargetModified;

  const matchesNetworkCommand = NETWORK_ESCALATION_PATTERN.test(editedCommand);
  const escalatedByEdit =
    proposal.kind !== "network_deploy" && hasCommandModified && matchesNetworkCommand;
  const effectiveVariantC = proposal.kind === "network_deploy" || matchesNetworkCommand;
  const isRegulated = Boolean(isDomainRegulated || proposal.domainPolicyCode);
  const isClickOnlyGate = effectiveVariantC || isRegulated;
  const isPreviewLocked = proposal.previewStatus !== "ready";

  useEffect(() => {
    if (confirmExternalOpen) {
      cancelConfirmBtnRef.current?.focus();
    }
  }, [confirmExternalOpen]);

  const actionLabel = escalatedByEdit
    ? "Network + command (escalated by edit)"
    : proposal.kind === "network_deploy"
      ? "External network / deploy"
      : proposal.kind === "command"
        ? "Run workspace command"
        : "Edit workspace file";

  const dispatchDecision = useCallback(
    (
      decision: P10DecisionAction,
      extra?: { scopedRule?: P10ScopedRuleSpec; confirmedExternalSend?: boolean },
    ) => {
      if (submitting || activeReceipt) return;
      if (decision !== "deny" && isPreviewLocked) return;

      const decidedAt = new Date().toISOString();
      const trimmedDeny = denyReason.trim();
      const payload: P10ApprovalDecisionPayload = {
        proposalId: proposal.id,
        taskId: proposal.taskId,
        decision,
        ...(hasCommandModified ? { modifiedCommand: editedCommand.trim() } : {}),
        ...(hasTargetModified ? { modifiedTargetPath: editedTargetPath.trim() } : {}),
        ...(escalatedByEdit ? { escalatedToNetwork: true } : {}),
        ...(extra?.scopedRule ? { scopedRule: extra.scopedRule } : {}),
        ...(decision === "deny" && trimmedDeny ? { denyReason: trimmedDeny } : {}),
        ...(extra?.confirmedExternalSend ? { confirmedExternalSend: true } : {}),
        decidedBy: "human_keyboard_or_pointer",
        decidedAt,
      };

      const fallback: P10ApprovalReceipt = {
        proposalId: proposal.id,
        recordSeq: proposal.recordSeqCandidate ?? 1284,
        decision,
        summary: decision === "deny" && trimmedDeny ? `${proposal.title} — ${trimmedDeny}` : proposal.title,
        modifiedByUser: isModified,
        ...(escalatedByEdit ? { escalatedByEdit: true } : {}),
        decidedAt,
        actorLabel: "you (local keyboard)",
      };

      setSubmitError(null);
      try {
        const result = onSubmitDecision?.(payload);
        if (isPromiseLike<P10ApprovalReceipt | void>(result)) {
          setSubmitting(true);
          Promise.resolve(result)
            .then((resolved) => {
              if (latestProposalIdRef.current !== proposal.id) return;
              setInternalReceipt(resolved ?? fallback);
              setSubmitting(false);
            })
            .catch((err: unknown) => {
              if (latestProposalIdRef.current !== proposal.id) return;
              setSubmitting(false);
              setSubmitError(err instanceof Error ? err.message : "Failed to record P-10 decision.");
            });
        } else {
          setInternalReceipt(result ?? fallback);
        }
      } catch (err: unknown) {
        setSubmitError(err instanceof Error ? err.message : "Failed to record P-10 decision.");
      }
    },
    [
      activeReceipt, denyReason, editedCommand, editedTargetPath, escalatedByEdit,
      hasCommandModified, hasTargetModified, isModified, isPreviewLocked, onSubmitDecision,
      proposal.id, proposal.recordSeqCandidate, proposal.taskId, proposal.title, submitting,
    ],
  );

  useEffect(() => {
    if (!enableKeyboardShortcuts || activeReceipt || isClickOnlyGate) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return;
      if (!isTrustedUserEvent(event)) return;
      if (!(event.metaKey || event.ctrlKey) || !event.shiftKey || event.altKey) return;
      const focusedCard = document.activeElement?.closest("[data-p10-card]");
      if (focusedCard && focusedCard !== articleRef.current) return;

      const lower = event.key.toLowerCase();
      if (lower === "y") {
        event.preventDefault();
        if (!isPreviewLocked) dispatchDecision("allow_once");
      } else if (lower === "n") {
        event.preventDefault();
        dispatchDecision("deny");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeReceipt, dispatchDecision, enableKeyboardShortcuts, isClickOnlyGate, isPreviewLocked]);

  if (activeReceipt) {
    const isDenied = activeReceipt.decision === "deny";
    const allowedLabel =
      activeReceipt.decision === "allow_always_scoped" ? "Allowed (scoped)" : "Allowed";

    return (
      <div
        role="status"
        data-testid={`p10-receipt-${proposal.id}`}
        className="flex min-h-row flex-wrap items-center justify-between gap-2 rounded-sm border border-border-strong bg-surface px-3 py-1 text-xs text-fg"
      >
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <SemanticBadge kind={isDenied ? "failed" : "passed"} labelOverride={isDenied ? "Denied" : allowedLabel} />
          <span className="truncate font-medium text-fg">{activeReceipt.summary}</span>
          {activeReceipt.modifiedByUser ? (
            <SemanticBadge kind="reconfirm" labelOverride="modified by you" />
          ) : null}
          {activeReceipt.escalatedByEdit ? (
            <span className="font-mono text-[11px] text-warning">escalated by edit</span>
          ) : null}
        </div>
        <span className="shrink-0 font-mono tabular-nums text-fg-muted">
          {`Record #${activeReceipt.recordSeq}`}
        </span>
      </div>
    );
  }

  const guardTrusted = (event: React.SyntheticEvent): boolean => {
    if (!isTrustedUserEvent(event)) {
      event.preventDefault();
      event.stopPropagation();
      return false;
    }
    return true;
  };

  const handleAllowOnceClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (!guardTrusted(event) || isPreviewLocked || submitting) return;
    if (isClickOnlyGate) {
      if (event.detail === 0) {
        if (document.activeElement === allowOnceBtnRef.current) setConfirmExternalOpen(true);
        return;
      }
      dispatchDecision("allow_once");
      return;
    }
    dispatchDecision("allow_once");
  };

  const showShortcuts = enableKeyboardShortcuts && !isClickOnlyGate;

  return (
    <article
      ref={articleRef}
      onFocusCapture={onFocusCapture}
      aria-labelledby={headingId}
      data-p10-card={proposal.id}
      data-p10-variant={effectiveVariantC ? "C" : proposal.kind === "command" ? "B" : "A"}
      className="space-y-3 rounded-md border border-border-strong border-s-2 border-s-ochre bg-surface p-3.5 text-ui text-fg"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <SemanticBadge kind="needs-approval" />
            {isModified ? <SemanticBadge kind="reconfirm" labelOverride="modified by you" /> : null}
            {proposal.domainPolicyCode ? (
              <SemanticBadge kind="locked" detail={proposal.domainPolicyCode} />
            ) : isRegulated ? (
              <SemanticBadge kind="locked" detail="Human-only" />
            ) : null}
            {proposal.confidence ? (
              <SemanticBadge kind="estimated" labelOverride={`Confidence: ${proposal.confidence} (provisional)`} />
            ) : null}
          </div>
          <h3
            id={headingId}
            ref={setMergedHeadingRef}
            tabIndex={-1}
            data-programmatic-focus="true"
            className="text-sm font-semibold text-fg"
          >
            {proposal.title}
          </h3>
          <p className="text-xs text-fg-muted">{proposal.summary}</p>
        </div>
        <span className="font-mono text-[11px] text-fg-dim">
          <code dir="ltr" className="unicode-bidi-isolate">
            {`${proposal.modelId}@${proposal.modelVersion} · ${proposal.promptVersion}`}
          </code>
        </span>
      </div>

      <dl className="grid grid-cols-1 gap-1.5 rounded-sm border border-border bg-canvas/50 px-3 py-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="font-medium text-fg-dim">Action</dt>
          <dd className={escalatedByEdit ? "font-semibold text-warning" : "text-fg"}>{actionLabel}</dd>
        </div>
        <div>
          <dt className="font-medium text-fg-dim">Why</dt>
          <dd className="text-fg">{proposal.whyReason}</dd>
        </div>
      </dl>

      <ProposalPreviewBox
        proposal={proposal}
        effectiveCommand={editedCommand}
        effectiveTargetPath={editedTargetPath}
        onRetryPreview={onRetryPreview}
      />

      {isEditing ? (
        <div className="space-y-1 rounded-sm border border-border-strong bg-surface-elevated p-2.5">
          <label htmlFor={editFieldId} className="block text-xs font-medium text-fg">
            {isCommandProposal ? "Proposed command" : "Target file path"}
          </label>
          <input
            id={editFieldId}
            type="text"
            dir="ltr"
            value={isCommandProposal ? editedCommand : editedTargetPath}
            onChange={(e) => {
              const next = e.target.value;
              if (isCommandProposal) {
                setEditedCommand(next);
              } else {
                setEditedTargetPath(next);
              }
              setScopePattern(next);
            }}
            className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-code px-2.5 py-1 font-mono text-xs text-fg"
          />
        </div>
      ) : null}

      {isPreviewLocked ? (
        <p id={lockReasonId} className="text-xs text-fg-muted">
          Allow once unlocks when the preview has loaded.
        </p>
      ) : null}

      <div className="space-y-1">
        <label htmlFor={denyReasonId} className="block text-[11px] font-medium text-fg-muted">
          Deny reason (optional)
        </label>
        <input
          id={denyReasonId}
          type="text"
          value={denyReason}
          onChange={(e) => setDenyReason(e.target.value)}
          placeholder="Optional note recorded in ledger and returned to agent…"
          className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim"
        />
      </div>

      {confirmExternalOpen ? (
        <div
          role="region"
          aria-labelledby={confirmRegionHeadingId}
          className="space-y-2 rounded-sm border border-warning/45 bg-warning-subtle p-3 text-xs text-fg"
        >
          <div id={confirmRegionHeadingId} className="font-semibold text-fg">Confirm external send</div>
          <p className="text-fg-muted">
            Keyboard activation requires a second explicit confirmation before sending data outside this workspace. No timer is applied.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              ref={cancelConfirmBtnRef}
              size="sm"
              variant="secondary"
              autoFocus
              onClick={() => {
                setConfirmExternalOpen(false);
                allowOnceBtnRef.current?.focus();
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="warning-cta"
              clickOnly={true}
              onClick={(e) => {
                if (!guardTrusted(e) || isPreviewLocked || submitting) return;
                setConfirmExternalOpen(false);
                dispatchDecision("allow_once", { confirmedExternalSend: true });
              }}
            >
              Confirm send once
            </Button>
          </div>
        </div>
      ) : null}

      {submitError ? <p role="alert" className="text-xs text-danger">{submitError}</p> : null}

      <div className="flex flex-wrap items-center justify-between gap-2 pt-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            ref={allowOnceBtnRef}
            size="md"
            variant="warning-cta"
            clickOnly={isClickOnlyGate}
            shortcutHint={showShortcuts ? "⌘⇧Y" : undefined}
            previewLocked={isPreviewLocked}
            lockReasonId={lockReasonId}
            loading={submitting}
            onClick={handleAllowOnceClick}
          >
            Allow once
          </Button>

          {!isClickOnlyGate ? (
            <ScopedRulePopover
              proposal={proposal}
              open={scopeOpen}
              onOpenChange={setScopeOpen}
              scopePattern={scopePattern}
              onScopePatternChange={setScopePattern}
              expiresAfterSession={expiresAfterSession}
              onExpiresChange={setExpiresAfterSession}
              previewLocked={isPreviewLocked}
              lockReasonId={lockReasonId}
              onSave={(e) => {
                if (!guardTrusted(e) || isPreviewLocked || isClickOnlyGate) return;
                const rule: P10ScopedRuleSpec = {
                  scopePattern: scopePattern.trim() || defaultScopeForProposal(proposal),
                  actionKind: proposal.kind,
                  modelId: proposal.modelId,
                  promptVersion: proposal.promptVersion,
                  expiresAfterSession,
                };
                onCreateScopedRule?.(rule);
                setScopeOpen(false);
                dispatchDecision("allow_always_scoped", { scopedRule: rule });
              }}
            />
          ) : null}

          <Button size="md" variant="secondary" aria-expanded={isEditing} onClick={() => setIsEditing((p) => !p)}>
            {isEditing ? "Done editing" : "Edit request"}
          </Button>
        </div>

        <Button
          size="md"
          variant="danger-ghost"
          clickOnly={isClickOnlyGate}
          shortcutHint={showShortcuts ? "⌘⇧N" : undefined}
          onClick={(e) => {
            if (guardTrusted(e)) dispatchDecision("deny");
          }}
        >
          Deny
        </Button>
      </div>

      <p className="border-t border-border pt-2 text-[11px] text-fg-muted">
        {P10_GOVERNANCE_FOOTER_COPY}
      </p>
    </article>
  );
}
