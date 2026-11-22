import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Documentation — Keelway",
  description:
    "Keelway documentation — quickstart, architecture, security standards, and the engineering contract. Everything is on the record.",
};

const REPO = "https://github.com/creova-gif/keelway/blob/main";
const SITE = "https://kora-sable.vercel.app";

const GROUPS: { label: string; rows: { title: string; note: string; href: string }[] }[] = [
  {
    label: "Start",
    rows: [
      { title: "README", note: "What Keelway is, install, first run", href: `${REPO}/README.md` },
      { title: "Developer quickstart", note: "Zero to a running dev app", href: `${REPO}/docs/DEVELOPER_QUICKSTART.md` },
      { title: "Install script", note: "One line to a running system", href: `${SITE}/install.sh` },
      { title: "Demo guide", note: "Reproduce the platform walkthrough", href: `${REPO}/docs/DEMO.md` },
    ],
  },
  {
    label: "Architecture",
    rows: [
      { title: "System overview", note: "Topology, components, data flow", href: `${REPO}/docs/architecture/SYSTEM_OVERVIEW.md` },
      { title: "Hybrid AI architecture", note: "Open-weight vs frontier tiers", href: `${REPO}/docs/architecture/HYBRID_AI_ARCHITECTURE.md` },
      { title: "Model provider contract", note: "Provider adapter & gateway interfaces", href: `${REPO}/docs/architecture/MODEL_PROVIDER_CONTRACT.md` },
      { title: "Compatibility matrix", note: "Verified vs implied vs gated, per cell", href: `${REPO}/docs/architecture/MODEL_COMPATIBILITY_MATRIX.md` },
    ],
  },
  {
    label: "Operate",
    rows: [
      { title: "Security standards", note: "Invariants, sandboxing, fail-closed rules", href: `${REPO}/docs/engineering/SECURITY_STANDARDS.md` },
      { title: "Security invariants & audit report", note: "What the tape guarantees", href: `${REPO}/docs/SECURITY_INVARIANTS_AND_AUDIT_REPORT.md` },
      { title: "Quality gates", note: "CI, pre-commit, release gates", href: `${REPO}/docs/engineering/QUALITY_GATES.md` },
      { title: "Testing strategy", note: "Pyramid, mock policy, contract tests", href: `${REPO}/docs/engineering/TESTING_STRATEGY.md` },
    ],
  },
  {
    label: "Product & agents",
    rows: [
      { title: "Product strategy", note: "Positioning, hybrid cost advantage", href: `${REPO}/docs/product/PRODUCT_STRATEGY.md` },
      { title: "LangGraph migration", note: "keelway migrate — static AST importer", href: `${REPO}/docs/LANGGRAPH_MIGRATION.md` },
      { title: "Agent engineering contract", note: "AGENTS.md — how machines work this repo", href: `${REPO}/AGENTS.md` },
    ],
  },
];

export default function DocsPage() {
  return (
    <main className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Documentation</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-fg">Everything is on the record.</h1>
      <p className="mt-4 max-w-xl text-sm leading-6 text-fg-muted">
        Keelway&apos;s docs live in the repository — versioned, reviewed, and never
        out of sync with the code they describe.
      </p>
      {GROUPS.map((g) => (
        <section key={g.label} aria-label={g.label} className="mt-12">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">{g.label}</h2>
          <ul className="mt-4 divide-y divide-border border-y border-border">
            {g.rows.map((r) => (
              <li key={r.title}>
                <a
                  href={r.href}
                  target="_blank"
                  rel="noopener"
                  className="group flex items-baseline justify-between gap-4 px-1 py-3.5 transition-colors hover:bg-surface"
                >
                  <span>
                    <span className="text-[14px] font-medium text-fg group-hover:text-accent">
                      {r.title}
                    </span>
                    <span className="mt-0.5 block text-[12px] text-fg-muted">{r.note}</span>
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-fg-muted" aria-hidden="true">
                    &rarr;
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </main>
  );
}
