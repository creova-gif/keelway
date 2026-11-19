import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Keelway documentation — quickstart, architecture, security standards, and the engineering contract. Everything is on the record.",
};

const REPO = "/repo";

const GROUPS: { label: string; rows: { title: string; note: string; href: string }[] }[] = [
  {
    label: "START",
    rows: [
      { title: "README", note: "What Keelway is, install, first run", href: `${REPO}/README.md` },
      { title: "Developer quickstart", note: "Zero to a running dev app", href: `${REPO}/docs/DEVELOPER_QUICKSTART.md` },
      { title: "Install script", note: "One line to a running system", href: "/install.sh" },
      { title: "Demo guide", note: "Reproduce the platform walkthrough", href: `${REPO}/docs/DEMO.md` },
    ],
  },
  {
    label: "ARCHITECTURE",
    rows: [
      { title: "System overview", note: "Topology, components, data flow", href: `${REPO}/docs/architecture/SYSTEM_OVERVIEW.md` },
      { title: "Hybrid AI architecture", note: "Open-weight vs frontier tiers", href: `${REPO}/docs/architecture/HYBRID_AI_ARCHITECTURE.md` },
      { title: "Model provider contract", note: "Provider adapter & gateway interfaces", href: `${REPO}/docs/architecture/MODEL_PROVIDER_CONTRACT.md` },
      { title: "Compatibility matrix", note: "Verified vs implied vs gated, per cell", href: `${REPO}/docs/architecture/MODEL_COMPATIBILITY_MATRIX.md` },
    ],
  },
  {
    label: "OPERATE",
    rows: [
      { title: "Security standards", note: "Invariants, sandboxing, fail-closed rules", href: `${REPO}/docs/engineering/SECURITY_STANDARDS.md` },
      { title: "Security invariants & audit report", note: "What the tape guarantees", href: `${REPO}/docs/SECURITY_INVARIANTS_AND_AUDIT_REPORT.md` },
      { title: "Quality gates", note: "CI, pre-commit, release gates", href: `${REPO}/docs/engineering/QUALITY_GATES.md` },
      { title: "Testing strategy", note: "Pyramid, mock policy, contract tests", href: `${REPO}/docs/engineering/TESTING_STRATEGY.md` },
    ],
  },
  {
    label: "PRODUCT & AGENTS",
    rows: [
      { title: "Product strategy", note: "Positioning, hybrid cost advantage", href: `${REPO}/docs/product/PRODUCT_STRATEGY.md` },
      { title: "LangGraph migration", note: "keelway migrate — static AST importer", href: `${REPO}/docs/LANGGRAPH_MIGRATION.md` },
      { title: "Agent engineering contract", note: "AGENTS.md — how machines work this repo", href: `${REPO}/AGENTS.md` },
    ],
  },
];

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="kw-label">Documentation</p>
      <h1 className="kw-h1 mt-5">Everything is on the record.</h1>
      <p className="kw-body mt-5 max-w-xl">
        Keelway&apos;s docs live in the repository — versioned, reviewed, and never
        out of sync with the code they describe.
      </p>
      {GROUPS.map((g) => (
        <section key={g.label} className="mt-12">
          <p className="kw-label kw-label-brass">{g.label}</p>
          <ul className="mt-4 divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
            {g.rows.map((r) => (
              <li key={r.title}>
                <a
                  href={r.href}
                  target={r.href.startsWith("http") || r.href.startsWith("/repo") ? "_blank" : undefined}
                  rel={r.href.startsWith("http") || r.href.startsWith("/repo") ? "noopener" : undefined}
                  className="kw-row-hover group flex items-baseline justify-between gap-4 px-1 py-3.5"
                >
                  <span>
                    <span className="text-[14px] font-medium text-[var(--ink)] group-hover:text-[var(--brass)]">
                      {r.title}
                    </span>
                    <span className="mt-0.5 block text-[12px] text-[var(--muted)]">{r.note}</span>
                  </span>
                  <span className="kw-data shrink-0 text-[11px] text-[var(--dim)]">&rarr;</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <p className="kw-small mt-10">
        Can&apos;t find it? <a href="/repo" className="underline underline-offset-2">Browse the repository</a> — the tape doesn&apos;t lie.
      </p>
    </div>
  );
}
