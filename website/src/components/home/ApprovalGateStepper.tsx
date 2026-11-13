"use client";

import React, { useEffect, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { useReducedMotion } from "framer-motion";
import { CheckCheck, Pause, Play, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

interface WorkflowStage {
  id: string;
  label: string;
  badge: string;
  badgeVariant: "teal" | "amber";
  actor: string;
  blockHash: string;
  prevHash: string;
  output: string[];
}

const STAGES: WorkflowStage[] = [
  {
    id: "plan",
    label: "1. Plan",
    badge: "STEP 1 · PLAN READY",
    badgeVariant: "teal",
    actor: "Agent: coder-agent (keelway-coder:7b)",
    prevHash: "0000000000000000",
    blockHash: "3f9a1c82e7b405d1",
    output: [
      "[+] Goal: Fix 10% discount calculation bug in pricing.py and prove with tests",
      "[+] Formulated 3 deterministic execution steps:",
      '    1. read_file("pricing.py")   -> inspect apply_discount AST node',
      '    2. edit_file("pricing.py")   -> round(price_cents * (100 - percent) / 100)',
      '    3. run_command("pytest -q")  -> assert zero regressions before seal',
    ],
  },
  {
    id: "approve",
    label: "2. Approve",
    badge: "STEP 2 · HUMAN APPROVAL GATE",
    badgeVariant: "amber",
    actor: "Policy: confirm_mutation",
    prevHash: "3f9a1c82e7b405d1",
    blockHash: "7c2d90e41a6b8f33",
    output: [
      '[!] Mutating Tool Call Paused: edit_file("pricing.py")',
      "    - return price_cents - percent",
      "    + return round(price_cents * (100 - percent) / 100)",
      "[?] Decision recorded: ALLOW_ONCE (actor: lead_dev@keelway.local)",
    ],
  },
  {
    id: "patch",
    label: "3. Patch",
    badge: "STEP 3 · ATOMIC PATCH APPLIED",
    badgeVariant: "teal",
    actor: "Surface: Git Working Tree",
    prevHash: "7c2d90e41a6b8f33",
    blockHash: "b18e44c709d23a5f",
    output: [
      "diff --git a/pricing.py b/pricing.py",
      "@@ -3,7 +3,7 @@",
      " def apply_discount(price_cents: int, percent: int) -> int:",
      "-    return price_cents - percent",
      "+    return round(price_cents * (100 - percent) / 100)",
    ],
  },
  {
    id: "verify",
    label: "4. Verify",
    badge: "STEP 4 · TEST SUITE GREEN",
    badgeVariant: "teal",
    actor: "Runner: SelfHealingLoop (pytest)",
    prevHash: "b18e44c709d23a5f",
    blockHash: "d409f6a182c7e519",
    output: [
      "$ python3 -m unittest -q test_pricing.py",
      "----------------------------------------------------------------------",
      "Ran 3 tests in 0.032s",
      "",
      "OK · Exit Code 0",
    ],
  },
  {
    id: "seal",
    label: "5. Seal",
    badge: "STEP 5 · LEDGER SEALED",
    badgeVariant: "teal",
    actor: "Audit: FlightRecorder (SQLite + SHA-256)",
    prevHash: "d409f6a182c7e519",
    blockHash: "f91a83e54b20c67d",
    output: [
      "[+] Flight tape appended to local hash-chained record (.keelway/flight.db)",
      "[+] Chain root digest: sha256:f91a83e54b20c67d881209c4e7b3102a",
      "[+] Independent offline verification: GET /v1/audit/verify -> VALID",
    ],
  },
];

/**
 * Preserves and upgrades the signature 5-step Agent Approval Gate demo
 * with keyboard-accessible Radix Tabs, optional auto-walkthrough, and
 * live hash-chain continuity verification.
 */
export function ApprovalGateStepper() {
  const prefersReducedMotion = useReducedMotion();
  const [activeStep, setActiveStep] = useState<string>("plan");
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [chainVerified, setChainVerified] = useState<boolean>(false);

  useEffect(() => {
    if (!isPlaying || prefersReducedMotion) return;
    const timer = window.setInterval(() => {
      setActiveStep((prev) => {
        const idx = STAGES.findIndex((s) => s.id === prev);
        return STAGES[(idx + 1) % STAGES.length].id;
      });
    }, 2800);
    return () => window.clearInterval(timer);
  }, [isPlaying, prefersReducedMotion]);

  const handleVerifyChain = () => {
    // Deterministically check prevHash -> blockHash linkage across all 5 stages
    const intact = STAGES.every(
      (stage, i) => i === 0 || stage.prevHash === STAGES[i - 1].blockHash
    );
    if (intact) {
      setChainVerified(true);
      trackEvent("hash_chain_verified", { blocks: STAGES.length });
    }
  };

  return (
    <section
      id="workflow"
      aria-labelledby="workflow-heading"
      className="border-t border-border-subtle bg-surface/35 py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              02 // VERIFIABLE AGENT EXECUTION
            </p>
            <h2
              id="workflow-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Every mutating agent step passes a human or policy gate
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-fg-muted">
              A deterministic plan, a scoped mutation gate, an atomic Git patch,
              an automated test run, and a hash-chained flight tape you can
              audit offline.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!prefersReducedMotion && (
              <button
                type="button"
                onClick={() => setIsPlaying((p) => !p)}
                className="kw-btn kw-btn-secondary font-mono text-xs"
              >
                {isPlaying ? (
                  <>
                    <Pause className="h-3.5 w-3.5 text-amber-alert" aria-hidden="true" />
                    <span>Pause walkthrough</span>
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
                    <span>Auto-play 5 stages</span>
                  </>
                )}
              </button>
            )}
            <button
              type="button"
              onClick={handleVerifyChain}
              className="kw-btn kw-btn-secondary font-mono text-xs"
            >
              {chainVerified ? (
                <>
                  <CheckCheck
                    className="h-4 w-4 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>5/5 Blocks Verified</span>
                </>
              ) : (
                <>
                  <ShieldCheck
                    className="h-4 w-4 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>Verify Hash Chain</span>
                </>
              )}
            </button>
          </div>
        </div>

        <div className="mt-8 rounded-lg border border-border-strong bg-surface p-5 sm:p-6">
          <Tabs.Root
            value={activeStep}
            onValueChange={(val) => {
              setIsPlaying(false);
              setActiveStep(val);
              trackEvent("workflow_step_selected", { step: val });
            }}
          >
            {/* 5-Stage Horizontal Tab Rail */}
            <Tabs.List
              aria-label="5-stage agent approval workflow"
              className="grid grid-cols-2 gap-2 sm:grid-cols-5"
            >
              {STAGES.map((stage) => {
                const isSelected = activeStep === stage.id;
                return (
                  <Tabs.Trigger
                    key={stage.id}
                    value={stage.id}
                    className={cn(
                      "min-h-[44px] rounded-sm border px-3 py-2 text-left font-mono text-xs font-semibold transition-colors duration-150",
                      isSelected
                        ? "border-teal-accent bg-teal-accent text-teal-ink"
                        : "border-border-strong bg-canvas text-fg-muted hover:border-teal-accent/60 hover:text-fg"
                    )}
                  >
                    {stage.label}
                  </Tabs.Trigger>
                );
              })}
            </Tabs.List>

            {/* Stage Content Panels */}
            {STAGES.map((stage) => (
              <Tabs.Content
                key={stage.id}
                value={stage.id}
                className="mt-5 focus:outline-none"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "rounded-sm px-2.5 py-1",
                        stage.badgeVariant === "amber"
                          ? "chip-amber"
                          : "chip-teal"
                      )}
                    >
                      {stage.badge}
                    </span>
                    <span className="chip-neutral rounded-sm px-2.5 py-1">
                      {stage.actor}
                    </span>
                  </div>

                  <div className="font-mono text-[11px] text-fg-muted">
                    prev: <span className="text-fg-dim">{stage.prevHash}</span>{" "}
                    → block:{" "}
                    <span className="text-teal-accent">{stage.blockHash}</span>
                  </div>
                </div>

                <pre className="mt-4 overflow-x-auto rounded-md border border-border-strong bg-canvas p-4 font-mono text-xs leading-relaxed text-fg">
                  {stage.output.join("\n")}
                </pre>
              </Tabs.Content>
            ))}
          </Tabs.Root>

          {chainVerified && (
            <div
              aria-live="polite"
              className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-sm border border-teal-accent/50 bg-teal-surface px-3.5 py-2.5 font-mono text-xs text-fg"
            >
              <span>
                Cryptographic continuity verified across blocks{" "}
                <code>0000000000000000 → f91a83e54b20c67d</code>.
              </span>
              <span className="font-semibold text-teal-accent">
                ZERO TAMPERING DETECTED
              </span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
