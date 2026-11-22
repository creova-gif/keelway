import type { Metadata } from "next";
import { RELEASES } from "@/data/releases";
import { Reveal } from "@/components/motion/reveal";

export const metadata: Metadata = {
  title: "Changelog — Keelway",
  description: "The logbook, public. Every Keelway release, sealed and dated.",
};

export default function ChangelogPage() {
  return (
    <main className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Changelog</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-fg">The logbook, public.</h1>
      <div className="mt-14 border-t border-border">
        {RELEASES.map((r) => (
          <Reveal key={r.version}>
          <article className="border-b border-border py-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="text-lg font-semibold tracking-tight text-fg">v{r.version}</h2>
              <p className="font-mono text-[11px] text-fg-muted">{r.date}</p>
            </div>
            <ul className="mt-4 space-y-2 text-[14px] leading-relaxed text-fg-muted">
              {r.highlights.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </article>
          </Reveal>
        ))}
      </div>
    </main>
  );
}
