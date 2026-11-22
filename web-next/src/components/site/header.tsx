"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Mark } from "@/components/site/mark";

const REPO_URL = "https://github.com/creova-gif/keelway";

const NAV = [
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const linkClass = (href: string) =>
    `text-[13px] transition-colors hover:text-fg ${
      pathname.startsWith(href) ? "text-fg" : "text-fg-muted"
    }`;

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-canvas/85 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="flex items-center gap-2.5 text-fg" aria-label="K′ Keelway home">
          <Mark />
          <span className="text-[15px] font-bold tracking-tight">Keelway</span>
        </Link>
        <nav className="hidden items-center gap-7 md:flex" aria-label="Primary">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={linkClass(item.href)}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener"
            className="text-[13px] text-fg-muted transition-colors hover:text-fg"
          >
            GitHub
          </a>
        </nav>
        <button
          type="button"
          className="text-fg md:hidden"
          aria-expanded={open}
          aria-label="Toggle navigation"
          onClick={() => setOpen((v) => !v)}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            {open ? <path d="M5 5l10 10M15 5L5 15" /> : <path d="M3 6h14M3 10h14M3 14h14" />}
          </svg>
        </button>
      </div>
      {open && (
        <nav className="border-t border-border px-5 py-4 md:hidden" aria-label="Mobile">
          <div className="flex flex-col gap-4 text-sm">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-fg"
                aria-current={pathname.startsWith(item.href) ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <a href={REPO_URL} target="_blank" rel="noopener" className="text-fg">
              GitHub
            </a>
          </div>
        </nav>
      )}
    </header>
  );
}
