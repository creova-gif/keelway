"use client";

import React, { useState } from "react";
import Link from "next/link";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, Copy, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

interface SnippetTab {
  id: string;
  label: string;
  filename: string;
  code: string;
}

const SNIPPETS: SnippetTab[] = [
  {
    id: "cli",
    label: "Local Studio & CLI",
    filename: "terminal — zsh",
    code: `git clone https://github.com/creova-gif/kora.git
cd kora && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Launch Keelway Studio (127.0.0.1:7420) or Hybrid API (127.0.0.1:8000)
python3 cli.py dev
python3 cli.py opencore --status`,
  },
  {
    id: "python",
    label: "Python SDK v1",
    filename: "hybrid_agent.py",
    code: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_dev")

# Zero-egress local OpenCore execution with 4D routing provenance
res = client.responses.create(
    model="keelway-core:7b",
    input="Audit src/billing/retry.py for integer rounding bugs.",
    privacy="private",
)
print(res.output_text, res.provenance.data_boundary)`,
  },
  {
    id: "openai",
    label: "OpenAI Drop-In",
    filename: "openai_compat.py",
    code: `from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="kw_live_dev",
)

chat = client.chat.completions.create(
    model="gemini-3.5-flash-lite",
    messages=[{"role": "user", "content": "Compare QLoRA rank 16 vs 32."}],
)
print(chat.choices[0].message.content)`,
  },
  {
    id: "install",
    label: "1-Line Installer",
    filename: "install.sh",
    code: `curl -fsSL https://kora-sable.vercel.app/install.sh | sh
keelway doctor
keelway swarm --workers 8 --task "Run security regression audit"`,
  },
];

/**
 * 60-Second Multi-Surface Quickstart Terminal with accessible clipboard copy.
 */
export function QuickstartTerminal() {
  const [activeTab, setActiveTab] = useState<string>("cli");
  const [copied, setCopied] = useState<boolean>(false);

  const current = SNIPPETS.find((s) => s.id === activeTab) ?? SNIPPETS[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(current.code);
      setCopied(true);
      trackEvent("code_snippet_copied", { tab: activeTab });
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback ignored if clipboard blocked
    }
  };

  return (
    <section
      id="quickstart"
      aria-labelledby="quickstart-heading"
      className="border-t border-border-subtle py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              04 // 5-MINUTE QUICKSTART
            </p>
            <h2
              id="quickstart-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Start locally in 60 seconds. Scale to governed hybrid fleets when
              ready.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              No mandatory cloud account, no vendor lock-in, and zero telemetry
              behind your back. Pull an Apache-2.0 OpenCore weight manifest onto
              Apple Silicon or CUDA, or connect Gemini, OpenAI, and Anthropic
              through the exact same typed SDK.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/docs" className="kw-btn kw-btn-primary">
                <span>Read Full Documentation</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/api-reference" className="kw-btn kw-btn-secondary">
                <span>Explore 183 API Endpoints</span>
              </Link>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="frame-crosshair overflow-hidden rounded-lg border border-border-strong bg-surface shadow-xl">
              <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle bg-surface-elevated/80 px-3 py-2">
                  <Tabs.List
                    aria-label="Quickstart code surfaces"
                    className="flex flex-wrap gap-1"
                  >
                    {SNIPPETS.map((tab) => (
                      <Tabs.Trigger
                        key={tab.id}
                        value={tab.id}
                        className={cn(
                          "min-h-[40px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors duration-150",
                          activeTab === tab.id
                            ? "bg-canvas text-teal-accent border border-border-strong"
                            : "text-fg-muted hover:text-fg"
                        )}
                      >
                        {tab.label}
                      </Tabs.Trigger>
                    ))}
                  </Tabs.List>

                  <button
                    type="button"
                    onClick={handleCopy}
                    aria-label={`Copy ${current.label} code snippet`}
                    className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-3 font-mono text-xs font-medium text-fg transition-colors duration-150 hover:border-teal-accent hover:text-teal-accent"
                  >
                    {copied ? (
                      <>
                        <Check
                          className="h-3.5 w-3.5 text-teal-accent"
                          aria-hidden="true"
                        />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="border-b border-border-subtle bg-canvas/60 px-4 py-1.5 font-mono text-[11px] text-fg-dim">
                  {current.filename}
                </div>

                {SNIPPETS.map((tab) => (
                  <Tabs.Content
                    key={tab.id}
                    value={tab.id}
                    className="focus:outline-none"
                  >
                    <pre className="overflow-x-auto bg-canvas p-5 font-mono text-xs leading-relaxed text-fg">
                      <code>{tab.code}</code>
                    </pre>
                  </Tabs.Content>
                ))}
              </Tabs.Root>
              <span className="sr-only" aria-live="polite">
                {copied ? `${current.label} snippet copied to clipboard.` : ""}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
