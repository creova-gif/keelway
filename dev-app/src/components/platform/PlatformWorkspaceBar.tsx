import React, { useEffect, useState } from "react";
import { GoldenThreadJourneyBar } from "@/components/platform/GoldenThreadJourneyBar";
import { Button } from "@/components/ui/Button";
import { SUBSCRIPTION_TIERS } from "@/lib/platformData";
import {
  DEFAULT_WORKSPACES, fetchWorkspacesList, postCreateWorkspace,
  type RbacRoleId, type WorkspaceDirectoryItem,
} from "@/lib/platformRuntimeApi";
import type { ExperienceMode, PlatformViewId, SubscriptionTierId } from "@/lib/types";

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
}

const PLATFORM_VIEWS: Array<{ id: PlatformViewId; label: string; capability: string }> = [
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
  const activeMeta = PLATFORM_VIEWS.find((v) => v.id === activeView) ?? PLATFORM_VIEWS[0]!;

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
    <section aria-label="Unified workspace bar" className="flex shrink-0 flex-col gap-1.5 border-b border-border bg-chrome px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5 rounded-sm border border-border-strong bg-surface px-2.5 py-1 font-mono text-[11px] text-fg-muted">
          <code dir="ltr" className="unicode-bidi-isolate text-fg">{workspacePath}</code>
          <span aria-hidden="true">·</span>
          <span>
            <span aria-hidden="true" className="me-0.5">⎇</span>
            <code dir="ltr" className="unicode-bidi-isolate text-fg">{workspaceBranch}</code>
          </span>
          <span aria-hidden="true">·</span>
          <code dir="ltr" className="unicode-bidi-isolate">{activeModelLabel}</code>
          <span aria-hidden="true">·</span>
          <span className="font-medium text-teal-accent">Zero Context Loss</span>
          {pendingApprovalCount > 0 ? (
            <span className="ms-1 rounded-xs border border-ochre/40 bg-ochre-subtle px-1.5 py-0.5 text-[10px] font-semibold text-ochre">
              {`${pendingApprovalCount} P-10 pending`}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-1.5 rounded-sm border border-border-control/70 bg-surface px-2 py-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-fg-muted">WS</span>
            <select aria-label="Active workspace switcher" value={effectiveWsId} onChange={(e) => handleSelectWorkspace(e.target.value)} className="bg-surface font-mono text-[11px] font-semibold text-fg focus:outline-none focus-visible:underline">
              {localWorkspaces.map((ws) => <option key={ws.id} value={ws.id}>{`${ws.id} · ${ws.name}`}</option>)}
            </select>
            <button type="button" aria-label="New workspace" aria-expanded={creatingWs} onClick={() => setCreatingWs((v) => !v)} className="rounded-xs border border-border-control px-1.5 py-0.5 font-mono text-[10px] font-semibold text-teal-accent hover:bg-teal-surface">
              + New
            </button>
          </div>

          <div className="inline-flex items-center gap-1.5 rounded-sm border border-border-control/70 bg-surface px-2 py-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-fg-muted">RBAC</span>
            <select aria-label="Active RBAC role" value={effectiveRole} onChange={(e) => handleSelectRole(e.target.value as RbacRoleId)} className="bg-surface font-mono text-[11px] font-semibold text-teal-accent focus:outline-none focus-visible:underline">
              <option value="owner">owner</option>
              <option value="admin">admin</option>
              <option value="builder">builder</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </div>

          <div role="group" aria-label="Experience persona" className="inline-flex items-center rounded-sm border border-border-control/70 bg-surface p-0.5">
            <button type="button" aria-pressed={experienceMode === "builder"} onClick={() => onChangeExperienceMode("builder")} className={`rounded-xs px-2 py-0.5 text-[11px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent ${experienceMode === "builder" ? "bg-teal-surface text-teal-accent" : "text-fg-muted hover:text-fg"}`}>
              Builder
            </button>
            <button type="button" aria-pressed={experienceMode === "non_coder"} onClick={() => onChangeExperienceMode("non_coder")} className={`rounded-xs px-2 py-0.5 text-[11px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent ${experienceMode === "non_coder" ? "bg-teal-surface text-teal-accent" : "text-fg-muted hover:text-fg"}`}>
              Guided Non-Coder
            </button>
          </div>

          {experienceMode === "non_coder" && activeView !== "nocode" ? (
            <Button size="sm" variant="primary" onClick={() => onSelectView("nocode")}>Open No-Code Builder</Button>
          ) : null}

          <div className="inline-flex items-center gap-1.5 rounded-sm border border-border-control/70 bg-surface px-2 py-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-fg-dim">Tier</span>
            <select aria-label="Subscription tier" value={subscriptionTier} onChange={(e) => onChangeSubscriptionTier(e.target.value as SubscriptionTierId)} className="bg-transparent font-mono text-[11px] font-semibold text-teal-accent focus:outline-none focus-visible:underline">
              <option value="community">Community</option>
              <option value="pro">Pro</option>
              <option value="byom">BYOM · 0% Markup</option>
              <option value="enterprise">Enterprise</option>
            </select>
            <span className="hidden font-mono text-[10px] text-fg-dim xl:inline">{tierMeta.priceLabel}</span>
          </div>
        </div>
      </div>

      {creatingWs ? (
        <form onSubmit={handleCreateWorkspaceSubmit} className="flex flex-wrap items-center gap-2 rounded-sm border border-border-strong bg-surface px-2.5 py-1.5">
          <input type="text" aria-label="New workspace name" value={newWsName} onChange={(e) => setNewWsName(e.target.value)} placeholder="e.g. PCI Audit Enclave" className="min-h-ctrl-sm rounded-xs border border-border-control bg-canvas px-2 py-0.5 text-xs text-fg" />
          <Button type="submit" size="sm" variant="primary">Create Workspace</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setCreatingWs(false)}>Cancel</Button>
        </form>
      ) : null}

      <GoldenThreadJourneyBar
        activeView={activeView}
        onSelectView={onSelectView}
        experienceMode={experienceMode}
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <nav aria-label="Unified platform views" className="flex flex-wrap items-center gap-1">
          {PLATFORM_VIEWS.map((view) => {
            const isActive = activeView === view.id;
            return (
              <button
                key={view.id}
                type="button"
                title={`${view.label} — ${view.capability}`}
                aria-current={isActive ? "page" : undefined}
                onClick={() => onSelectView(view.id)}
                className={`rounded-sm border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent ${
                  isActive ? "border-teal-accent/50 bg-teal-surface font-semibold text-teal-accent" : "border-transparent text-fg-muted hover:border-border-strong hover:bg-surface hover:text-fg"
                }`}
              >
                {view.label}
              </button>
            );
          })}
        </nav>
        <span aria-live="polite" className="hidden items-center gap-1.5 rounded-xs border border-border bg-surface px-2 py-0.5 font-mono text-[11px] text-fg-muted lg:inline-flex">
          <span className="text-teal-accent">{activeMeta.label}</span>
          <span aria-hidden="true">·</span>
          <span>{activeMeta.capability}</span>
          <span aria-hidden="true">·</span>
          <kbd className="font-mono text-[10px] text-fg-dim">⌘K</kbd>
        </span>
      </div>
    </section>
  );
}
