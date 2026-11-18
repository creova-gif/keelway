import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  approveP10Quorum,
  canRbacApproveP10Quorum,
  canRbacManageEnterprise,
  fetchOidcConfig,
  fetchScimUsers,
  provisionScimUser,
  type EnterpriseOidcConfig,
  type P10QuorumProposalState,
  type ScimUserResource,
} from "@/lib/platformEnterpriseApi";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface EnterpriseIdentityAndQuorumPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

const IDP_GROUP_OPTIONS = [
  "keelway-operators",
  "keelway-builders",
  "keelway-owners",
  "keelway-auditors",
] as const;

export function EnterpriseIdentityAndQuorumPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: EnterpriseIdentityAndQuorumPanelProps): React.JSX.Element {
  const canManageIdentity = canRbacManageEnterprise(activeRbacRole);
  const canSignQuorum = canRbacApproveP10Quorum(activeRbacRole);

  const [oidcConfig, setOidcConfig] = useState<EnterpriseOidcConfig | null>(null);
  const [scimUsers, setScimUsers] = useState<ScimUserResource[]>([]);
  const [scimEmail, setScimEmail] = useState("");
  const [scimGroup, setScimGroup] = useState<string>("keelway-operators");
  const [scimBusy, setScimBusy] = useState(false);

  const [proposalId, setProposalId] = useState("prop-prod-deploy-001");
  const [approverId, setApproverId] = useState("alice@keelway.local");
  const [quorumByProposal, setQuorumByProposal] = useState<Record<string, P10QuorumProposalState>>({});
  const [quorumBusy, setQuorumBusy] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchOidcConfig(workspaceId, activeRbacRole)
      .then((cfg) => { if (!cancelled) setOidcConfig(cfg); })
      .catch((err) => { if (!cancelled) setErrorBanner(err instanceof Error ? err.message : "Failed to load OIDC configuration."); });
    void fetchScimUsers(workspaceId, activeRbacRole)
      .then((res) => { if (!cancelled) setScimUsers(res.Resources); })
      .catch((err) => { if (!cancelled) setErrorBanner(err instanceof Error ? err.message : "Failed to load SCIM directory users."); });
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const handleProvisionScim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManageIdentity) {
      setErrorBanner(`RBAC Denied (${activeRbacRole}): rbac:manage requires owner or admin.`);
      return;
    }
    const cleanEmail = scimEmail.trim();
    if (!cleanEmail) {
      setErrorBanner("Valid SCIM user email is required to provision directory identity.");
      return;
    }
    setScimBusy(true);
    setErrorBanner(null);
    try {
      const created = await provisionScimUser(
        { workspace_id: workspaceId, userName: cleanEmail, groups: [scimGroup], active: true },
        activeRbacRole,
      );
      setScimUsers((prev) => {
        const idx = prev.findIndex((u) => u.userName.toLowerCase() === created.userName.toLowerCase());
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = created;
          return copy;
        }
        return [...prev, created];
      });
      setScimEmail("");
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to provision SCIM 2.0 user.");
    } finally {
      setScimBusy(false);
    }
  };

  const handleSignQuorum = async () => {
    if (!canSignQuorum) {
      setErrorBanner(`RBAC Denied (${activeRbacRole}): Only owner or operator can sign P-10 quorum approvals.`);
      return;
    }
    const cleanProposal = proposalId.trim();
    const cleanApprover = approverId.trim();
    if (!cleanProposal || !cleanApprover) {
      setErrorBanner("Quorum proposal ID and human approver identity are required.");
      return;
    }
    setQuorumBusy(true);
    setErrorBanner(null);
    try {
      const next = await approveP10Quorum(
        {
          workspace_id: workspaceId,
          proposal_id: cleanProposal,
          approver_id: cleanApprover,
          initiator_id: "ci-initiator@keelway.local",
          required_approvals: 2,
          reason: "Dual-human P-10 production release sign-off",
        },
        activeRbacRole,
      );
      setQuorumByProposal((prev) => ({ ...prev, [cleanProposal]: next }));
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to record P-10 quorum approval.");
    } finally {
      setQuorumBusy(false);
    }
  };

  const activeProposalKey = proposalId.trim();
  const activeQuorum = activeProposalKey ? quorumByProposal[activeProposalKey] ?? null : null;
  const issuerDisplay = oidcConfig?.issuer ?? "https://idp.enterprise.example";
  const progressLabel = activeQuorum
    ? `${activeQuorum.approvals_count} / ${activeQuorum.required_approvals} · ${activeQuorum.status}`
    : "0 / 2";

  return (
    <section
      aria-label="Enterprise OIDC, SCIM 2.0 directory and dual-human P-10 quorum"
      className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">
            Enterprise OIDC Federation, SCIM 2.0 Directory &amp; Dual-Human P-10 Quorum
          </h2>
          <p className="text-xs text-fg-muted">
            Federate enterprise OIDC + PKCE issuers, provision SCIM 2.0 IdP groups into least-privilege RBAC roles, and enforce 2-of-2 separation-of-duties on P-10 gates.
          </p>
        </div>
        <SemanticBadge kind="opencore" detail={`Workspace · ${workspaceId}`} />
      </div>

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          {errorBanner}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">OIDC Federation &amp; SCIM 2.0 User Provisioning</h3>
              <p className="font-mono text-[11px] text-fg-muted">
                Issuer: <span className="text-teal-accent">{issuerDisplay}</span>
              </p>
            </div>
            <SemanticBadge
              kind={oidcConfig?.enabled !== false ? "passed" : "reconfirm"}
              labelOverride={oidcConfig?.enforce_pkce !== false ? "OIDC + PKCE Active" : "OIDC Enabled"}
            />
          </div>

          <form onSubmit={(e) => { void handleProvisionScim(e); }} className="grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>User email (SCIM userName)</span>
              <input
                type="email"
                aria-label="SCIM user email"
                value={scimEmail}
                onChange={(e) => setScimEmail(e.target.value)}
                placeholder="sre.lead@enterprise.example"
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>IdP group mapping</span>
              <select
                aria-label="SCIM IdP group"
                value={scimGroup}
                onChange={(e) => setScimGroup(e.target.value)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              >
                {IDP_GROUP_OPTIONS.map((grp) => (
                  <option key={grp} value={grp}>{grp}</option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap items-center justify-between gap-2 sm:col-span-2">
              <span className="font-mono text-[10px] text-fg-muted">
                {canManageIdentity
                  ? `SCIM 2.0 directory (${scimUsers.length} Resources)`
                  : `RBAC Lock (${activeRbacRole}): owner or admin required for rbac:manage`}
              </span>
              <Button type="submit" size="sm" variant="primary" loading={scimBusy} disabled={!canManageIdentity}>
                Provision SCIM 2.0 User
              </Button>
            </div>
          </form>

          <ul aria-label="SCIM 2.0 directory users" className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-xs">
            {scimUsers.length === 0 ? (
              <li className="text-[11px] text-fg-muted">No SCIM 2.0 directory users provisioned yet.</li>
            ) : (
              scimUsers.map((user) => (
                <li key={user.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-1 last:border-b-0 last:pb-0">
                  <span className="max-w-[220px] truncate text-fg" title={user.userName}>{user.userName}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-1.5 py-0.5 text-[10px] text-teal-accent">
                      {user.mapped_role}
                    </span>
                    <SemanticBadge
                      kind={user.active ? "passed" : "reconfirm"}
                      labelOverride={user.active ? "active" : "inactive"}
                    />
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>

        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">Dual-Human P-10 Quorum Gate (2-of-2)</h3>
              <p className="font-mono text-[11px] text-fg-muted">
                Enforces 2 distinct human signers · Separation-of-duties verified
              </p>
            </div>
            <SemanticBadge
              kind={activeQuorum?.quorum_met ? "passed" : "needs-approval"}
              labelOverride={progressLabel}
            />
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Proposal ID</span>
              <input
                type="text"
                aria-label="Quorum proposal ID"
                value={proposalId}
                onChange={(e) => setProposalId(e.target.value)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Human approver</span>
              <input
                type="text"
                aria-label="Human approver identity"
                value={approverId}
                onChange={(e) => setApproverId(e.target.value)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono text-[10px] text-fg-muted">
              {canSignQuorum
                ? `Active signer role: ${activeRbacRole}`
                : `RBAC Lock (${activeRbacRole}): Only owner or operator can sign P-10 quorum`}
            </span>
            <Button
              size="sm"
              variant="warning-cta"
              clickOnly
              loading={quorumBusy}
              disabled={!canSignQuorum}
              onClick={() => { void handleSignQuorum(); }}
            >
              Sign P-10 Quorum Approval
            </Button>
          </div>

          <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-xs">
            <div className="flex items-center justify-between gap-2 text-[11px]">
              <span className="text-fg-muted">Quorum Progress:</span>
              <span className={activeQuorum?.quorum_met ? "font-semibold text-ok" : "font-semibold text-ochre"}>
                {progressLabel}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              <span className="text-fg-muted">Distinct Signers:</span>
              {!activeQuorum || activeQuorum.approvers.length === 0 ? (
                <span className="text-fg-dim">0 signers recorded</span>
              ) : (
                activeQuorum.approvers.map((signer) => (
                  <span
                    key={signer}
                    className="rounded-xs border border-teal-accent/40 bg-teal-surface px-1.5 py-0.5 text-[10px] text-teal-accent"
                  >
                    {signer}
                  </span>
                ))
              )}
            </div>

            {activeQuorum ? (
              <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[11px]">
                <span className="text-fg-muted">Quorum Receipt:</span>
                <code
                  className="max-w-[240px] truncate font-mono text-xs text-teal-accent"
                  title={activeQuorum.quorum_receipt_sha256}
                >
                  {activeQuorum.quorum_receipt_sha256}
                </code>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
