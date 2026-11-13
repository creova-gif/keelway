"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { trackEvent } from "@/lib/analytics";

interface DocSectionLink {
  id: string;
  label: string;
}

const DOC_SECTIONS: DocSectionLink[] = [
  { id: "quickstart", label: "1. 5-Minute Quickstart" },
  { id: "surfaces", label: "2. Operational Surfaces" },
  { id: "opencore", label: "3. OpenCore & QLoRA Weights" },
  { id: "routing", label: "4. Unified API & 4D Routing" },
  { id: "approval-loop", label: "5. Approval Gate & Audit Ledger" },
  { id: "status", label: "6. Verified v1 vs. Roadmap" },
];

function CodePanel({
  id,
  title,
  code,
}: {
  id: string;
  title: string;
  code: string;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      trackEvent("code_snippet_copied", { tab: id });
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Ignore clipboard failures
    }
  };

  return (
    <div className="my-4 overflow-hidden rounded-md border border-border-strong bg-canvas">
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated/70 px-3.5 py-2">
        <span className="font-mono text-xs text-fg-muted">{title}</span>
        <button
          type="button"
          onClick={onCopy}
          aria-label={`Copy ${title}`}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-2.5 font-mono text-xs text-fg hover:border-teal-accent hover:text-teal-accent"
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
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-fg">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/**
 * Interactive Developer Documentation Hub (/docs)
 * Sticky sidebar on desktop + horizontal section jump bar on mobile/tablet,
 * runnable examples, and an honest v1 Verified Capabilities vs. Roadmap table.
 */
export function DocsHub() {
  return (
    <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
      {/* Mobile / Tablet Quick-Jump Bar */}
      <nav
        aria-label="Documentation sections mobile jump bar"
        className="flex gap-2 overflow-x-auto rounded-md border border-border-strong bg-surface p-2 lg:hidden"
      >
        {DOC_SECTIONS.map((sec) => (
          <a
            key={sec.id}
            href={`#${sec.id}`}
            onClick={() =>
              trackEvent("docs_section_jumped", { section: sec.id })
            }
            className="inline-flex min-h-[40px] shrink-0 items-center rounded-sm px-3 font-mono text-xs text-fg-muted hover:bg-surface-elevated hover:text-teal-accent"
          >
            {sec.label}
          </a>
        ))}
      </nav>

      {/* Desktop Sticky Sidebar */}
      <aside className="hidden lg:col-span-3 lg:block">
        <div className="sticky top-28 space-y-6 rounded-lg border border-border-strong bg-surface p-5">
          <div>
            <div className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-teal-accent">
              <BookOpen className="h-4 w-4" aria-hidden="true" />
              <span>On This Page</span>
            </div>
            <nav aria-label="Documentation table of contents" className="mt-3 space-y-1">
              {DOC_SECTIONS.map((sec) => (
                <a
                  key={sec.id}
                  href={`#${sec.id}`}
                  onClick={() =>
                    trackEvent("docs_section_jumped", { section: sec.id })
                  }
                  className="flex min-h-[40px] items-center rounded-sm px-2.5 text-xs font-medium text-fg-muted transition-colors duration-150 hover:bg-surface-elevated hover:text-teal-accent"
                >
                  {sec.label}
                </a>
              ))}
            </nav>
          </div>

          <div className="border-t border-border-subtle pt-4">
            <p className="font-mono text-[11px] text-fg-muted">
              Looking for endpoint schemas &amp; status codes?
            </p>
            <Link
              href="/api-reference"
              className="kw-btn kw-btn-secondary mt-2.5 w-full font-mono text-xs"
            >
              <span>Open API Reference</span>
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          </div>
        </div>
      </aside>

      {/* Main Technical Documentation Prose */}
      <article className="space-y-14 lg:col-span-9">
        {/* 1. 5-Minute Quickstart */}
        <section id="quickstart" aria-labelledby="doc-qs-h" className="scroll-mt-28">
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5">
            SECTION 01
          </span>
          <h2 id="doc-qs-h" className="mt-2 text-2xl font-bold text-fg">
            Getting Started in 5 Minutes
          </h2>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
            Clone the Apache-2.0 repository and launch locally — no hosted
            account, no proprietary package registry, and zero forced cloud
            telemetry.
          </p>

          <CodePanel
            id="docs-quickstart-bash"
            title="bash — local setup & verification"
            code={`git clone https://github.com/creova-gif/kora.git
cd kora
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Run all 5 engineering verification stages (167 automated tests)
./scripts/verify_engineering_gates.sh

# 2. Launch Keelway Studio IDE on loopback (http://127.0.0.1:7420)
python3 cli.py dev

# 3. Launch the Unified Hybrid AI & Governance Server (http://127.0.0.1:8000)
make serve`}
          />
        </section>

        {/* 2. The Operational Surfaces */}
        <section
          id="surfaces"
          aria-labelledby="doc-surfaces-h"
          className="scroll-mt-28 border-t border-border-subtle pt-12"
        >
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5">
            SECTION 02
          </span>
          <h2 id="doc-surfaces-h" className="mt-2 text-2xl font-bold text-fg">
            The Four Operational Surfaces
          </h2>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
            Keelway separates day-to-day local developer velocity from shared
            team governance while sharing a single underlying model registry and
            audit format:
          </p>

          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-md border border-border-strong bg-surface p-4">
              <div className="font-mono text-xs font-bold text-teal-accent">
                1. Keelway Studio (127.0.0.1:7420)
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
                Local-first developer IDE launched via{" "}
                <code className="text-fg">python3 cli.py dev</code> with real-time
                external editor sync (VS Code, Cursor, Zed) and interactive diff
                gates.
              </p>
            </div>

            <div className="rounded-md border border-border-strong bg-surface p-4">
              <div className="font-mono text-xs font-bold text-teal-accent">
                2. Hybrid API &amp; Governance Server (:8000)
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
                FastAPI control plane (<code className="text-fg">make serve</code>)
                serving <code className="text-fg">/v1/responses</code>,{" "}
                <code className="text-fg">/v1/chat/completions</code>, 4D routing,
                and tenant spend policies.
              </p>
            </div>

            <div className="rounded-md border border-border-strong bg-surface p-4">
              <div className="font-mono text-xs font-bold text-teal-accent">
                3. 6-Tab Air-Gap Web Console
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
                Zero-CDN governance dashboard bundled with strict CSP headers for
                inspecting models, OpenCore LoRAs, routing receipts, and tenant
                budgets.
              </p>
            </div>

            <div className="rounded-md border border-border-strong bg-surface p-4">
              <div className="font-mono text-xs font-bold text-teal-accent">
                4. Typed Python SDK v1 &amp; CLI
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
                Sync &amp; async <code className="text-fg">KeelwayClient</code>{" "}
                with typed error hierarchy (<code className="text-fg">BudgetExceededError</code>,{" "}
                <code className="text-fg">AirGapEgressError</code>) plus{" "}
                <code className="text-fg">cli.py</code> subcommands.
              </p>
            </div>
          </div>
        </section>

        {/* 3. OpenCore Runtime & Legitimate Weight Acquisition */}
        <section
          id="opencore"
          aria-labelledby="doc-opencore-h"
          className="scroll-mt-28 border-t border-border-subtle pt-12"
        >
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5">
            SECTION 03
          </span>
          <h2 id="doc-opencore-h" className="mt-2 text-2xl font-bold text-fg">
            OpenCore Weights, Modelfile Compiler &amp; QLoRA Verification
          </h2>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
            Model weights and binary GGUF/safetensors checkpoints are{" "}
            <strong className="text-fg">never committed to Git</strong>. Obtain
            permitted weights directly from official registries (Ollama or
            HuggingFace), compile a deterministic Keelway Modelfile, and verify
            any QLoRA adapter&apos;s SHA-256 checksum on disk prior to hot-attach:
          </p>

          <CodePanel
            id="docs-opencore-cli"
            title="bash — legitimate weight pull & Modelfile registration"
            code={`# Pull an Apache-2.0 base checkpoint locally via Ollama
ollama pull qwen2.5-coder:7b

# Inspect local runtime discovery & registered OpenCore manifests
python3 cli.py opencore --status

# Compile a deterministic OpenCore Modelfile and register keelway-coder:7b
python3 cli.py opencore --modelfile keelway-coder:7b > Modelfile.coder
ollama create 'keelway-coder:7b' -f './Modelfile.coder'

# Generate a synthetic domain/multilingual QLoRA adaptation recipe
python3 cli.py opencore --adapt swahili`}
          />
        </section>

        {/* 4. Unified Responses & 4D Routing */}
        <section
          id="routing"
          aria-labelledby="doc-routing-h"
          className="scroll-mt-28 border-t border-border-subtle pt-12"
        >
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5">
            SECTION 04
          </span>
          <h2 id="doc-routing-h" className="mt-2 text-2xl font-bold text-fg">
            Unified Responses API &amp; Deterministic 4D Routing
          </h2>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
            Use <code className="font-mono text-fg">KeelwayClient</code> (sync or{" "}
            <code className="font-mono text-fg">AsyncKeelwayClient</code>) to
            chain multi-turn stateful responses, enforce zero-egress privacy, or
            inspect a 4-dimension routing decision before executing inference:
          </p>

          <CodePanel
            id="docs-python-sdk"
            title="python — stateful responses & 4D routing provenance"
            code={`from core.sdk import KeelwayClient, BudgetExceededError

client = KeelwayClient(
    base_url="http://127.0.0.1:8000",
    api_key="kw_live_7f3a1c_0123456789abcdef0123456789abcdef",
)

# 1. Inspect 4D routing provenance without spending tokens
plan = client.routing.explain(
    prompt="Audit authentication middleware for timing side-channels",
    privacy_level="private",
)
print(plan["selected_model"], plan["provenance"])

# 2. Stateful multi-turn generation with speculative draft acceleration
turn1 = client.responses.create(
    model="keelway-coder:7b",
    input="Write a constant-time HMAC verifier in Python.",
    privacy_level="private",
)
turn2 = client.responses.create(
    previous_response_id=turn1["id"],
    input="Now generate pytest unit tests covering truncated signatures.",
    privacy_level="private",
)`}
          />
        </section>

        {/* 5. The Approval Loop & Hash-Chained Audit */}
        <section
          id="approval-loop"
          aria-labelledby="doc-approval-h"
          className="scroll-mt-28 border-t border-border-subtle pt-12"
        >
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5">
            SECTION 05
          </span>
          <h2 id="doc-approval-h" className="mt-2 text-2xl font-bold text-fg">
            The Approval Loop &amp; Hash-Chained Flight Ledger
          </h2>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
            Under <code className="font-mono text-fg">AutonomyPolicy.CONFIRM_MUTATION</code>,
            an autonomous agent plans its change, computes a unified diff, and
            pauses before touching any file or shell command. You can approve
            once, grant a scoped standing rule for a specific tool and path
            glob, or deny. Every decision — approved, denied, or budget-downgraded —
            is appended to a genesis-anchored SHA-256 chain verifiable via{" "}
            <code className="font-mono text-fg">GET /v1/audit/verify</code> or{" "}
            <code className="font-mono text-fg">FlightPlayer.verify_integrity()</code>.
          </p>
        </section>

        {/* 6. Honest v1 Capabilities vs. Roadmap */}
        <section
          id="status"
          aria-labelledby="doc-status-h"
          className="scroll-mt-28 border-t border-border-subtle pt-12"
        >
          <span className="chip-amber inline-block rounded-sm px-2 py-0.5">
            SECTION 06 · RADICAL TRANSPARENCY
          </span>
          <h2 id="doc-status-h" className="mt-2 text-2xl font-bold text-fg">
            Functioning v1 Capabilities vs. Active Roadmap
          </h2>
          <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
            We distinguish strictly between capabilities verified by automated
            repository tests today and multi-region infrastructure currently in
            staged rollout:
          </p>

          <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
            <div className="rounded-lg border border-teal-accent/50 bg-surface p-5">
              <div className="flex items-center gap-2 font-mono text-xs font-bold text-teal-accent">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <span>VERIFIED TODAY IN REPO (167/167 GATES)</span>
              </div>
              <ul className="mt-3 space-y-2 text-xs leading-relaxed text-fg-muted">
                <li>
                  • Unified <code className="text-fg">/v1/models</code>,{" "}
                  <code className="text-fg">/v1/chat/completions</code>,{" "}
                  <code className="text-fg">/v1/responses</code>, and SSE streaming
                </li>
                <li>
                  • Live Ollama Metal, vLLM OpenAI-compatible bridge, Google
                  Gemini (<code className="text-fg">x-goog-api-key</code>), OpenAI
                  &amp; Anthropic adapters
                </li>
                <li>
                  • OpenCore Modelfile compiler, SHA-256 LoRA registry &amp;
                  speculative lookahead decoding
                </li>
                <li>
                  • Deterministic 4D routing provenance &amp; MiroFish hybrid
                  swarm evaluation harness
                </li>
                <li>
                  • Scoped <code className="text-fg">kw_live_*</code> keys, USD
                  spend caps, secret redaction &amp; hash-chained audit logs
                </li>
              </ul>
            </div>

            <div className="rounded-lg border border-border-strong bg-surface p-5">
              <div className="flex items-center gap-2 font-mono text-xs font-bold text-amber-alert">
                <Clock className="h-4 w-4" aria-hidden="true" />
                <span>IN PROGRESS / EARLY ACCESS ROADMAP</span>
              </div>
              <ul className="mt-3 space-y-2 text-xs leading-relaxed text-fg-muted">
                <li>
                  • Managed multi-region cloud control plane &amp; hosted CRDT
                  team workspace relays
                </li>
                <li>
                  • Turnkey customer-owned VPC Terraform modules for AWS, GCP
                  &amp; African sovereign data centers
                </li>
                <li>
                  • Native TypeScript / Go SDK packages published to npm &amp;
                  pkg.go.dev
                </li>
                <li>
                  • Hardware enclave attestation (Tier-2 HAL) for confidential
                  GPU clusters
                </li>
              </ul>
              <Link
                href="/#early-access"
                className="mt-4 inline-flex min-h-[40px] items-center gap-1.5 font-mono text-xs font-semibold text-teal-accent hover:underline"
              >
                <Terminal className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Join Early Access for Hosted &amp; VPC Rollouts →</span>
              </Link>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-2 rounded-md border border-border-subtle bg-surface/60 px-4 py-3 font-mono text-xs text-fg-muted">
            <ShieldCheck
              className="h-4 w-4 shrink-0 text-teal-accent"
              aria-hidden="true"
            />
            <span>
              Source code licensed under <strong>Apache-2.0</strong>. Third-party
              model weights remain subject to their respective upstream model
              licenses.
            </span>
          </div>
        </section>
      </article>
    </div>
  );
}
