type Variant = "gate" | "flow" | "policy";

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

function Chip({ tone, children }: { tone: "brass" | "green" | "red" | "blue" | "dim"; children: React.ReactNode }) {
  const cls = { brass: "kw-chip-brass", green: "kw-chip-green", red: "kw-chip-red", blue: "kw-chip-blue", dim: "" }[tone];
  return <span className={`kw-chip ${cls}`}>{children}</span>;
}

function Chrome({ right }: { right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--rule)] px-4 py-2.5">
      <span className="kw-label">Keelway — control plane</span>
      {right}
    </div>
  );
}

function GatePanel() {
  return (
    <div className="grid sm:grid-cols-[15rem_1fr]">
      <div className="hidden border-r border-[var(--rule)] sm:block">
        <p className="kw-label px-4 pt-4">Tasks</p>
        <ul className="mt-2">
          {TASKS.map((t) => (
            <li key={t.name} className={`px-4 py-3 ${t.active ? "bg-[var(--fog-8)]" : ""}`}>
              <p className="text-[12px] leading-snug text-[var(--ink)]">{t.name}</p>
              <p className="kw-data mt-1.5 text-[10px] text-[var(--dim)]">{t.meta}</p>
            </li>
          ))}
        </ul>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Chip tone="brass">P-10 GATE · QUORUM 1/2</Chip>
          <span className="kw-data text-[10px] text-[var(--dim)]">run 7b02.5.1 · p-14</span>
        </div>
        <ol className="mt-4 flex flex-wrap gap-2">
          {STEPS.map((s) => (
            <li key={s.n} className="flex items-center gap-2">
              <span className={`kw-data text-[10px] ${s.state === "gate" ? "text-[var(--brass)]" : s.state === "done" ? "text-[var(--green)]" : "text-[var(--dim)]"}`}>
                {s.n} {s.name}
              </span>
              {s.n !== "04" && <span className="h-px w-4 bg-[var(--rule-strong)]" aria-hidden="true" />}
            </li>
          ))}
        </ol>
        <p className="kw-label mt-6">Execution receipts</p>
        <ul className="mt-2 divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
          {RECEIPTS.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-3 py-2.5">
              <span className="kw-data text-[11px] text-[var(--muted)]"><span className="text-[var(--dim)]">{r.id}</span> {r.action}</span>
              <Chip tone={r.state === "sealed" ? "green" : "brass"}>{r.state.toUpperCase()}</Chip>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex items-center gap-3">
          <span className="kw-btn kw-btn-primary px-3 py-1.5 text-[11px]">Allow once</span>
          <span className="kw-btn kw-btn-secondary px-3 py-1.5 text-[11px]">Deny</span>
          <span className="kw-data ml-auto text-[10px] text-[var(--dim)]">Esc = deny</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-[var(--rule)] px-4 py-2.5 sm:col-span-2">
        <span className="kw-data text-[10px] text-[var(--dim)]">cost $0.00</span>
        <span className="kw-data text-[10px] text-[var(--dim)]">tape #1283</span>
        <span className="kw-data text-[10px] text-[var(--green)]">chain verified</span>
      </div>
    </div>
  );
}

function FlowPanel() {
  const nodes = [
    { name: "ingest", sub: "spec parse", tone: "dim" as const },
    { name: "plan", sub: "KFlow DAG", tone: "dim" as const },
    { name: "P-10", sub: "human gate", tone: "brass" as const },
    { name: "execute", sub: "sandboxed", tone: "blue" as const },
    { name: "seal", sub: "tape #1283", tone: "green" as const },
  ];
  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="flex items-center justify-between">
        <span className="kw-label">KFlow run · langgraph-refund-cycle</span>
        <Chip tone="brass">AWAITING GATE</Chip>
      </div>
      <div className="mt-8 flex flex-wrap items-center gap-y-6">
        {nodes.map((n, i) => (
          <div key={n.name} className="flex items-center">
            <div className={`kw-card px-4 py-3 ${n.tone === "brass" ? "border-[var(--brass-40)]" : ""}`}>
              <p className={`kw-data text-[11px] ${n.tone === "brass" ? "text-[var(--brass)]" : "text-[var(--ink)]"}`}>{n.name}</p>
              <p className="mt-1 text-[10px] text-[var(--dim)]">{n.sub}</p>
            </div>
            {i < nodes.length - 1 && (
              <div className="mx-1 flex items-center sm:mx-2" aria-hidden="true">
                <span className="h-px w-5 bg-[var(--rule-strong)] sm:w-9" />
                <span className="text-[8px] text-[var(--dim)]">&#9656;</span>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-8 flex flex-wrap gap-x-6 gap-y-1 border-t border-[var(--rule)] pt-3">
        <span className="kw-data text-[10px] text-[var(--dim)]">iterations 1/10 bounded</span>
        <span className="kw-data text-[10px] text-[var(--dim)]">egress 0 bytes</span>
        <span className="kw-data text-[10px] text-[var(--muted)]">every edge writes to the tape</span>
      </div>
    </div>
  );
}

function PolicyPanel() {
  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex items-center justify-between">
        <span className="kw-label">Policy engine · evaluated pre-egress</span>
        <Chip tone="red">AIR-GAP ARMED</Chip>
      </div>
      <ul className="mt-4 divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
        {RULES.map((r) => (
          <li key={r.rule} className="grid gap-1 py-3 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-4">
            <span className="text-[12px] text-[var(--ink)]">{r.rule}</span>
            <span className="kw-data text-[10px] text-[var(--dim)]">{r.route}</span>
            <Chip tone={r.verdict === "ALLOW" ? "green" : "red"}>{r.verdict}</Chip>
          </li>
        ))}
      </ul>
      <p className="kw-data mt-4 text-[10px] text-[var(--dim)]">denials are sealed, not silent — every decision lands on the tape</p>
    </div>
  );
}

export function ControlPlaneFigure({ variant = "gate" }: { variant?: Variant }) {
  return (
    <div className="kw-figure bg-[var(--fog-4)]" role="img" aria-label={LABELS[variant]}>
      <div aria-hidden="true">
        <Chrome />
        {variant === "gate" && <GatePanel />}
        {variant === "flow" && <FlowPanel />}
        {variant === "policy" && <PolicyPanel />}
      </div>
    </div>
  );
}
