import type { Metadata } from "next";
import { RELEASES } from "@/data/releases";

export const metadata: Metadata = {
  title: "Changelog",
  description: "The logbook, public. Every Keelway release, sealed and dated.",
};

export default function ChangelogPage() {
  return (
    <div className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="kw-label">Changelog</p>
      <h1 className="kw-h1 mt-5">The logbook, public.</h1>
      <div className="mt-14 border-t border-[var(--rule)]">
        {RELEASES.map((r) => (
          <article key={r.version} className="kw-row-hover border-b border-[var(--rule)] py-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="kw-h3">v{r.version}</h2>
              <p className="kw-data text-[var(--dim)]">{r.date}</p>
            </div>
            <ul className="mt-4 space-y-2 text-[14px] leading-relaxed text-[var(--muted)]">
              {r.highlights.map((h) => <li key={h}>{h}</li>)}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
