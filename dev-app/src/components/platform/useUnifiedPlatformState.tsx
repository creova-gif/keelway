import React, { useCallback, useState } from "react";
import { AgentsWorkspaceView } from "@/components/platform/AgentsWorkspaceView";
import {
  AutomationWorkspaceView,
  OperationsWorkspaceView,
} from "@/components/platform/AutomationAndOpsViews";
import {
  DocumentationWorkspaceView,
  MarketplaceWorkspaceView,
  SecurityPostureBanner,
} from "@/components/platform/MarketplaceAndDocsViews";
import { NoCodeBuilderView } from "@/components/platform/NoCodeBuilderView";
import {
  ProductWorkspaceView,
  ProjectManagerView,
} from "@/components/platform/PmAndProductViews";
import { RecordAuditLedger } from "@/components/screens/RecordAuditLedger";
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
  syncPlatformBlueprintOptional,
  type AutomationWorkflowItem,
  type DeploymentEnvItem,
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
} from "@/lib/platformData";

export function useUnifiedPlatformState(options: {
  onJumpToIdeComposer: (prefill: string) => void;
  onBumpRecordSeq: () => number;
}) {
  const { onJumpToIdeComposer, onBumpRecordSeq } = options;

  const [platformView, setPlatformView] = useState<PlatformViewId>("ide");
  const [experienceMode, setExperienceMode] = useState<ExperienceMode>("builder");
  const [subscriptionTier, setSubscriptionTier] = useState<SubscriptionTierId>("pro");

  const [agents, setAgents] = useState<LifecycleAgentItem[]>(INITIAL_LIFECYCLE_AGENTS);
  const [teams, setTeams] = useState<MultiAgentTeamItem[]>(INITIAL_MULTI_AGENT_TEAMS);
  const [issues, setIssues] = useState<PmIssueItem[]>(INITIAL_PM_ISSUES);
  const [prds, setPrds] = useState<ProductPrdItem[]>(INITIAL_PRODUCT_PRDS);
  const [workflows, setWorkflows] = useState<AutomationWorkflowItem[]>(INITIAL_AUTOMATION_WORKFLOWS);
  const [packages, setPackages] = useState<MarketplacePackageItem[]>(INITIAL_MARKETPLACE_PACKAGES);
  const [installedPackageIds, setInstalledPackageIds] = useState<string[]>([
    "pkg-wcag-skill",
    "pkg-incident-dag",
  ]);
  const [deployments, setDeployments] = useState<DeploymentEnvItem[]>(INITIAL_DEPLOYMENTS);
  const [latestBlueprint, setLatestBlueprint] = useState<GeneratedProjectBlueprint | null>(null);
  const [blueprintCount, setBlueprintCount] = useState(0);

  const handleCreateCustomAgent = useCallback((agent: LifecycleAgentItem) => {
    setAgents((prev) => [agent, ...prev]);
  }, []);

  const handleDispatchTeam = useCallback((teamId: string) => {
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
  }, []);

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
    },
    [],
  );

  const handleUpdateIssueStatus = useCallback((issueId: string, status: PmIssueStatus) => {
    setIssues((prev) => prev.map((iss) => (iss.id === issueId ? { ...iss, status } : iss)));
  }, []);

  const handleDelegateIssueToAgent = useCallback((issueId: string) => {
    setIssues((prev) =>
      prev.map((iss) =>
        iss.id === issueId
          ? { ...iss, status: "in_progress", assignedAgentId: iss.assignedAgentId ?? "feature-coder" }
          : iss,
      ),
    );
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

  const handleCreateWorkflow = useCallback(
    (spec: {
      name: string;
      triggerKind: "cron" | "webhook" | "event";
      triggerSpec: string;
      tokenBudget: number;
    }) => {
      setWorkflows((prev) => [
        {
          id: `WF-0${prev.length + 1}`,
          name: spec.name,
          triggerKind: spec.triggerKind,
          triggerSpec: spec.triggerSpec,
          lastRunStatus: "ready",
          tokenBudget: spec.tokenBudget,
          nodes: [
            { id: `nw-${Date.now()}-1`, label: "Execute primary agent step", agentId: "workflow-automator", dependsOn: [], status: "ready" },
            { id: `nw-${Date.now()}-2`, label: "Verify output & log Record receipt", agentId: "qa-ci-runner", dependsOn: ["step-1"], status: "ready" },
          ],
        },
        ...prev,
      ]);
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
        return {
          ...wf,
          lastRunStatus: anyFailed ? "failed" : "passed",
          nodes: updatedNodes,
        };
      }),
    );
  }, []);

  const handleToggleInstallPackage = useCallback((packageId: string) => {
    setInstalledPackageIds((prev) =>
      prev.includes(packageId) ? prev.filter((id) => id !== packageId) : [...prev, packageId],
    );
  }, []);

  const handlePublishVerifiedPackage = useCallback((pkg: MarketplacePackageItem) => {
    setPackages((prev) => [pkg, ...prev]);
    setInstalledPackageIds((prev) => [...prev, pkg.id]);
  }, []);

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
      void syncPlatformBlueprintOptional(idea, templateLabel);
    },
    [blueprintCount],
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
            onCreateIssue={handleCreateIssue}
            onUpdateIssueStatus={handleUpdateIssueStatus}
            onDelegateIssueToAgent={handleDelegateIssueToAgent}
          />
        );
      case "product":
        return (
          <ProductWorkspaceView
            experienceMode={experienceMode}
            prds={prds}
            feedback={INITIAL_USER_FEEDBACK}
            onToggleCriterion={handleToggleCriterion}
            onJumpToPm={() => setPlatformView("pm")}
          />
        );
      case "automation":
        return (
          <AutomationWorkspaceView
            experienceMode={experienceMode}
            workflows={workflows}
            onCreateWorkflow={handleCreateWorkflow}
            onRunWorkflow={handleRunWorkflow}
            onRetryFailedNode={handleRetryFailedNode}
          />
        );
      case "marketplace":
        return (
          <MarketplaceWorkspaceView
            packages={packages}
            installedPackageIds={installedPackageIds}
            onToggleInstallPackage={handleToggleInstallPackage}
            onPublishVerifiedPackage={handlePublishVerifiedPackage}
          />
        );
      case "security":
        return (
          <div>
            <SecurityPostureBanner installedPackagesCount={installedPackageIds.length} />
            <RecordAuditLedger
              selectedSeq={recordProps.selectedSeq}
              onSelectSeq={recordProps.onSelectSeq}
              verifyRequestNonce={recordProps.verifyRequestNonce}
              onOpenDiffInReview={recordProps.onOpenDiffInReview}
            />
          </div>
        );
      case "docs":
        return (
          <DocumentationWorkspaceView
            experienceMode={experienceMode}
            guides={INITIAL_DOC_GUIDES}
          />
        );
      case "operations":
        return (
          <OperationsWorkspaceView
            subscriptionTier={subscriptionTier}
            deployments={deployments}
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
    renderPlatformCanvas,
  };
}
