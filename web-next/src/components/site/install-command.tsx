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
    <div className="mt-8 flex max-w-2xl items-center gap-4 overflow-x-auto rounded-md border border-border bg-surface p-4 font-mono text-[12px] text-fg">
      <span className="flex-1 whitespace-nowrap">
        <span className="text-fg-muted">$ </span>
        {CMD}
      </span>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 rounded-sm border border-border-strong px-2.5 py-1 font-mono text-[11px] text-fg-muted transition-colors hover:bg-surface hover:text-fg"
        aria-label="Copy install command"
      >
        {copied ? <span className="text-ok">✓ copied</span> : "copy"}
      </button>
    </div>
  );
}
