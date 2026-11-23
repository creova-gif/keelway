import React, { useEffect, useState } from "react";
import { GoldenThreadJourneyBar } from "@/components/platform/GoldenThreadJourneyBar";
import { BrandMark } from "@/components/ui/BrandMark";
import { Button } from "@/components/ui/Button";
import { SUBSCRIPTION_TIERS } from "@/lib/platformData";
import {
  DEFAULT_WORKSPACES, fetchWorkspacesList, postCreateWorkspace,
  type RbacRoleId, type WorkspaceDirectoryItem,
} from "@/lib/platformRuntimeApi";
import type { ExperienceMode, PlatformViewId, SidebarTaskItem, SubscriptionTierId } from "@/lib/types";
import { InboxPopover } from "@/components/shell/InboxPopover";

export interface PlatformWorkspaceBarProps {
  activeView: PlatformViewId;
  onSelectView: (view: PlatformViewId) => void;
  experienceMode: ExperienceMode;
  onChangeExperienceMode: (mode: ExperienceMode) => void;
  subscriptionTier: SubscriptionTierId;
  onChangeSubscriptionTier: (tier: SubscriptionTierId) => void;
  workspacePath: string;
  workspaceBranch: string;
  activeModelLabel: string;
  pendingApprovalCount: number;
  activeWorkspaceId?: string;
  workspaces?: WorkspaceDirectoryItem[];
  onSelectWorkspaceId?: (workspaceId: string) => void;
  onCreateWorkspace?: (ws: { id: string; name: string; branch: string }) => void;
  activeRbacRole?: RbacRoleId;
  onChangeRbacRole?: (role: RbacRoleId) => void;
  platformHydration?: "loading" | "live" | "example";
  inboxTasks?: SidebarTaskItem[];
  onInboxSelectTask?: (taskId: string) => void;
  onInboxJumpToApproval?: () => void;
  onOpenRecordAudit?: () => void;
}

export const PLATFORM_VIEWS: Array<{ id: PlatformViewId; label: string; capability: string }> = [
  { id: "ide", label: "IDE", capability: "Tasks, Diff Review & Sandbox" },
  { id: "agents", label: "Agents", capability: "12 Lifecycle Agents & Squads" },
  { id: "pm", label: "Project Manager", capability: "Kanban, Sprints & Delegation" },
  { id: "product", label: "Product", capability: "PRDs, RICE & Feedback" },
  { id: "automation", label: "Automation", capability: "KFlow DAGs & Triggers" },
  { id: "marketplace", label: "Marketplace", capability: "Verified Packages & Scanner" },
  { id: "security", label: "Security", capability: "Compliance, RBAC & Ledger" },
  { id: "docs", label: "Documentation", capability: "Diataxis Editor & 9-Stage SDLC" },
  { id: "operations", label: "Operations", capability: "GPU Fleet, Canary & BYOM" },
  { id: "nocode", label: "No-Code Builder", capability: "Plain-English App Blueprint" },
];

export function PlatformWorkspaceBar({
  activeView, onSelectView, experienceMode, onChangeExperienceMode, subscriptionTier, onChangeSubscriptionTier,
  workspacePath, workspaceBranch, activeModelLabel, pendingApprovalCount,
  activeWorkspaceId, workspaces, onSelectWorkspaceId, onCreateWorkspace, activeRbacRole, onChangeRbacRole,
  platformHydration = "loading",
  inboxTasks, onInboxSelectTask, onInboxJumpToApproval, onOpenRecordAudit,
}: PlatformWorkspaceBarProps): React.JSX.Element {
  const [localWorkspaces, setLocalWorkspaces] = useState<WorkspaceDirectoryItem[]>(workspaces ?? DEFAULT_WORKSPACES);
  const [localWsId, setLocalWsId] = useState<string>(activeWorkspaceId ?? "default");
  const [localRole, setLocalRole] = useState<RbacRoleId>(activeRbacRole ?? "owner");
  const [creatingWs, setCreatingWs] = useState(false);
  const [newWsName, setNewWsName] = useState("");

  useEffect(() => { if (workspaces?.length) setLocalWorkspaces(workspaces); }, [workspaces]);
  useEffect(() => { if (activeWorkspaceId) setLocalWsId(activeWorkspaceId); }, [activeWorkspaceId]);
  useEffect(() => { if (activeRbacRole) setLocalRole(activeRbacRole); }, [activeRbacRole]);

  useEffect(() => {
    if (workspaces?.length) return;
    let cancelled = false;
    void fetchWorkspacesList().then((remote) => {
      if (cancelled || !remote?.length) return;
      setLocalWorkspaces((prev) => {
        const byId = new Map(prev.map((w) => [w.id, w]));
        remote.forEach((w) => byId.set(w.id, w));
        return Array.from(byId.values());
      });
    });
    return () => { cancelled = true; };
  }, [workspaces]);

  const effectiveWsId = activeWorkspaceId ?? localWsId;
  const effectiveRole = activeRbacRole ?? localRole;
  const tierMeta = SUBSCRIPTION_TIERS[subscriptionTier];

  const handleSelectWorkspace = (wsId: string) => {
    setLocalWsId(wsId);
    onSelectWorkspaceId?.(wsId);
  };

  const handleSelectRole = (role: RbacRoleId) => {
    setLocalRole(role);
    onChangeRbacRole?.(role);
  };

  const handleCreateWorkspaceSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = newWsName.trim();
    if (!cleanName) return;
    const slug = cleanName.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "") || `ws-${Date.now()}`;
    const created: WorkspaceDirectoryItem = { id: slug, name: cleanName, branch: `feat/${slug}`, path: `/workspace/${slug}` };
    setLocalWorkspaces((prev) => [...prev.filter((w) => w.id !== slug), created]);
    setLocalWsId(slug);
    onCreateWorkspace?.({ id: slug, name: cleanName, branch: created.branch });
    onSelectWorkspaceId?.(slug);
    void postCreateWorkspace({ id: slug, name: cleanName, branch: created.branch });
    setNewWsName("");
    setCreatingWs(false);
  };

  return (
    <section aria-label="Unified workspace bar" className="flex shrink-0 flex-col gap-1 border-b border-border bg-chrome px-3 py-1.5 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="flex flex-wrap items-center gap-1.5 rounded-sm border border-border-strong bg-surface px-2 py-0.5 font-mono text-[11px] text-fg-muted">
          <BrandMark size={18} showWordmark />
          <span aria-hidden="true">·</span>
          <code dir="ltr" className="unicode-bidi-isolate text-fg">{workspacePath}</code>
          <span aria-hidden="true">·</span>
          {platformHydration === "example" ? (
            <span
              role="status"
              title="The platform API did not return workspace data — agents, issues, deployments and marketplace entries below are bundled examples, not your live state."
              className="rounded-xs border border-warning/60 bg-warning-subtle px-1.5 py-0.2 font-semibold text-warning"
            >
              EXAMPLE DATA
            </span>
          ) : null}
          <span>
            <span aria-hidden="true" className="me-0.5">⎇</span>
            <code dir="ltr" className="unicode-bidi-isolate text-fg">{workspaceBranch}</code>
          </span>
          <span aria-hidden="true">·</span>
          <code dir="ltr" className="unicode-bidi-isolate">{activeModelLabel}</code>
          {pendingApprovalCount > 0 ? (
            <span className="ms-1 rounded-xs border border-ochre/40 bg-ochre-subtle px-1.5 py-0.5 text-[10px] font-semibold text-ochre">
              {`${pendingApprovalCount} P-10 pending`}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-sm border border-border-control/70 bg-surface px-2 py-0.5">
            <span className="inline-flex items-center gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wide text-fg-muted">WS</span>
              <select aria-label="Active workspace switcher" value={effectiveWsId} onChange={(e) => handleSelectWorkspace(e.target.value)} className="bg-surface font-mono text-[11px] font-semibold text-fg focus:outline-none focus-visible:underline">
                {localWorkspaces.map((ws) => <option key={ws.id} value={ws.id}>{`${ws.id} · ${ws.name}`}</option>)}
              </select>
              <button type="button" aria-label="New workspace" aria-expanded={creatingWs} onClick={() => setCreatingWs((v) => !v)} className="rounded-xs px-1 py-0.5 font-mono text-[10px] font-semibold text-accent hover:bg-accent-subtle">
                + New
              </button>
            </span>
            <span aria-hidden="true" className="h-3.5 w-px bg-border-strong" />
            <span className="inline-flex items-center gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wide text-fg-muted">RBAC</span>
              <select aria-label="Active RBAC role" value={effectiveRole} onChange={(e) => handleSelectRole(e.target.value as RbacRoleId)} className="bg-surface font-mono text-[11px] font-semibold text-accent focus:outline-none focus-visible:underline">
                <option value="owner">owner</option>
                <option value="admin">admin</option>
                <option value="builder">builder</option>
                <option value="operator">operator</option>
                <option value="viewer">viewer</option>
              </select>
            </span>
            <span aria-hidden="true" className="h-3.5 w-px bg-border-strong" />
            <div role="group" aria-label="Experience persona" className="inline-flex items-center gap-0.5">
              <button type="button" aria-pressed={experienceMode === "builder"} onClick={() => onChangeExperienceMode("builder")} className={`rounded-xs px-1.5 py-0.5 text-[11px] font-medium transition-colors duration-fast ease-state focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${experienceMode === "builder" ? "bg-accent-subtle text-accent" : "text-fg-muted hover:text-fg"}`}>
                Builder
              </button>
              <button type="button" aria-pressed={experienceMode === "non_coder"} onClick={() => onChangeExperienceMode("non_coder")} className={`rounded-xs px-1.5 py-0.5 text-[11px] font-medium transition-colors duration-fast ease-state focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${experienceMode === "non_coder" ? "bg-accent-subtle text-accent" : "text-fg-muted hover:text-fg"}`}>
                Guided Non-Coder
              </button>
            </div>
            <span aria-hidden="true" className="h-3.5 w-px bg-border-strong" />
            <span className="inline-flex items-center gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wide text-fg-dim">Tier</span>
              <select aria-label="Subscription tier" value={subscriptionTier} onChange={(e) => onChangeSubscriptionTier(e.target.value as SubscriptionTierId)} className="bg-transparent font-mono text-[11px] font-semibold text-accent focus:outline-none focus-visible:underline">
                <option value="community">Community</option>
                <option value="pro">Pro</option>
                <option value="byom">BYOM · 0% Markup</option>
                <option value="enterprise">Enterprise</option>
              </select>
              <span className="hidden font-mono text-[10px] text-fg-dim xl:inline">{tierMeta.priceLabel}</span>
            </span>
          </div>

          {inboxTasks ? (
            <InboxPopover
              tasks={inboxTasks}
              onSelectTask={onInboxSelectTask}
              onJumpToApprovalHeading={onInboxJumpToApproval}
              onOpenRecord={onOpenRecordAudit}
            />
          ) : null}

          {experienceMode === "non_coder" && activeView !== "nocode" ? (
            <Button size="sm" variant="primary" onClick={() => onSelectView("nocode")}>Open No-Code Builder</Button>
          ) : null}
        </div>
      </div>

      {creatingWs ? (
        <form onSubmit={handleCreateWorkspaceSubmit} className="flex flex-wrap items-center gap-2 rounded-sm border border-border-strong bg-surface px-2.5 py-1.5">
          <input type="text" aria-label="New workspace name" value={newWsName} onChange={(e) => setNewWsName(e.target.value)} placeholder="e.g. PCI Audit Enclave" className="min-h-ctrl-sm rounded-xs border border-border-control bg-canvas px-2 py-0.5 text-xs text-fg" />
          <Button type="submit" size="sm" variant="primary">Create Workspace</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setCreatingWs(false)}>Cancel</Button>
        </form>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-border pt-1">
        <GoldenThreadJourneyBar
          activeView={activeView}
          onSelectView={onSelectView}
          experienceMode={experienceMode}
        />

      </div>
    </section>
  );
}
