import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { fetchPlatformSbom, type PlatformSbomSummary } from "@/lib/platformKflowApi";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface CycloneDxSbomPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

export function CycloneDxSbomPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: CycloneDxSbomPanelProps): React.JSX.Element {
  const [sbom, setSbom] = useState<PlatformSbomSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const handleGenerateAndVerify = async () => {
    if (loading) return;
    setLoading(true);
    setErrorBanner(null);
    try {
      const result = await fetchPlatformSbom(workspaceId, activeRbacRole);
      setSbom(result);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to generate or verify CycloneDX 1.5 SBOM.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      aria-label="CycloneDX 1.5 SBOM and supply-chain provenance"
      className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">CycloneDX 1.5 SBOM &amp; Supply-Chain Provenance</h2>
          <p className="text-xs text-fg-muted">
            Generate deterministic Software Bill of Materials manifests and verify cryptographic SHA-256 Merkle component provenance.
          </p>
        </div>
        <Button size="sm" variant="primary" loading={loading} onClick={() => { void handleGenerateAndVerify(); }}>
          Generate &amp; Verify CycloneDX 1.5 SBOM
        </Button>
      </div>

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          {errorBanner}
        </div>
      ) : null}

      {sbom ? (
        <div className="space-y-3">
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-sm border border-border bg-chrome px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">Format &amp; Spec</div>
              <div className="mt-0.5 font-mono text-xs font-semibold text-fg">{`${sbom.bom_format} · v${sbom.spec_version}`}</div>
            </div>
            <div className="rounded-sm border border-border bg-chrome px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">Provenance Status</div>
              <div className="mt-0.5">
                <SemanticBadge
                  kind={sbom.verified ? "passed" : "failed"}
                  labelOverride={sbom.verified ? "VERIFIED" : sbom.verification_status}
                />
              </div>
            </div>
            <div className="rounded-sm border border-border bg-chrome px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">Component Inventory</div>
              <div className="mt-0.5 font-mono text-xs font-semibold text-accent">{`${sbom.component_count} components`}</div>
            </div>
            <div className="rounded-sm border border-border bg-chrome px-3 py-2">
              <div className="font-mono text-[10px] uppercase text-fg-muted">Root Merkle Digest</div>
              <code className="mt-0.5 block max-w-[260px] truncate font-mono text-xs font-semibold text-accent">
                {sbom.root_digest_sha256}
              </code>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-border bg-canvas px-3 py-2 font-mono text-[11px] text-fg-muted">
            <span className="truncate">{`Serial: ${sbom.serial_number}`}</span>
            <code className="max-w-[260px] truncate text-fg">{sbom.provenance_signature}</code>
          </div>
        </div>
      ) : (
        <div className="rounded-xs border border-border bg-chrome px-3 py-2.5 font-mono text-xs text-fg-muted">
          Ready to synthesize CycloneDX v1.5 component inventory, package PURL digests, and HMAC-SHA256 provenance attestation.
        </div>
      )}
    </section>
  );
}
