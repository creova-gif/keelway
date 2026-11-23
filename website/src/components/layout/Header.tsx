"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { Mark } from "@/components/site/Mark";

const NAV = [
  { href: "/product", label: "Product" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
  { href: "/changelog", label: "Changelog" },
  { href: "/about", label: "About" },
];

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--rule)] bg-[rgba(8,9,10,0.85)] backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link href="/" className="kw-link flex items-center gap-2.5 text-[var(--ink)]" aria-label="K′ Keelway home">
          <Mark />
          <span className="text-[15px] font-bold tracking-tight">Keelway</span>
        </Link>
        <nav className="hidden items-center gap-7 md:flex" aria-label="Primary">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="kw-navlink"
              data-active={pathname.startsWith(item.href) ? "true" : undefined}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-5 md:flex">
          <Link href="/sign-in" className="kw-navlink">Sign in</Link>
          <Link href="/#install" className="kw-btn kw-btn-primary">Install Keelway</Link>
        </div>
        <button
          type="button"
          className="kw-link md:hidden"
          aria-expanded={open}
          aria-label="Toggle navigation"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <X size={20} strokeWidth={1.5} aria-hidden="true" />
          ) : (
            <Menu size={20} strokeWidth={1.5} aria-hidden="true" />
          )}
        </button>
      </div>
      {open && (
        <nav className="border-t border-[var(--rule)] px-5 py-4 md:hidden" aria-label="Mobile">
          <div className="flex flex-col gap-4 text-sm">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="kw-navlink text-[var(--ink)]" onClick={() => setOpen(false)}>
                {item.label}
              </Link>
            ))}
            <Link href="/sign-in" className="kw-navlink" onClick={() => setOpen(false)}>Sign in</Link>
            <Link href="/#install" className="kw-btn kw-btn-primary mt-1" onClick={() => setOpen(false)}>
              Install Keelway
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
