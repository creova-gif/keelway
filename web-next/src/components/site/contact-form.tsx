"use client";

import { useState } from "react";

const REPO_URL = "https://github.com/creova-gif/keelway";

const INPUT =
  "w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-fg placeholder:text-fg-muted focus:border-border-focus focus:outline-none";

export function ContactForm() {
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <div className="mt-9 rounded-md border border-ok bg-ok-subtle p-6">
        <p className="text-sm font-medium text-fg">Logged.</p>
        <p className="mt-2 text-[13px] leading-relaxed text-fg-muted">
          Your message is drafted as a GitHub issue — submit it there and we reply on the thread.
        </p>
      </div>
    );
  }

  return (
    <form
      className="mt-9 space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        const title = encodeURIComponent(`[Contact] ${data.get("topic")}`);
        const body = encodeURIComponent(
          `From: ${data.get("email")}\nTopic: ${data.get("topic")}\n\n${data.get("message") ?? ""}`,
        );
        window.open(`${REPO_URL}/issues/new?title=${title}&body=${body}`, "_blank", "noopener");
        setSent(true);
      }}
    >
      <div>
        <label htmlFor="email" className="mb-2 block font-mono text-[11px] uppercase tracking-wide text-fg-muted">
          Work email
        </label>
        <input id="email" name="email" type="email" required placeholder="name@company.com" className={INPUT} />
      </div>
      <div>
        <label htmlFor="topic" className="mb-2 block font-mono text-[11px] uppercase tracking-wide text-fg-muted">
          Topic
        </label>
        <select id="topic" name="topic" className={INPUT} defaultValue="Enterprise Sovereign VPC">
          <option>Enterprise Sovereign VPC</option>
          <option>BYOM / Pro rollout</option>
          <option>Air-gapped deployment</option>
          <option>Security review</option>
          <option>Something else</option>
        </select>
      </div>
      <div>
        <label htmlFor="message" className="mb-2 block font-mono text-[11px] uppercase tracking-wide text-fg-muted">
          Message
        </label>
        <textarea id="message" name="message" required rows={5} placeholder="What should we know?" className={`${INPUT} resize-none`} />
      </div>
      <button
        type="submit"
        className="h-9 w-full rounded-sm bg-accent px-4 text-sm font-medium text-accent-ink hover:opacity-90"
      >
        Send
      </button>
      <p className="text-center text-[12px] text-fg-muted">
        Opens a drafted issue on{" "}
        <a href={REPO_URL} target="_blank" rel="noopener" className="underline underline-offset-2">
          GitHub
        </a>{" "}
        — our public line until a mailbox ships.
      </p>
    </form>
  );
}
