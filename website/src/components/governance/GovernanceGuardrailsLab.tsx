"use client";

import React, { useMemo, useState } from "react";
import { EyeOff, KeyRound, RefreshCw, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

const SAMPLE_PROMPTS = [
  {
    label: "Leaked Cloud Keys",
    text: `Debug upstream error using OPENAI_API_KEY=sk-proj-98abcDef1234567890ghIJklmnop and x-goog-api-key: AIzaSyD9128374650abcdefGHIJKLMNOpqrstu.`,
  },
  {
    label: "Tenant Token + Bearer",
    text: `Replay curl -H "Authorization: Bearer kw_live_dec0de_deadbeefdeadbeefdeadbeef00" against /v1/responses.`,
  },
  {
    label: "Database DSN + Email",
    text: `Migrate postgres://admin:Sup3rS3cretPwd!@db.internal:5432/prod requested by cto@enterprise.africa.`,
  },
];

const AVAILABLE_SCOPES = [
  "responses:write",
  "models:read",
  "opencore:lora",
  "routing:explain",
  "governance:admin",
];

/**
 * Mirrors Keelway's `core/security/redact.py` deterministic pre-egress scrubber
 * so visitors can test credential & PII redaction interactively in the browser.
 */
function scrubSecretsPreview(input: string): {
  redacted: string;
  count: number;
} {
  let count = 0;
  const patterns: [RegExp, string][] = [
    [/sk-[a-zA-Z0-9_-]{12,}/g, "[REDACTED_OPENAI_KEY]"],
    [/AIza[0-9A-Za-z_-]{20,}/g, "[REDACTED_GOOGLE_API_KEY]"],
    [/kw_live_[0-9a-f]{6}_[0-9a-f]{16,}/gi, "[REDACTED_KEELWAY_KEY]"],
    [/Bearer\s+[A-Za-z0-9._~+/-]+=*/gi, "Bearer [REDACTED_TOKEN]"],
    [/(postgres(?:ql)?:\/\/[^:\s]+:)([^@\s]+)(@)/gi, "$1[REDACTED_DB_PASS]$3"],
    [/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, "[REDACTED_EMAIL]"],
  ];

  let out = input;
  for (const [re, replacement] of patterns) {
    out = out.replace(re, (match, ...args) => {
      count += 1;
      if (replacement.includes("$1")) {
        return `${args[0]}[REDACTED_DB_PASS]${args[2]}`;
      }
      return replacement;
    });
  }
  return { redacted: out, count };
}

function randomHex(len: number): string {
  const chars = "0123456789abcdef";
  let out = "";
  for (let i = 0; i < len; i += 1) {
    out += chars[Math.floor(Math.random() * chars.length)];
  }
  return out;
}

/**
 * Interactive Layer 6 Security Lab:
 * 1. Pre-Egress Secret & PII Redaction Sandbox
 * 2. Scoped `kw_live_*` Key Minting & Salted SHA-256 Storage Preview
 */
export function GovernanceGuardrailsLab() {
  const [rawPrompt, setRawPrompt] = useState<string>(SAMPLE_PROMPTS[0].text);
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    "responses:write",
    "models:read",
  ]);
  const [shortId, setShortId] = useState<string>("7f3a1c");
  const [secretDigest, setSecretDigest] = useState<string>(
    "c4810e92b73a5d16f092837465ab12cd89ef0123456789abcdef0123456789ab"
  );

  const scrubbed = useMemo(() => scrubSecretsPreview(rawPrompt), [rawPrompt]);

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) => {
      if (prev.includes(scope)) {
        return prev.length > 1 ? prev.filter((s) => s !== scope) : prev;
      }
      return [...prev, scope].sort();
    });
  };

  const mintPreviewKey = () => {
    const nextShort = randomHex(6);
    setShortId(nextShort);
    setSecretDigest(randomHex(64));
    trackEvent("scoped_key_preview_minted", {
      scopes_count: selectedScopes.length,
    });
  };

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      {/* ====================================================================
          PANEL A: Pre-Egress Secret & PII Redaction Engine
          ==================================================================== */}
      <article className="rounded-lg border border-border-strong bg-surface p-6">
        <div className="flex items-center justify-between gap-2">
          <span className="chip-teal inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1">
            <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
            PRE-EGRESS REDACTION
          </span>
          <span className="font-mono text-xs text-fg-muted">
            log_redacted_prompts=False default
          </span>
        </div>

        <h3 className="mt-3 text-xl font-bold text-fg">
          Zero-Leak Credential &amp; PII Scrubber
        </h3>
        <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
          Keelway never logs raw prompts by default. Before any authorized cloud
          dispatch or state persistence, <code className="text-fg">redact_text()</code>{" "}
          strips leaked API tokens, DSNs, and emails synchronously.
        </p>

        {/* Sample Injection Presets */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {SAMPLE_PROMPTS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => {
                setRawPrompt(preset.text);
                trackEvent("redaction_sandbox_tested", {
                  preset: preset.label,
                });
              }}
              className="min-h-[36px] rounded-sm border border-border-strong bg-canvas px-2.5 font-mono text-[11px] text-fg-muted transition-colors duration-150 hover:border-teal-accent hover:text-fg"
            >
              Load: {preset.label}
            </button>
          ))}
        </div>

        <div className="mt-3">
          <label
            htmlFor="redaction-input"
            className="block font-mono text-[11px] uppercase text-fg-muted"
          >
            Simulated Outbound Prompt / Log Payload
          </label>
          <textarea
            id="redaction-input"
            rows={3}
            value={rawPrompt}
            onChange={(e) => setRawPrompt(e.target.value)}
            className="mt-1.5 w-full rounded-md border border-border-strong bg-canvas p-3 font-mono text-xs leading-relaxed text-fg focus:border-teal-accent"
          />
        </div>

        <div className="mt-3">
          <div className="flex items-center justify-between font-mono text-[11px]">
            <span className="uppercase text-fg-muted">
              Sanitized Wire / Ledger Output
            </span>
            <span className="font-semibold text-teal-accent">
              {scrubbed.count} sensitive token(s) scrubbed
            </span>
          </div>
          <pre
            aria-live="polite"
            className="mt-1.5 whitespace-pre-wrap break-words rounded-md border border-teal-accent/40 bg-canvas p-3 font-mono text-xs leading-relaxed text-teal-accent"
          >
            {scrubbed.redacted}
          </pre>
        </div>
      </article>

      {/* ====================================================================
          PANEL B: Scoped kw_live_* Tenant API Key Minting
          ==================================================================== */}
      <article className="rounded-lg border border-border-strong bg-surface p-6">
        <div className="flex items-center justify-between gap-2">
          <span className="chip-neutral inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1">
            <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
            SCOPED TENANT CREDENTIALS
          </span>
          <span className="font-mono text-xs text-fg-muted">
            POST /v1/governance/keys
          </span>
        </div>

        <h3 className="mt-3 text-xl font-bold text-fg">
          Salted SHA-256 Key Vault &amp; RBAC Scopes
        </h3>
        <p className="mt-1.5 text-xs leading-relaxed text-fg-muted">
          Keys follow <code className="text-fg">kw_live_&lt;6hex&gt;_&lt;32hex&gt;</code>.
          Only the 14-char prefix and salted SHA-256 digest are persisted —
          constant-time comparison prevents timing side-channels.
        </p>

        <div className="mt-4">
          <span className="block font-mono text-[11px] uppercase text-fg-muted">
            Select Key Permission Scopes
          </span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {AVAILABLE_SCOPES.map((scope) => {
              const active = selectedScopes.includes(scope);
              return (
                <button
                  key={scope}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleScope(scope)}
                  className={cn(
                    "min-h-[38px] rounded-sm border px-2.5 font-mono text-xs transition-colors duration-150",
                    active
                      ? "border-teal-accent bg-teal-surface text-teal-accent font-semibold"
                      : "border-border-strong bg-canvas text-fg-muted hover:text-fg"
                  )}
                >
                  {scope}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] uppercase text-fg-muted">
            Stored Key Metadata Record (No Raw Secret on Disk)
          </span>
          <button
            type="button"
            onClick={mintPreviewKey}
            className="inline-flex min-h-[38px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-3 font-mono text-xs text-fg hover:border-teal-accent"
          >
            <RefreshCw className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
            <span>Rotate Preview Key</span>
          </button>
        </div>

        <pre className="mt-2 overflow-x-auto rounded-md border border-border-strong bg-canvas p-3.5 font-mono text-[11px] leading-relaxed text-fg">
          {JSON.stringify(
            {
              key_id: `key_${shortId}_a901e4b2`,
              tenant_id: "org_sovereign_fin",
              key_prefix: `kw_live_${shortId}`,
              scopes: selectedScopes,
              secret_sha256: `${secretDigest.slice(0, 28)}...`,
              revoked: false,
            },
            null,
            2
          )}
        </pre>

        <div className="mt-3 flex items-center gap-2 font-mono text-[11px] text-fg-muted">
          <ShieldCheck
            className="h-4 w-4 shrink-0 text-teal-accent"
            aria-hidden="true"
          />
          <span>
            Upstream cloud keys (e.g. <code>x-goog-api-key</code>) stay locked
            server-side and never touch client bundles or URL query strings.
          </span>
        </div>
      </article>
    </div>
  );
}
