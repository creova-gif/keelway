"use client";

import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, Send } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

/**
 * Upgraded Early Access & Enterprise VPC Intake Form (#early-access)
 * Captures Work Email, Engineering/Executive Role, Primary Use Case, and
 * Data Residency Region, submitting to POST /api/early-access.
 */
export function EarlyAccessForm() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("ai_engineer");
  const [interest, setInterest] = useState("hybrid_routing");
  const [region, setRegion] = useState("global");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setStatus("submitting");
    setMessage("");

    try {
      const res = await fetch("/api/early-access", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          role,
          interest,
          region,
        }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
        preview?: boolean;
      };

      if (res.ok && data.ok) {
        setStatus("success");
        setMessage(
          `Request recorded for ${email.trim()} — our engineering team will follow up with ${region.toUpperCase()} onboarding details.`
        );
        trackEvent("early_access_submitted", { role, interest, region });
      } else {
        setStatus("error");
        setMessage(
          data.error || "Could not submit your request right now. Please try again shortly."
        );
      }
    } catch {
      setStatus("error");
      setMessage("Network error — please verify your connection and retry.");
    }
  };

  return (
    <section
      id="early-access"
      aria-labelledby="ea-heading"
      className="border-t border-border-subtle bg-surface/40 py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="mx-auto max-w-2xl">
          <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-6 shadow-xl sm:p-8">
            <div className="text-center">
              <span className="chip-teal inline-block rounded-sm px-2.5 py-1">
                ENTERPRISE &amp; TEAM ONBOARDING
              </span>
              <h2
                id="ea-heading"
                className="mt-3 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
              >
                Request Hybrid Cloud &amp; Sovereign VPC Access
              </h2>
              <p className="mt-2 text-sm text-fg-muted">
                Need hosted CRDT workspace sync, dedicated OpenCore GPU runners,
                or regional data residency across Africa, EU, US, or air-gapped
                VPCs? Tell us about your workload.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mt-7 space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="work-email"
                    className="block font-mono text-xs font-semibold text-fg"
                  >
                    Work Email <span className="text-teal-accent">*</span>
                  </label>
                  <input
                    id="work-email"
                    name="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="architect@company.com"
                    autoComplete="email"
                    className="mt-1.5 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3.5 text-sm text-fg placeholder:text-fg-dim focus:border-teal-accent"
                  />
                </div>

                <div>
                  <label
                    htmlFor="role-select"
                    className="block font-mono text-xs font-semibold text-fg"
                  >
                    Your Role
                  </label>
                  <select
                    id="role-select"
                    name="role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="mt-1.5 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3 text-sm text-fg focus:border-teal-accent"
                  >
                    <option value="ai_engineer">AI / Platform Engineer</option>
                    <option value="cto_vp">CTO / VP of Engineering</option>
                    <option value="security_lead">
                      Security &amp; Governance Architect
                    </option>
                    <option value="ml_researcher">
                      Applied ML / OpenCore Researcher
                    </option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="interest-select"
                    className="block font-mono text-xs font-semibold text-fg"
                  >
                    Primary Workload
                  </label>
                  <select
                    id="interest-select"
                    name="interest"
                    value={interest}
                    onChange={(e) => setInterest(e.target.value)}
                    className="mt-1.5 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3 text-sm text-fg focus:border-teal-accent"
                  >
                    <option value="hybrid_routing">
                      Hybrid OpenCore + Frontier API Routing
                    </option>
                    <option value="local">
                      Local Desktop IDE &amp; OpenCore Weights
                    </option>
                    <option value="agent">
                      Approval-Gated Autonomous Agents
                    </option>
                    <option value="team">
                      Team Governance &amp; Spend Caps
                    </option>
                    <option value="vpc">
                      Dedicated Customer-Owned VPC Fleet
                    </option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="region-select"
                    className="block font-mono text-xs font-semibold text-fg"
                  >
                    Deployment Residency
                  </label>
                  <select
                    id="region-select"
                    name="region"
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    className="mt-1.5 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3 text-sm text-fg focus:border-teal-accent"
                  >
                    <option value="global">Global Multi-Region</option>
                    <option value="africa">
                      Africa Sovereign Edge &amp; Multilingual LoRA
                    </option>
                    <option value="eu">European Union (GDPR Strict)</option>
                    <option value="us">United States</option>
                    <option value="airgapped">
                      100% Air-Gapped / On-Premises
                    </option>
                  </select>
                </div>
              </div>

              <div className="flex items-start gap-3 pt-1">
                <input
                  id="consent-checkbox"
                  type="checkbox"
                  required
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-1 h-5 w-5 shrink-0 accent-[#2DD4BF]"
                />
                <label
                  htmlFor="consent-checkbox"
                  className="text-xs leading-relaxed text-fg-muted"
                >
                  Submitting records your work email, role, workload, and
                  deployment region so the Keelway engineering team can follow
                  up. Zero third-party ad pixels or broker sharing.
                </label>
              </div>

              <button
                type="submit"
                disabled={status === "submitting"}
                className="kw-btn kw-btn-primary w-full"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
                <span>
                  {status === "submitting"
                    ? "Recording Request…"
                    : "Request Early Access"}
                </span>
              </button>

              {status === "success" && (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-start gap-2.5 rounded-md border border-teal-accent/60 bg-teal-surface p-3.5 text-xs text-fg"
                >
                  <CheckCircle2
                    className="mt-0.5 h-4 w-4 shrink-0 text-teal-accent"
                    aria-hidden="true"
                  />
                  <span>{message}</span>
                </div>
              )}

              {status === "error" && (
                <div
                  role="alert"
                  aria-live="polite"
                  className="flex items-start gap-2.5 rounded-md border border-amber-alert/60 bg-amber-surface p-3.5 text-xs text-fg"
                >
                  <AlertTriangle
                    className="mt-0.5 h-4 w-4 shrink-0 text-amber-alert"
                    aria-hidden="true"
                  />
                  <span>{message}</span>
                </div>
              )}
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}
