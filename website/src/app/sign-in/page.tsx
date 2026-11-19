import type { Metadata } from "next";
import { Mark } from "@/components/site/Mark";
import { MagicLinkForm } from "@/components/site/MagicLinkForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to Keelway Cloud. SAML/OIDC on Pro and Enterprise — magic link only, no passwords stored.",
};

export default function SignInPage() {
  return (
    <div className="mx-auto max-w-sm px-5 py-24 text-center sm:py-32">
      <div className="inline-flex"><Mark size={30} /></div>
      <h1 className="kw-h2 mt-7">Sign in to Keelway Cloud</h1>
      <p className="kw-body mt-3 text-sm">Your tapes stay yours. We keep the index.</p>
      <div className="mt-9 space-y-3">
        <button type="button" className="kw-btn kw-btn-secondary w-full" disabled title="Available on Pro and Enterprise">
          Continue with SSO
        </button>
        <button type="button" className="kw-btn kw-btn-secondary w-full" disabled title="Available on Pro and Enterprise">
          Continue with GitHub
        </button>
      </div>
      <div className="my-7 flex items-center gap-3">
        <span className="h-px flex-1 bg-[var(--rule)]" />
        <span className="kw-label">or</span>
        <span className="h-px flex-1 bg-[var(--rule)]" />
      </div>
      <MagicLinkForm />
      <p className="kw-small mt-7 leading-relaxed">
        SAML/OIDC on Pro &amp; Enterprise.<br />No passwords stored — magic link only.
      </p>
    </div>
  );
}
