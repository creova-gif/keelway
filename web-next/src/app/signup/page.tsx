import type { Metadata } from "next";
import { Mark } from "@/components/site/mark";
import { MagicLinkForm } from "@/components/site/magic-link-form";
import { InstallCommand } from "@/components/site/install-command";

export const metadata: Metadata = {
  title: "Get started — Keelway",
  description:
    "Start with the free Apache-2.0 core, or request Keelway Cloud access — private preview, magic link only.",
};

export default function SignupPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-5 py-24 text-center sm:py-32">
      <div className="inline-flex self-center"><Mark size={30} /></div>
      <h1 className="mt-7 text-2xl font-semibold tracking-tight text-fg">Get started</h1>
      <p className="mt-3 text-sm text-fg-muted">
        Community is free and self-hosted. Cloud is in private preview.
      </p>

      <h2 className="mt-10 font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
        Community — self-hosted
      </h2>
      <p className="mt-3 text-[12px] leading-relaxed text-fg-muted">
        Apache-2.0. Runs fully offline; your tapes never leave the machine.
      </p>
      <div className="text-left">
        <InstallCommand />
      </div>

      <div className="my-8 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />
        <span className="font-mono text-[11px] uppercase tracking-wide text-fg-muted">or</span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
        Keelway Cloud — private preview
      </h2>
      <div className="mt-4">
        <MagicLinkForm />
      </div>
      <p className="mt-7 text-[12px] leading-relaxed text-fg-muted">
        No passwords stored — magic link only.<br />BYOM and Pro tiers bill per seat, 0% token markup.
      </p>
    </main>
  );
}
