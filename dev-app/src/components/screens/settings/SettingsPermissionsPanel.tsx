import React, { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  fetchAgentManifests,
  inspectAgentManifest,
  toggleAgentManifest,
} from "@/lib/api";
import type {
  AgentManifestItem,
  ManifestInspectResult,
  ScopedPermissionRule,
} from "@/lib/types";

export const DEFAULT_SCOPED_RULES: ScopedPermissionRule[] = [
  {
    id: "rule-pytest-local",
    capability: "Run sandboxed command",
    scopePattern: "pytest tests/**",
    mode: "allow_scoped",
    boundModelId: "coder-7b@2.5.1",
    boundPromptVersion: "p-13",
    currentPromptVersion: "p-14",
    driftDetected: true,
    createdAt: "2026-11-12T18:00:00Z",
  },
  {
    id: "rule-edit-devapp",
    capability: "Edit workspace files",
    scopePattern: "dev-app/src/**",
    mode: "allow_scoped",
    boundModelId: "coder-7b@2.5.1",
    boundPromptVersion: "p-13",
    currentPromptVersion: "p-14",
    driftDetected: true,
    createdAt: "2026-11-12T19:15:00Z",
  },
];

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
  scopedRules: ScopedPermissionRule[];
  onUpdateScopedRules: (nextRules: ScopedPermissionRule[]) => void;
  activeModelId?: string;
  fetchManifestsFn?: typeof fetchAgentManifests;
  toggleManifestFn?: typeof toggleAgentManifest;
  inspectManifestFn?: typeof inspectAgentManifest;
}

export function SettingsPermissionsPanel({
  scopedRules,
  onUpdateScopedRules,
  activeModelId,
  fetchManifestsFn = fetchAgentManifests,
  toggleManifestFn = toggleAgentManifest,
  inspectManifestFn = inspectAgentManifest,
}: SettingsPermissionsPanelProps): React.JSX.Element {
  const [manifests, setManifests] = useState<AgentManifestItem[]>([]);
  const [manifestsLoading, setManifestsLoading] = useState(true);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [manifestJson, setManifestJson] = useState(SAMPLE_MANIFEST_JSON);
  const [inspectResult, setInspectResult] = useState<ManifestInspectResult | null>(null);
  const [inspecting, setInspecting] = useState(false);

  const firstReconfirmRef = useRef<HTMLButtonElement | null>(null);
  const rulesTableRef = useRef<HTMLTableElement | null>(null);
  const manifestInputId = useId();
  const fetchManifestsRef = useRef(fetchManifestsFn);
  fetchManifestsRef.current = fetchManifestsFn;

  useEffect(() => {
    let cancelled = false;
    setManifestsLoading(true);
    fetchManifestsRef
      .current()
      .then((items) => {
        if (!cancelled) {
          setManifests(items);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setManifestsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const driftedRules = scopedRules.filter((r) => r.driftDetected);
  const firstDrifted = driftedRules[0];
  const hasPromptVersionDelta = Boolean(
    firstDrifted && firstDrifted.boundPromptVersion !== firstDrifted.currentPromptVersion,
  );
  const driftTitle =
    hasPromptVersionDelta && firstDrifted
      ? `Prompt version changed: ${firstDrifted.boundPromptVersion} → ${firstDrifted.currentPromptVersion}`
      : "Active model or prompt binding changed";
  const driftDescription =
    driftedRules.length === 1
      ? "1 Allow always rule is paused until you re-confirm it."
      : `${driftedRules.length} Allow always rules are paused until you re-confirm them.`;

  const handleReconfirmOne = (ruleId: string) => {
    onUpdateScopedRules(
      scopedRules.map((rule) =>
        rule.id === ruleId
          ? {
              ...rule,
              boundPromptVersion: rule.currentPromptVersion,
              boundModelId: activeModelId ?? rule.boundModelId,
              driftDetected: false,
            }
          : rule,
      ),
    );
  };

  const handleReconfirmAll = () => {
    onUpdateScopedRules(
      scopedRules.map((rule) => ({
        ...rule,
        boundPromptVersion: rule.currentPromptVersion,
        boundModelId: activeModelId ?? rule.boundModelId,
        driftDetected: false,
      })),
    );
  };

  const handleRevokeOne = (ruleId: string) => {
    onUpdateScopedRules(scopedRules.filter((rule) => rule.id !== ruleId));
  };

  const handleRevokeAll = () => {
    onUpdateScopedRules([]);
  };

  const handleToggleManifest = async (item: AgentManifestItem) => {
    setTogglingId(item.id);
    try {
      const updated = await toggleManifestFn(item.id, !item.enabled);
      setManifests((prev) =>
        prev.map((m) => (m.id === item.id ? { ...m, enabled: updated.enabled } : m)),
      );
    } finally {
      setTogglingId(null);
    }
  };

  const handleValidateManifest = async (event: React.FormEvent) => {
    event.preventDefault();
    setInspecting(true);
    try {
      const result = await inspectManifestFn(manifestJson);
      setInspectResult(result);
    } finally {
      setInspecting(false);
    }
  };

  const renderSignatureBadge = (status: AgentManifestItem["signatureStatus"]): React.JSX.Element => {
    if (status === "verified") {
      return <SemanticBadge kind="passed" labelOverride="Verified" />;
    }
    if (status === "unsigned") {
      return <SemanticBadge kind="reconfirm" labelOverride="Unsigned" />;
    }
    return <SemanticBadge kind="failed" labelOverride="Invalid" />;
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
          </div>
          {scopedRules.length > 0 ? (
            <Button size="sm" variant="danger-ghost" onClick={handleRevokeAll}>
              Revoke all
            </Button>
          ) : null}
        </div>

        {scopedRules.length === 0 ? (
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
                  const attachRef = rule.driftDetected && !assignedFirstReconfirmRef;
                  if (attachRef) {
                    assignedFirstReconfirmRef = true;
                  }
                  return (
                    <tr key={rule.id} className="min-h-table-row hover:bg-surface-elevated">
                      <td className="px-3 py-2 font-medium text-fg">{rule.capability}</td>
                      <td className="px-3 py-2">
                        <code dir="ltr" className="unicode-bidi-isolate rounded-xs border border-border bg-code px-1.5 py-0.5 font-mono text-fg">
                          {rule.scopePattern}
                        </code>
                      </td>
                      <td className="px-3 py-2 font-mono text-fg-muted">
                        <code dir="ltr" className="unicode-bidi-isolate">
                          {`${rule.boundModelId} · ${rule.boundPromptVersion}`}
                        </code>
                        {rule.driftDetected && rule.boundPromptVersion !== rule.currentPromptVersion ? (
                          <span className="ms-1.5 text-warning">
                            {"→ "}
                            <code dir="ltr" className="unicode-bidi-isolate">
                              {rule.currentPromptVersion}
                            </code>
                          </span>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">
                        {rule.driftDetected ? (
                          <SemanticBadge kind="reconfirm" />
                        ) : (
                          <SemanticBadge kind="ready" labelOverride="Active" />
                        )}
                      </td>
                      <td className="px-3 py-2 text-end">
                        <div className="inline-flex items-center justify-end gap-1.5">
                          {rule.driftDetected ? (
                            <Button
                              ref={attachRef ? firstReconfirmRef : undefined}
                              size="sm"
                              variant="primary"
                              onClick={() => handleReconfirmOne(rule.id)}
                            >
                              Re-confirm
                            </Button>
                          ) : null}
                          <Button
                            size="sm"
                            variant="danger-ghost"
                            onClick={() => handleRevokeOne(rule.id)}
                          >
                            Revoke
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

        <div className="overflow-x-auto rounded-sm border border-border bg-canvas">
          <table
            aria-label="Agent manifest registry"
            className="w-full border-collapse text-start text-xs"
          >
            <thead className="border-b border-border-strong bg-chrome text-fg-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Agent</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Schema</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">HMAC-SHA256 Signature</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Autonomy / Tier</th>
                <th scope="col" className="px-3 py-2 text-end font-semibold">Kill-Switch</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {manifestsLoading && manifests.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-3 font-mono text-fg-muted">
                    Loading registered manifests…
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
                      {item.securityWarnings && item.securityWarnings.length > 0 ? (
                        <ul className="mt-1 space-y-1">
                          {item.securityWarnings.map((warn) => (
                            <li
                              key={warn}
                              className="rounded-xs border border-warning bg-warning-subtle px-1.5 py-0.5 text-[11px] text-fg"
                            >
                              {warn}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 font-mono text-fg-muted">
                      <code dir="ltr" className="unicode-bidi-isolate">{item.schemaVersion}</code>
                    </td>
                    <td className="px-3 py-2">{renderSignatureBadge(item.signatureStatus)}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="rounded-xs border border-border-control bg-surface-elevated px-1.5 py-0.5 font-mono text-[11px] text-fg">
                          {`Tier ${item.maxTier}`}
                        </span>
                        {item.networkAllowed ? (
                          <SemanticBadge kind="reconfirm" labelOverride="Network allowed" />
                        ) : (
                          <span className="font-mono text-[11px] text-fg-muted">Offline sandbox</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-end">
                      <Button
                        size="sm"
                        variant={item.enabled ? "secondary" : "danger-ghost"}
                        aria-pressed={item.enabled}
                        aria-label={`Kill-switch for ${item.name}@${item.version}: ${item.enabled ? "Enabled" : "Disabled"}`}
                        loading={togglingId === item.id}
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
            <Button type="submit" size="sm" variant="primary" loading={inspecting}>
              Validate manifest
            </Button>
          </div>
          <textarea
            id={manifestInputId}
            dir="ltr"
            spellCheck={false}
            rows={6}
            value={manifestJson}
            onChange={(e) => setManifestJson(e.target.value)}
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
