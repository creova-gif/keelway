import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-5 py-24 sm:px-8">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">
        ERR 404 — off the chart
      </p>
      <h1 className="mt-6 max-w-2xl text-5xl font-semibold tracking-tight text-fg sm:text-6xl">
        This page isn&rsquo;t on the tape.
      </h1>
      <p className="mt-6 max-w-md text-base leading-7 text-fg-muted">
        The route you asked for has no receipt. Check the URL, or head back to
        the bridge.
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-5">
        <Button asChild>
          <Link href="/">Back to bridge</Link>
        </Button>
        <Link href="/docs" className="text-sm text-fg-muted transition-colors hover:text-fg">
          Search docs →
        </Link>
      </div>
      <p className="mt-16 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
        trace: — · client-side 404, nothing logged
      </p>
    </main>
  );
}
