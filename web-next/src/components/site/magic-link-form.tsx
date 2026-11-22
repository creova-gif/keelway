"use client";

import { useState } from "react";

const REPO_URL = "https://github.com/creova-gif/keelway";

export function MagicLinkForm() {
  const [requested, setRequested] = useState(false);

  if (requested) {
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

  return (
    <form
      className="contents"
      onSubmit={(e) => {
        e.preventDefault();
        setRequested(true);
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
        className="mt-3 h-9 w-full rounded-sm bg-accent px-4 text-sm font-medium text-accent-ink hover:opacity-90"
      >
        Email me a link
      </button>
    </form>
  );
}
