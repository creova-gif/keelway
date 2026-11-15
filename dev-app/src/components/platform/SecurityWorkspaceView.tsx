import React, { useEffect, useMemo, useState } from "react";
import { GoldenEvalScorecardPanel } from "@/components/platform/GoldenEvalScorecardPanel";
import { VaultAndWebhooksPanel } from "@/components/platform/VaultAndWebhooksPanel";
import { RecordAuditLedger } from "@/components/screens/RecordAuditLedger";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type { EnterpriseRetentionMode } from "@/lib/platformApi";
import { scanMarketplacePackageClient, type MarketplaceScanReport } from "@/lib/platformData";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface SecurityPostureBannerProps {
  installedPackagesCount: number;
  retentionMode?: EnterpriseRetentionMode;
  onRetentionModeChange?: (mode: EnterpriseRetentionMode) => void;
}

export function SecurityPostureBanner({
  installedPackagesCount,
  retentionMode = "standard_30d",
  onRetentionModeChange,
}: SecurityPostureBannerProps): React.JSX.Element {
  const [localRetention, setLocalRetention] = useState<EnterpriseRetentionMode>(retentionMode);

  useEffect(() => {
    setLocalRetention(retentionMode);
  }, [retentionMode]);

  const handleChange = (next: EnterpriseRetentionMode) => {
    setLocalRetention(next);
    onRetentionModeChange?.(next);
  };

  return (
    <section aria-label="Security governance posture summary" className="border-b border-border bg-chrome px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-sm font-semibold text-fg">Security Governance &amp; Sovereign Posture</h1>
          <p className="text-xs text-fg-muted">
            Unified RBAC, SQLite WAL tenant isolation, Ed25519 + SHA-256 package signing, and hash-chained Record audit ledger.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
          <span className="rounded-xs border border-ok/40 bg-ok-subtle px-2 py-0.5 text-ok">RBAC + Seatbelt Isolated</span>
          <span className="rounded-xs border border-ok/40 bg-ok-subtle px-2 py-0.5 text-ok">
            {`Ed25519 + SHA-256 Verified (${installedPackagesCount} pkgs)`}
          </span>
          <label className="inline-flex items-center gap-1.5 rounded-xs border border-border-control bg-surface px-2 py-0.5 text-fg">
            <span className="text-fg-muted">Retention:</span>
            <select
              aria-label="Enterprise data retention policy"
              value={localRetention}
              onChange={(e) => handleChange(e.target.value as EnterpriseRetentionMode)}
              className="bg-surface font-mono text-[11px] text-fg"
            >
              <option value="ephemeral_0d">ephemeral_0d (0-Day Ephemeral)</option>
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

type ComplianceFrameworkId = "SOC2" | "HIPAA" | "ISO27001" | "GDPR";

interface EvaluatedControlRow {
  id: string;
  title: string;
  passed: boolean;
  remediation: string;
}

function buildFrameworkControls(
  framework: ComplianceFrameworkId,
  policies: {
    piiRedaction: boolean;
    requireP10Webhooks: boolean;
    airGapSovereign: boolean;
    retentionMode: EnterpriseRetentionMode;
  },
): EvaluatedControlRow[] {
  const retentionLong = policies.retentionMode === "regulated_365d" || policies.retentionMode === "worm_7y";
  const gdprMinRetention = policies.retentionMode === "ephemeral_0d" || policies.retentionMode === "standard_30d";
  const codes: Record<ComplianceFrameworkId, [string, string, string, string]> = {
    SOC2: ["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
    HIPAA: ["164.312(a)", "164.312(b)", "164.312(e)", "164.316(b)"],
    ISO27001: ["A.8.24", "A.8.11", "A.8.28", "A.5.33"],
    GDPR: ["Art.32(1)", "Art.25", "Art.22", "Art.5(1)(e)"],
  };
  const c = codes[framework];

  return [
    {
      id: c[0],
      title: `${c[0]} · Cryptographic Ed25519 Signing & SHA-256 Record Provenance`,
      passed: true,
      remediation: "Active by default in Seatbelt sovereign runtime.",
    },
    {
      id: c[1],
      title: `${c[1]} · Automated DLP & PII/PHI Redaction Before Prompt Egress`,
      passed: policies.piiRedaction,
      remediation: "Enable 'PII Redaction Enforced' to scrub sensitive identifiers pre-inference.",
    },
    {
      id: c[2],
      title: `${c[2]} · Human-in-the-Loop P-10 Gate on External Webhooks & Mutations`,
      passed: policies.requireP10Webhooks,
      remediation: "Enable 'Require P-10 on External Webhooks' to block autonomous outbound calls.",
    },
    {
      id: c[3],
      title:
        framework === "GDPR"
          ? `${c[3]} · Sovereign VPC Isolation & Data Minimization Retention`
          : `${c[3]} · Air-Gap / Sovereign VPC Topology & Regulated Audit Retention`,
      passed:
        framework === "GDPR"
          ? policies.airGapSovereign && gdprMinRetention
          : framework === "HIPAA"
            ? policies.airGapSovereign && retentionLong
            : policies.airGapSovereign,
      remediation:
        framework === "HIPAA" && !retentionLong
          ? "Enable 'Air-Gap / Sovereign VPC Topology' and set retention to regulated_365d or worm_7y."
          : framework === "GDPR" && !gdprMinRetention
            ? "Select standard_30d or ephemeral_0d retention and enable 'Air-Gap / Sovereign VPC Topology'."
            : "Enable 'Air-Gap / Sovereign VPC Topology' to lock egress to loopback/VPC endpoints.",
    },
  ];
}

export interface SecurityWorkspaceViewProps {
  installedPackagesCount: number;
  retentionMode?: EnterpriseRetentionMode;
  onRetentionModeChange?: (mode: EnterpriseRetentionMode) => void;
  selectedSeq?: number | null;
  onSelectSeq?: (seq: number | null) => void;
  verifyRequestNonce?: number;
  onOpenDiffInReview?: (diffPath: string, seq?: number) => void;
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

const SECRET_PREFIX_RE = /\b(?:sk-live-[a-zA-Z0-9_-]*|AKIA[0-9A-Z]{4,}|ghp_[a-zA-Z0-9]{4,})/;

export function SecurityWorkspaceView({
  installedPackagesCount,
  retentionMode = "standard_30d",
  onRetentionModeChange,
  selectedSeq,
  onSelectSeq,
  verifyRequestNonce,
  onOpenDiffInReview,
  workspaceId = "default",
  activeRbacRole = "owner",
}: SecurityWorkspaceViewProps): React.JSX.Element {
  const [effectiveRetention, setEffectiveRetention] = useState<EnterpriseRetentionMode>(retentionMode);
  const [framework, setFramework] = useState<ComplianceFrameworkId>("SOC2");
  const [piiRedaction, setPiiRedaction] = useState(true);
  const [requireP10Webhooks, setRequireP10Webhooks] = useState(true);
  const [airGapSovereign, setAirGapSovereign] = useState(true);

  const [scanTargetPath, setScanTargetPath] = useState("skills/openapi-audit/manifest.json");
  const [scanSnippet, setScanSnippet] = useState(
    "Audit workspace schemas in read-only mode and log SHA-256 verification receipts.",
  );
  const [liveScanResult, setLiveScanResult] = useState<MarketplaceScanReport | null>(null);

  useEffect(() => {
    setEffectiveRetention(retentionMode);
  }, [retentionMode]);

  const handleRetentionChange = (next: EnterpriseRetentionMode) => {
    setEffectiveRetention(next);
    onRetentionModeChange?.(next);
  };

  const controls = useMemo(
    () =>
      buildFrameworkControls(framework, {
        piiRedaction,
        requireP10Webhooks,
        airGapSovereign,
        retentionMode: effectiveRetention,
      }),
    [airGapSovereign, effectiveRetention, framework, piiRedaction, requireP10Webhooks],
  );

  const complianceScore = useMemo(
    () => Math.round((controls.filter((c) => c.passed).length / controls.length) * 100),
    [controls],
  );

  const handleRunLiveScan = (e: React.FormEvent) => {
    e.preventDefault();
    const baseReport = scanMarketplacePackageClient({
      name: scanTargetPath.trim() || "workspace-target",
      category: "dev_tool",
      publisherTier: "first_party",
      instructions: scanSnippet,
      writePaths: scanTargetPath.trim() || "reports/*",
      networkFull: false,
      requiresP10Approval: requireP10Webhooks,
    });
    const findings = [...baseReport.findings];
    if (SECRET_PREFIX_RE.test(scanSnippet) && !findings.some((f) => f.code === "EMBEDDED_SECRET_DETECTED")) {
      findings.push({
        code: "EMBEDDED_SECRET_DETECTED",
        severity: "critical",
        message: "Live secret prefix (sk-live-, AKIA, or ghp_) detected in scanned snippet.",
      });
    }
    setLiveScanResult({
      ...baseReport,
      passed: findings.length === 0,
      riskGrade: findings.length > 0 ? "BLOCKED" : "A",
      findings,
    });
  };

  return (
    <div className="space-y-0">
      <SecurityPostureBanner
        installedPackagesCount={installedPackagesCount}
        retentionMode={effectiveRetention}
        onRetentionModeChange={handleRetentionChange}
      />

      <div className="mx-auto max-w-6xl space-y-5 p-4 md:p-6">
        <div className="grid gap-4 lg:grid-cols-2">
          <section aria-label="Compliance framework evaluator" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-fg">Interactive Compliance Framework Evaluator</h2>
                <p className="text-xs text-fg-muted">Evaluate live workspace guardrails against regulated security standards.</p>
              </div>
              <SemanticBadge kind={complianceScore === 100 ? "passed" : "reconfirm"} labelOverride={`Score: ${complianceScore}%`} />
            </div>

            <div role="group" aria-label="Compliance frameworks" className="flex flex-wrap gap-1.5">
              {(["SOC2", "HIPAA", "ISO27001", "GDPR"] as const).map((fw) => (
                <button
                  key={fw}
                  type="button"
                  aria-pressed={framework === fw}
                  onClick={() => setFramework(fw)}
                  className={`rounded-sm border px-2.5 py-1 font-mono text-xs font-medium ${
                    framework === fw ? "border-teal-accent/50 bg-teal-surface text-teal-accent" : "border-border bg-chrome text-fg-muted hover:text-fg"
                  }`}
                >
                  {fw}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-3 rounded-xs border border-border bg-chrome p-2.5 text-xs text-fg">
              <label className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={piiRedaction} onChange={(e) => setPiiRedaction(e.target.checked)} />
                <span>PII Redaction Enforced</span>
              </label>
              <label className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={requireP10Webhooks} onChange={(e) => setRequireP10Webhooks(e.target.checked)} />
                <span>Require P-10 on External Webhooks</span>
              </label>
              <label className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={airGapSovereign} onChange={(e) => setAirGapSovereign(e.target.checked)} />
                <span>Air-Gap / Sovereign VPC Topology</span>
              </label>
            </div>

            <ul className="space-y-1.5 text-xs">
              {controls.map((ctrl) => (
                <li key={ctrl.id} className="rounded-xs border border-border bg-canvas px-2.5 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-fg">{ctrl.title}</span>
                    <span className={`font-mono text-[10px] font-semibold uppercase ${ctrl.passed ? "text-ok" : "text-danger"}`}>
                      {ctrl.passed ? "PASS" : "FAIL"}
                    </span>
                  </div>
                  {!ctrl.passed ? <p className="mt-1 font-mono text-[11px] text-warning">{ctrl.remediation}</p> : null}
                </li>
              ))}
            </ul>
          </section>

          <section aria-label="Workspace security scanner" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
            <div>
              <h2 className="text-sm font-semibold text-fg">Live Workspace Vulnerability, Prompt-Injection &amp; Secret Scanner</h2>
              <p className="text-xs text-fg-muted">
                Inspect manifests, prompts, or diffs for guardrail bypasses, shell/eval hooks, and live credentials (`sk-live-`, `AKIA`, `ghp_`).
              </p>
            </div>

            <form onSubmit={handleRunLiveScan} className="space-y-2.5">
              <label className="flex flex-col gap-1 text-xs text-fg-muted">
                <span>Target file or manifest path</span>
                <input
                  type="text"
                  aria-label="Scan target path"
                  value={scanTargetPath}
                  onChange={(e) => setScanTargetPath(e.target.value)}
                  className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-fg-muted">
                <span>Manifest or code snippet</span>
                <textarea
                  rows={4}
                  aria-label="Workspace manifest or code snippet to scan"
                  value={scanSnippet}
                  onChange={(e) => setScanSnippet(e.target.value)}
                  className="rounded-sm border border-border-control bg-canvas p-2.5 font-mono text-xs text-fg"
                />
              </label>
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-fg-dim">Deterministic client + policy scanner · 0 external calls</span>
                <Button type="submit" size="sm" variant="primary">Run Security Scan</Button>
              </div>
            </form>

            {liveScanResult ? (
              liveScanResult.passed ? (
                <div role="status" className="rounded-xs border border-ok/40 bg-ok-subtle px-3 py-2 text-xs text-fg">
                  <span className="font-semibold text-ok">Risk Grade A · Zero Findings</span> — Verified digest{" "}
                  <code className="font-mono">{liveScanResult.manifestSha256}</code> for{" "}
                  <code className="font-mono">{scanTargetPath}</code>.
                </div>
              ) : (
                <div role="alert" className="space-y-1 rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 text-xs text-fg">
                  <div className="font-semibold text-danger">Critical Security Findings Detected (Risk Grade: BLOCKED)</div>
                  <ul className="list-inside list-disc font-mono text-[11px]">
                    {liveScanResult.findings.map((f) => (
                      <li key={f.code}><strong>{f.code}</strong>: {f.message}</li>
                    ))}
                  </ul>
                </div>
              )
            ) : null}
          </section>
        </div>

        <VaultAndWebhooksPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />

        <GoldenEvalScorecardPanel workspaceId={workspaceId} activeRbacRole={activeRbacRole} />
      </div>

      <div className="border-t border-border">
        <RecordAuditLedger
          selectedSeq={selectedSeq}
          onSelectSeq={onSelectSeq}
          verifyRequestNonce={verifyRequestNonce}
          onOpenDiffInReview={onOpenDiffInReview}
        />
      </div>
    </div>
  );
}
