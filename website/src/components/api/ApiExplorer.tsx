"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, Copy, Download, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

export interface OpenApiOperationSummary {
  method: string;
  path: string;
  tag: string;
  summary: string;
  statusCodes: string[];
}

interface FlagshipEndpoint {
  id: string;
  method: "GET" | "POST";
  path: string;
  title: string;
  description: string;
  curl: string;
  pythonSdk: string;
  openaiCompat: string;
  cli: string;
  sampleResponse: string;
}

const FLAGSHIP_ENDPOINTS: FlagshipEndpoint[] = [
  {
    id: "responses",
    method: "POST",
    path: "/v1/responses",
    title: "Create Stateful Hybrid Response",
    description:
      "Unified stateful generation supporting previous_response_id chaining, zero-egress privacy, SSE streaming, and speculative Nano draft acceleration.",
    curl: `curl -X POST http://127.0.0.1:8000/v1/responses \\
  -H "Authorization: Bearer kw_live_7f3a1c_0123456789abcdef0123456789abcdef" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "keelway-core:7b",
    "input": "Audit src/billing/retry.py for discount rounding errors.",
    "privacy_level": "private"
  }'`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_...")
resp = client.responses.create(
    model="keelway-core:7b",
    input="Audit src/billing/retry.py for discount rounding errors.",
    privacy_level="private",
)
print(resp["id"], resp["output_text"])`,
    openaiCompat: `from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="kw_live_...")
resp = client.responses.create(
    model="keelway-core:7b",
    input="Audit src/billing/retry.py for discount rounding errors.",
)
print(resp.output_text)`,
    cli: `python3 cli.py route --model keelway-core:7b --privacy private \\
  --prompt "Audit src/billing/retry.py for discount rounding errors."`,
    sampleResponse: `{
  "id": "resp_8f91c20e4a1b",
  "object": "response",
  "model": "keelway-core:7b",
  "output_text": "Replace integer subtraction with round(price_cents * (100 - percent) / 100).",
  "provenance": {
    "model_license": "Apache-2.0",
    "hosting_topology": "local_loopback",
    "data_boundary": "zero_external_egress"
  },
  "usage": { "input_tokens": 28, "output_tokens": 41, "cost_usd": 0.0 }
}`,
  },
  {
    id: "chat",
    method: "POST",
    path: "/v1/chat/completions",
    title: "Chat Completions (OpenAI-Compatible)",
    description:
      "Drop-in chat completion contract normalized across local Ollama/vLLM weights and Google Gemini, OpenAI, and Anthropic commercial APIs.",
    curl: `curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Authorization: Bearer kw_live_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gemini-3.5-flash-lite",
    "messages": [{"role": "user", "content": "Summarize QLoRA rank trade-offs."}],
    "stream": false
  }'`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_...")
chat = client.chat.complete(
    model="gemini-3.5-flash-lite",
    messages=[{"role": "user", "content": "Summarize QLoRA rank trade-offs."}],
)
print(chat["choices"][0]["message"]["content"])`,
    openaiCompat: `from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="kw_live_...")
chat = client.chat.completions.create(
    model="gemini-3.5-flash-lite",
    messages=[{"role": "user", "content": "Summarize QLoRA rank trade-offs."}],
)
print(chat.choices[0].message.content)`,
    cli: `python3 cli.py route --model gemini-3.5-flash-lite \\
  --prompt "Summarize QLoRA rank trade-offs."`,
    sampleResponse: `{
  "id": "chatcmpl_4d01e92a",
  "model": "gemini-3.5-flash-lite",
  "provider": "gemini",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "Rank 16 balances VRAM and domain recall..." },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 19, "completion_tokens": 64, "total_tokens": 83 }
}`,
  },
  {
    id: "models",
    method: "GET",
    path: "/v1/models",
    title: "List Registered Hybrid Models",
    description:
      "Discover all active OpenCore open-weight and commercial Frontier models with live license, capability, context length, and VRAM metadata.",
    curl: `curl http://127.0.0.1:8000/v1/models \\
  -H "Authorization: Bearer kw_live_..."`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_...")
models = client.models.list(category="open_weight")
for m in models["data"]:
    print(m["id"], m["license"], m["recommended_vram_gb"])`,
    openaiCompat: `from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="kw_live_...")
for m in client.models.list().data:
    print(m.id)`,
    cli: `python3 cli.py opencore --weights --json`,
    sampleResponse: `{
  "object": "list",
  "data": [
    {
      "id": "keelway-core:7b",
      "category": "open_weight",
      "license": "Apache-2.0",
      "context_window": 65536,
      "recommended_vram_gb": 6.0
    }
  ]
}`,
  },
  {
    id: "explain",
    method: "POST",
    path: "/v1/routing/explain",
    title: "Explain 4D Routing Provenance",
    description:
      "Dry-run deterministic routing policy without executing upstream tokens. Returns 4D provenance across license, hosting, operator, and data boundary.",
    curl: `curl -X POST http://127.0.0.1:8000/v1/routing/explain \\
  -H "Authorization: Bearer kw_live_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "Refactor HIPAA patient intake parser",
    "privacy_level": "private",
    "required_capabilities": ["code"]
  }'`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_...")
plan = client.routing.explain(
    prompt="Refactor HIPAA patient intake parser",
    privacy_level="private",
    required_capabilities=["code"],
)
print(plan["selected_model"], plan["provenance"])`,
    openaiCompat: `# 4D Routing Explain is a Keelway governance extension endpoint:
import httpx

r = httpx.post(
    "http://127.0.0.1:8000/v1/routing/explain",
    json={"prompt": "Refactor parser", "privacy_level": "private"},
)
print(r.json())`,
    cli: `python3 cli.py route --explain --privacy private \\
  --prompt "Refactor HIPAA patient intake parser"`,
    sampleResponse: `{
  "selected_model": "keelway-coder:7b",
  "category": "open_weight",
  "provenance": {
    "model_license": "open_weight_permissive",
    "hosting_topology": "local_loopback",
    "operator_control": "self_operated",
    "data_boundary": "zero_external_egress"
  }
}`,
  },
  {
    id: "modelfile",
    method: "POST",
    path: "/v1/opencore/modelfile",
    title: "Compile Deterministic OpenCore Modelfile",
    description:
      "Generates an Ollama-compatible Modelfile pinned to verified quantization parameters, stop tokens, and optional SHA-256 QLoRA adapter paths.",
    curl: `curl -X POST http://127.0.0.1:8000/v1/opencore/modelfile \\
  -H "Content-Type: application/json" \\
  -d '{
    "model_id": "keelway-core:7b",
    "quantization": "Q4_K_M",
    "num_ctx": 65536
  }'`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_...")
mf = client.opencore.compile_modelfile(model_id="keelway-core:7b", quantization="Q4_K_M")
print(mf["modelfile_content"])`,
    openaiCompat: `import httpx

mf = httpx.post(
    "http://127.0.0.1:8000/v1/opencore/modelfile",
    json={"model_id": "keelway-core:7b", "quantization": "Q4_K_M"},
).json()
print(mf["ollama_create_command"])`,
    cli: `python3 cli.py opencore --modelfile keelway-core:7b`,
    sampleResponse: `{
  "model_id": "keelway-core:7b",
  "quantization": "Q4_K_M",
  "ollama_create_command": "ollama create 'keelway-core:7b' -f './Modelfile'",
  "modelfile_content": "FROM qwen3.5:7b-instruct\\nPARAMETER temperature 0.7..."
}`,
  },
  {
    id: "governance",
    method: "POST",
    path: "/v1/governance/policies",
    title: "Configure Tenant Spend & Residency Policy",
    description:
      "Set per-tenant provider allowlists, regional data residency zones (Africa, EU, Local-Only), RPM/TPM quotas, and OpenCore budget fallback.",
    curl: `curl -X POST http://127.0.0.1:8000/v1/governance/policies \\
  -H "Authorization: Bearer kw_live_admin_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "tenant_id": "org_nairobi_fin",
    "name": "Nairobi Core Banking",
    "allowed_providers": ["local", "gemini"],
    "residency_zone": "africa_sovereign",
    "monthly_spend_limit_usd": 250.0,
    "fallback_to_opencore_on_budget_exceeded": true
  }'`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_admin_...")
policy = client.governance.upsert_policy(
    tenant_id="org_nairobi_fin",
    name="Nairobi Core Banking",
    allowed_providers=["local", "gemini"],
    residency_zone="africa_sovereign",
    monthly_spend_limit_usd=250.0,
)
print(policy["tenant_id"], policy["residency_zone"])`,
    openaiCompat: `import httpx

resp = httpx.post(
    "http://127.0.0.1:8000/v1/governance/policies",
    headers={"Authorization": "Bearer kw_live_admin_..."},
    json={"tenant_id": "org_nairobi_fin", "name": "Nairobi Core Banking"},
)
print(resp.status_code)`,
    cli: `python3 cli.py governance --tenants --audit`,
    sampleResponse: `{
  "tenant_id": "org_nairobi_fin",
  "residency_zone": "africa_sovereign",
  "monthly_spend_limit_usd": 250.0,
  "fallback_to_opencore_on_budget_exceeded": true,
  "audit_chain_head": "sha256:94e1b7c02a8f..."
}`,
  },
  {
    id: "swarm",
    method: "POST",
    path: "/v1/eval/swarm",
    title: "Run Hybrid Multi-Agent Swarm",
    description:
      "Dispatches parallel high-volume simulation entities to $0.00 local OpenCore workers and synthesizes executive consensus on a Frontier judge.",
    curl: `curl -X POST http://127.0.0.1:8000/v1/eval/swarm \\
  -H "Authorization: Bearer kw_live_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "simulation_goal": "Stress-test regional payment retry policy under network partitions."
  }'`,
    pythonSdk: `from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_...")
report = client.swarm.evaluate(
    simulation_goal="Stress-test regional payment retry policy."
)
print(report["cost_savings_pct"], report["consensus_summary"])`,
    openaiCompat: `import httpx

report = httpx.post(
    "http://127.0.0.1:8000/v1/eval/swarm",
    json={"simulation_goal": "Stress-test payment retry policy."},
).json()
print(report["cost_savings_pct"])`,
    cli: `python3 cli.py swarm --offline --json`,
    sampleResponse: `{
  "local_worker_calls": 10,
  "frontier_judge_calls": 2,
  "hybrid_total_cost_usd": 0.0012,
  "all_cloud_baseline_usd": 0.0390,
  "cost_savings_pct": 96.9
}`,
  },
];

function methodBadgeClass(method: string): string {
  switch (method.toUpperCase()) {
    case "GET":
      return "chip-teal";
    case "DELETE":
      return "chip-fault";
    default:
      return "chip-neutral";
  }
}

function ApiQuerySync({
  onQuery,
  onSelectFlagship,
}: {
  onQuery: (q: string) => void;
  onSelectFlagship: (id: string) => void;
}) {
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("q");
  useEffect(() => {
    if (urlQuery !== null) {
      onQuery(urlQuery);
      const matchingFlagship = FLAGSHIP_ENDPOINTS.find(
        (ep) => ep.path === urlQuery
      );
      if (matchingFlagship) {
        onSelectFlagship(matchingFlagship.id);
      }
    }
  }, [urlQuery, onQuery, onSelectFlagship]);
  return null;
}

/**
 * Interactive API Reference Workbench + Complete 183-Endpoint OpenAPI 3.1 Directory.
 */
export function ApiExplorer({
  operations,
  tags,
}: {
  operations: OpenApiOperationSummary[];
  tags: string[];
}) {
  const [selectedId, setSelectedId] = useState<string>("responses");
  const [langTab, setLangTab] = useState<string>("python");
  const [copied, setCopied] = useState<boolean>(false);

  // Full OpenAPI Directory Search & Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [methodFilter, setMethodFilter] = useState<string>("ALL");
  const [tagFilter, setTagFilter] = useState<string>("ALL");
  const [showAllRows, setShowAllRows] = useState<boolean>(false);

  const activeEndpoint =
    FLAGSHIP_ENDPOINTS.find((e) => e.id === selectedId) ??
    FLAGSHIP_ENDPOINTS[0];

  const activeCode =
    langTab === "curl"
      ? activeEndpoint.curl
      : langTab === "python"
      ? activeEndpoint.pythonSdk
      : langTab === "openai"
      ? activeEndpoint.openaiCompat
      : activeEndpoint.cli;

  const copyActiveCode = async () => {
    try {
      await navigator.clipboard.writeText(activeCode);
      setCopied(true);
      trackEvent("code_snippet_copied", {
        tab: `${activeEndpoint.id}_${langTab}`,
      });
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Ignore clipboard failures
    }
  };

  const filteredOperations = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return operations.filter((op) => {
      if (methodFilter !== "ALL" && op.method !== methodFilter) return false;
      if (tagFilter !== "ALL" && op.tag !== tagFilter) return false;
      if (q) {
        const hay = `${op.method} ${op.path} ${op.summary} ${op.tag}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [operations, searchQuery, methodFilter, tagFilter]);

  const visibleOperations = showAllRows
    ? filteredOperations
    : filteredOperations.slice(0, 30);

  return (
    <div className="space-y-16">
      <Suspense fallback={null}>
        <ApiQuerySync
          onQuery={setSearchQuery}
          onSelectFlagship={setSelectedId}
        />
      </Suspense>
      {/* ====================================================================
          1. INTERACTIVE 4-LANGUAGE ENDPOINT WORKBENCH
          ==================================================================== */}
      <section aria-labelledby="workbench-heading">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              INTERACTIVE SDK &amp; REST WORKBENCH
            </p>
            <h2
              id="workbench-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg"
            >
              Core v1 Hybrid AI Endpoints
            </h2>
          </div>

          <a
            href="/openapi.json"
            target="_blank"
            rel="noopener noreferrer"
            className="kw-btn kw-btn-secondary font-mono text-xs"
          >
            <Download className="h-4 w-4 text-teal-accent" aria-hidden="true" />
            <span>Download openapi.json ({operations.length} ops)</span>
          </a>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Endpoint Selector Rail */}
          <div
            role="listbox"
            aria-label="Core v1 endpoints"
            className="space-y-2 lg:col-span-4"
          >
            {FLAGSHIP_ENDPOINTS.map((ep) => {
              const active = ep.id === selectedId;
              return (
                <button
                  key={ep.id}
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => {
                    setSelectedId(ep.id);
                    trackEvent("api_endpoint_selected", { endpoint: ep.path });
                  }}
                  className={cn(
                    "flex min-h-[58px] w-full flex-col justify-center rounded-md border px-3.5 py-2.5 text-left transition-colors duration-150",
                    active
                      ? "border-teal-accent bg-surface-elevated"
                      : "border-border-subtle bg-surface hover:border-border-strong"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "rounded-sm px-1.5 py-0.5 text-[10px]",
                        methodBadgeClass(ep.method)
                      )}
                    >
                      {ep.method}
                    </span>
                    <code className="truncate font-mono text-xs font-bold text-fg">
                      {ep.path}
                    </code>
                  </div>
                  <span className="mt-1 text-xs text-fg-muted">{ep.title}</span>
                </button>
              );
            })}
          </div>

          {/* 4-Tab Code & Response Inspector */}
          <div className="lg:col-span-8">
            <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-6">
              <div className="border-b border-border-subtle pb-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "rounded-sm px-2 py-0.5",
                      methodBadgeClass(activeEndpoint.method)
                    )}
                  >
                    {activeEndpoint.method}
                  </span>
                  <code className="font-mono text-sm font-bold text-teal-accent">
                    {activeEndpoint.path}
                  </code>
                </div>
                <h3 className="mt-2 text-lg font-bold text-fg">
                  {activeEndpoint.title}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-fg-muted">
                  {activeEndpoint.description}
                </p>
              </div>

              {/* 4-Language Tabs */}
              <Tabs.Root
                value={langTab}
                onValueChange={setLangTab}
                className="mt-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Tabs.List
                    aria-label="Client SDK language"
                    className="flex flex-wrap gap-1 rounded-sm border border-border-strong bg-canvas p-1"
                  >
                    {[
                      { id: "python", label: "Python SDK v1" },
                      { id: "curl", label: "cURL" },
                      { id: "openai", label: "OpenAI Compat" },
                      { id: "cli", label: "Keelway CLI" },
                    ].map((t) => (
                      <Tabs.Trigger
                        key={t.id}
                        value={t.id}
                        className={cn(
                          "min-h-[36px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors duration-150",
                          langTab === t.id
                            ? "bg-teal-accent text-teal-ink"
                            : "text-fg-muted hover:text-fg"
                        )}
                      >
                        {t.label}
                      </Tabs.Trigger>
                    ))}
                  </Tabs.List>

                  <button
                    type="button"
                    onClick={copyActiveCode}
                    className="inline-flex min-h-[38px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-3 font-mono text-xs text-fg hover:border-teal-accent"
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
                        <span>Copy Request</span>
                      </>
                    )}
                  </button>
                </div>

                <pre className="mt-3 overflow-x-auto rounded-md border border-border-strong bg-canvas p-4 font-mono text-xs leading-relaxed text-fg">
                  <code>{activeCode}</code>
                </pre>
              </Tabs.Root>

              {/* Verified Response Schema Preview */}
              <div className="mt-5">
                <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px]">
                  <span className="uppercase text-fg-muted">
                    200 OK · Normalized JSON Payload
                  </span>
                  <span className="text-fg-dim">
                    Errors: 401 Auth · 402 BudgetCap · 403 AirGap · 429 Quota
                  </span>
                </div>
                <pre className="mt-1.5 overflow-x-auto rounded-md border border-border-subtle bg-canvas/80 p-3.5 font-mono text-xs leading-relaxed text-teal-accent">
                  <code>{activeEndpoint.sampleResponse}</code>
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ====================================================================
          2. COMPLETE SEARCHABLE OPENAPI 3.1 DIRECTORY (ALL 183 OPERATIONS)
          ==================================================================== */}
      <section
        aria-labelledby="openapi-dir-heading"
        className="border-t border-border-subtle pt-14"
      >
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              GENERATED DIRECTLY FROM OPENAPI.JSON (v3.1.0)
            </p>
            <h2
              id="openapi-dir-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg"
            >
              Complete {operations.length}-Endpoint Schema Index
            </h2>
          </div>
          <p aria-live="polite" className="font-mono text-xs text-fg-muted">
            Matching <strong className="text-fg">{filteredOperations.length}</strong>{" "}
            of {operations.length} exported routes
          </p>
        </div>

        {/* Search + Method + Tag Filters */}
        <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-12">
          <div className="relative md:col-span-6">
            <label htmlFor="api-dir-search" className="sr-only">
              Filter OpenAPI endpoints by path, summary, or tag
            </label>
            <Search
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-dim"
              aria-hidden="true"
            />
            <input
              id="api-dir-search"
              type="search"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                trackEvent("api_catalog_searched", {
                  has_query: e.target.value.length > 0,
                });
              }}
              placeholder="Filter /v1/opencore, /v1/governance, audit, kflow…"
              className="min-h-[44px] w-full rounded-md border border-border-strong bg-surface pl-10 pr-4 text-sm text-fg placeholder:text-fg-dim focus:border-teal-accent"
            />
          </div>

          <div className="md:col-span-3">
            <label htmlFor="api-method-select" className="sr-only">
              Filter by HTTP method
            </label>
            <select
              id="api-method-select"
              value={methodFilter}
              onChange={(e) => setMethodFilter(e.target.value)}
              className="min-h-[44px] w-full rounded-md border border-border-strong bg-surface px-3 font-mono text-xs text-fg"
            >
              <option value="ALL">All HTTP Methods</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <label htmlFor="api-tag-select" className="sr-only">
              Filter by OpenAPI tag
            </label>
            <select
              id="api-tag-select"
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              className="min-h-[44px] w-full rounded-md border border-border-strong bg-surface px-3 font-mono text-xs text-fg"
            >
              <option value="ALL">All Domain Tags ({tags.length})</option>
              {tags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Operations Table */}
        <div className="mt-5 overflow-x-auto rounded-lg border border-border-strong bg-surface">
          <table className="w-full min-w-[640px] border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-border-strong bg-surface-elevated font-mono uppercase text-fg">
                <th scope="col" className="px-4 py-3">
                  Method
                </th>
                <th scope="col" className="px-4 py-3">
                  Endpoint Path
                </th>
                <th scope="col" className="px-4 py-3">
                  Domain Tag
                </th>
                <th scope="col" className="px-4 py-3">
                  Summary &amp; Codes
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {visibleOperations.map((op) => (
                <tr
                  key={`${op.method}-${op.path}`}
                  className="hover:bg-surface-elevated/50"
                >
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-block rounded-sm px-2 py-0.5 text-[10px]",
                        methodBadgeClass(op.method)
                      )}
                    >
                      {op.method}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono font-semibold text-fg">
                    {op.path}
                  </td>
                  <td className="px-4 py-3 font-mono text-fg-muted">
                    {op.tag}
                  </td>
                  <td className="px-4 py-3 text-fg-muted">
                    <span>{op.summary}</span>
                    <span className="ml-2 font-mono text-[10px] text-fg-dim">
                      [{op.statusCodes.join(", ")}]
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredOperations.length > 30 && (
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => setShowAllRows((prev) => !prev)}
              className="kw-btn kw-btn-secondary font-mono text-xs"
            >
              {showAllRows
                ? "Collapse to Top 30 Routes"
                : `Show All ${filteredOperations.length} Matching Routes`}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
