import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { fetchSystemDoctor, openWorkspace } from "@/lib/api";
import type { DoctorCheckItem } from "@/lib/types";

export interface OnboardingCompletionPayload {
  workspacePath: string;
  doctorChecks: DoctorCheckItem[];
}

export interface OnboardingModalProps {
  open: boolean;
  onOpenChange?: (open: boolean) => void;
  onComplete: (payload: OnboardingCompletionPayload) => void;
  onOpenSettingsLater?: () => void;
  initialStep?: 1 | 2;
  defaultWorkspacePath?: string;
  openWorkspaceFn?: typeof openWorkspace;
  fetchDoctorFn?: typeof fetchSystemDoctor;
}

export function OnboardingModal({
  open,
  onOpenChange,
  onComplete,
  onOpenSettingsLater,
  initialStep = 1,
  defaultWorkspacePath = "/workspace/keelway",
  openWorkspaceFn = openWorkspace,
  fetchDoctorFn = fetchSystemDoctor,
}: OnboardingModalProps): React.JSX.Element {
  const [step, setStep] = useState<1 | 2>(initialStep);
  const [workspacePath, setWorkspacePath] = useState(defaultWorkspacePath);
  const [openedWorkspaceInfo, setOpenedWorkspaceInfo] = useState<{
    path: string;
    branch: string;
    filesCount: number;
  } | null>(null);
  const [doctorChecks, setDoctorChecks] = useState<DoctorCheckItem[]>([]);
  const [doctorLoading, setDoctorLoading] = useState(false);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);

  const hasAutoLoadedDoctorRef = useRef(false);
  const baseId = useId();
  const descId = `${baseId}-onboarding-desc`;
  const wsInputId = `${baseId}-workspace-path`;

  useEffect(() => {
    if (!open) {
      hasAutoLoadedDoctorRef.current = false;
      return;
    }
    setStep(initialStep);
  }, [initialStep, open]);

  const runDoctor = useCallback(async () => {
    setDoctorLoading(true);
    try {
      const checks = await fetchDoctorFn();
      setDoctorChecks(checks);
    } finally {
      setDoctorLoading(false);
    }
  }, [fetchDoctorFn]);

  useEffect(() => {
    if (!open || step !== 2 || hasAutoLoadedDoctorRef.current) {
      return;
    }
    hasAutoLoadedDoctorRef.current = true;
    let cancelled = false;
    setDoctorLoading(true);
    fetchDoctorFn()
      .then((checks) => {
        if (!cancelled) {
          setDoctorChecks(checks);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDoctorLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fetchDoctorFn, open, step]);

  const handleOpenWorkspace = async () => {
    const trimmed = workspacePath.trim();
    if (!trimmed) {
      return;
    }
    setWorkspaceLoading(true);
    try {
      const res = await openWorkspaceFn(trimmed);
      if (res.ok) {
        setOpenedWorkspaceInfo({
          path: res.path,
          branch: res.branch,
          filesCount: res.filesCount,
        });
      }
    } finally {
      setWorkspaceLoading(false);
    }
  };

  const handleComplete = () => {
    onComplete({ workspacePath: workspacePath.trim() || defaultWorkspacePath, doctorChecks });
    onOpenChange?.(false);
  };

  const renderDoctorBadge = (status: DoctorCheckItem["status"]): React.JSX.Element => {
    if (status === "ok") {
      return <SemanticBadge kind="passed" />;
    }
    if (status === "warning") {
      return <SemanticBadge kind="reconfirm" labelOverride="Warning" />;
    }
    return <SemanticBadge kind="failed" />;
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/65" />
        <Dialog.Content
          aria-describedby={descId}
          className="fixed start-1/2 top-[10%] z-50 flex w-full max-w-2xl -translate-x-1/2 flex-col overflow-hidden rounded-md border border-border-strong bg-surface text-fg shadow-modal rtl:translate-x-1/2"
        >
          {/* Modal Header */}
          <div className="flex items-center justify-between gap-3 border-b border-border bg-chrome px-5 py-3.5">
            <div>
              <Dialog.Title className="text-sm font-semibold text-fg">
                {step === 1
                  ? "Welcome to Keelway — Honest Sovereign Defaults"
                  : "Workspace & Local System Readiness"}
              </Dialog.Title>
              <Dialog.Description id={descId} className="mt-0.5 text-xs text-fg-muted">
                {step === 1
                  ? "Step 1 of 2 · Review how models, human approvals, and network boundaries start on this machine."
                  : "Step 2 of 2 · Bind a local workspace directory and verify OS sandbox, OpenCore runtime, and audit ledger."}
              </Dialog.Description>
            </div>
            <span className="shrink-0 rounded-xs border border-border-strong bg-surface px-2 py-1 font-mono text-[11px] text-fg-muted">
              {`Step ${step} / 2`}
            </span>
          </div>

          {/* Step 1: 3 Transparent Sovereign Default Cards (Wireframe 12) */}
          {step === 1 ? (
            <div className="space-y-3 p-5">
              {/* Card 1: Local Model */}
              <div className="rounded-md border border-border-strong bg-canvas/70 p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
                    Model
                  </div>
                  <SemanticBadge kind="opencore" />
                </div>
                <div className="mt-1 text-sm font-semibold text-fg">
                  Local ·{" "}
                  <code dir="ltr" className="unicode-bidi-isolate font-mono">
                    coder-7b v2.5.1
                  </code>
                </div>
                <p className="mt-1 text-xs text-fg-muted">
                  Runs on this machine via OpenCore
                </p>
              </div>

              {/* Card 2: P-10 Human-Only Approvals */}
              <div className="rounded-md border border-border-strong bg-canvas/70 p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
                    Approvals
                  </div>
                  <SemanticBadge kind="locked" />
                </div>
                <div className="mt-1 text-sm font-semibold text-fg">Ask every time</div>
                <p className="mt-1 text-xs text-fg-muted">
                  Only a person, at this keyboard, can approve edits, commands, or network
                  calls
                </p>
              </div>

              {/* Card 3: Honest Network Setting */}
              <div className="rounded-md border border-border-strong bg-canvas/70 p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
                    Network
                  </div>
                  <SemanticBadge kind="unmeasured" />
                </div>
                <div className="mt-1 text-sm font-semibold text-fg">Offline (setting)</div>
                <p className="mt-1 text-xs text-fg-muted">
                  {"Set to keep your use on this machine. Network use isn't measured yet."}
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                <Button
                  size="md"
                  variant="ghost"
                  onClick={() => {
                    onOpenSettingsLater?.();
                    setStep(2);
                  }}
                >
                  Change in Settings later
                </Button>
                <Button
                  size="md"
                  variant="primary"
                  onClick={() => setStep(2)}
                >
                  Continue to workspace check
                </Button>
              </div>
            </div>
          ) : (
            /* Step 2: Workspace Selector & /v1/system/doctor Checks */
            <div className="space-y-4 p-5">
              <div className="space-y-1.5">
                <label
                  htmlFor={wsInputId}
                  className="block text-xs font-semibold text-fg"
                >
                  Workspace directory
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id={wsInputId}
                    type="text"
                    dir="ltr"
                    value={workspacePath}
                    onChange={(e) => setWorkspacePath(e.target.value)}
                    className="unicode-bidi-isolate min-h-ctrl-md flex-1 rounded-sm border border-border-control bg-canvas px-3 py-1.5 font-mono text-xs text-fg focus:outline-none"
                  />
                  <Button
                    size="md"
                    variant="secondary"
                    loading={workspaceLoading}
                    onClick={handleOpenWorkspace}
                  >
                    Open workspace
                  </Button>
                </div>
                {openedWorkspaceInfo ? (
                  <p className="text-xs text-fg-muted">
                    Opened{" "}
                    <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">
                      {openedWorkspaceInfo.path}
                    </code>{" "}
                    on branch{" "}
                    <code dir="ltr" className="unicode-bidi-isolate font-mono text-fg">
                      {openedWorkspaceInfo.branch}
                    </code>{" "}
                    ({openedWorkspaceInfo.filesCount} files)
                  </p>
                ) : null}
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
                    System Doctor (/v1/system/doctor)
                  </h3>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={doctorLoading}
                    onClick={runDoctor}
                  >
                    Re-run doctor
                  </Button>
                </div>

                <ul className="divide-y divide-border rounded-md border border-border-strong bg-canvas/70">
                  {doctorChecks.map((check) => (
                    <li key={check.id} className="space-y-1 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-fg">
                          {check.label}
                        </span>
                        {renderDoctorBadge(check.status)}
                      </div>
                      <p className="text-xs text-fg-muted">{check.detail}</p>
                      {(check.status === "warning" || check.status === "failed") &&
                      check.remediation ? (
                        <p className="rounded-xs border border-warning/40 bg-warning-subtle px-2.5 py-1.5 font-mono text-[11px] text-fg">
                          {check.remediation}
                        </p>
                      ) : null}
                    </li>
                  ))}
                  {doctorChecks.length === 0 && !doctorLoading ? (
                    <li className="p-3 text-xs text-fg-muted">
                      No diagnostic checks reported yet.
                    </li>
                  ) : null}
                </ul>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                <Button
                  size="md"
                  variant="ghost"
                  onClick={() => setStep(1)}
                >
                  Back to defaults
                </Button>
                <Button
                  size="md"
                  variant="primary"
                  onClick={handleComplete}
                >
                  Start using Keelway
                </Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
