"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Check, Copy, FileCode2, Lock, Package, Search, ShieldCheck, Sparkles, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

export type MarketplaceCategoryId =
  | "all" | "ai_agent" | "multi_agent_system" | "agent_skill"
  | "plugin_extension" | "automation_template" | "dev_tool" | "industry_enterprise_solution";

export type PublisherTierFilter = "all" | "first_party" | "verified_third_party" | "enterprise_partner";

export interface CatalogPackage {
  id: string; name: string; kind: Exclude<MarketplaceCategoryId, "all">; categoryLabel: string;
  version: string; publisher: string; publisherTier: Exclude<PublisherTierFilter, "all">;
  pricingModel: "free" | "monthly" | "one_time" | "enterprise"; priceUsd: number;
  license: string; keyId: string; sha256: string; description: string;
  permissions: { readPaths: string[]; writePaths: string[]; network: "none" | "scoped"; requiresP10Approval: boolean };
}

const CATEGORIES: { id: MarketplaceCategoryId; label: string }[] = [
  { id: "all", label: "All Categories" },
  { id: "ai_agent", label: "AI Agents" },
  { id: "multi_agent_system", label: "Multi-Agent Systems" },
  { id: "agent_skill", label: "Agent Skills" },
  { id: "plugin_extension", label: "Plugins & Extensions" },
  { id: "automation_template", label: "Automation Workflows" },
  { id: "dev_tool", label: "Development Tools" },
  { id: "industry_enterprise_solution", label: "Enterprise & Industry Solutions" },
];

const PUBLISHER_FILTERS: { id: PublisherTierFilter; label: string }[] = [
  { id: "all", label: "All Publishers" },
  { id: "first_party", label: "1st-Party Sorvex Labs" },
  { id: "verified_third_party", label: "Verified 3rd-Party (85/15 Split)" },
  { id: "enterprise_partner", label: "Enterprise Partner" },
];

export const MARKETPLACE_PACKAGES: CatalogPackage[] = [
  {
    id: "keelway-pr-sentinel", name: "Keelway PR Sentinel Agent", kind: "ai_agent", categoryLabel: "AI Agents",
    version: "1.4.0", publisher: "Sorvex Labs", publisherTier: "first_party", pricingModel: "free", priceUsd: 0,
    license: "Apache-2.0", keyId: "ed25519:sorvex-root-2026",
    sha256: "9c4e18b20fa74d19e3c611b08a5d27f4e91c30b4a8f126d5c03e9a7b41d8f206",
    description: "Deterministic diff reviewer enforcing architecture boundaries, typing, and regression tests.",
    permissions: { readPaths: ["core/", "tests/"], writePaths: [], network: "none", requiresP10Approval: false },
  },
  {
    id: "keelway-release-swarm", name: "Autonomous Release Gate Squad", kind: "multi_agent_system", categoryLabel: "Multi-Agent Systems",
    version: "2.1.0", publisher: "Sorvex Labs", publisherTier: "first_party", pricingModel: "monthly", priceUsd: 29,
    license: "Keelway Commercial v1", keyId: "ed25519:sorvex-root-2026",
    sha256: "3f81d62a94c0e71b520d89fa41ce6b3097ad1580f4c2e69b1a730d84e52c19b0",
    description: "Coordinated Architect + QA + Security Auditor swarm with mandatory P-10 deploy checkpoints.",
    permissions: { readPaths: ["./"], writePaths: ["artifacts/"], network: "scoped", requiresP10Approval: true },
  },
  {
    id: "sorvex-diataxis-writer", name: "Diataxis Architecture Skill Pack", kind: "agent_skill", categoryLabel: "Agent Skills",
    version: "1.2.2", publisher: "Sorvex Labs", publisherTier: "first_party", pricingModel: "free", priceUsd: 0,
    license: "Apache-2.0", keyId: "ed25519:sorvex-root-2026",
    sha256: "7a12e409bc5831d6f9042ec781a53b60d4f92817c6e03b4a951d72f80e6c34a1",
    description: "Structured tutorials, how-to runbooks, API references, and ADR synthesis from live repositories.",
    permissions: { readPaths: ["core/", "docs/"], writePaths: ["docs/"], network: "none", requiresP10Approval: false },
  },
  {
    id: "linear-github-mcp-bridge", name: "Linear & GitHub Bidirectional Bridge", kind: "plugin_extension", categoryLabel: "Plugins & Extensions",
    version: "1.3.1", publisher: "Northstar DevTools", publisherTier: "verified_third_party", pricingModel: "monthly", priceUsd: 15,
    license: "Commercial Creator (85/15)", keyId: "ed25519:northstar-verified-04",
    sha256: "5b09f741d2e863a0c1497be520d83f61a9c40275e8b16d3f04a92c71e58d3b12",
    description: "Synchronizes Keelway PM sprint issues, PR status checks, and release milestones via scoped webhooks.",
    permissions: { readPaths: ["docs/"], writePaths: [".keelway/sync/"], network: "scoped", requiresP10Approval: true },
  },
  {
    id: "kflow-ci-healer-dag", name: "Nightly Flake Triage & Patch DAG", kind: "automation_template", categoryLabel: "Automation Workflows",
    version: "1.1.0", publisher: "BuildPulse Studio", publisherTier: "verified_third_party", pricingModel: "one_time", priceUsd: 39,
    license: "Commercial Creator (85/15)", keyId: "ed25519:buildpulse-verified-09",
    sha256: "e14c82d09a375fb618204ce97a51d380b6f4921ec7038a5d49b12f608ce73a45",
    description: "Durable KFlow workflow template that isolates failing pytest/vitest targets and proposes minimal diffs.",
    permissions: { readPaths: ["tests/", "src/"], writePaths: [".keelway/patches/"], network: "none", requiresP10Approval: true },
  },
  {
    id: "ast-boundary-profiler", name: "Polyglot AST Dependency & Size Guard", kind: "dev_tool", categoryLabel: "Development Tools",
    version: "1.0.4", publisher: "Lattice Static Analysis", publisherTier: "verified_third_party", pricingModel: "free", priceUsd: 0,
    license: "MIT", keyId: "ed25519:lattice-oss-02",
    sha256: "2d76a913f804cb52e1973da6408bf5129ce30746a182d95f03b74c81e62a90d4",
    description: "Zero-egress static analyzer enforcing module import layering and file-size ratchets.",
    permissions: { readPaths: ["./"], writePaths: [], network: "none", requiresP10Approval: false },
  },
  {
    id: "finreg-sovereign-compliance", name: "FinReg SOC2 / PCI Sovereign Control Suite", kind: "industry_enterprise_solution", categoryLabel: "Enterprise & Industry Solutions",
    version: "3.0.0", publisher: "Aegis Regulated Systems", publisherTier: "enterprise_partner", pricingModel: "enterprise", priceUsd: 499,
    license: "Enterprise Sovereign SLA", keyId: "ed25519:aegis-hsm-prod-01",
    sha256: "8f30c519e274ab68d1095cf372a48e61b90d3572c84e16f0a593b72d41c8e609",
    description: "Air-gapped financial compliance pack with dual-human quorum policies and hash-chained evidence export.",
    permissions: { readPaths: ["core/", "audit/"], writePaths: ["exports/"], network: "none", requiresP10Approval: true },
  },
  {
    id: "hipaa-clinical-intake-pack", name: "Clinical Operations & PHI Guardrail System", kind: "industry_enterprise_solution", categoryLabel: "Enterprise & Industry Solutions",
    version: "2.2.0", publisher: "Veridian Health Partners", publisherTier: "enterprise_partner", pricingModel: "enterprise", priceUsd: 399,
    license: "Enterprise Sovereign SLA", keyId: "ed25519:veridian-hsm-03",
    sha256: "6c91b408d372ef51a8046bc921e73d50f8a41926b73c05e8d149a63f20b7c518",
    description: "Healthcare workflow automation with local-only PHI redaction and audit-locked retention policies.",
    permissions: { readPaths: ["workflows/"], writePaths: ["audit_bundles/"], network: "none", requiresP10Approval: true },
  },
  {
    id: "nocode-crud-launchpad", name: "Guided Internal Tool Scaffold Skill", kind: "agent_skill", categoryLabel: "Agent Skills",
    version: "1.5.0", publisher: "CraftWorks AI", publisherTier: "verified_third_party", pricingModel: "one_time", priceUsd: 25,
    license: "Commercial Creator (85/15)", keyId: "ed25519:craftworks-verified-07",
    sha256: "4a85e217c903df64b1825ae7309cd418f7b20635e914a82d05c73b91f46e82c3",
    description: "Turns plain-language business forms and approval tables into accessible React + FastAPI apps.",
    permissions: { readPaths: ["templates/"], writePaths: ["app_scaffold/"], network: "none", requiresP10Approval: false },
  },
  {
    id: "secops-sbom-sentinel", name: "Zero-Egress CycloneDX & CVE Triage Agent", kind: "ai_agent", categoryLabel: "AI Agents",
    version: "1.1.3", publisher: "SignalForge Security", publisherTier: "verified_third_party", pricingModel: "free", priceUsd: 0,
    license: "MIT", keyId: "ed25519:signalforge-oss-05",
    sha256: "1e57d904a826bc31f7094ed825a61c49b3f80721d64e93a0c518b74e29d60f37",
    description: "Offline dependency graph auditor mapping CVEs to reachable call sites without external telemetry.",
    permissions: { readPaths: ["pyproject.toml", "package.json", "core/"], writePaths: [], network: "none", requiresP10Approval: false },
  },
];

const PUBLISH_STEPS = [
  {
    step: "01", title: "Author SDK Extension Manifest",
    summary: "Declare typed tools, SemVer version, SPDX license, and explicit read/write/network scopes in keelway.package/v1.",
    code: `await client.platform.registerExtension({\n  id: "acme-sql-auditor", kind: "agent_skill", version: "1.0.0",\n  permissions: { read_paths: ["migrations/"], write_paths: [], network: "none" }\n});`,
  },
  {
    step: "02", title: "Pre-Publish Security Review",
    summary: "Deterministic scanner blocks prompt-injection phrases, shell=True / eval() sinks, traversal paths, and live secrets.",
    code: `const report = await client.platform.scanMarketplacePackage(manifest);\n// => { passed: true, risk_grade: "A", findings_count: 0 }`,
  },
  {
    step: "03", title: "Ed25519 Sign & SemVer Publish",
    summary: "Canonical JSON payload is hashed (SHA-256) and signed with your verified publisher Ed25519 key.",
    code: `const signed = await client.platform.publishMarketplacePackage({\n  ...manifest, publisher_tier: "verified_third_party", pricing_model: "monthly", price_usd: 19\n});`,
  },
  {
    step: "04", title: "85% Creator Payout & Hub Sync",
    summary: "Verified 3rd-party creators keep 85% of gross package revenue (85% Creator / 15% Platform) with instant workspace install.",
    code: `# Instant availability across CLI, Studio (:7420), and /app Hub\nkeelway marketplace list --query acme-sql-auditor`,
  },
];

function formatPriceBadge(pkg: CatalogPackage): string {
  if (pkg.pricingModel === "free") return "$0 · Free";
  if (pkg.pricingModel === "monthly") return `$${pkg.priceUsd}/mo`;
  if (pkg.pricingModel === "one_time") return `$${pkg.priceUsd} one-time`;
  return `$${pkg.priceUsd}/mo · Enterprise`;
}

function formatSplitSummary(pkg: CatalogPackage): string {
  if (pkg.publisherTier === "first_party") {
    return pkg.priceUsd === 0
      ? "100% OpenCore First-Party ($0.00)"
      : `100% First-Party Sorvex Labs ($${pkg.priceUsd.toFixed(2)})`;
  }
  const creator = (pkg.priceUsd * 0.85).toFixed(2);
  const platform = (pkg.priceUsd * 0.15).toFixed(2);
  return pkg.publisherTier === "enterprise_partner"
    ? `85% Creator / 15% Platform ($${creator} Partner / $${platform} Platform SLA)`
    : `85% Creator / 15% Platform ($${creator} Creator / $${platform} Platform)`;
}

export function MarketplaceCatalogExplorer() {
  const [category, setCategory] = useState<MarketplaceCategoryId>("all");
  const [publisherFilter, setPublisherFilter] = useState<PublisherTierFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string>(MARKETPLACE_PACKAGES[0].id);
  const [copiedKey, setCopiedKey] = useState<"cli" | "sdk" | null>(null);
  const [activePublishStep, setActivePublishStep] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const q = new URLSearchParams(window.location.search).get("q")?.trim();
    if (q) {
      setSearch(q);
      const exact = MARKETPLACE_PACKAGES.find((p) => p.id === q);
      if (exact) setSelectedId(exact.id);
    }
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return MARKETPLACE_PACKAGES.filter((pkg) => {
      if (category !== "all" && pkg.kind !== category) return false;
      if (publisherFilter !== "all" && pkg.publisherTier !== publisherFilter) return false;
      if (!q) return true;
      const hay = `${pkg.name} ${pkg.id} ${pkg.description} ${pkg.publisher} ${pkg.license}`.toLowerCase();
      return hay.includes(q);
    });
  }, [category, publisherFilter, search]);

  const selected = useMemo(
    () =>
      filtered.find((p) => p.id === selectedId) ??
      MARKETPLACE_PACKAGES.find((p) => p.id === selectedId) ??
      MARKETPLACE_PACKAGES[0],
    [filtered, selectedId]
  );

  const cliSnippet = `keelway marketplace list --kind ${selected.kind}\nkeelway hub --install ${selected.id}`;
  const sdkSnippet = `import { KeelwayClient } from "@keelway/sdk";\n\nconst client = new KeelwayClient({ apiKey: process.env.KEELWAY_API_KEY });\nconst receipt = await client.platform.installMarketplacePackage("${selected.id}", {\n  workspaceId: "default",\n});`;

  const copyText = async (target: "cli" | "sdk", content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedKey(target);
      trackEvent("code_snippet_copied", { surface: "marketplace", snippet: `${target}:${selected.id}` });
      setTimeout(() => setCopiedKey(null), 1800);
    } catch {
      // Clipboard unavailable in headless environments
    }
  };

  return (
    <div className="space-y-12">
      {/* Filter & Search Control Bar */}
      <div className="rounded-md border border-border-strong bg-surface p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-dim" aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search Marketplace agents, skills, plugins, and workflows"
              placeholder="Search packages by name, ID, publisher, or SPDX license (Apache-2.0, MIT)..."
              className="min-h-[44px] w-full rounded-sm border border-border-strong bg-canvas pl-10 pr-4 text-sm text-fg placeholder:text-fg-dim"
            />
          </div>
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by publisher tier">
            {PUBLISHER_FILTERS.map((pf) => {
              const active = publisherFilter === pf.id;
              return (
                <button
                  key={pf.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setPublisherFilter(pf.id)}
                  className={cn(
                    "min-h-[40px] rounded-sm border px-3 font-mono text-xs transition-colors duration-150",
                    active
                      ? "border-border-strong bg-surface-elevated font-semibold text-fg"
                      : "border-border-subtle bg-canvas text-fg-muted hover:border-border-strong hover:text-fg"
                  )}
                >
                  {pf.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border-subtle pt-4" role="group" aria-label="Filter by Marketplace category">
          {CATEGORIES.map((cat) => {
            const active = category === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                aria-pressed={active}
                onClick={() => setCategory(cat.id)}
                className={cn(
                  "min-h-[40px] rounded-sm border px-3 text-xs font-medium transition-colors duration-150",
                  active ? "border-fg bg-fg text-canvas" : "border-border-subtle bg-canvas text-fg-muted hover:border-border-strong hover:text-fg"
                )}
              >
                {cat.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Catalog Grid + Sticky Security & Install Inspector */}
      <div className="grid gap-8 lg:grid-cols-12 lg:items-start">
        <div className="min-w-0 space-y-3 lg:col-span-7">
          <div className="flex items-center justify-between font-mono text-xs text-fg-muted">
            <span>SHOWING {filtered.length} OF {MARKETPLACE_PACKAGES.length} VERIFIED PACKAGES (keelway.package/v1)</span>
            <span>RISK GRADE A ENFORCED</span>
          </div>

          {filtered.length === 0 ? (
            <div className="rounded-md border border-border-subtle bg-surface p-8 text-center">
              <p className="text-sm text-fg-muted">No packages matched your current category, publisher, and query filters.</p>
              <button
                type="button"
                onClick={() => { setCategory("all"); setPublisherFilter("all"); setSearch(""); }}
                className="kw-btn kw-btn-secondary mt-4"
              >
                Reset Catalog Filters
              </button>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {filtered.map((pkg) => {
                const isSelected = selected.id === pkg.id;
                return (
                  <button
                    key={pkg.id}
                    type="button"
                    onClick={() => { setSelectedId(pkg.id); trackEvent("marketplace_package_scanned", { package_id: pkg.id }); }}
                    aria-pressed={isSelected}
                    className={cn(
                      "flex flex-col justify-between rounded-md border p-4 text-left transition-colors duration-150",
                      isSelected ? "border-teal-accent bg-surface-elevated" : "border-border-subtle bg-surface hover:border-border-strong"
                    )}
                  >
                    <div>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="chip-neutral rounded-sm px-2 py-0.5">{pkg.categoryLabel}</span>
                        <span className="chip-neutral rounded-sm px-2 py-0.5 font-mono text-[11px] font-semibold">
                          {formatPriceBadge(pkg)}
                        </span>
                      </div>
                      <h2 className="mt-3 text-base font-bold text-fg">{pkg.name}</h2>
                      <p className="mt-0.5 font-mono text-[11px] text-fg-dim">{pkg.id} · v{pkg.version} · {pkg.publisher}</p>
                      <p className="mt-2 text-xs leading-relaxed text-fg-muted">{pkg.description}</p>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-3 font-mono text-[11px]">
                      <span className="inline-flex items-center gap-1 text-teal-accent">
                        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                        Ed25519 Signed
                      </span>
                      <span className="text-fg-muted">{pkg.license}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Interactive Package Security & Install Drawer / Inspector */}
        <aside
          aria-label="Package Security and Install Inspector"
          className="rounded-md border border-border-strong bg-surface p-5 sm:p-6 lg:sticky lg:top-24 lg:col-span-5 min-w-0"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle pb-4">
            <div>
              <span className="font-mono text-[11px] uppercase tracking-wider text-teal-accent">PACKAGE SECURITY &amp; INSTALL INSPECTOR</span>
              <h3 className="mt-1 text-xl font-bold text-fg">{selected.name}</h3>
              <p className="font-mono text-xs text-fg-muted">{selected.id}@{selected.version} · {selected.publisher}</p>
            </div>
            <span className="chip-teal rounded-sm px-2.5 py-1">Ed25519 Signed</span>
          </div>

          <div className="mt-4 space-y-2.5 rounded-sm border border-border-subtle bg-canvas p-3.5 text-xs">
            <div className="flex items-center justify-between font-mono">
              <span className="font-semibold text-fg">Pre-Publish Security Scan: PASSED</span>
              <span className="chip-teal rounded-sm px-2 py-0.5">GRADE A</span>
            </div>
            <p className="text-fg-muted">0 prompt-injection · 0 shell-exfil · 0 live secrets · least-privilege permission scope</p>
            <div className="space-y-1 border-t border-border-subtle pt-2 font-mono text-[11px]">
              <div className="flex justify-between gap-2">
                <span className="text-fg-dim">Publisher Signing Key:</span>
                <span className="text-fg">{selected.keyId}</span>
              </div>
              <div>
                <span className="text-fg-dim">SHA-256 Digest: </span>
                <span className="break-all text-fg">{selected.sha256}</span>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <span className="chip-neutral rounded-sm px-2 py-0.5">read: {selected.permissions.readPaths.join(", ") || "none"}</span>
                <span className="chip-neutral rounded-sm px-2 py-0.5">write: {selected.permissions.writePaths.join(", ") || "read-only"}</span>
                <span className="chip-neutral rounded-sm px-2 py-0.5">net: {selected.permissions.network}</span>
                <span className="chip-neutral rounded-sm px-2 py-0.5">
                  {selected.permissions.requiresP10Approval ? "P-10 Human Gate Required" : "Zero-Mutation Safe"}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-sm border border-border-subtle bg-canvas p-3.5 text-xs">
            <div className="flex items-center justify-between font-mono">
              <span className="text-fg-dim">License &amp; Monetization</span>
              <span className="font-semibold text-fg">{selected.license}</span>
            </div>
            <p className="mt-1 font-mono text-[11px] text-teal-accent">{formatSplitSummary(selected)}</p>
          </div>

          <div className="mt-4 space-y-3">
            <div>
              <div className="mb-1.5 flex items-center justify-between font-mono text-[11px]">
                <span className="inline-flex items-center gap-1.5 text-fg-muted">
                  <Terminal className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
                  CLI Discovery &amp; Workspace Hub Install
                </span>
                <button
                  type="button"
                  onClick={() => void copyText("cli", cliSnippet)}
                  className="inline-flex min-h-[32px] items-center gap-1 rounded-sm border border-border-strong bg-canvas px-2 text-fg hover:border-teal-accent"
                >
                  {copiedKey === "cli" ? <Check className="h-3 w-3 text-teal-accent" aria-hidden="true" /> : <Copy className="h-3 w-3" aria-hidden="true" />}
                  <span>{copiedKey === "cli" ? "Copied" : "Copy CLI"}</span>
                </button>
              </div>
              <pre role="region" aria-label="CLI install snippet" tabIndex={0} className="overflow-x-auto rounded-sm border border-border-subtle bg-canvas p-3 font-mono text-[11px] text-fg"><code>{cliSnippet}</code></pre>
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between font-mono text-[11px]">
                <span className="inline-flex items-center gap-1.5 text-fg-muted">
                  <FileCode2 className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
                  Official TypeScript SDK (@keelway/sdk)
                </span>
                <button
                  type="button"
                  onClick={() => void copyText("sdk", sdkSnippet)}
                  className="inline-flex min-h-[32px] items-center gap-1 rounded-sm border border-border-strong bg-canvas px-2 text-fg hover:border-teal-accent"
                >
                  {copiedKey === "sdk" ? <Check className="h-3 w-3 text-teal-accent" aria-hidden="true" /> : <Copy className="h-3 w-3" aria-hidden="true" />}
                  <span>{copiedKey === "sdk" ? "Copied" : "Copy SDK"}</span>
                </button>
              </div>
              <pre role="region" aria-label="SDK install snippet" tabIndex={0} className="overflow-x-auto rounded-sm border border-border-subtle bg-canvas p-3 font-mono text-[11px] text-fg"><code>{sdkSnippet}</code></pre>
            </div>
          </div>
        </aside>
      </div>

      {/* Interactive "Publish Your Own Agent, Skill, or Plugin" Preview Strip */}
      <section aria-labelledby="publish-extension-heading" className="rounded-md border border-border-strong bg-surface p-6 sm:p-8">
        <div className="flex flex-col justify-between gap-4 border-b border-border-subtle pb-6 lg:flex-row lg:items-end">
          <div>
            <span className="chip-teal rounded-sm px-2.5 py-1">CREATOR &amp; PARTNER SDK</span>
            <h2 id="publish-extension-heading" className="mt-3 text-2xl font-bold text-fg">
              Publish Your Own Agent, Skill, or Plugin
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-fg-muted">
              Ship SemVer-versioned extensions with mandatory pre-publication security scanning,
              Ed25519 manifest signing, and transparent <strong className="text-fg">85% creator payout</strong> (85% Creator / 15% Platform).
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/governance#manifest-drift" className="kw-btn kw-btn-secondary">
              <Lock className="h-4 w-4 text-teal-accent" aria-hidden="true" />
              <span>Test Pre-Publish Security Scanner</span>
            </Link>
            <Link href="/#quickstart" className="kw-btn kw-btn-primary">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              <span>Launch in Local Dev Tool</span>
            </Link>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          <div className="grid min-w-0 gap-2.5 sm:grid-cols-2 lg:col-span-6">
            {PUBLISH_STEPS.map((item, idx) => {
              const active = activePublishStep === idx;
              return (
                <button
                  key={item.step}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setActivePublishStep(idx)}
                  className={cn(
                    "rounded-sm border p-4 text-left transition-colors duration-150",
                    active ? "border-teal-accent bg-surface-elevated" : "border-border-subtle bg-canvas hover:border-border-strong"
                  )}
                >
                  <div className="flex items-center justify-between font-mono text-xs">
                    <span className="text-teal-accent">STEP {item.step}</span>
                    <Package className="h-3.5 w-3.5 text-fg-dim" aria-hidden="true" />
                  </div>
                  <h3 className="mt-2 text-sm font-bold text-fg">{item.title}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-fg-muted">{item.summary}</p>
                </button>
              );
            })}
          </div>

          <div className="flex min-w-0 flex-col justify-between rounded-sm border border-border-subtle bg-canvas p-4 lg:col-span-6">
            <div className="flex items-center justify-between font-mono text-xs text-fg-muted">
              <span>STEP {PUBLISH_STEPS[activePublishStep].step} · {PUBLISH_STEPS[activePublishStep].title.toUpperCase()}</span>
              <span className="text-teal-accent">keelway.package/v1</span>
            </div>
            <pre role="region" aria-label="Package manifest preview" tabIndex={0} className="mt-3 overflow-x-auto rounded-sm border border-border-subtle bg-surface p-4 font-mono text-xs text-fg">
              <code>{PUBLISH_STEPS[activePublishStep].code}</code>
            </pre>
            <p className="mt-3 font-mono text-[11px] text-fg-dim">
              Every release is immutable per SemVer tag and verified offline via Ed25519 signature + SHA-256 digest before workspace activation.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
