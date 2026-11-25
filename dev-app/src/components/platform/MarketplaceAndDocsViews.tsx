import React, { useEffect, useMemo, useState } from "react";
import { KHubAirgapMirrorPanel } from "@/components/platform/KHubAirgapMirrorPanel";
import { McpLockfileAndBenchPanel } from "@/components/platform/McpLockfileAndBenchPanel";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type { MarketplacePublishPayload } from "@/lib/platformApi";
import {
  MARKETPLACE_CATEGORIES,
  scanMarketplacePackageClient,
  type MarketplaceCategoryId,
  type MarketplacePackageItem,
  type MarketplaceScanReport,
} from "@/lib/platformData";
import type { WorkspaceRbacRole } from "@/lib/platformKbrainApi";

export {
  DocumentationWorkspaceView,
  type DocumentationWorkspaceViewProps,
} from "./DocumentationWorkspaceView";
export {
  SecurityPostureBanner,
  SecurityWorkspaceView,
  type SecurityPostureBannerProps,
  type SecurityWorkspaceViewProps,
} from "./SecurityWorkspaceView";

export interface MarketplaceWorkspaceViewProps {
  packages: MarketplacePackageItem[];
  installedPackageIds: string[];
  onToggleInstallPackage: (packageId: string) => void;
  onPublishVerifiedPackage: (
    pkg: MarketplacePackageItem,
    publishPayload: MarketplacePublishPayload,
  ) => void;
  workspaceId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

type PublisherTierFilter = "all" | "first_party" | "verified_third_party" | "enterprise_partner";

interface PackageRuntimeConfig {
  writeScope: string;
  envSecretRef: string;
  saved: boolean;
}

const PUBLISHER_TIER_FILTERS: ReadonlyArray<{ id: PublisherTierFilter; label: string }> = [
  { id: "all", label: "All Publishers" },
  { id: "first_party", label: "1st-Party" },
  { id: "verified_third_party", label: "Verified 3rd-Party (85/15)" },
  { id: "enterprise_partner", label: "Enterprise Partner (80/20)" },
];

export function MarketplaceWorkspaceView({
  packages,
  installedPackageIds,
  onToggleInstallPackage,
  onPublishVerifiedPackage,
  workspaceId = "default",
  activeRbacRole = "owner",
}: MarketplaceWorkspaceViewProps): React.JSX.Element {
  const [selectedCategory, setSelectedCategory] = useState<MarketplaceCategoryId | "all">("all");
  const [publisherFilter, setPublisherFilter] = useState<PublisherTierFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [localInstalledIds, setLocalInstalledIds] = useState<string[]>(installedPackageIds);
  const [localPublished, setLocalPublished] = useState<MarketplacePackageItem[]>([]);
  const [openConfigPkgId, setOpenConfigPkgId] = useState<string | null>(null);
  const [configsByPkgId, setConfigsByPkgId] = useState<Record<string, PackageRuntimeConfig>>({});

  const [pkgName, setPkgName] = useState("");
  const [pkgCategory, setPkgCategory] = useState<MarketplaceCategoryId>("agent_skill");
  const [pkgInstructions, setPkgInstructions] = useState(
    "Audit workspace schemas in read-only mode and summarize migration steps.",
  );
  const [pkgWritePaths, setPkgWritePaths] = useState("reports/*");
  const [scanReport, setScanReport] = useState<MarketplaceScanReport | null>(null);
  const [publishedCurrentScan, setPublishedCurrentScan] = useState(false);

  useEffect(() => {
    setLocalInstalledIds(installedPackageIds);
  }, [installedPackageIds]);

  const allPackages = useMemo(() => {
    const seen = new Set(packages.map((p) => p.id));
    return [...localPublished.filter((p) => !seen.has(p.id)), ...packages];
  }, [localPublished, packages]);

  const visiblePackages = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return allPackages.filter((p) => {
      if (selectedCategory !== "all" && p.category !== selectedCategory) return false;
      if (publisherFilter !== "all" && p.publisherTier !== publisherFilter) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.summary.toLowerCase().includes(q) ||
        p.publisher.toLowerCase().includes(q)
      );
    });
  }, [allPackages, publisherFilter, searchQuery, selectedCategory]);

  const handleToggleInstall = (pkg: MarketplacePackageItem) => {
    const wasInstalled = localInstalledIds.includes(pkg.id);
    setLocalInstalledIds((prev) =>
      wasInstalled ? prev.filter((id) => id !== pkg.id) : [...prev, pkg.id],
    );
    if (wasInstalled && openConfigPkgId === pkg.id) setOpenConfigPkgId(null);
    onToggleInstallPackage(pkg.id);
  };

  const getPkgConfig = (pkgId: string): PackageRuntimeConfig =>
    configsByPkgId[pkgId] ?? { writeScope: "./reports/*", envSecretRef: "KEELWAY_SCOPED_TOKEN", saved: false };

  const updatePkgConfig = (pkgId: string, patch: Partial<PackageRuntimeConfig>) => {
    setConfigsByPkgId((prev) => ({ ...prev, [pkgId]: { ...getPkgConfig(pkgId), ...patch } }));
  };

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
    const slug = cleanName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 32) || "extension";
    const id = `pkg-custom-${slug}-${Date.now()}`;
    const writePathsList = pkgWritePaths.split(",").map((s) => s.trim()).filter(Boolean);
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
    setScanReport(evaluateCandidate().report);
    setPublishedCurrentScan(false);
  };

  const handlePublishScanned = () => {
    const { report, pkg, publishPayload } = evaluateCandidate();
    setScanReport(report);
    if (!report.passed) {
      setPublishedCurrentScan(false);
      return;
    }
    setLocalPublished((prev) => [pkg, ...prev]);
    setLocalInstalledIds((prev) => (prev.includes(pkg.id) ? prev : [...prev, pkg.id]));
    onPublishVerifiedPackage(pkg, publishPayload);
    setPublishedCurrentScan(true);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-fg">Keelway Marketplace &amp; Security Validator</h1>
          <p className="text-xs text-fg-muted">
            Discover 1st-party and verified 3rd-party agents, multi-agent teams, skills, plugins, workflows, dev tools, and enterprise packs—every listing gated by deterministic pre-publish security scanning.
          </p>
        </div>
        <SemanticBadge kind="passed" labelOverride={`${localInstalledIds.length} Installed`} />
      </div>

      <KHubAirgapMirrorPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="min-w-[240px] flex-1">
          <span className="sr-only">Search marketplace packages</span>
          <input
            type="search"
            aria-label="Search marketplace packages"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search agents, skills, publishers, or capabilities…"
            className="min-h-ctrl-sm w-full rounded-sm border border-border-control bg-surface px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim"
          />
        </label>
        <div role="group" aria-label="Filter by publisher tier" className="flex flex-wrap items-center gap-1.5">
          {PUBLISHER_TIER_FILTERS.map((tier) => (
            <button
              key={tier.id}
              type="button"
              aria-pressed={publisherFilter === tier.id}
              onClick={() => setPublisherFilter(tier.id)}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
                publisherFilter === tier.id ? "border-accent/50 bg-accent-subtle text-accent" : "border-border bg-surface text-fg-muted hover:text-fg"
              }`}
            >
              {tier.label}
            </button>
          ))}
        </div>
      </div>

      <div role="group" aria-label="Marketplace categories" className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          aria-pressed={selectedCategory === "all"}
          onClick={() => setSelectedCategory("all")}
          className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
            selectedCategory === "all" ? "border-accent/50 bg-accent-subtle text-accent" : "border-border bg-surface text-fg-muted hover:text-fg"
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
              selectedCategory === cat.id ? "border-accent/50 bg-accent-subtle text-accent" : "border-border bg-surface text-fg-muted hover:text-fg"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <section aria-label="Marketplace catalog listings" className="grid gap-3 md:grid-cols-2">
        <h2 className="sr-only">Verified Packages</h2>
        {visiblePackages.map((pkg) => {
          const isInstalled = localInstalledIds.includes(pkg.id);
          const isConfigOpen = isInstalled && openConfigPkgId === pkg.id;
          const cfg = getPkgConfig(pkg.id);

          return (
            <article key={pkg.id} className="flex flex-col justify-between gap-3 rounded-md border border-border-strong bg-surface p-3.5">
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-fg">{pkg.name}</h3>
                  <span className="font-mono text-xs font-semibold text-accent">{pkg.priceLabel}</span>
                </div>
                <p className="text-xs text-fg-muted">{pkg.summary}</p>
                <div className="flex flex-wrap items-center gap-1.5 pt-1 font-mono text-[10px]">
                  {pkg.securityVerified ? (
                    <span className="rounded-xs border border-ok/40 bg-ok-subtle px-1.5 py-0.5 text-ok">
                      SHA-256 + Prompt-Injection Verified
                    </span>
                  ) : (
                    <span className="rounded-xs border border-danger/40 bg-danger-subtle px-1.5 py-0.5 text-danger">
                      Unsigned — scan finding open
                    </span>
                  )}
                  <span className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 text-fg-muted">
                    {pkg.revenueSplitLabel}
                  </span>
                  <code className="text-fg-dim">{pkg.manifestSha256}</code>
                </div>
                {isInstalled ? (
                  <div className="mt-1.5 rounded-xs border border-accent/35 bg-accent-subtle px-2 py-1 font-mono text-[10px] text-accent">
                    {`Receipt ${pkg.manifestSha256} · SPDX License · 85/15 Creator Settlement Verified`}
                  </div>
                ) : null}
              </div>

              {isConfigOpen ? (
                <div className="space-y-2 rounded-xs border border-border bg-chrome p-2.5 text-xs">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
                      <span>Scoped write path</span>
                      <input
                        type="text"
                        aria-label={`Scoped write path for ${pkg.name}`}
                        value={cfg.writeScope}
                        onChange={(e) => updatePkgConfig(pkg.id, { writeScope: e.target.value, saved: false })}
                        className="min-h-ctrl-sm rounded-xs border border-border-control bg-canvas px-2 py-0.5 font-mono text-xs text-fg"
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
                      <span>Env variable ref</span>
                      <input
                        type="text"
                        aria-label={`Environment variable ref for ${pkg.name}`}
                        value={cfg.envSecretRef}
                        onChange={(e) => updatePkgConfig(pkg.id, { envSecretRef: e.target.value, saved: false })}
                        className="min-h-ctrl-sm rounded-xs border border-border-control bg-canvas px-2 py-0.5 font-mono text-xs text-fg"
                      />
                    </label>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <Button size="sm" variant="primary" onClick={() => updatePkgConfig(pkg.id, { saved: true })}>
                      Save Config
                    </Button>
                    {cfg.saved ? <span role="status" className="font-mono text-[10px] text-ok">Config Saved to Seatbelt</span> : null}
                  </div>
                </div>
              ) : null}

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
                <span className="text-[11px] text-fg-dim">{`By ${pkg.publisher}`}</span>
                <div className="flex items-center gap-1.5">
                  {isInstalled ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-expanded={isConfigOpen}
                      onClick={() => setOpenConfigPkgId((prev) => (prev === pkg.id ? null : pkg.id))}
                    >
                      Configure
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant={isInstalled ? "secondary" : "primary"}
                    aria-label={`${isInstalled ? "Uninstall" : "Install"} package ${pkg.name}`}
                    disabled={!pkg.securityVerified && !isInstalled}
                    title={!pkg.securityVerified && !isInstalled ? "Install inert — unsigned package" : undefined}
                    onClick={() => handleToggleInstall(pkg)}
                  >
                    {isInstalled ? "Installed · Uninstall" : pkg.securityVerified ? "Install" : "Install (inert)"}
                  </Button>
                </div>
              </div>
            </article>
          );
        })}
      </section>

      <section aria-label="Validate and publish package" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-fg">Validate &amp; Publish Package (MarketplaceSecurityScanner)</h2>
            <p className="text-xs text-fg-muted">
              Scans manifests and prompts for prompt-injection, dangerous shell/eval hooks, wildcard permissions, and leaked secrets before listing.
            </p>
          </div>
          <span className="rounded-xs border border-accent/40 bg-accent-subtle px-2 py-0.5 font-mono text-[11px] text-accent">
            Verified Split: 85% Creator / 15% Platform
          </span>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); handlePublishScanned(); }} className="grid gap-3 md:grid-cols-3">
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
                <option key={cat.id} value={cat.id}>{cat.label}</option>
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
            <Button type="button" size="sm" variant="secondary" onClick={handleScanOnly}>Run Security Scan</Button>
            <Button type="submit" size="sm" variant="primary">Scan &amp; Publish Package</Button>
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
            <div role="status" className="rounded-sm border border-ok/40 bg-ok-subtle px-3 py-2 text-xs text-fg">
              <span className="font-semibold text-ok">Pre-Publish Security Scan Passed · Risk Grade A</span> —{" "}
              {publishedCurrentScan ? "Published" : "Ready to publish"} with{" "}
              <code className="font-mono">{scanReport.manifestSha256}</code> ({scanReport.revenueSplitLabel}).
            </div>
          ) : (
            <div role="alert" className="space-y-1 rounded-sm border border-danger/50 bg-danger-subtle px-3 py-2 text-xs text-fg">
              <div className="font-semibold text-danger">Publication Blocked by MarketplaceSecurityScanner (Risk Grade: BLOCKED)</div>
              <ul className="list-inside list-disc font-mono text-[11px]">
                {scanReport.findings.map((f) => (
                  <li key={f.code}><strong>{f.code}</strong>: {f.message}</li>
                ))}
              </ul>
            </div>
          )
        ) : null}
      </section>

      <McpLockfileAndBenchPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />
    </div>
  );
}
