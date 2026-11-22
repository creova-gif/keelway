"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

type Variant = "gate" | "flow" | "policy";
type GateState = "gated" | "sealed" | "denied";

const LABELS: Record<Variant, string> = {
  gate: "Keelway control plane sample: task queue, P-10 approval gate, sealed execution receipts, and tape status.",
  flow: "Keelway KFlow sample: a deterministic run graph with a P-10 gate between planning and ship.",
  policy: "Keelway policy engine sample: egress rules evaluated before a call leaves the machine.",
};

const TASKS = [
  { name: "Harden loopback CSP & verify Studio token middleware", meta: "needs approval · 2m ago", active: true },
  { name: "Audit SHA-256 Merkle inclusion proofs", meta: "sealed · 14m ago", active: false },
  { name: "Route frontier call through BYOM gateway", meta: "running · just now", active: false },
];

const STEPS = [
  { n: "01", name: "plan", state: "done" },
  { n: "02", name: "retrieve", state: "done" },
  { n: "03", name: "P-10 gate", state: "gate" },
  { n: "04", name: "ship", state: "todo" },
];

const RECEIPTS = [
  { id: "#1281", action: "Read file core/main.py", state: "sealed" },
  { id: "#1282", action: "Edited file core/main.py", state: "sealed" },
  { id: "#1283", action: "Run workspace command pytest -q", state: "awaiting" },
];

const RULES = [
  { rule: "prompt contains classified tenant payload", route: "open_weight · local", verdict: "ALLOW" },
  { rule: "airgap_strict profile active", route: "cloud egress", verdict: "DENY" },
  { rule: "spend cap $25/day reached", route: "frontier pool", verdict: "DENY" },
  { rule: "BYOM key scoped kw_live_***", route: "frontier · 0% markup", verdict: "ALLOW" },
];

function Chip({ tone, children }: { tone: "accent" | "ok" | "danger" | "dim"; children: React.ReactNode }) {
  const cls = {
    accent: "bg-accent-subtle text-accent",
    ok: "bg-ok-subtle text-ok",
    danger: "bg-danger-subtle text-danger",
    dim: "bg-surface-raised text-fg-muted",
  }[tone];
  return (
    <span className={`rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {children}
    </span>
  );
}

function Chrome({ right }: { right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
      <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Keelway — control plane</span>
      {right}
    </div>
  );
}

function GatePanel() {
  const [gate, setGate] = useState<GateState>("gated");

  const gateChip =
    gate === "gated"
      ? { tone: "accent" as const, text: "P-10 GATE · QUORUM 1/2" }
      : gate === "sealed"
        ? { tone: "ok" as const, text: "P-10 GATE · APPROVED" }
        : { tone: "danger" as const, text: "P-10 GATE · DENIED" };

  const stepState = (s: (typeof STEPS)[number]) =>
    s.state !== "gate" ? s.state : gate === "sealed" ? "done" : gate === "denied" ? "denied" : "gate";

  const receiptState = (r: (typeof RECEIPTS)[number]) =>
    r.state !== "awaiting" ? r.state : gate === "sealed" ? "sealed" : gate === "denied" ? "denied" : "awaiting";

  return (
    <div className="grid sm:grid-cols-[15rem_1fr]">
      <div className="hidden border-r border-border sm:block" aria-hidden="true">
        <p className="px-4 pt-4 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Tasks</p>
        <ul className="mt-2">
          {TASKS.map((t) => (
            <li key={t.name} className={`px-4 py-3 ${t.active ? "bg-surface" : ""}`}>
              <p className="text-[12px] leading-snug text-fg">{t.name}</p>
              <p className="mt-1.5 font-mono text-[10px] text-fg-muted">{t.meta}</p>
            </li>
          ))}
        </ul>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className={gate === "sealed" ? "kw-seal-ring inline-flex" : "inline-flex"}>
            <Chip tone={gateChip.tone}>{gateChip.text}</Chip>
          </span>
          <span className="font-mono text-[10px] text-fg-muted">run 7b02.5.1 · p-14</span>
        </div>
        <ol className="mt-4 flex flex-wrap gap-2" aria-hidden="true">
          {STEPS.map((s) => {
            const st = stepState(s);
            return (
              <li key={s.n} className="flex items-center gap-2">
                <span
                  className={`font-mono text-[10px] ${
                    st === "gate"
                      ? "text-accent"
                      : st === "done"
                        ? "text-ok"
                        : st === "denied"
                          ? "text-danger"
                          : "text-fg-muted"
                  }`}
                >
                  {s.n} {s.name}
                </span>
                {s.n !== "04" && <span className="h-px w-4 bg-border-strong" aria-hidden="true" />}
              </li>
            );
          })}
        </ol>
        <p className="mt-6 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Execution receipts</p>
        <ul className="mt-2 divide-y divide-border border-y border-border" aria-live="polite">
          {RECEIPTS.map((r) => {
            const st = receiptState(r);
            return (
              <li
                key={r.id}
                className={`flex items-center justify-between gap-3 py-2.5 ${
                  r.state === "awaiting" && gate !== "gated" ? "kw-land" : ""
                }`}
              >
                <span className="font-mono text-[11px] text-fg-muted">
                  <span className="text-fg-muted">{r.id}</span> {r.action}
                </span>
                <Chip tone={st === "sealed" ? "ok" : st === "denied" ? "danger" : "accent"}>{st.toUpperCase()}</Chip>
              </li>
            );
          })}
        </ul>
        <div className="mt-4 flex items-center gap-3">
          {gate === "gated" ? (
            <>
              <Button size="sm" onClick={() => setGate("sealed")}>Allow once</Button>
              <Button size="sm" variant="secondary" onClick={() => setGate("denied")}>Deny</Button>
              <span className="ml-auto font-mono text-[10px] text-fg-muted">try the gate</span>
            </>
          ) : (
            <>
              <Button size="sm" variant="secondary" onClick={() => setGate("gated")}>↺ replay</Button>
              <span className="ml-auto font-mono text-[10px] text-fg-muted">
                {gate === "sealed" ? "approval sealed to tape #1284" : "denial sealed to tape #1284"}
              </span>
            </>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-border px-4 py-2.5 sm:col-span-2" aria-hidden="true">
        <span className="font-mono text-[10px] text-fg-muted">cost $0.00</span>
        <span className="font-mono text-[10px] text-fg-muted">tape #{gate === "gated" ? "1283" : "1284"}</span>
        <span className="font-mono text-[10px] text-ok">chain verified</span>
      </div>
    </div>
  );
}

function FlowPanel() {
  const nodes = [
    { name: "ingest", sub: "spec parse", tone: "dim" as const },
    { name: "plan", sub: "KFlow DAG", tone: "dim" as const },
    { name: "P-10", sub: "human gate", tone: "accent" as const },
    { name: "execute", sub: "sandboxed", tone: "dim" as const },
    { name: "seal", sub: "tape #1283", tone: "ok" as const },
  ];
  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
          KFlow run · langgraph-refund-cycle
        </span>
        <Chip tone="accent">AWAITING GATE</Chip>
      </div>
      <div className="mt-8 flex flex-wrap items-center gap-y-6">
        {nodes.map((n, i) => (
          <div key={n.name} className="flex items-center">
            <div
              className={`rounded-md border px-4 py-3 ${
                n.tone === "accent" ? "border-accent/40 bg-surface" : "border-border bg-surface"
              }`}
            >
              <p className={`font-mono text-[11px] ${n.tone === "accent" ? "text-accent" : "text-fg"}`}>{n.name}</p>
              <p className="mt-1 text-[10px] text-fg-muted">{n.sub}</p>
            </div>
            {i < nodes.length - 1 && (
              <div className="mx-1 flex items-center sm:mx-2" aria-hidden="true">
                <span className="h-px w-5 bg-border-strong sm:w-9" />
                <span className="text-[8px] text-fg-muted">&#9656;</span>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-8 flex flex-wrap gap-x-6 gap-y-1 border-t border-border pt-3">
        <span className="font-mono text-[10px] text-fg-muted">iterations 1/10 bounded</span>
        <span className="font-mono text-[10px] text-fg-muted">egress 0 bytes</span>
        <span className="font-mono text-[10px] text-fg-muted">every edge writes to the tape</span>
      </div>
    </div>
  );
}

function PolicyPanel() {
  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
          Policy engine · evaluated pre-egress
        </span>
        <Chip tone="danger">AIR-GAP ARMED</Chip>
      </div>
      <ul className="mt-4 divide-y divide-border border-y border-border">
        {RULES.map((r) => (
          <li key={r.rule} className="grid gap-1 py-3 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-4">
            <span className="text-[12px] text-fg">{r.rule}</span>
            <span className="font-mono text-[10px] text-fg-muted">{r.route}</span>
            <Chip tone={r.verdict === "ALLOW" ? "ok" : "danger"}>{r.verdict}</Chip>
          </li>
        ))}
      </ul>
      <p className="mt-4 font-mono text-[10px] text-fg-muted">
        denials are sealed, not silent — every decision lands on the tape
      </p>
    </div>
  );
}

export function ControlPlaneFigure({ variant = "gate" }: { variant?: Variant }) {
  const interactive = variant === "gate";
  return (
    <div
      className="overflow-hidden rounded-md border border-border bg-surface-raised"
      role={interactive ? "group" : "img"}
      aria-label={LABELS[variant]}
    >
      <div aria-hidden={interactive ? undefined : true}>
        <Chrome />
        {variant === "gate" && <GatePanel />}
        {variant === "flow" && <FlowPanel />}
        {variant === "policy" && <PolicyPanel />}
      </div>
    </div>
  );
}
