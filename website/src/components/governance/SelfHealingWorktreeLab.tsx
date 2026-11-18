"use client";

import React, { useState } from "react";
import { CheckCircle2, Loader2, Lock, LockOpen, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

/**
 * Closed-loop self-healing worktree demo — migrated from the legacy Kora
 * landing page. Simulates intercepting a failing test, slicing the AST frame,
 * and patching inside an isolated ephemeral Git worktree.
 */
export function SelfHealingWorktreeLab() {
  const [airGapped, setAirGapped] = useState(true);
  const [patch, setPatch] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  function toggleAirGap() {
    setAirGapped((v) => {
      trackEvent(v ? "airgap_disabled" : "airgap_enabled");
      return !v;
    });
  }

  function runRepair() {
    setRunning(true);
    trackEvent("self_healing_demo_run");
    setTimeout(() => {
      setPatch(
        `1. Slicing AST target: core/broker.py:42...
2. Spawning isolated ephemeral Git worktree...
3. Executing local keelway-coder:7b mutation...
[✓] VERIFIED: 1 passed in 0.08s (Zero Regression)
+ if settlement_proof: return True`
      );
      setRunning(false);
    }, 900);
  }

  return (
    <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-canvas px-3.5 py-1 font-mono text-xs text-fg">
            <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
            <span className="font-semibold">CLOSED-LOOP SELF-HEALING LAB</span>
          </div>
          <h2 className="mt-3 text-xl font-bold tracking-tight text-fg sm:text-2xl">
            AST Repair in an Isolated Worktree
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-fg-muted">
            Failing tests are intercepted, the AST frame is sliced, and a verified
            patch is proposed — never merged without review.
          </p>
        </div>
        <button
          type="button"
          onClick={toggleAirGap}
          aria-pressed={airGapped}
          className={cn(
            "inline-flex min-h-[44px] items-center gap-2 rounded-md border px-3.5 py-2 font-mono text-xs font-semibold transition-colors duration-150",
            airGapped
              ? "border-teal-accent bg-teal-surface text-teal-accent"
              : "border-border-strong bg-canvas text-fg-muted"
          )}
        >
          {airGapped ? (
            <Lock className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <LockOpen className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          <span>{airGapped ? "AIR-GAP: ACTIVE" : "HYBRID CLOUD: ALLOWED"}</span>
        </button>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-fg-muted">
            Failing Test Intercepted
          </div>
          <div className="mt-2 rounded-md border border-border-subtle bg-canvas p-4 font-mono text-xs text-fg-muted">
            <div className="text-fault">FAIL tests/test_payment.py::test_mpesa_daraja</div>
            <div>&gt; assert response.status == &apos;settled&apos;</div>
            <div className="font-bold text-fault">
              E AssertionError: assert &apos;pending&apos; == &apos;settled&apos;
            </div>
            <div className="mt-2 text-fg-dim">
              Locating AST frame: verify_settlement() in core/broker.py:42
            </div>
          </div>

          <button
            type="button"
            onClick={runRepair}
            disabled={running}
            className="mt-4 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-teal-accent bg-teal-surface px-4 py-2.5 font-sans text-sm font-bold text-teal-accent transition-colors duration-150 hover:brightness-110 disabled:opacity-60"
          >
            {running ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Zap className="h-4 w-4" aria-hidden="true" />
            )}
            {running ? "Healing in isolated worktree…" : "Run Closed-Loop Self-Healing"}
          </button>
        </div>

        <div>
          <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-fg-muted">
            Automated AST Patch &amp; Worktree
          </div>
          <div className="mt-2 min-h-[160px] rounded-md border border-border-subtle bg-canvas p-4 font-mono text-xs leading-relaxed text-fg-muted">
            {patch ? (
              <pre className="whitespace-pre-wrap">{patch}</pre>
            ) : (
              <span className="text-fg-dim">
                // Press &apos;Run Closed-Loop Self-Healing&apos; to simulate edge AST repair.
              </span>
            )}
          </div>
          {patch && (
            <div className="mt-2 flex items-center gap-1.5 font-mono text-[11px] text-teal-accent">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Patch verified — awaiting human review (P-10)</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
