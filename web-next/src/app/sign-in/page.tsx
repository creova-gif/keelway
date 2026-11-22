import type { Metadata } from "next";
import { Mark } from "@/components/site/mark";
import { MagicLinkForm } from "@/components/site/magic-link-form";

export const metadata: Metadata = {
  title: "Sign in — Keelway",
  description: "Sign in to Keelway Cloud. SAML/OIDC on Pro and Enterprise — magic link only, no passwords stored.",
};

export default function SignInPage() {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-5 py-24 text-center sm:py-32">
      <div className="inline-flex self-center"><Mark size={30} /></div>
      <h1 className="mt-7 text-2xl font-semibold tracking-tight text-fg">Sign in to Keelway Cloud</h1>
      <p className="mt-3 text-sm text-fg-muted">Your tapes stay yours. We keep the index.</p>
      <div className="mt-9 space-y-3">
        <button
          type="button"
          className="h-9 w-full rounded-sm border border-border-strong bg-surface px-4 text-sm text-fg opacity-60"
          disabled
          title="Available on Pro and Enterprise"
        >
          Continue with SSO
        </button>
        <button
          type="button"
          className="h-9 w-full rounded-sm border border-border-strong bg-surface px-4 text-sm text-fg opacity-60"
          disabled
          title="Available on Pro and Enterprise"
        >
          Continue with GitHub
        </button>
      </div>
      <div className="my-7 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />
        <span className="font-mono text-[11px] uppercase tracking-wide text-fg-muted">or</span>
        <span className="h-px flex-1 bg-border" />
      </div>
      <MagicLinkForm />
      <p className="mt-7 text-[12px] leading-relaxed text-fg-muted">
        SAML/OIDC on Pro &amp; Enterprise.<br />No passwords stored — magic link only.
      </p>
    </main>
  );
}
