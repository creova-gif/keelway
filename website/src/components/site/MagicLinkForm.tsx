"use client";

import { useState } from "react";

const REPO_URL = "https://github.com/creova-gif/keelway";

export function MagicLinkForm() {
  const [requested, setRequested] = useState(false);

  if (requested) {
    return (
      <p className="kw-small leading-relaxed" role="status">
        Keelway Cloud is in private preview. Request access on{" "}
        <a href={REPO_URL} className="underline underline-offset-2">GitHub</a>.
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
      <input id="signin-email" name="email" type="email" required placeholder="name@company.com" className="kw-input text-center" />
      <button type="submit" className="kw-btn kw-btn-primary mt-3 w-full">Email me a link</button>
    </form>
  );
}
