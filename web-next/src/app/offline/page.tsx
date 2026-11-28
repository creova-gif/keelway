import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Offline — Keelway",
  description: "Keelway offline fallback — cached routes remain readable when the network drops.",
  alternates: { canonical: "/offline" },
};

export default function OfflinePage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-5 py-24 sm:px-8">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">
        OFFLINE — read only
      </p>
      <h1 className="mt-6 max-w-2xl text-5xl font-semibold tracking-tight text-fg sm:text-6xl">
        You&rsquo;re off the wire.
      </h1>
      <p className="mt-6 max-w-md text-base leading-7 text-fg-muted">
        The network dropped before this page loaded. Anything your browser
        already cached still works; live routes wait for the signal.
      </p>
      <p className="mt-4 max-w-md text-base leading-7 text-fg-muted">
        The self-hosted core doesn&rsquo;t — the workspace, tape, and ledger run
        fully offline on your machine.
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-5">
        <Button asChild>
          <Link href="/">Retry the bridge</Link>
        </Button>
        <Link href="/product" className="text-sm text-fg-muted transition-colors hover:text-fg">
          Run it locally →
        </Link>
      </div>
      <p className="mt-16 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
        signal: lost · cache: holding
      </p>
    </main>
  );
}
