import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-28 sm:px-8">
      <p className="kw-label text-[var(--red)]">ERR 404 — off the chart</p>
      <h1 className="kw-h1 mt-5">This page isn&apos;t on the tape.</h1>
      <p className="kw-body mt-5 max-w-md">
        The route you asked for has no receipt. Check the URL, or head back to the bridge.
      </p>
      <div className="mt-9 flex items-center gap-5">
        <Link href="/" className="kw-btn kw-btn-primary">Back to bridge</Link>
        <Link href="/changelog" className="kw-link">Changelog &rarr;</Link>
      </div>
      <p className="kw-data mt-16 text-[var(--dim)]">trace: 4f2a-99c1 &middot; logged &amp; sealed</p>
    </div>
  );
}
