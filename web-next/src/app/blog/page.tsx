import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Blog — Keelway",
  description: "Field notes on sovereign agent infrastructure — governance, receipts, and honest economics.",
};

const NOTES = [
  {
    tag: "Release",
    title: "1.1.0 — Golden-Thread Studio",
    excerpt:
      "Browser-native LangGraph → KFlow conversion, bidirectional codegen, and a flight-tape waterfall you can scrub like a timeline.",
    href: "/changelog",
  },
  {
    tag: "Release",
    title: "1.0.0 — The Sovereign Dev Tool",
    excerpt:
      "Ten views, one gate. KFlow DAGs with per-run budgets, P-10 pause gates, KSpaces CRDT sync, and a signed receipt for every action.",
    href: "/changelog",
  },
  {
    tag: "Product",
    title: "The tape is the audit",
    excerpt:
      "A hash-chained Merkle flight recorder turns every read, edit, route, and gate into a signed receipt — verifiable offline.",
    href: "/product",
  },
  {
    tag: "Economics",
    title: "0% markup, per-seat",
    excerpt:
      "You pay providers at their published rate card; we bill per seat. The pricing model is a contract, not a margin.",
    href: "/pricing",
  },
  {
    tag: "Principles",
    title: "Denials are receipts too",
    excerpt:
      "A governance system that only records approvals is a rubber stamp. Keelway seals denials onto the same tape — nothing fails silently.",
    href: "/about",
  },
] as const;

export default function BlogPage() {
  return (
    <main className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Blog</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-fg">Field notes.</h1>
      <p className="mt-6 max-w-2xl text-sm leading-6 text-fg-muted">
        Short notes on building sovereign agent infrastructure. The engineering
        log lives in the{" "}
        <Link href="/changelog" className="text-fg underline underline-offset-2">
          changelog
        </Link>
        .
      </p>
      <div className="mt-14 border-t border-border">
        {NOTES.map((note) => (
          <Link
            key={note.title}
            href={note.href}
            className="group flex flex-col gap-2 border-b border-border py-7 sm:flex-row sm:gap-10"
          >
            <p className="w-24 shrink-0 pt-1 font-mono text-[11px] uppercase tracking-wide text-fg-muted">
              {note.tag}
            </p>
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-fg transition-colors group-hover:text-accent">
                {note.title}
              </h2>
              <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-fg-muted">{note.excerpt}</p>
            </div>
          </Link>
        ))}
      </div>
      <p className="mt-14 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
        releases on the tape — <Link href="/feed.xml" className="underline underline-offset-2">rss</Link>
      </p>
    </main>
  );
}
