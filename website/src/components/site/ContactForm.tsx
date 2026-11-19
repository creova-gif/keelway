"use client";

import { useState } from "react";

const REPO_URL = "/repo";

export function ContactForm() {
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <div className="kw-card border-[var(--green-35)] p-6">
        <p className="text-sm font-medium text-[var(--ink)]">Logged.</p>
        <p className="mt-2 text-[13px] leading-relaxed text-[var(--muted)]">
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
        <label htmlFor="email" className="kw-label mb-2 block">Work email</label>
        <input id="email" name="email" type="email" required placeholder="name@company.com" className="kw-input" />
      </div>
      <div>
        <label htmlFor="topic" className="kw-label mb-2 block">Topic</label>
        <select id="topic" name="topic" className="kw-input" defaultValue="Enterprise Sovereign VPC">
          <option>Enterprise Sovereign VPC</option>
          <option>BYOM / Pro rollout</option>
          <option>Air-gapped deployment</option>
          <option>Security review</option>
          <option>Something else</option>
        </select>
      </div>
      <div>
        <label htmlFor="message" className="kw-label mb-2 block">Message</label>
        <textarea id="message" name="message" required rows={5} placeholder="What should we know?" className="kw-input resize-none" />
      </div>
      <button type="submit" className="kw-btn kw-btn-primary w-full">Send</button>
      <p className="kw-small text-center">
        Opens a drafted issue on{" "}
        <a href={REPO_URL} className="underline underline-offset-2">GitHub</a>{" "}
        — our public line until a mailbox ships.
      </p>
    </form>
  );
}
