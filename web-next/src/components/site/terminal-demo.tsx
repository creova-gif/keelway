"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

type Phase = "idle" | "typing" | "running" | "gate" | "done";
type Outcome = "sealed" | "denied" | null;

const CMD = 'keelway run "harden loopback CSP"';

const PRE_GATE: { text: string; tone: "dim" | "muted" | "info" }[] = [
  { text: "k′ run 7b02.5.2 · policy local-first · sandbox seatbelt", tone: "dim" },
  { text: "ⓘ step 01 plan    — parsed spec, 4 steps", tone: "muted" },
  { text: "ⓘ step 02 retrieve — read core/main.py, core/middleware.py", tone: "muted" },
  { text: "● step 03 execute  — run pytest -q — P-10 GATE RAISED", tone: "info" },
];

export function TerminalDemo() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [typed, setTyped] = useState(0);
  const [shown, setShown] = useState(0);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const timers = useRef<number[]>([]);

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const later = (fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, reduced ? 0 : ms));
  };

  const run = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setOutcome(null);
    setShown(0);
    setPhase("typing");
    if (reduced) {
      setTyped(CMD.length);
      setShown(PRE_GATE.length);
      setPhase("gate");
      return;
    }
    for (let i = 1; i <= CMD.length; i++) {
      later(() => setTyped(i), i * 28);
    }
    const base = CMD.length * 28 + 300;
    later(() => setPhase("running"), base);
    PRE_GATE.forEach((_, i) => {
      later(() => setShown(i + 1), base + i * 420);
    });
    later(() => setPhase("gate"), base + PRE_GATE.length * 420 + 500);
  };

  const decide = (o: Exclude<Outcome, null>) => {
    setOutcome(o);
    setPhase("done");
  };

  const replay = () => {
    setPhase("idle");
    setTyped(0);
    setShown(0);
    setOutcome(null);
  };

  const toneCls = { dim: "text-fg-muted", muted: "text-fg-muted", info: "text-accent" };

  return (
    <div
      className="overflow-hidden rounded-md border border-border bg-surface-raised"
      role="group"
      aria-label="Keelway terminal session replay: run a task, hit a P-10 gate, decide, and watch the receipt seal."
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">k′ — session replay</span>
        <span className="font-mono text-[10px] text-fg-muted">tty · sandboxed</span>
      </div>
      <div className="px-4 py-4 sm:px-5" aria-live={phase === "running" ? "polite" : "off"}>
        <div className="font-mono text-[12px] text-fg">
          <span className="text-accent">$ </span>
          {phase === "idle" ? <span className="text-fg-muted">ready — press run</span> : CMD.slice(0, typed)}
          {phase === "typing" && <span aria-hidden="true">▍</span>}
        </div>
        <ul className="mt-3 space-y-1.5" role="log">
          {PRE_GATE.slice(0, shown).map((l, i) => (
            <li key={i} className={`kw-land font-mono text-[11px] ${toneCls[l.tone]}`}>
              {l.text}
            </li>
          ))}
          {phase === "done" && outcome === "sealed" && (
            <>
              <li className="kw-land font-mono text-[11px] text-ok">✓ approved once — executed in sandbox</li>
              <li className="kw-land font-mono text-[11px] text-ok">✓ receipt #1284 sealed · hash ↱#1283</li>
              <li className="kw-land font-mono text-[11px] text-fg-muted">tape verified · chain ok · egress 0 bytes</li>
            </>
          )}
          {phase === "done" && outcome === "denied" && (
            <>
              <li className="kw-land font-mono text-[11px] text-danger">✗ denied by operator — run aborted</li>
              <li className="kw-land font-mono text-[11px] text-danger">✗ denial sealed to tape #1284 · denials record too</li>
            </>
          )}
        </ul>
        <div className="mt-4 flex items-center gap-3">
          {phase === "idle" && (
            <Button size="sm" onClick={run}>▸ run session</Button>
          )}
          {(phase === "typing" || phase === "running") && (
            <span className="font-mono text-[10px] text-fg-muted">running…</span>
          )}
          {phase === "gate" && (
            <>
              <Button size="sm" onClick={() => decide("sealed")}>Allow once</Button>
              <Button size="sm" variant="secondary" onClick={() => decide("denied")}>Deny</Button>
              <span className="ml-auto font-mono text-[10px] text-fg-muted">the gate waits for you</span>
            </>
          )}
          {phase === "done" && (
            <>
              <Button size="sm" variant="secondary" onClick={replay}>↺ replay</Button>
              <span className="ml-auto font-mono text-[10px] text-fg-muted">a = allow · d = deny · same keys as the real gate</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
