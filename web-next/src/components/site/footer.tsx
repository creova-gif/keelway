import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Keelway</p>
            <p className="mt-3 max-w-md font-mono text-[11px] leading-5 text-fg-muted">
              Apache-2.0 open core &middot; BYOM from $15/seat/mo &middot; Pro from
              $29/seat/mo &middot; 0% token markup
            </p>
            <p className="mt-4 font-mono text-[10px] text-fg-muted">A Sorvex Labs company.</p>
          </div>
          <nav className="flex gap-6 text-[13px]" aria-label="Footer">
            <Link href="/product" className="text-fg-muted transition-colors hover:text-fg">
              Product
            </Link>
            <Link href="/pricing" className="text-fg-muted transition-colors hover:text-fg">
              Pricing
            </Link>
            <Link href="/changelog" className="text-fg-muted transition-colors hover:text-fg">
              Changelog
            </Link>
            <Link href="/contact" className="text-fg-muted transition-colors hover:text-fg">
              Contact
            </Link>
            <Link href="/docs" className="text-fg-muted transition-colors hover:text-fg">
              Docs
            </Link>
            <a
              href="https://github.com/creova-gif/keelway"
              target="_blank"
              rel="noopener"
              className="text-fg-muted transition-colors hover:text-fg"
            >
              GitHub
            </a>
          </nav>
        </div>
      </div>
    </footer>
  );
}
