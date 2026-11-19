import React, { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  createApprovalRule,
  fetchAgentManifests,
  fetchApprovalRules,
  inspectAgentManifest,
  reconfirmApprovalRule,
  revokeApprovalRule,
  toggleAgentManifest,
} from "@/lib/api";
import type {
  AgentManifestItem,
  ApprovalRuleItem,
  ManifestInspectResult,
} from "@/lib/types";

/** The system prompt revision this build ships; bound rules on older versions drift. */
const PROTECTED_SEGMENTS = new Set([".keelway", ".kora", ".git"]);

type GrantPreview = { ok: boolean; text: string };

/** Client-side mirror of core/security/approval_rules.py validate_scope — preview only; the API re-validates. */
export function previewGrantScope(toolName: string, scope: string): GrantPreview {
  const trimmed = scope.trim();
  if (toolName === "run_command") {
    if (!trimmed) return { ok: false, text: "Enter the exact command to allow — e.g. pytest tests/." };
    return { ok: true, text: `Matches only the exact command "${trimmed}" run in this workspace.` };
  }
  const norm = trimmed.replace(/\\/g, "/").replace(/^\/+/, "");
  if (!norm || norm === "." || trimmed.startsWith("/") || /^[A-Za-z]:/.test(trimmed)) {
    return { ok: false, text: "Path rules must be relative to the workspace and stay inside it." };
  }
  if (norm.split("/").includes("..")) {
    return { ok: false, text: "Path rules must be relative to the workspace and stay inside it." };
  }
  if (!norm.replace(/[*?[\]/.]/g, "")) {
    return { ok: false, text: "That pattern matches every file; scope it to a file or folder." };
  }
  if (norm.split("/").some((part) => PROTECTED_SEGMENTS.has(part))) {
    return { ok: false, text: "Keelway and git internals always ask first." };
  }
  return { ok: true, text: `Matches files under "${norm}" inside this workspace.` };
}

export const CURRENT_PROMPT_VERSION = "p-14";

/** Plain-language capability labels per the permissions comprehension redesign. */
const TOOL_CAPABILITY_LABELS: Record<string, string> = {
  edit_file: "Edit workspace files",
  write_file: "Write workspace files",
  run_command: "Run sandboxed command",
};

/** Coarse plain-language categories the comprehension spec asks for. */
const TOOL_CATEGORY_LABELS: Record<string, string> = {
  edit_file: "File access",
  write_file: "File access",
  read_file: "File access",
  run_command: "Command execution",
};

/** What the rule lets the agent do, in one honest sentence. */
const TOOL_ALLOW_DESCRIPTIONS: Record<string, string> = {
  edit_file: "the agent may modify files matching this scope without asking",
  write_file: "the agent may create or overwrite files matching this scope without asking",
  read_file: "the agent may read files matching this scope without asking",
  run_command: "the agent may run this exact command without asking",
};

export function capabilityLabelForTool(toolName: string): string {
  return TOOL_CAPABILITY_LABELS[toolName] ?? toolName;
}

export function categoryLabelForTool(toolName: string): string {
  return TOOL_CATEGORY_LABELS[toolName] ?? "Agent access";
}

export function allowDescriptionForTool(toolName: string): string {
  return (
    TOOL_ALLOW_DESCRIPTIONS[toolName] ??
    "the agent may perform this action without asking"
  );
}

function formatGrantedAt(epoch: number): string {
  if (!Number.isFinite(epoch) || epoch <= 0) return "unknown date";
  return new Date(epoch * 1000).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function isRuleDrifted(
  rule: ApprovalRuleItem,
  activeModelId: string | undefined,
  currentPromptVersion: string,
): boolean {
  if (rule.boundPromptVersion && rule.boundPromptVersion !== currentPromptVersion) return true;
  return Boolean(rule.boundModelId && activeModelId && rule.boundModelId !== activeModelId);
}

const SAMPLE_MANIFEST_JSON = JSON.stringify(
  {
    schemaVersion: "keelway.agent/v1",
    name: "test-fixer",
    version: "1.2.0",
    permissions: {
      network: false,
      writeWorkspace: "ask_every_time",
      maxTier: 2,
    },
    tools: ["read_file", "search_code", "propose_patch", "run_pytest_sandbox"],
  },
  null,
  2,
);

export interface SettingsPermissionsPanelProps {
  /** Controlled rules state; when omitted the panel fetches and owns them. */
  scopedRules?: ApprovalRuleItem[];
  /** Called with the reconciled list after every successful load/mutation. */
  onUpdateScopedRules?: (nextRules: ApprovalRuleItem[]) => void;
  /** Current system prompt version — used to detect bound-version drift. */
  currentPromptVersion?: string;
  activeModelId?: string;
  /** Display name/path of the workspace these rules govern (stored in its .keelway/ dir). */
  workspaceName?: string;
  fetchRulesFn?: typeof fetchApprovalRules;
  createRuleFn?: typeof createApprovalRule;
  reconfirmRuleFn?: typeof reconfirmApprovalRule;
  revokeRuleFn?: typeof revokeApprovalRule;
  fetchManifestsFn?: typeof fetchAgentManifests;
  toggleManifestFn?: typeof toggleAgentManifest;
  inspectManifestFn?: typeof inspectAgentManifest;
}

export function SettingsPermissionsPanel({
  scopedRules: controlledRules,
  onUpdateScopedRules,
  currentPromptVersion = CURRENT_PROMPT_VERSION,
  activeModelId,
  workspaceName,
  fetchRulesFn = fetchApprovalRules,
  createRuleFn = createApprovalRule,
  reconfirmRuleFn = reconfirmApprovalRule,
  revokeRuleFn = revokeApprovalRule,
  fetchManifestsFn = fetchAgentManifests,
  toggleManifestFn = toggleAgentManifest,
  inspectManifestFn = inspectAgentManifest,
}: SettingsPermissionsPanelProps): React.JSX.Element {
  const [uncontrolledRules, setUncontrolledRules] = useState<ApprovalRuleItem[]>([]);
  const [rulesLoading, setRulesLoading] = useState(controlledRules === undefined);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [rulesBusy, setRulesBusy] = useState(false);
  const [rulesWorkspace, setRulesWorkspace] = useState<string | null>(null);
  const [grantTool, setGrantTool] = useState<"edit_file" | "write_file" | "run_command">("edit_file");
  const [grantScope, setGrantScope] = useState("");
  const [grantTtl, setGrantTtl] = useState("");
  const [grantBusy, setGrantBusy] = useState(false);
  const [armedRevokeId, setArmedRevokeId] = useState<string | null>(null);
  const [armedRevokeAll, setArmedRevokeAll] = useState(false);
  const [manifests, setManifests] = useState<AgentManifestItem[]>([]);
  const [manifestsLoading, setManifestsLoading] = useState(true);
  const [manifestsError, setManifestsError] = useState<string | null>(null);
  const [togglingIds, setTogglingIds] = useState<Record<string, boolean>>({});
  const [manifestJson, setManifestJson] = useState("");
  const [inspectResult, setInspectResult] = useState<ManifestInspectResult | null>(null);
  const [inspecting, setInspecting] = useState(false);

  const mountedRef = useRef(true);
  const togglingSetRef = useRef<Set<string>>(new Set());
  const inspectingRef = useRef(false);
  const firstReconfirmRef = useRef<HTMLButtonElement | null>(null);
  const rulesTableRef = useRef<HTMLTableElement | null>(null);
  const manifestInputId = useId();
  const fetchManifestsRef = useRef(fetchManifestsFn);
  fetchManifestsRef.current = fetchManifestsFn;
  const fetchRulesRef = useRef(fetchRulesFn);
  fetchRulesRef.current = fetchRulesFn;
  const onUpdateRulesRef = useRef(onUpdateScopedRules);
  onUpdateRulesRef.current = onUpdateScopedRules;

  const isControlled = controlledRules !== undefined;
  const scopedRules = isControlled ? controlledRules : uncontrolledRules;
  const commitRules = (next: ApprovalRuleItem[]) => {
    if (!isControlled) setUncontrolledRules(next);
    onUpdateRulesRef.current?.(next);
  };

  useEffect(() => {
    if (controlledRules !== undefined) return;
    let cancelled = false;
    setRulesLoading(true);
    fetchRulesRef
      .current()
      .then((res) => {
        if (!cancelled) {
          setUncontrolledRules(res.rules);
          setRulesWorkspace(res.workspace);
          onUpdateRulesRef.current?.(res.rules);
          setRulesError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setRulesError(
            err instanceof Error ? err.message : "Standing rules could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setRulesLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    setManifestsLoading(true);
    setManifestsError(null);
    fetchManifestsRef
      .current()
      .then((items) => {
        if (!cancelled) {
          setManifests(items);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setManifestsError(
            err instanceof Error ? err.message : "Manifest registry could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setManifestsLoading(false);
        }
      });
    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, []);

  const driftedRules = scopedRules.filter(
    (r) => !r.expired && isRuleDrifted(r, activeModelId, currentPromptVersion),
  );
  const workspaceLabel = rulesWorkspace ?? workspaceName ?? null;
  const grantPreview = previewGrantScope(grantTool, grantScope);
  const firstDrifted = driftedRules[0];
  const hasPromptVersionDelta = Boolean(
    firstDrifted?.boundPromptVersion &&
      firstDrifted.boundPromptVersion !== currentPromptVersion,
  );
  const driftTitle =
    hasPromptVersionDelta && firstDrifted
      ? `Prompt version changed: ${firstDrifted.boundPromptVersion} → ${currentPromptVersion}`
      : "Active model or prompt binding changed";
  const driftDescription =
    driftedRules.length === 1
      ? "1 Allow always rule is paused until you re-confirm it."
      : `${driftedRules.length} Allow always rules are paused until you re-confirm them.`;

  const handleGrantRule = async (event: React.FormEvent) => {
    event.preventDefault();
    if (grantBusy || !grantPreview.ok) return;
    setGrantBusy(true);
    setRulesError(null);
    try {
      const created = await createRuleFn({
        toolName: grantTool,
        scope: grantScope.trim(),
        modelId: activeModelId,
        promptVersion: currentPromptVersion,
        ...(grantTtl ? { ttlSeconds: Number(grantTtl) } : {}),
      });
      commitRules([created.rule, ...scopedRules]);
      setGrantScope("");
    } catch (err) {
      setRulesError(
        err instanceof Error ? err.message : "Grant failed — no rule was saved.",
      );
    } finally {
      setGrantBusy(false);
    }
  };

  const handleReconfirmOne = async (ruleId: string) => {
    if (rulesBusy) return;
    setRulesBusy(true);
    setRulesError(null);
    try {
      const updated = await reconfirmRuleFn(ruleId, {
        modelId: activeModelId,
        promptVersion: currentPromptVersion,
      });
      commitRules(scopedRules.map((rule) => (rule.id === ruleId ? updated : rule)));
    } catch (err) {
      setRulesError(
        err instanceof Error ? err.message : "Re-confirm failed — rule unchanged.",
      );
    } finally {
      setRulesBusy(false);
    }
  };

  const handleReconfirmAll = async () => {
    if (rulesBusy || driftedRules.length === 0) return;
    setRulesBusy(true);
    setRulesError(null);
    const results = await Promise.allSettled(
      driftedRules.map((rule) =>
        reconfirmRuleFn(rule.id, {
          modelId: activeModelId,
          promptVersion: currentPromptVersion,
        }),
      ),
    );
    const failedIds = new Set(
      results
        .map((result, idx) => (result.status === "rejected" ? driftedRules[idx]!.id : null))
        .filter((id): id is string => id !== null),
    );
    if (failedIds.size > 0) {
      setRulesError(`${failedIds.size} rule${failedIds.size === 1 ? "" : "s"} could not be re-confirmed — left unchanged.`);
    }
    const updatedById = new Map(
      results
        .map((result, idx) =>
          result.status === "fulfilled" ? ([driftedRules[idx]!.id, result.value] as const) : null,
        )
        .filter((entry): entry is readonly [string, ApprovalRuleItem] => entry !== null),
    );
    commitRules(scopedRules.map((rule) => updatedById.get(rule.id) ?? rule));
    setRulesBusy(false);
  };

  const handleRevokeOne = async (ruleId: string) => {
    if (rulesBusy) return;
    if (armedRevokeId !== ruleId) {
      setArmedRevokeId(ruleId);
      return;
    }
    setArmedRevokeId(null);
    setRulesBusy(true);
    setRulesError(null);
    try {
      await revokeRuleFn(ruleId);
      commitRules(scopedRules.filter((rule) => rule.id !== ruleId));
    } catch (err) {
      setRulesError(
        err instanceof Error ? err.message : "Revoke failed — rule is still active.",
      );
    } finally {
      setRulesBusy(false);
    }
  };

  const handleRevokeAll = async () => {
    if (rulesBusy || scopedRules.length === 0) return;
    if (!armedRevokeAll) {
      setArmedRevokeAll(true);
      return;
    }
    setArmedRevokeAll(false);
    setRulesBusy(true);
    setRulesError(null);
    const results = await Promise.allSettled(
      scopedRules.map((rule) => revokeRuleFn(rule.id)),
    );
    const kept = scopedRules.filter((_, idx) => results[idx]!.status === "rejected");
    if (kept.length > 0) {
      setRulesError(`${kept.length} rule${kept.length === 1 ? "" : "s"} could not be revoked — still active.`);
    }
    commitRules(kept);
    setRulesBusy(false);
  };

  const handleToggleManifest = async (item: AgentManifestItem) => {
    if (togglingSetRef.current.has(item.id)) return;
    togglingSetRef.current.add(item.id);
    setTogglingIds((prev) => ({ ...prev, [item.id]: true }));
    try {
      const updated = await toggleManifestFn(item.id, !item.enabled);
      if (!mountedRef.current) return;
      setManifests((prev) =>
        prev.map((m) => (m.id === item.id ? { ...m, enabled: updated.enabled } : m)),
      );
    } catch (err) {
      if (mountedRef.current) {
        setManifestsError(
          err instanceof Error ? err.message : "Kill-switch toggle failed — manifest state unchanged.",
        );
      }
    } finally {
      togglingSetRef.current.delete(item.id);
      if (mountedRef.current) {
        setTogglingIds((prev) => {
          const next = { ...prev };
          delete next[item.id];
          return next;
        });
      }
    }
  };

  const handleValidateManifest = async (event: React.FormEvent) => {
    event.preventDefault();
    if (inspectingRef.current) return;
    inspectingRef.current = true;
    setInspecting(true);
    try {
      const result = await inspectManifestFn(manifestJson);
      if (mountedRef.current) setInspectResult(result);
    } catch {
      if (mountedRef.current) {
        setInspectResult({
          valid: false,
          schemaVersion: "keelway.agent/v1",
          riskLevel: "high",
          requiresHumanP10: true,
          capabilities: [],
          warnings: [],
          errors: ["Failed to inspect manifest — loopback inspector unavailable."],
        });
      }
    } finally {
      inspectingRef.current = false;
      if (mountedRef.current) setInspecting(false);
    }
  };

  const renderSignatureStatus = (status: AgentManifestItem["signatureStatus"]): React.JSX.Element => {
    const spec =
      status === "verified"
        ? { dot: "bg-ok", text: "text-fg-muted", label: "Verified" }
        : status === "unsigned"
          ? { dot: "bg-warning", text: "text-warning", label: "Unsigned" }
          : { dot: "bg-danger", text: "text-danger", label: "Invalid" };
    return (
      <span className={`inline-flex items-center gap-1.5 font-mono text-[11px] ${spec.text}`}>
        <span aria-hidden="true" className={`inline-block h-1.5 w-1.5 rounded-full ${spec.dot}`} />
        {spec.label}
      </span>
    );
  };

  let assignedFirstReconfirmRef = false;

  return (
    <div className="space-y-5 text-ui text-fg">
      <header className="space-y-1 border-b border-border pb-3">
        <h2 className="text-sm font-semibold text-fg">Permissions &amp; Agent Manifests</h2>
        <p className="text-xs text-fg-muted">
          Scoped human-granted P-10 standing rules, immutable gate invariants, and{" "}
          <code dir="ltr" className="unicode-bidi-isolate font-mono">
            keelway.agent/v1
          </code>{" "}
          manifest kill-switches.
        </p>
      </header>

      {driftedRules.length > 0 ? (
        <CalloutBanner
          variant="prompt-drift"
          title={driftTitle}
          description={driftDescription}
          safeStateNote="Paused rules fall back to Ask every time until re-confirmed by a person."
          actions={
            <>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  if (firstReconfirmRef.current) {
                    firstReconfirmRef.current.focus();
                  } else {
                    rulesTableRef.current?.focus();
                  }
                }}
              >
                {`Review ${driftedRules.length} ${driftedRules.length === 1 ? "rule" : "rules"}`}
              </Button>
              <Button size="sm" variant="primary" onClick={handleReconfirmAll}>
                Re-confirm all
              </Button>
            </>
          }
        />
      ) : null}

      {/* Card 1: Human-Granted Allow always (scoped) Rules */}
      <section
        aria-label="Standing Allow always rules"
        className="rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
              Human-granted Allow always (scoped) rules
            </h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Bound to exact path/command scope, active model ID, and system prompt version.
            </p>
            <p className="mt-0.5 text-xs text-fg-muted">
              {workspaceLabel
                ? `Rules govern the ${workspaceLabel} workspace only — they are stored in that workspace's .keelway/ folder.`
                : "Rules govern the current workspace only — they are stored in its .keelway/ folder."}
            </p>
          </div>
          {scopedRules.length > 0 ? (
            <Button
              size="sm"
              variant={armedRevokeAll ? "primary" : "danger-ghost"}
              disabled={rulesBusy}
              onClick={() => void handleRevokeAll()}
            >
              {armedRevokeAll ? "Confirm revoke all (this workspace)" : "Revoke all"}
            </Button>
          ) : null}
        </div>

        {rulesError ? (
          <div
            role="alert"
            className="mb-3 rounded-sm border border-danger bg-danger-subtle px-3 py-2 text-xs text-fg"
          >
            {rulesError}
          </div>
        ) : null}

        <details className="mb-3 rounded-sm border border-border bg-canvas px-3 py-2.5 text-xs">
          <summary className="cursor-pointer select-none font-semibold text-fg">
            Grant a standing rule for this workspace…
          </summary>
          <form className="mt-2.5 space-y-2.5" onSubmit={(e) => void handleGrantRule(e)}>
            <div className="flex flex-wrap items-end gap-2.5">
              <label className="space-y-1">
                <span className="block text-[10px] font-semibold uppercase tracking-wide text-fg-muted">
                  Capability
                </span>
                <select
                  value={grantTool}
                  onChange={(e) => setGrantTool(e.target.value as typeof grantTool)}
                  className="rounded-xs border border-border bg-surface px-2 py-1.5 text-xs text-fg"
                >
                  <option value="edit_file">Edit workspace files</option>
                  <option value="write_file">Write workspace files</option>
                  <option value="run_command">Run sandboxed command</option>
                </select>
              </label>
              <label className="min-w-56 flex-1 space-y-1">
                <span className="block text-[10px] font-semibold uppercase tracking-wide text-fg-muted">
                  {grantTool === "run_command" ? "Exact command" : "Path pattern"}
                </span>
                <input
                  type="text"
                  value={grantScope}
                  onChange={(e) => setGrantScope(e.target.value)}
                  placeholder={
                    grantTool === "run_command" ? "pytest tests/" : "dev-app/src/**"
                  }
                  className="w-full rounded-xs border border-border bg-surface px-2 py-1.5 font-mono text-xs text-fg"
                />
              </label>
              <label className="space-y-1">
                <span className="block text-[10px] font-semibold uppercase tracking-wide text-fg-muted">
                  Expires
                </span>
                <select
                  value={grantTtl}
                  onChange={(e) => setGrantTtl(e.target.value)}
                  className="rounded-xs border border-border bg-surface px-2 py-1.5 text-xs text-fg"
                >
                  <option value="">Never</option>
                  <option value="3600">In 1 hour</option>
                  <option value="86400">In 1 day</option>
                  <option value="604800">In 7 days</option>
                </select>
              </label>
              <Button
                size="sm"
                variant="primary"
                type="submit"
                disabled={grantBusy || !grantPreview.ok}
              >
                {grantBusy ? "Granting…" : "Grant rule"}
              </Button>
            </div>
            <p
              aria-live="polite"
              className={grantPreview.ok ? "text-fg-muted" : "text-warning"}
            >
              {grantScope.trim()
                ? grantPreview.text
                : grantTool === "run_command"
                  ? "The rule fires only when the command matches exactly."
                  : "Glob pattern relative to the workspace. Keelway/git internals always ask first."}
            </p>
            <p className="text-fg-muted">
              Bound to the active model and system prompt at grant time — a model or prompt change pauses the rule until re-confirmed.
            </p>
          </form>
        </details>

        {rulesLoading ? (
          <div className="rounded-sm border border-border bg-canvas px-3 py-4 font-mono text-xs text-fg-muted">
            Loading standing rules…
          </div>
        ) : scopedRules.length === 0 ? (
          <div className="rounded-sm border border-border bg-canvas px-3 py-4 text-xs text-fg-muted">
            No standing Allow always rules — Keelway asks every time.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-sm border border-border bg-canvas">
            <table
              ref={rulesTableRef}
              tabIndex={-1}
              aria-label="Scoped Allow always rules"
              className="w-full border-collapse text-start text-xs"
            >
              <thead className="border-b border-border-strong bg-chrome text-fg-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Capability</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Scope pattern</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Bound model &amp; prompt</th>
                  <th scope="col" className="px-3 py-2 text-start font-semibold">Status</th>
                  <th scope="col" className="px-3 py-2 text-end font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {scopedRules.map((rule) => {
                  const drifted = isRuleDrifted(rule, activeModelId, currentPromptVersion);
                  const attachRef = drifted && !assignedFirstReconfirmRef;
                  if (attachRef) {
                    assignedFirstReconfirmRef = true;
                  }
                  return (
                    <tr key={rule.id} className="min-h-table-row hover:bg-surface-elevated">
                      <td className="px-3 py-2">
                        <div className="text-[10px] font-semibold uppercase tracking-wide text-fg-muted">
                          {categoryLabelForTool(rule.toolName)}
                        </div>
                        <div className="font-medium text-fg">{capabilityLabelForTool(rule.toolName)}</div>
                        <div className="text-[11px] text-fg-muted">
                          {`While active, ${allowDescriptionForTool(rule.toolName)} in this workspace.`}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <code dir="ltr" className="unicode-bidi-isolate rounded-xs border border-border bg-code px-1.5 py-0.5 font-mono text-fg">
                          {rule.scope}
                        </code>
                      </td>
                      <td className="px-3 py-2 font-mono text-fg-muted">
                        {drifted &&
                        rule.boundPromptVersion &&
                        rule.boundPromptVersion !== currentPromptVersion ? (
                          <div className="mb-1 text-warning">
                            {"prompt drift → "}
                            <code dir="ltr" className="unicode-bidi-isolate">
                              {currentPromptVersion}
                            </code>
                          </div>
                        ) : null}
                        <details className="text-[11px]">
                          <summary className="cursor-pointer select-none text-fg">
                            {rule.boundModelId || rule.boundPromptVersion
                              ? "Bound to model & prompt — details"
                              : "No model binding — details"}
                          </summary>
                          <dl className="mt-1.5 space-y-1 rounded-xs border border-border bg-surface-elevated p-2">
                            <div className="flex gap-1.5">
                              <dt className="min-w-20 text-fg-muted">Bound model</dt>
                              <dd className="text-fg">
                                <code dir="ltr" className="unicode-bidi-isolate">
                                  {rule.boundModelId ?? "none recorded"}
                                </code>
                              </dd>
                            </div>
                            <div className="flex gap-1.5">
                              <dt className="min-w-20 text-fg-muted">Bound prompt</dt>
                              <dd className="text-fg">
                                <code dir="ltr" className="unicode-bidi-isolate">
                                  {rule.boundPromptVersion ?? "none recorded"}
                                </code>
                              </dd>
                            </div>
                            <div className="flex gap-1.5">
                              <dt className="min-w-20 text-fg-muted">Granted by</dt>
                              <dd className="text-fg">{rule.createdBy || "unknown"}</dd>
                            </div>
                            <div className="flex gap-1.5">
                              <dt className="min-w-20 text-fg-muted">Granted on</dt>
                              <dd className="text-fg">{formatGrantedAt(rule.createdAtEpoch)}</dd>
                            </div>
                            <div className="flex gap-1.5">
                              <dt className="min-w-20 text-fg-muted">Expires</dt>
                              <dd className="text-fg">
                                {rule.expiresAtEpoch
                                  ? `${formatGrantedAt(rule.expiresAtEpoch)}${rule.expired ? " — dormant, kept for audit" : ""}`
                                  : "No expiry — stays until revoked"}
                              </dd>
                            </div>
                          </dl>
                        </details>
                      </td>
                      <td className="px-3 py-2">
                        {rule.expired ? (
                          <SemanticBadge kind="failed" labelOverride="Expired" />
                        ) : drifted ? (
                          <SemanticBadge kind="reconfirm" />
                        ) : (
                          <SemanticBadge kind="ready" labelOverride="Active" />
                        )}
                      </td>
                      <td className="px-3 py-2 text-end">
                        <div className="inline-flex items-center justify-end gap-1.5">
                          {drifted ? (
                            <Button
                              ref={attachRef ? firstReconfirmRef : undefined}
                              size="sm"
                              variant="primary"
                              disabled={rulesBusy}
                              onClick={() => void handleReconfirmOne(rule.id)}
                            >
                              Re-confirm
                            </Button>
                          ) : null}
                          <Button
                            size="sm"
                            variant={armedRevokeId === rule.id ? "primary" : "danger-ghost"}
                            disabled={rulesBusy}
                            onClick={() => void handleRevokeOne(rule.id)}
                          >
                            {armedRevokeId === rule.id ? "Confirm revoke" : "Revoke"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Card 2: Immutable Always ask & Who can approve Invariants */}
      <section
        aria-label="Immutable P-10 governance invariants"
        className="rounded-md border border-border-strong bg-surface p-4"
      >
        <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
          Immutable P-10 approval invariants
        </h3>
        <p className="mt-0.5 text-xs text-fg-muted">
          Enforced in runtime code; standing rules and agent manifests cannot weaken these gates.
        </p>

        <ul className="mt-3 divide-y divide-border rounded-sm border border-border bg-canvas text-xs">
          <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <div>
              <div className="font-semibold text-fg">Network and deploy</div>
              <div className="text-fg-muted">
                External sockets, git push, package publish, and cloud deployment commands require click-only Variant C confirmation.
              </div>
            </div>
            <SemanticBadge kind="locked" labelOverride="Always ask" />
          </li>
          <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <div>
              <div className="font-semibold text-fg">
                Domain-regulated actions CRE-231 / CRE-42
              </div>
              <div className="text-fg-muted">
                Healthcare, financial ledger, and tenant boundary mutations never accept standing Allow always rules.
              </div>
            </div>
            <SemanticBadge kind="locked" labelOverride="Always ask" />
          </li>
          <li className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <div>
              <div className="font-semibold text-fg">Who can approve</div>
              <div className="mt-0.5 font-medium text-fg">Only a person, at this keyboard</div>
              <div className="text-fg-muted">
                Agents and CLI scripts cannot approve P-10 gates; synthetic untrusted events are rejected.
              </div>
            </div>
            <SemanticBadge kind="locked" />
          </li>
        </ul>
      </section>

      {/* Card 3: keelway.agent/v1 Manifest Registry & Live JSON Inspector */}
      <section
        aria-label="Agent manifest registry and validator"
        className="space-y-4 rounded-md border border-border-strong bg-surface p-4"
      >
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
            Agent Manifest Registry (<code dir="ltr" className="unicode-bidi-isolate font-mono">keelway.agent/v1</code>)
          </h3>
          <p className="mt-0.5 text-xs text-fg-muted">
            HMAC-SHA256 signed capability envelopes and Tier-3 runtime kill-switches.
          </p>
        </div>

        {manifestsError ? (
          <div
            role="alert"
            className="rounded-sm border border-danger bg-danger-subtle px-3 py-2 text-xs text-fg"
          >
            {manifestsError}
          </div>
        ) : null}

        <div className="overflow-x-auto rounded-sm border border-border bg-canvas">
          <table
            aria-label="Agent manifest registry"
            className="w-full border-collapse text-start text-xs"
          >
            <thead className="border-b border-border-strong bg-chrome text-fg-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Agent</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Signature</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Autonomy</th>
                <th scope="col" className="px-3 py-2 text-end font-semibold">Kill-Switch</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {manifestsLoading && manifests.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-3 font-mono text-fg-muted">
                    Loading registered manifests…
                  </td>
                </tr>
              ) : manifests.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-3 text-fg-muted">
                    No agent manifests registered on this install.
                  </td>
                </tr>
              ) : (
                manifests.map((item) => (
                  <tr key={item.id} className="min-h-table-row hover:bg-surface-elevated">
                    <td className="px-3 py-2">
                      <div className="font-mono font-medium text-fg">
                        <code dir="ltr" className="unicode-bidi-isolate">
                          {`${item.name}@${item.version}`}
                        </code>
                      </div>
                      <div className="text-[11px] text-fg-muted">{item.description}</div>
                      <div className="mt-0.5 font-mono text-[10px] text-fg-dim">
                        <code dir="ltr" className="unicode-bidi-isolate">{item.schemaVersion}</code>
                      </div>
                      {item.securityWarnings && item.securityWarnings.length > 0 ? (
                        <details className="mt-1 text-[11px]">
                          <summary className="cursor-pointer select-none text-warning">
                            {`${item.securityWarnings.length} warning${item.securityWarnings.length === 1 ? "" : "s"}`}
                          </summary>
                          <ul className="mt-1 space-y-1">
                            {item.securityWarnings.map((warn) => (
                              <li
                                key={warn}
                                className="rounded-xs border border-warning bg-warning-subtle px-1.5 py-0.5 text-fg"
                              >
                                {warn}
                              </li>
                            ))}
                          </ul>
                        </details>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{renderSignatureStatus(item.signatureStatus)}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-baseline gap-x-1.5 font-mono text-[11px]">
                        <span className="text-fg">{`Tier ${item.maxTier}`}</span>
                        {item.networkAllowed ? (
                          <span className="inline-flex items-center gap-1 text-warning">
                            <span aria-hidden="true" className="inline-block h-1.5 w-1.5 rounded-full bg-warning" />
                            network allowed
                          </span>
                        ) : (
                          <span className="text-fg-dim">· offline</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-end">
                      <Button
                        size="sm"
                        variant={item.enabled ? "secondary" : "danger-ghost"}
                        aria-pressed={item.enabled}
                        aria-label={`Kill-switch for ${item.name}@${item.version}: ${item.enabled ? "Enabled" : "Disabled"}`}
                        loading={Boolean(togglingIds[item.id])}
                        onClick={() => void handleToggleManifest(item)}
                      >
                        {item.enabled ? "Enabled" : "Disabled"}
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <form onSubmit={(e) => void handleValidateManifest(e)} className="space-y-2.5 pt-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor={manifestInputId} className="text-xs font-semibold text-fg">
              Manifest JSON (keelway.agent/v1)
            </label>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setManifestJson(SAMPLE_MANIFEST_JSON)}
              >
                Insert example manifest
              </Button>
              <Button type="submit" size="sm" variant="primary" loading={inspecting}>
                Validate manifest
              </Button>
            </div>
          </div>
          <textarea
            id={manifestInputId}
            dir="ltr"
            spellCheck={false}
            rows={6}
            value={manifestJson}
            onChange={(e) => setManifestJson(e.target.value)}
            placeholder={'Paste a keelway.agent/v1 manifest, or press "Insert example manifest".'}
            className="unicode-bidi-isolate w-full rounded-sm border border-border-control bg-code p-2.5 font-mono text-xs text-fg"
          />

          {inspectResult ? (
            <div
              data-testid="manifest-inspect-result"
              className="space-y-2 rounded-sm border border-border-strong bg-canvas p-3 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2">
                {inspectResult.valid ? (
                  <SemanticBadge kind="passed" labelOverride="Valid" />
                ) : (
                  <SemanticBadge kind="failed" labelOverride="Invalid" />
                )}
                <span className="font-mono text-fg-muted">
                  Risk: <strong className="uppercase text-fg">{inspectResult.riskLevel}</strong>
                </span>
                <span className="font-mono text-fg-muted">
                  {inspectResult.requiresHumanP10
                    ? "P-10 human gate required"
                    : "Read-only Tier 1"}
                </span>
              </div>

              {inspectResult.capabilities.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-fg-muted">Capabilities:</span>
                  {inspectResult.capabilities.map((cap) => (
                    <code
                      key={cap}
                      dir="ltr"
                      className="unicode-bidi-isolate rounded-xs border border-border bg-code px-1.5 py-0.5 font-mono text-[11px] text-fg"
                    >
                      {cap}
                    </code>
                  ))}
                </div>
              ) : null}

              {inspectResult.warnings.map((warn) => (
                <p key={warn} className="rounded-xs border border-warning bg-warning-subtle px-2 py-1 text-fg">
                  {warn}
                </p>
              ))}
              {inspectResult.errors.map((err) => (
                <p key={err} role="alert" className="rounded-xs border border-danger bg-danger-subtle px-2 py-1 text-fg">
                  {err}
                </p>
              ))}
            </div>
          ) : null}
        </form>
      </section>
    </div>
  );
}
