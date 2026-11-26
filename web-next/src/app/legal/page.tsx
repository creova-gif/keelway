import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Legal — Keelway",
  description: "Terms of service, privacy, and licensing for Keelway — in plain language.",
};

const TERMS = [
  {
    id: "T-01",
    title: "The open core is Apache-2.0",
    body: "Everything in the public repository ships under the Apache License 2.0. Use it, audit it, fork it — the license text in the repo is the operative document.",
  },
  {
    id: "T-02",
    title: "Keelway Cloud is in private preview",
    body: "Hosted workspaces are offered to preview participants as-is. Features, limits, and availability may change while the preview runs; we flag breaking changes in the changelog.",
  },
  {
    id: "T-03",
    title: "Honest economics",
    body: "Paid tiers bill per seat at the published rate. Token markup is 0% — you pay model providers at their own rate card, through keys that stay in your vault.",
  },
  {
    id: "T-04",
    title: "Acceptable use",
    body: "Don't use the platform to attack systems you don't own, to launder egress past your own policies, or to process data you have no right to handle. Governance gates you disable are your responsibility.",
  },
  {
    id: "T-05",
    title: "Enterprise supersedes by contract",
    body: "Sovereign VPC, SLA, and indemnification terms are set in the commercial agreement for each deployment — not on this page.",
  },
] as const;

const PRIVACY = [
  {
    id: "P-01",
    title: "Your tapes stay yours",
    body: "Execution tapes, receipts, and workspace state live where you run Keelway. Self-hosted means self-held — we never take custody of your prompts or payloads.",
  },
  {
    id: "P-02",
    title: "Magic-link only",
    body: "Keelway Cloud sign-in stores a work email — nothing else. No passwords exist to leak. SAML/OIDC on Pro and Enterprise keeps identity in your IdP.",
  },
  {
    id: "P-03",
    title: "Contact data stays private",
    body: "Contact and access requests are handled directly — never routed to public trackers or public issues. Email us to delete what we hold about you.",
  },
  {
    id: "P-04",
    title: "Telemetry is off by default",
    body: "The self-hosted core phones home for nothing. No usage beacons, no hidden egress — the same fail-closed posture the router enforces for your agents.",
  },
] as const;

function ClauseRow({ id, title, body }: { id: string; title: string; body: string }) {
  return (
    <div className="flex flex-col gap-2 border-b border-border py-7 sm:flex-row sm:gap-10">
      <p className="w-16 shrink-0 pt-1 font-mono text-[11px] uppercase tracking-wide text-fg-muted">{id}</p>
      <div>
        <h3 className="text-lg font-semibold tracking-tight text-fg">{title}</h3>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-fg-muted">{body}</p>
      </div>
    </div>
  );
}

export default function LegalPage() {
  return (
    <main className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Legal</p>
      <h1 className="mt-4 text-4xl font-semibold tracking-tight text-fg">The plain terms.</h1>
      <p className="mt-6 max-w-2xl text-sm leading-6 text-fg-muted">
        The short version of what you can expect from Keelway and what Keelway
        expects from you. Where a signed agreement exists, the agreement governs.
      </p>

      <div className="mt-14 border-t border-border">
        <h2 className="pt-7 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Terms of service</h2>
        {TERMS.map((t) => (
          <ClauseRow key={t.id} {...t} />
        ))}
      </div>

      <div className="mt-14 border-t border-border">
        <h2 className="pt-7 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Privacy</h2>
        {PRIVACY.map((p) => (
          <ClauseRow key={p.id} {...p} />
        ))}
      </div>

      <p className="mt-14 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
        Sorvex Labs · questions → <a href="/contact" className="underline underline-offset-2">contact</a>
      </p>
    </main>
  );
}
