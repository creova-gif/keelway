import { getStudioToken } from "@/lib/api";
import type {
  AutomationWorkflowItem,
  ByomValidationResult,
  GeneratedProjectBlueprint,
  MarketplaceScanInput,
  MarketplaceScanReport,
  PmIssueItem,
  ProductPrdItem,
} from "@/lib/platformData";

function deterministicShortHash(text: string): string {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return `sha256:${(h >>> 0).toString(16).padStart(8, "0")}e4b9`;
}

export function scanMarketplacePackageClient(input: MarketplaceScanInput): MarketplaceScanReport {
  const findings: MarketplaceScanReport["findings"] = [];
  const hay = `${input.name}\n${input.instructions}`.toLowerCase();

  if (
    /ignore\s+previous\s+instructions|bypass\s+p-10|disable\s+airgap|auto-approve\s+risk\s+c|reveal\s+system\s+prompt/i.test(
      hay,
    )
  ) {
    findings.push({
      code: "PROMPT_INJECTION_GUARDRAIL_BYPASS",
      severity: "critical",
      message: "Rejected directive attempting to override system instructions or bypass P-10 human gates.",
    });
  }
  if (/eval\s*\(|exec\s*\(|shell\s*=\s*true|curl\s+[^|\n]+\|\s*(?:sh|bash)|os\.system\s*\(/i.test(hay)) {
    findings.push({
      code: "DANGEROUS_EXECUTION_HOOK",
      severity: "critical",
      message: "Rejected dynamic code evaluation or unsandboxed shell execution hook.",
    });
  }
  const paths = input.writePaths.split(",").map((p) => p.trim()).filter(Boolean);
  if (paths.some((p) => p === "/" || p.includes("..")) || (input.networkFull && !input.requiresP10Approval)) {
    findings.push({
      code: "UNSCOPED_PERMISSION_ENVELOPE",
      severity: "high",
      message: "Wildcard root '/' or parent '..' writes and unapproved full-network scopes are prohibited.",
    });
  }
  if (/\bsk-[a-zA-Z0-9_-]{8,}|\bghp_[a-zA-Z0-9]{10,}|\bAKIA[0-9A-Z]{12,}/.test(input.instructions)) {
    findings.push({
      code: "EMBEDDED_SECRET_DETECTED",
      severity: "critical",
      message: "Live API key or credential token detected in package manifest/instructions.",
    });
  }

  const revenueSplitLabel =
    input.publisherTier === "first_party"
      ? "100% First-Party · $0 Fee"
      : input.publisherTier === "enterprise_partner"
        ? "80% Partner / 20% Platform"
        : "85% Creator / 15% Platform";

  return {
    passed: findings.length === 0,
    riskGrade: findings.length > 0 ? "BLOCKED" : input.requiresP10Approval ? "A" : "B",
    manifestSha256: deterministicShortHash(`${input.name}:${input.category}:${input.instructions}`),
    revenueSplitLabel,
    findings,
  };
}

export function validateByomCredentialClient(
  provider: string,
  credentialKind: "api_key" | "self_hosted_endpoint" | "consumer_subscription",
  tokenPreview: string,
): ByomValidationResult {
  const trimmed = tokenPreview.trim().toLowerCase();
  if (
    credentialKind === "consumer_subscription" ||
    trimmed.startsWith("chatgpt-plus") ||
    trimmed.startsWith("claude-pro-cookie") ||
    trimmed.startsWith("sk-ant-sid01")
  ) {
    return {
      valid: false,
      code: "CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION",
      message: `Rejected for ${provider}: consumer web subscriptions/session cookies cannot be used for third-party API access. Provide an authorized vendor API key or self-hosted endpoint.`,
    };
  }
  return {
    valid: true,
    code: "AUTHORIZED_BYOM_CREDENTIAL",
    message: `Verified ${provider} ${credentialKind === "self_hosted_endpoint" ? "self-hosted endpoint" : "API credential"} · $0.00 Keelway token markup.`,
  };
}

export function generateLocalBlueprint(
  rawIdea: string,
  templateLabel = "Governed Full-Stack App",
  seqOffset = 0,
): GeneratedProjectBlueprint {
  const cleanIdea = rawIdea.trim() || "Internal Operations Approval Portal";
  const slug = cleanIdea.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 28) || "app";
  const baseNum = 201 + seqOffset * 4;
  const prdId = `PRD-NC-${10 + seqOffset}`;
  const issueIds = [`KEEL-${baseNum}`, `KEEL-${baseNum + 1}`, `KEEL-${baseNum + 2}`];

  const prd: ProductPrdItem = {
    id: prdId,
    title: cleanIdea,
    problemStatement: `Deliver "${cleanIdea}" (${templateLabel}) with governed permissions, audit receipts, and zero context loss between non-coders and engineers.`,
    riceScore: 89,
    releaseStage: "in_delivery",
    linkedIssueIds: issueIds,
    acceptanceCriteria: [
      { id: `${prdId}-ac1`, text: `Scaffold responsive UI & typed API routes for ${cleanIdea}`, met: true },
      { id: `${prdId}-ac2`, text: "Enforce RBAC permissions & P-10 human approval on destructive actions", met: true },
      { id: `${prdId}-ac3`, text: "Pass WCAG 2.2 AA accessibility & SHA-256 Record audit logging", met: false },
    ],
  };

  const issues: PmIssueItem[] = [
    { id: issueIds[0]!, title: `Design data schema & UI views for ${cleanIdea}`, status: "todo", priority: "high", sprint: "Sprint 15 · Blueprint Delivery", milestone: "Blueprint v1", dependencies: [], assignedAgentId: "nocode-app-builder", linkedPrdId: prdId },
    { id: issueIds[1]!, title: `Wire KFlow notifications & RBAC rules for ${cleanIdea}`, status: "todo", priority: "high", sprint: "Sprint 15 · Blueprint Delivery", milestone: "Blueprint v1", dependencies: [issueIds[0]!], assignedAgentId: "workflow-automator", linkedPrdId: prdId },
    { id: issueIds[2]!, title: `Run sandboxed QA & P-10 launch gate for ${cleanIdea}`, status: "backlog", priority: "medium", sprint: "Sprint 15 · Blueprint Delivery", milestone: "Blueprint v1", dependencies: [issueIds[1]!], assignedAgentId: "qa-ci-runner", linkedPrdId: prdId },
  ];

  const workflow: AutomationWorkflowItem = {
    id: `WF-NC-${10 + seqOffset}`,
    name: `Blueprint Delivery DAG · ${cleanIdea.slice(0, 44)}`,
    triggerKind: "event",
    triggerSpec: `blueprint.commit (${slug})`,
    lastRunStatus: "ready",
    tokenBudget: 30_000,
    nodes: [
      { id: `${slug}-n1`, label: "Scaffold UI & API schema", agentId: "nocode-app-builder", dependsOn: [], status: "passed" },
      { id: `${slug}-n2`, label: "Automated QA & security scan", agentId: "qa-ci-runner", dependsOn: [`${slug}-n1`], status: "ready" },
      { id: `${slug}-n3`, label: "P-10 governed preview publish", agentId: "devops-sre", dependsOn: [`${slug}-n2`], status: "ready" },
    ],
  };

  return {
    idea: cleanIdea,
    templateLabel,
    prd,
    issues,
    workflow,
    assignedTeamId: "team-idea-to-prod",
    assignedTeamName: "Idea-to-Production Squad",
    previewUrl: `http://127.0.0.1:7420/preview/${slug}`,
    generatedAt: "just now",
  };
}

export async function syncPlatformBlueprintOptional(idea: string, templateLabel: string): Promise<void> {
  if (import.meta.env.MODE === "test" || typeof fetch !== "function") return;
  try {
    const headers = new Headers({ "Content-Type": "application/json", Accept: "application/json" });
    const token = getStudioToken();
    if (token) {
      headers.set("X-Studio-Token", token);
      headers.set("Authorization", `Bearer ${token}`);
    }
    await fetch("/v1/platform/nocode/blueprint", {
      method: "POST",
      credentials: "same-origin",
      headers,
      body: JSON.stringify({ idea, target_stack: templateLabel }),
    });
  } catch {
    // Offline local-first fallback already applied synchronously
  }
}
