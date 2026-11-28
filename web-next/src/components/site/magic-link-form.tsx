"use client";

import { useState } from "react";

const REPO_URL = "https://github.com/creova-gif/keelway";

function GitHubFallback() {
  return (
    <p className="text-[12px] leading-relaxed text-fg-muted" role="status">
      Keelway Cloud is in private preview. Request access on{" "}
      <a href={REPO_URL} target="_blank" rel="noopener" className="underline underline-offset-2">
        GitHub
      </a>
      .
    </p>
  );
}

export function MagicLinkForm() {
  const [state, setState] = useState<"idle" | "pending" | "ok" | "unavailable" | "error">("idle");
  const [referenceId, setReferenceId] = useState("");

  if (state === "ok") {
    return (
      <p className="text-[12px] leading-relaxed text-fg-muted" role="status">
        Request recorded — reference <span className="font-mono text-fg">{referenceId}</span>.
        We reply when a private-preview seat opens.
      </p>
    );
  }

  if (state === "unavailable") {
    return <GitHubFallback />;
  }

  return (
    <form
      className="contents"
      onSubmit={async (e) => {
        e.preventDefault();
        const email = new FormData(e.currentTarget).get("email");
        if (typeof email !== "string" || !email) return;
        setState("pending");
        try {
          const res = await fetch("/api/early-access", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
          });
          if (res.status === 503) {
            setState("unavailable");
            return;
          }
          const data = (await res.json()) as { ok?: boolean; referenceId?: string };
          if (res.ok && data.ok && typeof data.referenceId === "string") {
            setReferenceId(data.referenceId);
            setState("ok");
          } else {
            setState("error");
          }
        } catch {
          setState("error");
        }
      }}
    >
      <label htmlFor="signin-email" className="sr-only">Work email</label>
      <input
        id="signin-email"
        name="email"
        type="email"
        required
        placeholder="name@company.com"
        className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-center text-sm text-fg placeholder:text-fg-muted focus:border-border-focus focus:outline-none"
      />
      <button
        type="submit"
        disabled={state === "pending"}
        className="mt-3 h-9 w-full rounded-sm bg-accent px-4 text-sm font-medium text-accent-ink hover:opacity-90 disabled:opacity-60"
      >
        {state === "pending" ? "Sending…" : "Request access"}
      </button>
      {state === "error" && (
        <p className="text-[12px] leading-relaxed text-fg-muted" role="alert">
          Could not record the request — try again shortly.
        </p>
      )}
    </form>
  );
}
