import Link from "next/link";

export function Footer() {
  return (
    <footer className="kw-rule">
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="kw-label">Keelway</p>
            <p className="kw-data mt-3 max-w-md text-[var(--muted)]">
              Apache-2.0 open core &middot; BYOM from $15/seat/mo &middot; Pro from $29/seat/mo &middot; 0% token markup
            </p>
            <p className="kw-data mt-4 text-[10px] text-[var(--dim)]">A Sorvex Labs company.</p>
          </div>
          <nav className="flex gap-6 text-[13px]" aria-label="Footer">
            <Link href="/product" className="kw-navlink">Product</Link>
            <Link href="/pricing" className="kw-navlink">Pricing</Link>
            <Link href="/changelog" className="kw-navlink">Changelog</Link>
            <Link href="/contact" className="kw-navlink">Contact</Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
