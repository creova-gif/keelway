import React, { useCallback, useEffect, useState } from "react";
import { AgentsWorkspaceView } from "@/components/platform/AgentsWorkspaceView";
import {
  AutomationWorkspaceView,
  OperationsWorkspaceView,
} from "@/components/platform/AutomationAndOpsViews";
import {
  DocumentationWorkspaceView,
  MarketplaceWorkspaceView,
  SecurityWorkspaceView,
} from "@/components/platform/MarketplaceAndDocsViews";
import { NoCodeBuilderView } from "@/components/platform/NoCodeBuilderView";
import {
  ProductWorkspaceView,
  ProjectManagerView,
} from "@/components/platform/PmAndProductViews";
import {
  fetchPlatformHydration,
  patchPlatformIssue,
  postMarketplaceInstall,
  postMarketplacePublish,
  postMarketplaceUninstall,
  postNoCodeBlueprint,
  postPlatformDoc,
  postPlatformIssue,
  postPlatformPrd,
  postPlatformWorkflow,
  postProductFeedback,
  postTeamDispatch,
  putPlatformDoc,
  type EnterpriseRetentionMode,
  type MarketplacePublishPayload,
} from "@/lib/platformApi";
import {
  generateLocalBlueprint,
  INITIAL_AUTOMATION_WORKFLOWS,
  INITIAL_DEPLOYMENTS,
  INITIAL_DOC_GUIDES,
  INITIAL_LIFECYCLE_AGENTS,
  INITIAL_MARKETPLACE_PACKAGES,
  INITIAL_MULTI_AGENT_TEAMS,
  INITIAL_PM_ISSUES,
  INITIAL_PRODUCT_PRDS,
  INITIAL_USER_FEEDBACK,
  type AutomationWorkflowItem,
  type DeploymentEnvItem,
  type DocGuideItem,
  type ExperienceMode,
  type GeneratedProjectBlueprint,
  type LifecycleAgentItem,
  type MarketplacePackageItem,
  type MultiAgentTeamItem,
  type PlatformViewId,
  type PmIssueItem,
  type PmIssuePriority,
  type PmIssueStatus,
  type ProductPrdItem,
  type SubscriptionTierId,
  type UserFeedbackItem,
} from "@/lib/platformData";
import {
  DEFAULT_WORKSPACES,
  postCreateWorkspace,
  type RbacRoleId,
  type WorkspaceDirectoryItem,
} from "@/lib/platformRuntimeApi";

function mergeById<T extends { id: string }>(incoming: T[], existing: T[]): T[] {
  const seen = new Set(existing.map((item) => item.id));
  const fresh = incoming.filter((item) => !seen.has(item.id));
  return fresh.length > 0 ? [...fresh, ...existing] : existing;
}

export function useUnifiedPlatformState(options: {
  onJumpToIdeComposer: (prefill: string) => void;
  onBumpRecordSeq: () => number;
}) {
  const { onJumpToIdeComposer, onBumpRecordSeq } = options;

  const [platformView, setPlatformView] = useState<PlatformViewId>("ide");
  const [experienceMode, setExperienceMode] = useState<ExperienceMode>("builder");
  const [subscriptionTier, setSubscriptionTier] = useState<SubscriptionTierId>("pro");
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string>("default");
  const [workspaces, setWorkspaces] = useState<WorkspaceDirectoryItem[]>(DEFAULT_WORKSPACES);
  const [activeRbacRole, setActiveRbacRole] = useState<RbacRoleId>("owner");

  const [agents, setAgents] = useState<LifecycleAgentItem[]>(INITIAL_LIFECYCLE_AGENTS);
  const [teams, setTeams] = useState<MultiAgentTeamItem[]>(INITIAL_MULTI_AGENT_TEAMS);
  const [issues, setIssues] = useState<PmIssueItem[]>(INITIAL_PM_ISSUES);
  const [prds, setPrds] = useState<ProductPrdItem[]>(INITIAL_PRODUCT_PRDS);
  const [docs, setDocs] = useState<DocGuideItem[]>(INITIAL_DOC_GUIDES);
  const [feedback, setFeedback] = useState<UserFeedbackItem[]>(INITIAL_USER_FEEDBACK);
  const [workflows, setWorkflows] = useState<AutomationWorkflowItem[]>(INITIAL_AUTOMATION_WORKFLOWS);
  const [packages, setPackages] = useState<MarketplacePackageItem[]>(INITIAL_MARKETPLACE_PACKAGES);
  const [installedPackageIds, setInstalledPackageIds] = useState<string[]>([
    "pkg-wcag-skill",
    "pkg-incident-dag",
  ]);
  const [deployments, setDeployments] = useState<DeploymentEnvItem[]>(INITIAL_DEPLOYMENTS);
  const [latestBlueprint, setLatestBlueprint] = useState<GeneratedProjectBlueprint | null>(null);
  const [blueprintCount, setBlueprintCount] = useState(0);
  const [retentionMode, setRetentionMode] = useState<EnterpriseRetentionMode>("standard_30d");
  const [platformHydration, setPlatformHydration] = useState<"loading" | "live" | "example">("loading");

  useEffect(() => {
    let cancelled = false;
    setPlatformHydration("loading");
    void fetchPlatformHydration(activeWorkspaceId).then((snap) => {
      if (cancelled) return;
      setPlatformHydration(snap.hydrated ? "live" : "example");
      if (!snap.hydrated) return;
      if (snap.packages.length > 0) setPackages((prev) => mergeById(snap.packages, prev));
      if (snap.installedPackageIds.length > 0) {
        setInstalledPackageIds((prev) => Array.from(new Set([...prev, ...snap.installedPackageIds])));
      }
      if (snap.issues.length > 0) setIssues((prev) => mergeById(snap.issues, prev));
      if (snap.prds.length > 0) setPrds((prev) => mergeById(snap.prds, prev));
      if (snap.workflows.length > 0) setWorkflows((prev) => mergeById(snap.workflows, prev));
      if (snap.docs && snap.docs.length > 0) setDocs((prev) => mergeById(snap.docs!, prev));
      if (snap.feedback && snap.feedback.length > 0) setFeedback((prev) => mergeById(snap.feedback!, prev));
      if (snap.retentionMode) setRetentionMode(snap.retentionMode);
    });
    return () => {
      cancelled = true;
    };
  }, [activeWorkspaceId]);

  const handleCreateWorkspace = useCallback(
    (ws: { id: string; name: string; branch: string }) => {
      const entry: WorkspaceDirectoryItem = {
        id: ws.id,
        name: ws.name,
        branch: ws.branch,
        path: `/workspace/${ws.id}`,
        isolationMode: "sqlite_wal_local",
      };
      setWorkspaces((prev) => [entry, ...prev.filter((w) => w.id !== ws.id)]);
      setActiveWorkspaceId(ws.id);
      void postCreateWorkspace(ws);
    },
    [],
  );

  const handleCreateCustomAgent = useCallback((agent: LifecycleAgentItem) => {
    setAgents((prev) => [agent, ...prev]);
  }, []);

  const handleDispatchTeam = useCallback(
    (teamId: string) => {
      const target = teams.find((t) => t.id === teamId);
      setTeams((prev) =>
        prev.map((t) =>
          t.id === teamId
            ? {
                ...t,
                lastRunStatus: "running",
                executionSteps: t.executionSteps.map((s, idx) =>
                  idx === 0 ? { ...s, status: "done" } : s.status === "ready" ? { ...s, status: "running" } : s,
                ),
              }
            : t,
        ),
      );
      void postTeamDispatch(
        teamId,
        target?.description ?? "Execute coordinated lifecycle team workflow",
        true,
      );
    },
    [teams],
  );

  const handleUpdateAgentModel = useCallback((agentId: string, modelId: string) => {
    setAgents((prev) => prev.map((a) => (a.id === agentId ? { ...a, defaultModel: modelId } : a)));
  }, []);

  const handleCreateIssue = useCallback(
    (spec: { title: string; priority: PmIssuePriority; assignedAgentId: string }) => {
      setIssues((prev) => [
        {
          id: `KEEL-${105 + prev.length}`,
          title: spec.title,
          status: "todo",
          priority: spec.priority,
          sprint: "Sprint 14 · Sovereign Platform",
          milestone: "v1.1 Unified GA",
          dependencies: [],
          assignedAgentId: spec.assignedAgentId,
        },
        ...prev,
      ]);
      void postPlatformIssue({
        title: spec.title,
        priority: spec.priority,
        assignedAgentId: spec.assignedAgentId,
      });
    },
    [],
  );

  const handleUpdateIssueStatus = useCallback((issueId: string, status: PmIssueStatus) => {
    setIssues((prev) => prev.map((iss) => (iss.id === issueId ? { ...iss, status } : iss)));
    void patchPlatformIssue(issueId, { status });
  }, []);

  const handleUpdateIssueDetails = useCallback(
    (issueId: string, updates: { description?: string; dependencies?: string[]; linkedPrdId?: string }) => {
      setIssues((prev) =>
        prev.map((iss) =>
          iss.id === issueId
            ? {
                ...iss,
                description: updates.description ?? iss.description,
                dependencies: updates.dependencies ?? iss.dependencies,
                linkedPrdId: updates.linkedPrdId ?? iss.linkedPrdId,
              }
            : iss,
        ),
      );
      void patchPlatformIssue(issueId, {
        description: updates.description,
        dependencies: updates.dependencies,
        prd_id: updates.linkedPrdId,
      });
    },
    [],
  );

  const handleDelegateIssueToAgent = useCallback((issueId: string) => {
    setIssues((prev) =>
      prev.map((iss) =>
        iss.id === issueId
          ? { ...iss, status: "in_progress", assignedAgentId: iss.assignedAgentId ?? "feature-coder" }
          : iss,
      ),
    );
    void patchPlatformIssue(issueId, { status: "in_progress", assignee_agent: "feature-coder" });
  }, []);

  const handleToggleCriterion = useCallback((prdId: string, criterionId: string) => {
    setPrds((prev) =>
      prev.map((prd) =>
        prd.id === prdId
          ? {
              ...prd,
              acceptanceCriteria: prd.acceptanceCriteria.map((ac) =>
                ac.id === criterionId ? { ...ac, met: !ac.met } : ac,
              ),
            }
          : prd,
      ),
    );
  }, []);

  const handleCreatePrd = useCallback((prd: ProductPrdItem) => {
    setPrds((prev) => [prd, ...prev]);
    void postPlatformPrd({
      title: prd.title,
      summary: prd.problemStatement,
      acceptance_criteria: prd.acceptanceCriteria.map((ac) => ac.text),
    });
  }, []);

  const handleGenerateIssuesFromPrd = useCallback((prd: ProductPrdItem) => {
    const newIssueTitle = `Implement ${prd.title} acceptance criteria`;
    setIssues((prev) => {
      const nextId = `KEEL-${105 + prev.length}`;
      setPrds((currPrds) =>
        currPrds.map((p) =>
          p.id === prd.id && !p.linkedIssueIds.includes(nextId)
            ? { ...p, linkedIssueIds: [...p.linkedIssueIds, nextId] }
            : p,
        ),
      );
      return [
        {
          id: nextId,
          title: newIssueTitle,
          status: "todo",
          priority: "high",
          sprint: "Sprint 14 · Sovereign Platform",
          milestone: "v1.1 Unified GA",
          dependencies: [],
          assignedAgentId: "feature-coder",
          linkedPrdId: prd.id,
        },
        ...prev,
      ];
    });
    void postPlatformIssue({
      title: newIssueTitle,
      priority: "high",
      assignedAgentId: "feature-coder",
      prdId: prd.id,
    });
  }, []);

  const handleCreateFeedback = useCallback((entry: UserFeedbackItem) => {
    setFeedback((prev) => [entry, ...prev]);
    void postProductFeedback({
      persona: entry.persona,
      quote: entry.quote,
      impact_score: entry.impactScore,
      linked_prd_id: entry.linkedPrdId,
    });
  }, []);

  const handleSaveDoc = useCallback((saved: DocGuideItem & { body: string }) => {
    let existed = false;
    setDocs((prev) => {
      existed = prev.some((d) => d.id === saved.id);
      return existed ? prev.map((d) => (d.id === saved.id ? { ...d, ...saved } : d)) : [saved, ...prev];
    });
    const payload = {
      title: saved.title,
      diataxis_kind: saved.quadrant.toLowerCase().replace("-", "_"),
      summary: saved.summary,
      body: saved.body,
      linked_prd_id: saved.linkedPrdId,
    };
    if (existed) {
      void putPlatformDoc(saved.id, payload);
    } else {
      void postPlatformDoc(payload);
    }
  }, []);

  const handleCreateWorkflow = useCallback(
    (spec: {
      name: string;
      triggerKind: "cron" | "webhook" | "event";
      triggerSpec: string;
      tokenBudget: number;
    }) => {
      const nodes = [
        { id: `nw-${Date.now()}-1`, label: "Execute primary agent step", agentId: "workflow-automator", dependsOn: [], status: "ready" as const },
        { id: `nw-${Date.now()}-2`, label: "Verify output & log Record receipt", agentId: "qa-ci-runner", dependsOn: ["step-1"], status: "ready" as const },
      ];
      setWorkflows((prev) => [
        {
          id: `WF-0${prev.length + 1}`,
          name: spec.name,
          triggerKind: spec.triggerKind,
          triggerSpec: spec.triggerSpec,
          lastRunStatus: "ready",
          tokenBudget: spec.tokenBudget,
          nodes,
        },
        ...prev,
      ]);
      void postPlatformWorkflow({
        name: spec.name,
        trigger: spec.triggerSpec,
        nodes: nodes.map((n) => ({ id: n.id, label: n.label, agent: n.agentId })),
      });
    },
    [],
  );

  const handleAddStepToWorkflow = useCallback(
    (workflowId: string, step: { label: string; agentId: string; requiresP10: boolean }) => {
      setWorkflows((prev) =>
        prev.map((wf) => {
          if (wf.id !== workflowId) return wf;
          const prevId = wf.nodes[wf.nodes.length - 1]?.id;
          const nextNode = {
            id: `n-custom-${wf.nodes.length + 1}`,
            label: step.label,
            agentId: step.agentId,
            dependsOn: prevId ? [prevId] : [],
            status: "ready" as const,
            requiresP10: step.requiresP10,
          };
          return { ...wf, nodes: [...wf.nodes, nextNode] };
        }),
      );
    },
    [],
  );

  const handleRunWorkflow = useCallback((workflowId: string) => {
    setWorkflows((prev) =>
      prev.map((wf) =>
        wf.id === workflowId
          ? {
              ...wf,
              lastRunStatus: "passed",
              nodes: wf.nodes.map((n) => ({ ...n, status: "passed", errorDetail: undefined })),
            }
          : wf,
      ),
    );
  }, []);

  const handleRetryFailedNode = useCallback((workflowId: string, nodeId: string) => {
    setWorkflows((prev) =>
      prev.map((wf) => {
        if (wf.id !== workflowId) return wf;
        const updatedNodes = wf.nodes.map((n) =>
          n.id === nodeId ? { ...n, status: "passed" as const, errorDetail: undefined } : n,
        );
        const anyFailed = updatedNodes.some((n) => n.status === "failed");
        return { ...wf, lastRunStatus: anyFailed ? "failed" : "passed", nodes: updatedNodes };
      }),
    );
  }, []);

  const handleToggleInstallPackage = useCallback(
    (packageId: string) => {
      const wasInstalled = installedPackageIds.includes(packageId);
      setInstalledPackageIds((prev) =>
        prev.includes(packageId) ? prev.filter((id) => id !== packageId) : [...prev, packageId],
      );
      if (wasInstalled) {
        void postMarketplaceUninstall(packageId, "default");
      } else {
        void postMarketplaceInstall(packageId, "default");
      }
    },
    [installedPackageIds],
  );

  const handlePublishVerifiedPackage = useCallback(
    (pkg: MarketplacePackageItem, publishPayload: MarketplacePublishPayload) => {
      setPackages((prev) => [pkg, ...prev]);
      setInstalledPackageIds((prev) => (prev.includes(pkg.id) ? prev : [...prev, pkg.id]));
      void postMarketplacePublish(publishPayload);
    },
    [],
  );

  const handleConfirmP10Rollback = useCallback(
    (deploymentId: string) => {
      const seq = onBumpRecordSeq();
      setDeployments((prev) =>
        prev.map((d) =>
          d.id === deploymentId
            ? {
                ...d,
                version: "v1.0.8-stable",
                status: "rolled_back",
                lastDeployedAt: "just now",
                rollbackReceipt: `Record #${seq}`,
              }
            : d,
        ),
      );
    },
    [onBumpRecordSeq],
  );

  const handleGenerateBlueprint = useCallback(
    (idea: string, templateLabel: string) => {
      const bp = generateLocalBlueprint(idea, templateLabel, blueprintCount);
      setBlueprintCount((n) => n + 1);
      setLatestBlueprint(bp);
      setPrds((prev) => [bp.prd, ...prev]);
      setIssues((prev) => [...bp.issues, ...prev]);
      setWorkflows((prev) => [bp.workflow, ...prev]);
      void postNoCodeBlueprint(idea, experienceMode, templateLabel);
    },
    [blueprintCount, experienceMode],
  );

  const renderPlatformCanvas = (recordProps: {
    selectedSeq: number | null | undefined;
    onSelectSeq: (seq: number | null) => void;
    verifyRequestNonce: number;
    onOpenDiffInReview: (diffPath: string, seq?: number) => void;
  }): React.ReactNode => {
    switch (platformView) {
      case "agents":
        return (
          <AgentsWorkspaceView
            experienceMode={experienceMode}
            agents={agents}
            teams={teams}
            workspaceId={activeWorkspaceId}
            activeRbacRole={activeRbacRole}
            onCreateCustomAgent={handleCreateCustomAgent}
            onDispatchTeam={handleDispatchTeam}
            onUpdateAgentModel={handleUpdateAgentModel}
            onJumpToIdeTask={(prefill) => {
              setPlatformView("ide");
              onJumpToIdeComposer(prefill);
            }}
          />
        );
      case "pm":
        return (
          <ProjectManagerView
            experienceMode={experienceMode}
            issues={issues}
            agents={agents}
            prds={prds}
            onCreateIssue={handleCreateIssue}
            onUpdateIssueStatus={handleUpdateIssueStatus}
            onDelegateIssueToAgent={handleDelegateIssueToAgent}
            onUpdateIssueDetails={handleUpdateIssueDetails}
            onOpenInIde={(prefill) => {
              setPlatformView("ide");
              onJumpToIdeComposer(prefill);
            }}
          />
        );
      case "product":
        return (
          <ProductWorkspaceView
            experienceMode={experienceMode}
            prds={prds}
            feedback={feedback}
            onToggleCriterion={handleToggleCriterion}
            onJumpToPm={() => setPlatformView("pm")}
            onCreatePrd={handleCreatePrd}
            onGenerateIssuesFromPrd={handleGenerateIssuesFromPrd}
            onCreateFeedback={handleCreateFeedback}
          />
        );
      case "automation":
        return (
          <AutomationWorkspaceView
            experienceMode={experienceMode}
            workflows={workflows}
            workspaceId={activeWorkspaceId}
            activeRbacRole={activeRbacRole}
            onCreateWorkflow={handleCreateWorkflow}
            onRunWorkflow={handleRunWorkflow}
            onRetryFailedNode={handleRetryFailedNode}
            onAddStepToWorkflow={handleAddStepToWorkflow}
          />
        );
      case "marketplace":
        return (
          <MarketplaceWorkspaceView
            packages={packages}
            installedPackageIds={installedPackageIds}
            workspaceId={activeWorkspaceId}
            activeRbacRole={activeRbacRole}
            onToggleInstallPackage={handleToggleInstallPackage}
            onPublishVerifiedPackage={handlePublishVerifiedPackage}
          />
        );
      case "security":
        return (
          <SecurityWorkspaceView
            installedPackagesCount={installedPackageIds.length}
            retentionMode={retentionMode}
            onRetentionModeChange={setRetentionMode}
            workspaceId={activeWorkspaceId}
            activeRbacRole={activeRbacRole}
            selectedSeq={recordProps.selectedSeq ?? undefined}
            onSelectSeq={recordProps.onSelectSeq}
            verifyRequestNonce={recordProps.verifyRequestNonce}
            onOpenDiffInReview={recordProps.onOpenDiffInReview}
          />
        );
      case "docs":
        return (
          <DocumentationWorkspaceView
            experienceMode={experienceMode}
            guides={docs}
            activePrdTitle={prds[0]?.title}
            workspaceId={activeWorkspaceId}
            activeRbacRole={activeRbacRole}
            onSaveDoc={handleSaveDoc}
          />
        );
      case "operations":
        return (
          <OperationsWorkspaceView
            subscriptionTier={subscriptionTier}
            deployments={deployments}
            workspaceId={activeWorkspaceId}
            activeRbacRole={activeRbacRole}
            onConfirmP10Rollback={handleConfirmP10Rollback}
          />
        );
      case "nocode":
        return (
          <NoCodeBuilderView
            experienceMode={experienceMode}
            latestBlueprint={latestBlueprint}
            onGenerateBlueprint={handleGenerateBlueprint}
            onNavigateView={setPlatformView}
          />
        );
      default:
        return null;
    }
  };

  return {
    platformView,
    setPlatformView,
    experienceMode,
    setExperienceMode,
    subscriptionTier,
    setSubscriptionTier,
    activeWorkspaceId,
    setActiveWorkspaceId,
    workspaces,
    handleCreateWorkspace,
    activeRbacRole,
    setActiveRbacRole,
    platformHydration,
    renderPlatformCanvas,
  };
}
