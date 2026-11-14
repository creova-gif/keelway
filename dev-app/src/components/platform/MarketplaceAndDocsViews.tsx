import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type {
  EnterpriseRetentionMode,
  MarketplacePublishPayload,
} from "@/lib/platformApi";
import {
  MARKETPLACE_CATEGORIES,
  SDLC_STAGES,
  scanMarketplacePackageClient,
  type DocGuideItem,
  type ExperienceMode,
  type MarketplaceCategoryId,
  type MarketplacePackageItem,
  type MarketplaceScanReport,
} from "@/lib/platformData";

export interface MarketplaceWorkspaceViewProps {
  packages: MarketplacePackageItem[];
  installedPackageIds: string[];
  onToggleInstallPackage: (packageId: string) => void;
  onPublishVerifiedPackage: (
    pkg: MarketplacePackageItem,
    publishPayload: MarketplacePublishPayload,
  ) => void;
}

export function MarketplaceWorkspaceView({
  packages,
  installedPackageIds,
  onToggleInstallPackage,
  onPublishVerifiedPackage,
}: MarketplaceWorkspaceViewProps): React.JSX.Element {
  const [selectedCategory, setSelectedCategory] = useState<MarketplaceCategoryId | "all">("all");
  const [pkgName, setPkgName] = useState("");
  const [pkgCategory, setPkgCategory] = useState<MarketplaceCategoryId>("agent_skill");
  const [pkgInstructions, setPkgInstructions] = useState(
    "Audit workspace schemas in read-only mode and summarize migration steps.",
  );
  const [pkgWritePaths, setPkgWritePaths] = useState("reports/*");
  const [scanReport, setScanReport] = useState<MarketplaceScanReport | null>(null);
  const [publishedCurrentScan, setPublishedCurrentScan] = useState(false);

  const visiblePackages = packages.filter((p) =>
    selectedCategory === "all" ? true : p.category === selectedCategory,
  );

  const evaluateCandidate = () => {
    const cleanName = pkgName.trim() || "Untitled Extension";
    const report = scanMarketplacePackageClient({
      name: cleanName,
      category: pkgCategory,
      publisherTier: "verified_third_party",
      instructions: pkgInstructions,
      writePaths: pkgWritePaths,
      networkFull: false,
      requiresP10Approval: true,
    });
    const slug =
      cleanName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 32) || "extension";
    const id = `pkg-custom-${slug}-${Date.now()}`;
    const writePathsList = pkgWritePaths
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const pkg: MarketplacePackageItem = {
      id,
      name: cleanName,
      category: pkgCategory,
      publisher: "Workspace Creator",
      publisherTier: "verified_third_party",
      revenueSplitLabel: report.revenueSplitLabel,
      priceLabel: "$14 / mo",
      summary: pkgInstructions.trim().slice(0, 140),
      manifestSha256: report.manifestSha256,
      securityVerified: true,
    };
    const publishPayload: MarketplacePublishPayload = {
      id,
      name: cleanName,
      kind: pkgCategory,
      version: "1.0.0",
      publisher: "Workspace Creator",
      publisher_tier: "verified_third_party",
      pricing_model: "monthly",
      price_usd: 14,
      description: pkgInstructions.trim(),
      permissions: {
        read_paths: ["./"],
        write_paths: writePathsList,
        network: "none",
        requires_p10_approval: true,
      },
    };
    return { report, pkg, publishPayload };
  };

  const handleScanOnly = () => {
    const { report } = evaluateCandidate();
    setScanReport(report);
    setPublishedCurrentScan(false);
  };

  const handlePublishScanned = () => {
    const { report, pkg, publishPayload } = evaluateCandidate();
    setScanReport(report);
    if (!report.passed) {
      setPublishedCurrentScan(false);
      return;
    }
    onPublishVerifiedPackage(pkg, publishPayload);
    setPublishedCurrentScan(true);
  };

  const handleValidateAndPublish = (e: React.FormEvent) => {
    e.preventDefault();
    handlePublishScanned();
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Keelway Marketplace &amp; Security Validator
          </h1>
          <p className="text-xs text-fg-muted">
            Discover 1st-party and verified 3rd-party agents, multi-agent teams, skills, plugins, workflows, dev tools, and enterprise packs—every listing gated by deterministic pre-publish security scanning.
          </p>
        </div>
        <SemanticBadge kind="passed" labelOverride={`${installedPackageIds.length} Installed`} />
      </div>

      {/* 7-Category Filter Bar */}
      <div
        role="group"
        aria-label="Marketplace categories"
        className="flex flex-wrap items-center gap-1.5"
      >
        <button
          type="button"
          aria-pressed={selectedCategory === "all"}
          onClick={() => setSelectedCategory("all")}
          className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
            selectedCategory === "all"
              ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
              : "border-border bg-surface text-fg-muted hover:text-fg"
          }`}
        >
          All Categories
        </button>
        {MARKETPLACE_CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            type="button"
            aria-pressed={selectedCategory === cat.id}
            onClick={() => setSelectedCategory(cat.id)}
            className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
              selectedCategory === cat.id
                ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
                : "border-border bg-surface text-fg-muted hover:text-fg"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Catalog Grid */}
      <section aria-label="Marketplace catalog listings" className="grid gap-3 md:grid-cols-2">
        <h2 className="sr-only">Verified Packages</h2>
        {visiblePackages.map((pkg) => {
          const isInstalled = installedPackageIds.includes(pkg.id);
          return (
            <article
              key={pkg.id}
              className="flex flex-col justify-between gap-3 rounded-md border border-border-strong bg-surface p-3.5"
            >
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-fg">{pkg.name}</h3>
                  <span className="font-mono text-xs font-semibold text-teal-accent">
                    {pkg.priceLabel}
                  </span>
                </div>
                <p className="text-xs text-fg-muted">{pkg.summary}</p>
                <div className="flex flex-wrap items-center gap-1.5 pt-1 font-mono text-[10px]">
                  <span className="rounded-xs border border-ok/40 bg-ok-subtle px-1.5 py-0.5 text-ok">
                    SHA-256 + Prompt-Injection Verified
                  </span>
                  <span className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 text-fg-muted">
                    {pkg.revenueSplitLabel}
                  </span>
                  <code className="text-fg-dim">{pkg.manifestSha256}</code>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2 border-t border-border pt-2">
                <span className="text-[11px] text-fg-dim">{`By ${pkg.publisher}`}</span>
                <Button
                  size="sm"
                  variant={isInstalled ? "secondary" : "primary"}
                  aria-label={`${isInstalled ? "Uninstall" : "Install"} package ${pkg.name}`}
                  onClick={() => onToggleInstallPackage(pkg.id)}
                >
                  {isInstalled ? "Installed · Uninstall" : "Install"}
                </Button>
              </div>
            </article>
          );
        })}
      </section>

      {/* Pre-Publication Security Scanner & Publisher */}
      <section
        aria-label="Validate and publish package"
        className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-fg">
              Validate &amp; Publish Package (MarketplaceSecurityScanner)
            </h2>
            <p className="text-xs text-fg-muted">
              Scans manifests and prompts for prompt-injection, dangerous shell/eval hooks, wildcard permissions, and leaked secrets before listing.
            </p>
          </div>
          <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-2 py-0.5 font-mono text-[11px] text-teal-accent">
            Verified Split: 85% Creator / 15% Platform
          </span>
        </div>

        <form onSubmit={handleValidateAndPublish} className="grid gap-3 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Package name</span>
            <input
              type="text"
              aria-label="Package name"
              value={pkgName}
              onChange={(e) => setPkgName(e.target.value)}
              placeholder="e.g. OpenAPI Contract Verifier"
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Package category</span>
            <select
              aria-label="Package category"
              value={pkgCategory}
              onChange={(e) => setPkgCategory(e.target.value as MarketplaceCategoryId)}
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
            >
              {MARKETPLACE_CATEGORIES.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted">
            <span>Declared write paths</span>
            <input
              type="text"
              aria-label="Declared write paths"
              value={pkgWritePaths}
              onChange={(e) => setPkgWritePaths(e.target.value)}
              className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-fg-muted md:col-span-3">
            <span>Manifest instructions &amp; execution hooks</span>
            <textarea
              rows={2}
              aria-label="Manifest instructions & execution hooks"
              value={pkgInstructions}
              onChange={(e) => setPkgInstructions(e.target.value)}
              className="rounded-sm border border-border-control bg-canvas px-2.5 py-1.5 font-mono text-xs text-fg"
            />
          </label>
          <div className="flex flex-wrap items-center gap-2 md:col-span-3">
            <Button type="button" size="sm" variant="secondary" onClick={handleScanOnly}>
              Run Security Scan
            </Button>
            <Button type="submit" size="sm" variant="primary">
              Scan &amp; Publish Package
            </Button>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={!scanReport || !scanReport.passed || publishedCurrentScan}
              onClick={handlePublishScanned}
            >
              Publish Verified Package to Workspace
            </Button>
          </div>
        </form>

        {scanReport ? (
          scanReport.passed ? (
            <div
              role="status"
              className="rounded-sm border border-ok/40 bg-ok-subtle px-3 py-2 text-xs text-fg"
            >
              <span className="font-semibold text-ok">
                Pre-Publish Security Scan Passed · Risk Grade A
              </span>{" "}
              — {publishedCurrentScan ? "Published" : "Ready to publish"} with{" "}
              <code className="font-mono">{scanReport.manifestSha256}</code> (
              {scanReport.revenueSplitLabel}).
            </div>
          ) : (
            <div
              role="alert"
              className="space-y-1 rounded-sm border border-danger/50 bg-danger-subtle px-3 py-2 text-xs text-fg"
            >
              <div className="font-semibold text-danger">
                Publication Blocked by MarketplaceSecurityScanner (Risk Grade: BLOCKED)
              </div>
              <ul className="list-inside list-disc font-mono text-[11px]">
                {scanReport.findings.map((f) => (
                  <li key={f.code}>
                    <strong>{f.code}</strong>: {f.message}
                  </li>
                ))}
              </ul>
            </div>
          )
        ) : null}
      </section>
    </div>
  );
}

export interface DocumentationWorkspaceViewProps {
  experienceMode: ExperienceMode;
  guides: DocGuideItem[];
}

export function DocumentationWorkspaceView({
  experienceMode,
  guides,
}: DocumentationWorkspaceViewProps): React.JSX.Element {
  const [quadrant, setQuadrant] = useState<"all" | DocGuideItem["quadrant"]>("all");
  const filtered = guides.filter((g) => (quadrant === "all" ? true : g.quadrant === quadrant));

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">
            Documentation Knowledge Base &amp; 9-Stage SDLC
          </h1>
          <p className="text-xs text-fg-muted">
            {experienceMode === "non_coder"
              ? "Guided tutorials and plain-language explanations synced with your live project."
              : "Diataxis technical documentation + canonical cross-agent engineering contract (Antigravity · Claude Code · Devin · gstack)."}
          </p>
        </div>
        <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-2 py-1 font-mono text-[11px] text-teal-accent">
          Antigravity · Claude Code · Devin · gstack
        </span>
      </div>

      <div role="group" aria-label="Diataxis quadrants" className="flex flex-wrap gap-1.5">
        {(["all", "Tutorial", "How-To", "Reference", "Explanation"] as const).map((q) => (
          <button
            key={q}
            type="button"
            aria-pressed={quadrant === q}
            onClick={() => setQuadrant(q)}
            className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
              quadrant === q
                ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
                : "border-border bg-surface text-fg-muted hover:text-fg"
            }`}
          >
            {q === "all" ? "All Docs" : q}
          </button>
        ))}
      </div>

      <section aria-label="Diataxis guides" className="grid gap-3 md:grid-cols-2">
        <h2 className="sr-only">Knowledge Base Guides</h2>
        {filtered.map((doc) => (
          <article key={doc.id} className="space-y-1.5 rounded-md border border-border bg-surface p-3.5">
            <span className="font-mono text-[10px] uppercase text-teal-accent">{doc.quadrant}</span>
            <h3 className="text-xs font-semibold text-fg">{doc.title}</h3>
            <p className="text-xs text-fg-muted">{doc.summary}</p>
          </article>
        ))}
      </section>

      <section aria-label="9-stage autonomous engineering workflow" className="space-y-2.5">
        <h2 className="text-sm font-semibold text-fg">
          9-Stage Autonomous Software Development Lifecycle
        </h2>
        <div className="grid gap-2 md:grid-cols-3">
          {SDLC_STAGES.map((st) => (
            <div key={st.stageNumber} className="rounded-sm border border-border bg-surface p-2.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono font-semibold text-teal-accent">{`Stage ${st.stageNumber}`}</span>
                <SemanticBadge
                  kind={st.gateStatus === "p10_human_gate" ? "needs-approval" : "passed"}
                  labelOverride={st.gateStatus === "p10_human_gate" ? "P-10 Gate" : "Verified"}
                />
              </div>
              <div className="mt-1 font-medium text-fg">{st.title}</div>
              <div className="mt-0.5 font-mono text-[10px] text-fg-dim">
                {`${st.leadAgent} · ${st.crossAgentHarness}`}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export function SecurityPostureBanner({
  installedPackagesCount,
  retentionMode = "standard_30d",
  onRetentionModeChange,
}: {
  installedPackagesCount: number;
  retentionMode?: EnterpriseRetentionMode;
  onRetentionModeChange?: (mode: EnterpriseRetentionMode) => void;
}): React.JSX.Element {
  return (
    <section
      aria-label="Security governance posture summary"
      className="border-b border-border bg-chrome px-4 py-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-sm font-semibold text-fg">
            Security Governance &amp; Sovereign Posture
          </h1>
          <p className="text-xs text-fg-muted">
            Unified RBAC, SQLite WAL tenant isolation, Ed25519 + SHA-256 package signing, and hash-chained Record audit ledger.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
          <span className="rounded-xs border border-ok/40 bg-ok-subtle px-2 py-0.5 text-ok">
            RBAC + Seatbelt Isolated
          </span>
          <span className="rounded-xs border border-ok/40 bg-ok-subtle px-2 py-0.5 text-ok">
            {`Ed25519 + SHA-256 Verified (${installedPackagesCount} pkgs)`}
          </span>
          <label className="inline-flex items-center gap-1.5 rounded-xs border border-border-control bg-surface px-2 py-0.5 text-fg">
            <span className="text-fg-muted">Retention:</span>
            <select
              aria-label="Enterprise data retention policy"
              value={retentionMode}
              onChange={(e) => onRetentionModeChange?.(e.target.value as EnterpriseRetentionMode)}
              className="bg-surface font-mono text-[11px] text-fg"
            >
              <option value="standard_30d">standard_30d (30-Day)</option>
              <option value="regulated_365d">regulated_365d (365-Day)</option>
              <option value="worm_7y">worm_7y (7-Year WORM)</option>
            </select>
          </label>
          <span className="rounded-xs border border-ochre/40 bg-ochre-subtle px-2 py-0.5 text-ochre">
            P-10 Human-Only Gate Active
          </span>
        </div>
      </div>
    </section>
  );
}
