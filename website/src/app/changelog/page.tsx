import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, Tag } from "lucide-react";
import { RELEASES } from "@/data/releases";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Changelog & Release Notes",
  description:
    "Keelway release history — new platform capabilities, security hardening, SDK parity, and governance features per version.",
  alternates: {
    canonical: "/changelog",
  },
  openGraph: {
    title: "Changelog & Release Notes · Keelway",
    description:
      "Keelway release history — platform capabilities, security hardening, and tri-SDK parity per version.",
    url: `${SITE_URL}/changelog`,
  },
};

/**
 * Changelog & Release Notes (/changelog) — renders repository CHANGELOG data.
 */
export default function ChangelogPage() {
  return (
    <div>
      <section
        aria-labelledby="changelog-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
            <span
              className="h-2 w-2 rounded-full bg-teal-accent"
              aria-hidden="true"
            />
            <span className="font-semibold text-fg">RELEASE HISTORY</span>
            <span className="text-fg-dim">·</span>
            <span className="text-fg-muted">Keep a Changelog · SemVer</span>
          </div>
          <h1
            id="changelog-heading"
            className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
          >
            Changelog &amp; <span className="text-teal-accent">Release Notes</span>
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-fg-muted sm:text-lg">
            Every Keelway release, synced with the repository&apos;s{" "}
            <code className="rounded-sm border border-border-subtle bg-canvas px-1.5 py-0.5 font-mono text-[0.85em]">
              CHANGELOG.md
            </code>{" "}
            (Keep a Changelog + SemVer).
          </p>
        </div>
      </section>

      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-3xl space-y-10 px-4 sm:px-6">
          {RELEASES.map((release) => (
            <article
              key={release.version}
              className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-8"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-4">
                <div className="flex items-center gap-2.5">
                  <Tag
                    className="h-4 w-4 text-teal-accent"
                    aria-hidden="true"
                  />
                  <h2 className="font-mono text-xl font-bold text-fg">
                    v{release.version}
                  </h2>
                  <span
                    className={
                      release.tag === "latest"
                        ? "rounded-sm border border-teal-accent bg-teal-surface px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-teal-accent"
                        : "rounded-sm border border-border-strong bg-canvas px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-fg-muted"
                    }
                  >
                    {release.tag}
                  </span>
                </div>
                <time
                  dateTime={release.date}
                  className="font-mono text-xs text-fg-muted"
                >
                  {release.date}
                </time>
              </div>
              <ul className="mt-4 space-y-2.5">
                {release.highlights.map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-2.5 text-sm leading-relaxed text-fg-muted"
                  >
                    <span
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-accent"
                      aria-hidden="true"
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}

          <div className="rounded-md border border-border-subtle bg-canvas p-5 font-mono text-xs text-fg-muted">
            <p>
              Install or upgrade:{" "}
              <code className="text-fg">
                curl -fsSL {SITE_URL}/install.sh | sh
              </code>
            </p>
            <p className="mt-2">
              <Link
                href="/docs"
                className="inline-flex items-center gap-1 text-teal-accent hover:underline"
              >
                <span>Docs &amp; getting started</span>
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
