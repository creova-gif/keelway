"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { Mark } from "@/components/site/mark";

const REPO_URL = "https://github.com/creova-gif/keelway";

const NAV = [
  { href: "/product", label: "Product" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
  { href: "/changelog", label: "Changelog" },
  { href: "/about", label: "About" },
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
          <span className="text-[15px] font-[640] tracking-tight">Keelway</span>
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
          <Link href="/sign-in" className={linkClass("/sign-in")}>
            Sign in
          </Link>
        </nav>
        <button
          type="button"
          className="-mr-3 flex h-[44px] w-[44px] items-center justify-center text-fg md:hidden"
          aria-expanded={open}
          aria-label="Toggle navigation"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={20} strokeWidth={1.5} aria-hidden="true" /> : <Menu size={20} strokeWidth={1.5} aria-hidden="true" />}
        </button>
      </div>
      {open && (
        <nav className="border-t border-border px-5 py-4 md:hidden" aria-label="Mobile">
          <div className="flex flex-col gap-4 text-sm">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="-my-1 flex min-h-[44px] items-center text-fg"
                aria-current={pathname.startsWith(item.href) ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <a href={REPO_URL} target="_blank" rel="noopener" className="-my-1 flex min-h-[44px] items-center text-fg">
              GitHub
            </a>
            <Link href="/sign-in" className="-my-1 flex min-h-[44px] items-center text-fg" onClick={() => setOpen(false)}>
              Sign in
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
