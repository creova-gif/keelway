import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";
import { CATALOG_MODELS } from "@/data/models";

export const dynamic = "force-static";

export interface SearchIndexItem {
  id: string;
  group: "page" | "model" | "docs" | "api";
  title: string;
  subtitle: string;
  badge: string;
  href: string;
  keywords: string;
}

interface RawOpenApi {
  paths?: Record<
    string,
    Record<string, { tags?: string[]; summary?: string }>
  >;
}

/**
 * GET /api/search-index
 * Pre-rendered at build time (`force-static`) so the Global Cmd+K Command Palette
 * searches all 7 routes, 15 models, 6 doc guides, and 183 OpenAPI endpoints
 * with zero runtime filesystem cost.
 */
export async function GET() {
  const items: SearchIndexItem[] = [
    // 1. Core Pages & Interactive Instruments
    {
      id: "page-home",
      group: "page",
      title: "Home & Live Control-Plane Cockpit",
      subtitle: "WebCrypto SHA-256 Approval Gate, 6-Layer Topology & Recorded Demos",
      badge: "PAGE",
      href: "/",
      keywords: "home cockpit approval gate topology swarm quickstart",
    },
    {
      id: "page-golden-thread-studio",
      group: "page",
      title: "Golden-Thread Bidirectional Studio Showcase",
      subtitle: "Convert LangGraph StateGraph to KFlow, sync AST lines, scrub Flight-Tapes & audit sandbox blast radius",
      badge: "STUDIO",
      href: "/#studio-showcase",
      keywords: "studio golden thread bidirectional langgraph stategraph kflow ast flight tape blast radius prompt gate",
    },
    {
      id: "page-step-debugger-bridge",
      group: "page",
      title: "Live Step-Through Debugger & VS Code / Cursor Extension Bridge",
      subtitle: "Conditional gutter breakpoints, F10/F11 frame stepping, DLP-guarded state mutation & 4D CodeLens",
      badge: "DEBUGGER",
      href: "/docs#surfaces",
      keywords: "step debugger breakpoints f10 f11 codelens vscode cursor extension bridge dlp state mutation",
    },
    {
      id: "page-dev-tool",
      group: "page",
      title: "Keelway Dev Tool & 10-View Workspace",
      subtitle: "Launch keelway dev locally (:7420/app) for Guided No-Code Builder, PRD, PM, Agents, IDE & Marketplace",
      badge: "DEV TOOL",
      href: "/#quickstart",
      keywords: "dev tool studio 10-view workspace nocode no-code builder agents ide pm product automation marketplace operations",
    },
    {
      id: "page-marketplace",
      group: "page",
      title: "Keelway Marketplace & Security Explorer",
      subtitle: "7 categories, Ed25519 signed keelway.package/v1 bundles, SHA-256 digests & 85/15 Creator Split",
      badge: "MARKETPLACE",
      href: "/marketplace",
      keywords: "marketplace agents skills plugins workflows ed25519 sha256 85/15 creator catalog",
    },
    {
      id: "mp-pkg-pr-sentinel",
      group: "page",
      title: "Keelway PR Sentinel Agent (keelway-pr-sentinel)",
      subtitle: "1st-Party Sorvex Labs · Apache-2.0 · Ed25519 Signed AI Agent",
      badge: "PACKAGE",
      href: "/marketplace?q=keelway-pr-sentinel",
      keywords: "marketplace package keelway-pr-sentinel ai agent apache-2.0 diff reviewer",
    },
    {
      id: "mp-pkg-linear-bridge",
      group: "page",
      title: "Linear & GitHub Bidirectional Bridge (linear-github-mcp-bridge)",
      subtitle: "Verified 3rd-Party (85/15 Split) · Scoped Webhook Plugin",
      badge: "PACKAGE",
      href: "/marketplace?q=linear-github-mcp-bridge",
      keywords: "marketplace package linear-github-mcp-bridge plugin extension github linear 85/15",
    },
    {
      id: "mp-pkg-finreg",
      group: "page",
      title: "FinReg SOC2 / PCI Sovereign Control Suite (finreg-sovereign-compliance)",
      subtitle: "Enterprise Partner · Air-Gapped Financial Compliance Pack",
      badge: "PACKAGE",
      href: "/marketplace?q=finreg-sovereign-compliance",
      keywords: "marketplace package finreg-sovereign-compliance enterprise soc2 pci compliance",
    },
    {
      id: "page-governance-tamper",
      group: "page",
      title: "Record Tamper Lab & Marketplace Pre-Publish Scanner",
      subtitle: "Simulate #1279 SHA-256 chain break, p-13->p-14 prompt drift & keelway.package/v1 validation",
      badge: "LAB",
      href: "/governance#tamper-lab",
      keywords: "governance tamper ledger sha256 manifest drift marketplace security scanner p-10",
    },
    {
      id: "page-pricing-byom",
      group: "page",
      title: "5-Stream Pricing, BYOM Compliance & Creator Marketplace",
      subtitle: "$0 Community, $15 BYOM, $29 Pro, 0%-Markup BYOM API Rules, Enterprise VPC & 85/15 Creator Split",
      badge: "PRICING",
      href: "/pricing#byom-compliance",
      keywords: "pricing community pro byom chatgpt claude api compliance marketplace creator 85 15",
    },
    {
      id: "page-models",
      group: "page",
      title: "Models & OpenCore Catalog",
      subtitle: "15 models, Hardware VRAM Fit Calculator & Modelfile Compiler",
      badge: "PAGE",
      href: "/models",
      keywords: "models opencore vram quantization modelfile qlora swahili",
    },
    {
      id: "page-governance",
      group: "page",
      title: "Hybrid Routing & Enterprise Governance",
      subtitle: "4D Provenance Simulator, USD Spend Caps & Secret Redaction Lab",
      badge: "PAGE",
      href: "/governance",
      keywords: "governance routing 4d simulator spend cap redaction kw_live",
    },
    {
      id: "page-pricing",
      group: "page",
      title: "Pricing & Sovereign VPC Tiers",
      subtitle: "$0 Apache-2.0 Local, 0%-Markup Team Hybrid & Enterprise VPC",
      badge: "PAGE",
      href: "/pricing",
      keywords: "pricing cost seats byok vpc enterprise apache",
    },
    {
      id: "page-docs",
      group: "page",
      title: "Developer Documentation",
      subtitle: "5-Minute Quickstart, Surfaces, OpenCore Weights & Roadmap",
      badge: "PAGE",
      href: "/docs",
      keywords: "documentation guide install studio cli sdk",
    },
    {
      id: "page-api",
      group: "page",
      title: "Interactive API Reference & Live Sandbox",
      subtitle: "OpenAPI 3.1 Workbench + Live Network /v1/routing/explain Runner",
      badge: "PAGE",
      href: "/api-reference",
      keywords: "api reference openapi rest curl python sandbox",
    },
    {
      id: "page-brand",
      group: "page",
      title: "Interface Identity & Brand Kit",
      subtitle: "Geometric 'K' SVG Lockups, Click-to-Copy Tokens & Typography",
      badge: "PAGE",
      href: "/brand",
      keywords: "brand logo svg colors tokens inter jetbrains mono",
    },

    // 2. Documentation Sections
    {
      id: "doc-quickstart",
      group: "docs",
      title: "5-Minute Quickstart",
      subtitle: "Clone, verify 167 gates, and launch Studio (:7420) or Server (:8000)",
      badge: "DOCS",
      href: "/docs#quickstart",
      keywords: "quickstart clone venv pip cli dev make serve",
    },
    {
      id: "doc-surfaces",
      group: "docs",
      title: "The Four Operational Surfaces",
      subtitle: "Keelway Studio, Governance Server, 6-Tab Console & Python SDK v1",
      badge: "DOCS",
      href: "/docs#surfaces",
      keywords: "surfaces studio ide web console sdk cli",
    },
    {
      id: "doc-opencore",
      group: "docs",
      title: "OpenCore Weights, Modelfiles & QLoRA",
      subtitle: "Legitimate Ollama/GGUF weight pulls and SHA-256 adapter checks",
      badge: "DOCS",
      href: "/docs#opencore",
      keywords: "opencore weights ollama pull modelfile lora sha256",
    },
    {
      id: "doc-routing",
      group: "docs",
      title: "Unified Responses & 4D Routing Provenance",
      subtitle: "Stateful previous_response_id chaining and zero-egress privacy",
      badge: "DOCS",
      href: "/docs#routing",
      keywords: "responses stateful routing explain privacy private",
    },
    {
      id: "doc-approval",
      group: "docs",
      title: "Approval Gate & Hash-Chained Flight Ledger",
      subtitle: "AutonomyPolicy.CONFIRM_MUTATION and offline GET /v1/audit/verify",
      badge: "DOCS",
      href: "/docs#approval-loop",
      keywords: "approval human quorum diff flight recorder hash chain",
    },
    {
      id: "doc-status",
      group: "docs",
      title: "Verified v1 Capabilities vs. Roadmap",
      subtitle: "Honest engineering inventory of tested v1 vs. staged VPC features",
      badge: "DOCS",
      href: "/docs#status",
      keywords: "roadmap limitations verified capabilities license",
    },
  ];

  // 3. All 15 Canonical Models
  for (const m of CATALOG_MODELS) {
    items.push({
      id: `model-${m.id}`,
      group: "model",
      title: `${m.name} (${m.id})`,
      subtitle: `${m.license} · ${Math.round(m.contextWindow / 1024)}K ctx · ${
        m.recommendedVramGb !== null ? `${m.recommendedVramGb} GB VRAM` : "Managed Cloud API"
      }`,
      badge: m.category === "open_weight" ? "OPEN-WEIGHT" : "FRONTIER",
      href: `/models?q=${encodeURIComponent(m.id)}`,
      keywords: `${m.id} ${m.name} ${m.family} ${m.license} ${m.capabilities.join(" ")}`,
    });
  }

  // 4. All 183 OpenAPI 3.1 Endpoints
  try {
    const specPath = path.join(process.cwd(), "public", "openapi.json");
    const raw = JSON.parse(fs.readFileSync(specPath, "utf8")) as RawOpenApi;
    const methodsAllowed = new Set(["get", "post", "put", "delete", "patch"]);

    for (const [routePath, methods] of Object.entries(raw.paths ?? {})) {
      for (const [method, meta] of Object.entries(methods)) {
        if (!methodsAllowed.has(method.toLowerCase())) continue;
        const upper = method.toUpperCase();
        const tag = meta.tags?.[0] ?? "Core";
        const summary = meta.summary ?? routePath;
        items.push({
          id: `api-${upper}-${routePath}`,
          group: "api",
          title: `${upper} ${routePath}`,
          subtitle: `${tag} — ${summary}`,
          badge: upper,
          href: `/api-reference?q=${encodeURIComponent(routePath)}`,
          keywords: `${upper} ${routePath} ${tag} ${summary}`,
        });
      }
    }
  } catch {
    // Graceful fallback if openapi.json is absent
  }

  return NextResponse.json({ count: items.length, items });
}
