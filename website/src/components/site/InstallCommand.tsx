"use client";

import { useState } from "react";

const CMD = "curl -fsSL https://kora-sable.vercel.app/install.sh | sh && keelway dev";

export function InstallCommand() {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(CMD);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="kw-card kw-data mt-8 flex max-w-2xl items-center gap-4 overflow-x-auto p-5 text-[var(--ink)]">
      <span className="flex-1 whitespace-nowrap">
        <span className="text-[var(--dim)]">$ </span>
        {CMD}
      </span>
      <button
        type="button"
        onClick={copy}
        className="kw-fig-btn shrink-0 border border-[var(--rule-strong)] text-[var(--muted)] hover:bg-[var(--fog-8)] hover:text-[var(--ink)]"
        aria-label="Copy install command"
      >
        {copied ? <span className="text-[var(--green)]">✓ copied</span> : "copy"}
      </button>
    </div>
  );
}
