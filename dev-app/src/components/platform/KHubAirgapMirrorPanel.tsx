import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacVerifyKhubMirror,
  fetchKhubSkills,
  verifyKhubMirror,
  type KhubMirrorVerificationResult,
  type KhubSkillsCatalogResponse,
  type WorkspaceRbacRole,
} from "@/lib/platformKbrainApi";

export interface KHubAirgapMirrorPanelProps {
  workspaceId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

export function KHubAirgapMirrorPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: KHubAirgapMirrorPanelProps): React.JSX.Element {
  const canVerify = canRbacVerifyKhubMirror(activeRbacRole);

  const [catalog, setCatalog] = useState<KhubSkillsCatalogResponse | null>(null);
  const [verification, setVerification] = useState<KhubMirrorVerificationResult | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setErrorBanner(null);
    setVerification(null);
    void fetchKhubSkills(workspaceId, activeRbacRole)
      .then((snap) => {
        if (!cancelled) setCatalog(snap);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorBanner(err instanceof Error ? err.message : "Failed to load KHub air-gapped skill catalog.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeRbacRole, workspaceId]);

  const handleVerifyMirror = async () => {
    if (!canVerify) {
      setErrorBanner(
        `RBAC Denied (${activeRbacRole}): Viewer role cannot execute KHub air-gapped mirror verification.`,
      );
      return;
    }
    setVerifyBusy(true);
    setErrorBanner(null);
    try {
      const skillIds = catalog?.skills.map((s) => s.skill_id);
      const result = await verifyKhubMirror(workspaceId, skillIds, activeRbacRole);
      setVerification(result);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "KHub air-gapped mirror verification failed.");
    } finally {
      setVerifyBusy(false);
    }
  };

  const skills = catalog?.skills ?? [];
  const builtinCount = catalog?.builtin_verified_count ?? skills.length;
  const isAirGapCompliant = catalog?.air_gap_compliant !== false;
  const catalogDigest = catalog?.catalog_digest_sha256 ?? "sha256:pending";

  return (
    <section
      aria-label="KHub air-gapped skill registry and mirror verifier"
      className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">
            KHub Air-Gapped Skill Registry &amp; Bundle Mirror Verifier
          </h2>
          <p className="text-xs text-fg-muted">
            Offline-verified <code className="font-mono text-teal-accent">kstack_builtin</code> role skill bundles with deterministic SHA-256 tar roundtrip attestation and zero external egress.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <SemanticBadge kind="opencore" detail={`kstack_builtin · ${builtinCount} Verified`} />
          <SemanticBadge
            kind={isAirGapCompliant ? "passed" : "reconfirm"}
            labelOverride={isAirGapCompliant ? "air_gap_compliant" : "egress_required"}
          />
        </div>
      </div>

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          {errorBanner}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-chrome px-3.5 py-2.5">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <span className="text-fg-muted">Catalog Digest:</span>
          <code
            className="max-w-[240px] truncate font-mono text-xs text-teal-accent"
            title={catalogDigest}
          >
            {catalogDigest}
          </code>
          <span className="text-[11px] text-fg-muted">{`· Workspace: ${workspaceId}`}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!canVerify ? (
            <span className="font-mono text-[10px] text-fg-muted">
              {`RBAC Lock (${activeRbacRole}): non-viewer role required`}
            </span>
          ) : null}
          <Button
            size="sm"
            variant="primary"
            loading={verifyBusy}
            disabled={!canVerify}
            onClick={() => {
              void handleVerifyMirror();
            }}
          >
            Verify Air-Gapped Skill Mirror
          </Button>
        </div>
      </div>

      {verification ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-ok/40 bg-ok-subtle px-3 py-2 font-mono text-xs text-fg"
        >
          <span>
            <strong className="text-ok">
              {`${verification.mirror_format} · ${verification.verified ? "Verified" : "Failed"}`}
            </strong>
            {` · skills_verified: ${verification.skills_verified} · air_gap_compliant`}
          </span>
          <code
            className="max-w-[240px] truncate font-mono text-xs text-teal-accent"
            title={verification.mirror_digest_sha256}
          >
            {verification.mirror_digest_sha256}
          </code>
        </div>
      ) : null}

      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
        {skills.map((skill) => (
          <article
            key={skill.skill_id}
            className="flex flex-col justify-between gap-1.5 rounded-sm bg-canvas p-2.5 text-xs"
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-1.5">
                <code className="font-mono text-[11px] font-semibold text-teal-accent">
                  {skill.skill_id}
                </code>
                {skill.source_type !== "kstack_builtin" ? (
                  <span className="rounded-xs border border-border bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                    {skill.source_type}
                  </span>
                ) : null}
              </div>
              <h3 className="text-xs font-semibold text-fg">{skill.name}</h3>
            </div>
            <div className="border-t border-border pt-1.5">
              <code
                className="block max-w-[220px] truncate font-mono text-[10px] text-fg-muted"
                title={skill.bundle_digest_sha256}
              >
                {skill.bundle_digest_sha256}
              </code>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
