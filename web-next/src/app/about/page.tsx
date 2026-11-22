import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About — Keelway",
  description: "Keelway is built by Sorvex Labs — a sovereign agent platform, Apache-2.0 open core.",
};

const PRINCIPLES = [
  { id: "P-01", title: "Sovereignty is a feature", body: "Your models, your keys, your tapes. Keelway never holds your prompts hostage — the platform runs where you put it, including air-gapped." },
  { id: "P-02", title: "Every action is accountable", body: "The execution tape is a hash-chained Merkle record. Denials are sealed too — nothing fails silently." },
  { id: "P-03", title: "Governance before egress", body: "Policy decides where a call runs before the prompt leaves the machine. Fail-closed, not best-effort." },
  { id: "P-04", title: "Honest economics", body: "0% token markup on paid tiers. You pay providers at their published rate card; we bill per seat." },
] as const;

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">About</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-fg">Built by Sorvex Labs.</h1>
      <p className="mt-6 max-w-2xl text-sm leading-6 text-fg-muted">
        Keelway exists because agent systems asked for trust they hadn&apos;t earned.
        We build the instrument that answers with receipts — an Apache-2.0 open core
        with commercial tiers for teams that need governed routing at scale.
      </p>
      <div className="mt-14 border-t border-border">
        {PRINCIPLES.map((p) => (
          <div key={p.id} className="flex flex-col gap-2 border-b border-border py-7 sm:flex-row sm:gap-10">
            <p className="w-16 shrink-0 pt-1 font-mono text-[11px] uppercase tracking-wide text-fg-muted">{p.id}</p>
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-fg">{p.title}</h2>
              <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-fg-muted">{p.body}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-16 border-t border-border pt-10">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Sorvex Labs</h2>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-fg-muted">
          Sorvex Labs is the company behind Keelway. We build sovereign AI
          infrastructure — systems that keep models, keys, and records under the
          operator&apos;s control. Keelway is our flagship platform: an open-core
          agent runtime with governed frontier routing and a signed receipt for
          every action.
        </p>
        <p className="mt-6 font-mono text-[10px] text-fg-muted">Keelway — a Sorvex Labs product.</p>
      </div>
    </main>
  );
}
