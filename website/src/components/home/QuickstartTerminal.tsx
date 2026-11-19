"use client";

import React, { useState } from "react";
import Link from "next/link";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, Copy, ArrowRight, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";
import type { QuickstartCliVariant } from "@/flags";

interface SnippetTab {
  id: string;
  label: string;
  filename: string;
  code: string;
}

const SNIPPETS: SnippetTab[] = [
  {
    id: "tui",
    label: "Interactive CLI Boot",
    filename: "keelway — Sovereign TUI",
    code: `curl -fsSL https://kora-sable.vercel.app/install.sh | sh
keelway init && keelway dev`,
  },
  {
    id: "cli",
    label: "Local Studio & CLI",
    filename: "terminal — zsh",
    code: `# Install Keelway CLI & OpenCore local runtime (macOS / Linux)
curl -fsSL https://kora-sable.vercel.app/install.sh | sh

# Initialize your project & open the 10-View Workspace (127.0.0.1:7420/app)
keelway init
keelway dev`,
  },
  {
    id: "python",
    label: "Python & TS SDKs",
    filename: "hybrid_agent.ts",
    code: `import { KeelwayClient } from "@keelway/sdk";

const client = new KeelwayClient({
  baseUrl: "http://127.0.0.1:8000",
  apiKey: "kw_live_dev",
});

// Zero-egress local OpenCore execution with 4D routing provenance
const res = await client.responses.create({
  model: "keelway-core:7b",
  input: "Audit src/billing/retry.py for integer rounding bugs.",
  privacy_level: "private",
});
console.log(res.output_text);`,
  },
  {
    id: "go",
    label: "Go SDK",
    filename: "main.go",
    code: `package main

import (
	"context"
	"fmt"
	"github.com/keelway/keelway-go"
)

func main() {
	client := keelway.NewClient("http://127.0.0.1:8000", keelway.WithAPIKey("kw_live_dev"))
	res, err := client.Responses.Create(context.Background(), keelway.ResponseCreateRequest{
		Model:        "keelway-core:7b",
		Input:        "Audit billing/retry.go for integer rounding bugs.",
		PrivacyLevel: "private",
	})
	if err != nil {
		panic(err)
	}
	fmt.Println(res.OutputText)
}`,
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
];

const TUI_SLASH_OUTPUTS: Record<string, string[]> = {
  boot: [
    "  [✓] Workspace bound: ~/projects/payments-api (git: main)",
    "  [✓] OS Sandbox verified: macOS Seatbelt · P-10 Human Gate armed",
    "  [✓] Local OpenCore online: keelway-core:7b (Apple Metal · 0 B egress)",
    "  Tip: Click a slash command below or run `keelway dev` to open /app.",
  ],
  "/model": [
    "  ▸ Active: keelway-core:7b (Apache-2.0 · Local Metal · $0.00/1M)",
    "    Available Frontier: gemini-3.5-flash-lite · claude-sonnet-4-6 · gpt-5.4-mini",
    "    Note: Switching models pauses standing Allow-always rules for re-confirm.",
  ],
  "/airgap": [
    "  [LOCKED] Sovereign Air-Gap Mode: ENABLED (NIST SP 800-53 SC-7)",
    "  Outbound cloud sockets blocked at gateway · Local loopback 127.0.0.1 only.",
  ],
  "/audit": [
    "  [✓] SQLite WAL Flight Chain verified: 1,285 entries intact",
    "  Latest root: sha256:f91a83e54b20c67d · 0 tamper mismatches.",
  ],
  "keelway dev": [
    "  [+] Starting Keelway Unified Sovereign Dev App on http://127.0.0.1:7420/app",
    "  [+] CSP: default-src 'self'; script-src 'self' · Opening workbench...",
  ],
};

interface QuickstartTerminalProps {
  variant?: QuickstartCliVariant;
}

/**
 * 60-Second Multi-Surface Quickstart Terminal supporting `exp-quickstart-cli-v1`:
 * - `code-tabs-default` (Control): defaults to copyable `Local Studio & CLI` snippet
 * - `interactive-tui-boot` (Treatment): defaults to Claude-Code-style boxed `KEELWAY` TUI boot
 */
export function QuickstartTerminal({
  variant = "code-tabs-default",
}: QuickstartTerminalProps) {
  const defaultTab = variant === "interactive-tui-boot" ? "tui" : "cli";
  const [activeTab, setActiveTab] = useState<string>(defaultTab);
  const [tuiCmd, setTuiCmd] = useState<string>("boot");
  const [copied, setCopied] = useState<boolean>(false);

  const visibleSnippets =
    variant === "interactive-tui-boot"
      ? SNIPPETS
      : SNIPPETS.filter((s) => s.id !== "tui");

  const current =
    visibleSnippets.find((s) => s.id === activeTab) ?? visibleSnippets[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(current.code);
      setCopied(true);
      trackEvent("code_snippet_copied", {
        tab: activeTab,
        quickstart_variant: variant,
      });
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback ignored if clipboard blocked
    }
  };

  return (
    <section
      id="quickstart"
      aria-labelledby="quickstart-heading"
      data-experiment-key="exp-quickstart-cli-v1"
      data-experiment-variant={variant}
      data-theme="dark" className="border-t border-border-subtle bg-canvas text-fg py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              QUICKSTART FOR DEVELOPERS &amp; TEAMS
            </p>
            <h2
              id="quickstart-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              Start locally in 60 seconds. Connect cloud APIs when you choose.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              No mandatory cloud account, no vendor lock-in, and zero hidden
              telemetry. Run local OpenCore models free on Apple Silicon or CUDA,
              or bring your own OpenAI, Anthropic, and Gemini API keys with 0%
              token markup.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/docs" className="kw-btn kw-btn-primary">
                <span>Read Documentation</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/api-reference" className="kw-btn kw-btn-secondary">
                <span>Explore 200+ API Endpoints</span>
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
                    {visibleSnippets.map((tab) => (
                      <Tabs.Trigger
                        key={tab.id}
                        value={tab.id}
                        className={cn(
                          "min-h-[40px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors duration-150",
                          activeTab === tab.id
                            ? "border border-border-strong bg-canvas text-teal-accent"
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

                {visibleSnippets.map((tab) => (
                  <Tabs.Content
                    key={tab.id}
                    value={tab.id}
                    className="bg-canvas p-4 focus:outline-none"
                  >
                    {tab.id === "tui" ? (
                      <div className="space-y-3 font-mono text-xs">
                        <div className="overflow-x-auto rounded-md border border-teal-accent/40 bg-surface/60 p-3.5 leading-[1.35]">
                          <div className="text-fg-dim">
                            ╭─── <span className="font-bold text-teal-accent">Keelway v1.1</span> · Sovereign Local-First AI Platform ───╮
                          </div>
                          <pre className="mt-2 select-none text-[10px] leading-[1.15] text-teal-accent sm:text-[11px]">
{`  ██╗  ██╗███████╗███████╗██╗     ██╗    ██╗ █████╗ ██╗   ██╗
  ██║ ██╔╝██╔════╝██╔════╝██║     ██║    ██║██╔══██╗╚██╗ ██╔╝
  █████╔╝ █████╗  █████╗  ██║     ██║ █╗ ██║███████║ ╚████╔╝ 
  ██╔═██╗ ██╔══╝  ██╔══╝  ██║     ██║███╗██║██╔══██║  ╚██╔╝  
  ██║  ██╗███████╗███████╗███████╗╚███╔███╔╝██║  ██║   ██║   
  ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝   `}
                          </pre>
                          <div className="mt-2.5 grid grid-cols-1 gap-1 border-t border-border-subtle pt-2 text-[11px] text-fg-muted sm:grid-cols-2">
                            <div>
                              Workspace:{" "}
                              <span className="text-fg">~/payments-api (main)</span>
                            </div>
                            <div>
                              Runtime:{" "}
                              <span className="text-teal-accent">
                                OpenCore · keelway-core:7b
                              </span>
                            </div>
                            <div>
                              Sandbox:{" "}
                              <span className="text-fg">Seatbelt (verified)</span>
                            </div>
                            <div>
                              Egress:{" "}
                              <span className="text-teal-accent">
                                Air-Gap Ready · 0 B
                              </span>
                            </div>
                          </div>
                          <div className="mt-2 text-fg-dim">
                            ╰──────────────────────── Sorvex Labs • https://keelway.dev ──╯
                          </div>
                        </div>

                        {/* Interactive Slash Command Simulator */}
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="inline-flex items-center gap-1 text-[11px] text-fg-muted">
                            <Terminal className="h-3 w-3 text-teal-accent" aria-hidden="true" />
                            Try CLI command:
                          </span>
                          {(["/model", "/airgap", "/audit", "keelway dev"] as const).map(
                            (cmd) => (
                              <button
                                key={cmd}
                                type="button"
                                onClick={() => {
                                  setTuiCmd(cmd);
                                  trackEvent("cli_tui_command_simulated", {
                                    command: cmd,
                                  });
                                }}
                                className={cn(
                                  "rounded-sm border px-2 py-1 text-[11px] transition-colors",
                                  tuiCmd === cmd
                                    ? "border-teal-accent bg-teal-accent/10 text-teal-accent"
                                    : "border-border-strong bg-surface text-fg-muted hover:text-fg"
                                )}
                              >
                                {cmd}
                              </button>
                            )
                          )}
                        </div>

                        <div className="rounded-sm border border-border-subtle bg-surface/50 p-3 text-[11px] leading-relaxed text-fg">
                          {(TUI_SLASH_OUTPUTS[tuiCmd] ?? TUI_SLASH_OUTPUTS.boot).map(
                            (line) => (
                              <div key={line}>{line}</div>
                            )
                          )}
                        </div>
                      </div>
                    ) : (
                      <pre className="overflow-x-auto font-mono text-xs leading-6 text-fg">
                        <code>{tab.code}</code>
                      </pre>
                    )}
                  </Tabs.Content>
                ))}
              </Tabs.Root>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
