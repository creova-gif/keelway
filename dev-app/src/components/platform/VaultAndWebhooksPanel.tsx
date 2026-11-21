import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateVaultOrWebhooks, computeLocalFingerprintHex, deleteVaultSecret, deleteWebhook,
  fetchVaultSecrets, fetchWebhooks, maskSecretValue, postCreateWebhook, postRotateVaultSecret,
  postTestWebhook, postVaultSecret, validateWebhookUrlClient,
  type RbacRoleId, type VaultSecretMetaItem, type WebhookDeliveryReceipt, type WebhookEndpointItem,
} from "@/lib/platformRuntimeApi";

export interface VaultAndWebhooksPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

const SEED_SECRETS: VaultSecretMetaItem[] = [
  { name: "OPENAI_BYOM_KEY", namespace: "byom", maskedPreview: "sk-p****9921", fingerprintSha256: "sha256:4a91c8e2d0b377f1", version: 1, cipher: "AES-256-GCM", updatedAt: "Seeded · WAL" },
  { name: "PARTNER_WEBHOOK_KEY", namespace: "webhooks", maskedPreview: "whse****4410", fingerprintSha256: "sha256:9d03b7c4e812aa50", version: 2, cipher: "AES-256-GCM", updatedAt: "Seeded · WAL" },
];

const SEED_WEBHOOKS: WebhookEndpointItem[] = [
  { id: "wh-sovereign-audit", url: "https://hooks.keelway.internal/v1/audit-events", events: ["run.completed", "p10.approved", "vault.rotated"], description: "Enterprise SIEM & plugin receipt subscriber", active: true, createdAt: "Seeded · Active" },
];

const WEBHOOK_EVENT_TOPICS = ["run.completed", "p10.held", "p10.approved", "vault.rotated"] as const;

export function VaultAndWebhooksPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: VaultAndWebhooksPanelProps): React.JSX.Element {
  const canMutate = canRbacMutateVaultOrWebhooks(activeRbacRole);
  const [secrets, setSecrets] = useState<VaultSecretMetaItem[]>(SEED_SECRETS);
  const [secretName, setSecretName] = useState("");
  const [secretNamespace, setSecretNamespace] = useState("byom");
  const secretInputRef = useRef<HTMLInputElement | null>(null);
  const [vaultFeedback, setVaultFeedback] = useState<string | null>(null);

  const [webhooks, setWebhooks] = useState<WebhookEndpointItem[]>(SEED_WEBHOOKS);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>(["run.completed", "p10.approved"]);
  const [webhookAlert, setWebhookAlert] = useState<string | null>(null);
  const [receiptsByWh, setReceiptsByWh] = useState<Record<string, WebhookDeliveryReceipt>>({});

  useEffect(() => {
    let cancelled = false;
    void fetchVaultSecrets(workspaceId).then((remote) => {
      if (cancelled || !remote?.length) return;
      setSecrets((prev) => {
        const byName = new Map(prev.map((s) => [s.name, s]));
        remote.forEach((r) => byName.set(r.name, r));
        return Array.from(byName.values());
      });
    });
    void fetchWebhooks(workspaceId).then((remoteWh) => {
      if (cancelled || !remoteWh?.length) return;
      setWebhooks((prev) => {
        const byId = new Map(prev.map((w) => [w.id, w]));
        remoteWh.forEach((w) => byId.set(w.id, w));
        return Array.from(byId.values());
      });
    });
    return () => { cancelled = true; };
  }, [workspaceId]);

  const handleStoreSecret = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canMutate) return;
    const cleanName = secretName.trim().toUpperCase().replace(/[^A-Z0-9_-]+/g, "_");
    const rawSecret = secretInputRef.current?.value.trim() ?? "";
    if (secretInputRef.current) secretInputRef.current.value = "";
    if (!cleanName || !rawSecret) return;

    const maskedPreview = maskSecretValue(rawSecret);
    const fingerprintSha256 = `sha256:${computeLocalFingerprintHex(`${cleanName}:v1:${rawSecret.length}:${maskedPreview}`)}`;
    const optimistic: VaultSecretMetaItem = {
      name: cleanName, namespace: secretNamespace, maskedPreview, fingerprintSha256,
      version: 1, cipher: "AES-256-GCM", updatedAt: "Encrypted just now",
    };
    setSecrets((prev) => [optimistic, ...prev.filter((s) => s.name !== cleanName)]);
    setSecretName("");
    setVaultFeedback(`Stored ${cleanName} (${maskedPreview}) in AES-256-GCM SQLite WAL vault.`);
    void postVaultSecret({ workspaceId, name: cleanName, namespace: secretNamespace, secretValue: rawSecret, role: activeRbacRole }).then((res) => {
      if (res.ok) setSecrets((prev) => prev.map((s) => (s.name === cleanName ? res.item : s)));
    });
  };

  const handleRotateSecret = (target: VaultSecretMetaItem) => {
    if (!canMutate) return;
    const typedReplacement = secretInputRef.current?.value.trim() ?? "";
    if (secretInputRef.current) secretInputRef.current.value = "";
    const nextVersion = target.version + 1;
    const nextMask = typedReplacement ? maskSecretValue(typedReplacement) : target.maskedPreview;
    const nextFp = `sha256:${computeLocalFingerprintHex(`${target.name}:v${nextVersion}:${nextMask}`)}`;
    setSecrets((prev) => prev.map((s) => s.name === target.name ? { ...s, version: nextVersion, maskedPreview: nextMask, fingerprintSha256: nextFp, updatedAt: "Rotated just now" } : s));
    setVaultFeedback(`Rotated ${target.name} to v${nextVersion} with fresh 12-byte GCM nonce.`);
    void postRotateVaultSecret({
      workspaceId, name: target.name, namespace: target.namespace, secretValue: typedReplacement,
      currentVersion: target.version, currentMask: target.maskedPreview, role: activeRbacRole,
    }).then((res) => {
      if (res.ok) setSecrets((prev) => prev.map((s) => (s.name === target.name ? res.item : s)));
    });
  };

  const handleRevokeSecret = (name: string) => {
    if (!canMutate) return;
    setSecrets((prev) => prev.filter((s) => s.name !== name));
    setVaultFeedback(`Revoked secret ${name} from workspace ${workspaceId}.`);
    void deleteVaultSecret(name, workspaceId, activeRbacRole);
  };

  const handleToggleEventTopic = (topic: string) => {
    setSelectedEvents((prev) => prev.includes(topic) ? (prev.length > 1 ? prev.filter((t) => t !== topic) : prev) : [...prev, topic]);
  };

  const handleRegisterWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canMutate) return;
    const clientValidation = validateWebhookUrlClient(webhookUrl);
    if (!clientValidation.valid) {
      setWebhookAlert(clientValidation.reason ?? "SSRF / Insecure Transport Blocked");
      return;
    }
    setWebhookAlert(null);
    const cleanUrl = webhookUrl.trim();
    const res = await postCreateWebhook({ workspaceId, url: cleanUrl, events: selectedEvents, role: activeRbacRole });
    if (!res.ok || !res.webhook) {
      setWebhookAlert(res.error ?? "SSRF / Insecure Transport Blocked");
      return;
    }
    setWebhooks((prev) => [res.webhook!, ...prev.filter((w) => w.url !== cleanUrl)]);
    setWebhookUrl("");
  };

  const handleSendTestPing = async (wh: WebhookEndpointItem) => {
    if (!canMutate) return;
    const receipt = await postTestWebhook(wh.id, workspaceId);
    setReceiptsByWh((prev) => ({ ...prev, [wh.id]: receipt }));
  };

  const handleRemoveWebhook = (wh: WebhookEndpointItem) => {
    if (!canMutate) return;
    setWebhooks((prev) => prev.filter((w) => w.id !== wh.id));
    void deleteWebhook(wh.id, workspaceId, activeRbacRole);
  };

  return (
    <div className="space-y-4">
      {!canMutate ? (
        <div role="status" className="rounded-sm border border-warning/45 bg-warning-subtle px-3.5 py-2 font-mono text-xs text-fg">
          {`RBAC Read-Only Notice (${activeRbacRole}): Vault secret mutations and webhook registrations are disabled for viewer role. Switch to owner, admin, builder, or operator to mutate.`}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Encrypted local secret vault" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-fg">Encrypted Local Secret Vault</h2>
              <p className="text-xs text-fg-muted">AES-256-GCM + HKDF-SHA256 SQLite WAL vault · raw plaintext never stored in state or returned over HTTP.</p>
            </div>
            <SemanticBadge kind="passed" labelOverride={`AES-256-GCM · ${workspaceId}`} />
          </div>

          <form onSubmit={handleStoreSecret} className="grid gap-2.5 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Secret name</span>
              <input type="text" aria-label="Secret name" value={secretName} onChange={(e) => setSecretName(e.target.value)} placeholder="ANTHROPIC_API_KEY" disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Namespace</span>
              <select aria-label="Secret namespace" value={secretNamespace} onChange={(e) => setSecretNamespace(e.target.value)} disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                <option value="byom">byom</option>
                <option value="webhooks">webhooks</option>
                <option value="plugins">plugins</option>
                <option value="mcp">mcp</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Plaintext value</span>
              <input ref={secretInputRef} type="password" aria-label="Plaintext secret value" defaultValue="" autoComplete="off" placeholder="sk-live-..." disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-2 sm:col-span-3">
              <span className="font-mono text-[11px] text-fg-muted">12-byte random nonce · masked **** preview only</span>
              <Button type="submit" size="sm" variant="primary" disabled={!canMutate}>Encrypt &amp; Store Secret</Button>
            </div>
          </form>

          {vaultFeedback ? (
            <div role="status" className="rounded-xs border border-ok/40 bg-ok-subtle px-2.5 py-1.5 font-mono text-[11px] text-fg">{vaultFeedback}</div>
          ) : null}

          <ul className="space-y-2 text-xs">
            {secrets.map((item) => (
              <li key={item.name} className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-canvas px-3 py-2">
                <div className="space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2 font-mono">
                    <span className="font-semibold text-fg">{item.name}</span>
                    <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 text-[10px] text-accent">{item.maskedPreview}</span>
                    <span className="text-[10px] text-fg-muted">{`v${item.version} · ${item.cipher}`}</span>
                  </div>
                  <div className="font-mono text-[10px] text-fg-muted">{`ns:${item.namespace} · ${item.fingerprintSha256}`}</div>
                </div>
                <div className="flex items-center gap-1.5">
                  <Button size="sm" variant="secondary" disabled={!canMutate} aria-label={`Rotate Secret ${item.name}`} onClick={() => handleRotateSecret(item)}>Rotate Secret</Button>
                  <Button size="sm" variant="danger-ghost" disabled={!canMutate} aria-label={`Revoke Secret ${item.name}`} onClick={() => handleRevokeSecret(item.name)}>Revoke Secret</Button>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section aria-label="Signed webhook and plugin event bus" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-fg">Signed Webhook &amp; Plugin Event Bus</h2>
              <p className="text-xs text-fg-muted">HMAC-SHA256 envelopes (`X-Keelway-Signature-256`) with strict cloud-metadata SSRF blocking.</p>
            </div>
            <SemanticBadge kind="opencore" labelOverride="HMAC-SHA256 + SSRF Guard" />
          </div>

          <form onSubmit={(e) => { void handleRegisterWebhook(e); }} className="space-y-2.5">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Destination HTTPS or loopback webhook URL</span>
              <input type="text" aria-label="Webhook endpoint URL" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://hooks.example.org/keelway/events" disabled={!canMutate} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <fieldset className="rounded-xs border border-border bg-chrome px-2.5 py-2">
              <legend className="px-1 font-mono text-[10px] text-fg-muted">Subscribed Event Topics</legend>
              <div className="flex flex-wrap gap-3 text-xs text-fg">
                {WEBHOOK_EVENT_TOPICS.map((topic) => (
                  <label key={topic} className="inline-flex items-center gap-1.5 font-mono text-[11px]">
                    <input type="checkbox" checked={selectedEvents.includes(topic)} disabled={!canMutate} onChange={() => handleToggleEventTopic(topic)} />
                    <span>{topic}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] text-fg-muted">Blocks 169.254.169.254, metadata.google.internal &amp; file://</span>
              <Button type="submit" size="sm" variant="primary" disabled={!canMutate}>Register Signed Webhook</Button>
            </div>
          </form>

          {webhookAlert ? (
            <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
              <span className="font-semibold text-danger">{webhookAlert}</span>
            </div>
          ) : null}

          <ul className="space-y-2 text-xs">
            {webhooks.map((wh) => {
              const receipt = receiptsByWh[wh.id];
              return (
                <li key={wh.id} className="space-y-2 rounded-sm border border-border bg-canvas px-3 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="space-y-0.5">
                      <code dir="ltr" className="unicode-bidi-isolate font-mono text-xs font-semibold text-fg">{wh.url}</code>
                      <div className="font-mono text-[10px] text-fg-muted">{`Events: ${wh.events.join(", ")}`}</div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Button size="sm" variant="secondary" disabled={!canMutate} aria-label={`Send Signed Test Ping ${wh.url}`} onClick={() => { void handleSendTestPing(wh); }}>Send Signed Test Ping</Button>
                      <Button size="sm" variant="ghost" disabled={!canMutate} aria-label={`Remove Webhook ${wh.url}`} onClick={() => handleRemoveWebhook(wh)}>Remove</Button>
                    </div>
                  </div>
                  {receipt ? (
                    <div role="status" className="rounded-xs border border-ok/40 bg-ok-subtle px-2.5 py-1 font-mono text-[11px] text-fg">
                      {`X-Keelway-Signature-256: ${receipt.signatureHeader} · event:${receipt.eventId}`}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}
