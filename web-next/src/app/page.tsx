import { Button } from "@/components/ui/button";

const FACTS = [
  { label: "Seat tiers", value: "4 + marketplace stream" },
  { label: "Approval gates", value: "P-10 — human only" },
  { label: "Audit", value: "hash-chained Record" },
  { label: "Egress", value: "fail closed, air-gap" },
] as const;

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-8 px-6 py-16">
      <header className="space-y-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
          Keelway · sovereign AI developer platform
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-fg">
          Agents you can audit. Egress you can prove.
        </h1>
        <p className="max-w-xl text-sm leading-6 text-fg-muted">
          Local-first orchestration with P-10 human approval gates, a hash-chained
          Record ledger, and fail-closed air-gap controls — measured, not marketed.
        </p>
        <div className="flex gap-2 pt-2">
          <Button>Get started</Button>
          <Button variant="secondary">Read the docs</Button>
        </div>
      </header>

      <section aria-label="Platform facts" className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-4">
        {FACTS.map((fact) => (
          <div key={fact.label} className="bg-surface px-4 py-3">
            <p className="font-mono text-[10px] uppercase tracking-wide text-fg-muted">{fact.label}</p>
            <p className="mt-1 text-sm font-medium text-fg">{fact.value}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
