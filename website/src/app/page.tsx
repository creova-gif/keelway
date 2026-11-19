import Link from "next/link";
import { ControlPlaneFigure } from "@/components/site/ControlPlaneFigure";

const PRINCIPLES = [
  {
    label: "YOUR HARDWARE",
    body: "Open-weight models run where they live — Ollama or private vLLM. $0 marginal token.",
    accent: true,
  },
  {
    label: "YOUR POLICY",
    body: "Privacy, cost, and capability decide where each call runs — before the prompt leaves the machine.",
    accent: false,
  },
  {
    label: "YOUR RECORDS",
    body: "Hash-chained tape of every action. P-10 human gates on anything that touches production.",
    accent: false,
  },
];

export default function HomePage() {
  return (
    <>
      <section className="mx-auto max-w-6xl px-5 pt-20 sm:px-8 sm:pt-28">
        <p className="kw-label kw-rise">Keelway — Sovereign Agent Platform</p>
        <h1 className="kw-display kw-rise mt-6 max-w-4xl" style={{ animationDelay: "60ms" }}>
          Agents that answer to you.
        </h1>
        <p className="kw-body kw-rise mt-6 max-w-xl" style={{ animationDelay: "120ms" }}>
          Keelway is a sovereign platform for AI agents. Local inference.
          Governed cloud routing. A signed receipt for every action.
        </p>
        <div className="kw-rise mt-9 flex flex-wrap items-center gap-5" style={{ animationDelay: "180ms" }}>
          <a href="#install" className="kw-btn kw-btn-primary">Install Keelway</a>
          <Link href="/product" className="kw-link">See how it works &rarr;</Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pt-16 sm:px-8 sm:pt-24">
        <figure>
          <ControlPlaneFigure />
          <figcaption className="kw-figcap mt-3">
            FIG 0.1 — Keelway control plane, sample render. Sealed receipts in green, P-10 gate in brass.
          </figcaption>
        </figure>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
        <div className="grid gap-10 border-t border-[var(--rule)] pt-12 sm:grid-cols-3">
          {PRINCIPLES.map((p) => (
            <div key={p.label}>
              <p className={`kw-label ${p.accent ? "kw-label-brass" : ""}`}>{p.label}</p>
              <p className="mt-4 text-[15px] leading-relaxed text-[var(--muted)]">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="install" className="kw-rule">
        <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
          <h2 className="kw-h2">One line to a running system.</h2>
          <div className="kw-card kw-data mt-8 max-w-2xl overflow-x-auto p-5 text-[var(--ink)]">
            <span className="text-[var(--dim)]">$ </span>curl -fsSL https://kora-sable.vercel.app/install.sh | sh &amp;&amp; keelway dev
          </div>
          <p className="kw-small mt-5">
            Apache-2.0 open core &middot; works fully offline &middot; BYOM and Pro tiers add governed frontier routing.
          </p>
        </div>
      </section>
    </>
  );
}
