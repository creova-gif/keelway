"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Check, Copy, Search, ShieldCheck } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

const DOC_SECTIONS = [
  { id: "quickstart", label: "01 Quickstart" },
  { id: "routing", label: "02 Routing & Governance" },
  { id: "enterprise", label: "03 Enterprise & Ecosystem" },
  { id: "surfaces", label: "04 SDKs & CLI" },
] as const;

const CAPABILITY_MATRIX = [
  {
    domain: "4-K Sovereign Architecture",
    title: "KFlow, KSpaces, KBrain & KHub Core",
    summary:
      "Topological KFlow DAGs, KSpaces CRDT sync, KBrain hybrid BM25 + n-gram memory, and KHub air-gapped skill mirrors (.skill.tar.gz).",
    cliOrSpec: "keelway hub · .skill.tar.gz",
  },
  {
    domain: "Visual & Code Sync",
    title: "Golden-Thread Bidirectional KFlow Studio",
    summary:
      "Round-trip Python/TypeScript workflows with Seatbelt Blast-Radius Radar and inline Prompt Regression Gate checks.",
    cliOrSpec: "kflow-sync · blast-radius · prompt-gate",
  },
  {
    domain: "Observability & Evals",
    title: "OpenTelemetry GenAI Flight-Tape Time-Travel Debugging",
    summary:
      "Deterministic step replay, 1-click Trace-to-Eval Promotion into the 16-probe Golden Benchmark, and Static AST LangGraph import.",
    cliOrSpec: "migrate-langgraph · OpenTelemetry OTLP",
  },
  {
    domain: "MCP & Supply Chain",
    title: "Model Context Protocol (2025-06-18) & Signed Artifacts",
    summary:
      "Zero-trust tool discovery, Ed25519 Marketplace verification, and reproducible CycloneDX 1.5 SBOM release attestations.",
    cliOrSpec: "MCP 2025-06-18 · CycloneDX 1.5 SBOM",
  },
  {
    domain: "Enterprise Identity & SIEM",
    title: "OIDC/SAML, SCIM 2.0 & Dual-Human P-10 Quorum",
    summary:
      "Directory-synced RBAC, two-person approval receipts for high-impact actions, and streaming OCSF, CEF, and JSONL audit exports.",
    cliOrSpec: "OIDC/SAML · SCIM 2.0 · OCSF / CEF / JSONL",
  },
] as const;

function CodePanel({ id, title, code }: { id: string; title: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      trackEvent("code_snippet_copied", { tab: id });
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard unavailable
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
              <Check className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
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
 * Minimalist Developer Documentation Hub (/docs)
 */
export function DocsHub() {
  const [filterQuery, setFilterQuery] = useState("");

  const filteredCapabilities = useMemo(() => {
    const q = filterQuery.trim().toLowerCase();
    if (!q) return CAPABILITY_MATRIX;
    return CAPABILITY_MATRIX.filter(
      (row) =>
        row.domain.toLowerCase().includes(q) ||
        row.title.toLowerCase().includes(q) ||
        row.summary.toLowerCase().includes(q) ||
        row.cliOrSpec.toLowerCase().includes(q)
    );
  }, [filterQuery]);

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
            onClick={() => trackEvent("docs_section_jumped", { section: sec.id })}
            className="inline-flex min-h-[40px] shrink-0 items-center rounded-sm px-3 font-mono text-xs text-fg-muted hover:bg-surface-elevated hover:text-teal-accent"
          >
            {sec.label}
          </a>
        ))}
      </nav>

      {/* Desktop Sticky Sidebar */}
      <aside className="hidden lg:col-span-3 lg:block">
        <div className="sticky top-28 space-y-5 rounded-lg border border-border-strong bg-surface p-5">
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
                  onClick={() => trackEvent("docs_section_jumped", { section: sec.id })}
                  className="flex min-h-[38px] items-center rounded-sm px-2.5 font-mono text-xs text-fg-muted transition-colors duration-150 hover:bg-surface-elevated hover:text-teal-accent"
                >
                  {sec.label}
                </a>
              ))}
            </nav>
          </div>

          <div className="space-y-2 border-t border-border-subtle pt-4 font-mono text-xs">
            <Link href="/api-reference" className="kw-btn kw-btn-secondary w-full justify-between">
              <span>API Reference</span>
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
            <div className="flex items-center justify-between px-1 pt-1 text-[11px] text-fg-muted">
              <Link href="/pricing" className="hover:text-teal-accent">Pricing &amp; BYOM</Link>
              <span>·</span>
              <Link href="/changelog" className="hover:text-teal-accent">Changelog</Link>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Documentation Body */}
      <article className="space-y-12 lg:col-span-9">
        {/* 01 Quickstart */}
        <section id="quickstart" aria-labelledby="doc-qs-h" className="scroll-mt-28">
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5 font-mono text-xs">
            01 QUICKSTART
          </span>
          <h2 id="doc-qs-h" className="mt-2 text-2xl font-bold text-fg">
            Boot Local Runtime in 60 Seconds
          </h2>
          <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-fg-muted">
            Run locally with zero mandatory cloud account, zero token markup, and crash-safe SQLite WAL state.
          </p>
          <CodePanel
            id="docs-quickstart-bash"
            title="bash — install & launch local runtime"
            code={`curl -fsSL https://kora-sable.vercel.app/install.sh | sh
keelway init && keelway dev`}
          />
        </section>

        {/* 02 Routing & Governance */}
        <section id="routing" aria-labelledby="doc-routing-h" className="scroll-mt-28 border-t border-border-subtle pt-10">
          <span id="approval-loop" className="sr-only" />
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5 font-mono text-xs">
            02 ROUTING &amp; GOVERNANCE
          </span>
          <h2 id="doc-routing-h" className="mt-2 text-2xl font-bold text-fg">
            Drop-In Hybrid API &amp; Deterministic Policy Gates
          </h2>
          <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-fg-muted">
            Point any OpenAI-compatible client or official SDK at{" "}
            <code className="font-mono text-fg">/v1/responses</code>. Every call evaluates privacy boundaries, USD spend caps, human P-10 approval gates, and appends a SHA-256 hash-chained receipt.
          </p>
          <CodePanel
            id="docs-python-sdk"
            title="python — zero-egress routing & stateful responses"
            code={`from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_dev")
plan = client.routing.explain(prompt="Audit billing webhook", privacy_level="private")
resp = client.responses.create(model=plan["selected_model"], input="Generate patch diff.")`}
          />
        </section>

        {/* 03 Enterprise & Ecosystem */}
        <section id="enterprise" aria-labelledby="doc-ent-h" className="scroll-mt-28 border-t border-border-subtle pt-10">
          <span id="status" className="sr-only" />
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <span className="chip-teal inline-block rounded-sm px-2 py-0.5 font-mono text-xs">
                03 ENTERPRISE &amp; ECOSYSTEM
              </span>
              <h2 id="doc-ent-h" className="mt-2 text-2xl font-bold text-fg">
                Production Architecture &amp; Security Capabilities
              </h2>
            </div>

            <div className="relative w-full sm:w-64">
              <label htmlFor="docs-cap-filter" className="sr-only">Filter architecture capabilities</label>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-dim" aria-hidden="true" />
              <input
                id="docs-cap-filter"
                type="search"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                placeholder="Filter OIDC, KBrain, MCP…"
                className="min-h-[38px] w-full rounded-md border border-border-strong bg-surface pl-8 pr-3 font-mono text-xs text-fg placeholder:text-fg-dim focus:border-teal-accent"
              />
            </div>
          </div>

          <div className="mt-5 overflow-x-auto rounded-lg border border-border-strong bg-surface">
            <table className="w-full min-w-[600px] border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-border-strong bg-surface-elevated font-mono uppercase text-fg">
                  <th scope="col" className="px-4 py-3">Layer</th>
                  <th scope="col" className="px-4 py-3">Capability</th>
                  <th scope="col" className="px-4 py-3">CLI / Standard</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {filteredCapabilities.map((row) => (
                  <tr key={row.domain} className="align-top hover:bg-surface-elevated/40">
                    <td className="px-4 py-3 font-mono font-semibold text-teal-accent">{row.domain}</td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-fg">{row.title}</div>
                      <p className="mt-1 leading-relaxed text-fg-muted">{row.summary}</p>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-fg-muted">{row.cliOrSpec}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* 04 SDKs & CLI */}
        <section id="surfaces" aria-labelledby="doc-sdks-h" className="scroll-mt-28 border-t border-border-subtle pt-10">
          <span className="chip-teal inline-block rounded-sm px-2 py-0.5 font-mono text-xs">
            04 SDKS &amp; CLI
          </span>
          <h2 id="doc-sdks-h" className="mt-2 text-2xl font-bold text-fg">
            Tri-Language SDKs &amp; Developer CLI
          </h2>
          <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-fg-muted">
            Zero-dependency TypeScript (<code className="font-mono text-fg">@keelway/sdk</code>), Python (
            <code className="font-mono text-fg">keelway</code>), Go (<code className="font-mono text-fg">keelway-go</code>), and the VS Code / Cursor extension share identical REST &amp; SSE contracts.
          </p>
          <CodePanel
            id="docs-cli-workflows"
            title="bash — studio sync, sandbox audit & migration CLI"
            code={`keelway kflow-sync --file workflow.py --direction code_to_graph
keelway blast-radius --workflow wf-prod && keelway prompt-gate --min-pass-rate 0.95
keelway migrate-langgraph --source graph.py`}
          />

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border-subtle bg-surface/60 px-4 py-3 font-mono text-xs text-fg-muted">
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
              <span>Licensed under <strong>Apache-2.0</strong>.</span>
            </span>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/api-reference" className="text-teal-accent hover:underline">OpenAPI Reference →</Link>
              <Link href="/pricing" className="hover:text-fg">Pricing</Link>
              <Link href="/changelog" className="hover:text-fg">Release Changelog</Link>
            </div>
          </div>
        </section>
      </article>
    </div>
  );
}
