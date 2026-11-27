import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 5 — Live SSE Execution, Encrypted Secret Vault, Multi-Workspace RBAC & Signed Webhooks", () => {
  it("switches workspaces, stores/rotates/revokes AES-256-GCM secrets without plaintext DOM leak, blocks SSRF webhooks, and enforces viewer RBAC with 0 axe violations", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    // 1. Switch active workspace in top bar -> hipaa-intake
    const wsSwitcher = screen.getByLabelText(/Active workspace switcher/i) as HTMLSelectElement;
    expect(wsSwitcher.value).toBe("default");
    await user.selectOptions(wsSwitcher, "hipaa-intake");
    expect(wsSwitcher.value).toBe("hipaa-intake");

    // 2. Navigate to Security -> Encrypted Local Secret Vault & Signed Webhook Event Bus
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Security$/i }));

    const vaultSec = (await screen.findByRole("region", { name: /Encrypted local secret vault/i }));
    expect(await within(vaultSec).findByText(/AES-256-GCM · hipaa-intake/i)).toBeInTheDocument();

    const secretNameInput = within(vaultSec).getByLabelText(/^Secret name$/i);
    const secretValInput = within(vaultSec).getByLabelText(/Plaintext secret value/i) as HTMLInputElement;

    const superSecret = "sk-live-top-secret-value-8877";
    await user.type(secretNameInput, "ANTHROPIC_BYOM_TOKEN");
    await user.type(secretValInput, superSecret);
    await user.click(within(vaultSec).getByRole("button", { name: /Encrypt & Store Secret/i }));

    // Password input clears immediately, masked preview renders, raw secret NEVER appears anywhere in DOM!
    expect(secretValInput.value).toBe("");
    expect(within(vaultSec).getByText("ANTHROPIC_BYOM_TOKEN")).toBeInTheDocument();
    expect(within(vaultSec).getByText("sk-l****8877")).toBeInTheDocument();
    expect(container.textContent).not.toContain(superSecret);

    // Rotate secret increments version to v2
    await user.click(within(vaultSec).getByRole("button", { name: /Rotate Secret ANTHROPIC_BYOM_TOKEN/i }));
    expect(within(vaultSec).getByText(/Rotated ANTHROPIC_BYOM_TOKEN to v2/i)).toBeInTheDocument();

    // Revoke secret removes it
    await user.click(within(vaultSec).getByRole("button", { name: /Revoke Secret ANTHROPIC_BYOM_TOKEN/i }));
    expect(within(vaultSec).queryByText("ANTHROPIC_BYOM_TOKEN")).toBeNull();

    // 3. Signed Webhooks: block cloud metadata SSRF, allow HTTPS, and verify HMAC-SHA256 test ping receipt
    const whSec = screen.getByRole("region", { name: /Signed webhook and plugin event bus/i });
    const whUrlInput = within(whSec).getByLabelText(/Webhook endpoint URL/i);
    await user.type(whUrlInput, "http://169.254.169.254/latest/meta-data/iam");
    await user.click(within(whSec).getByRole("button", { name: /Register Signed Webhook/i }));
    expect(within(whSec).getByRole("alert")).toHaveTextContent(/SSRF|Blocked|169\.254\.169\.254/i);

    await user.clear(whUrlInput);
    await user.type(whUrlInput, "https://siem.example.org/keelway/hooks");
    await user.click(within(whSec).getByRole("button", { name: /Register Signed Webhook/i }));
    expect(within(whSec).getByText("https://siem.example.org/keelway/hooks")).toBeInTheDocument();

    await user.click(
      within(whSec).getByRole("button", { name: /Send Signed Test Ping https:\/\/siem\.example\.org\/keelway\/hooks/i }),
    );
    expect(within(whSec).getByText(/X-Keelway-Signature-256: sha256=/i)).toBeInTheDocument();

    // 4. Switch RBAC role to viewer -> vault & webhook mutations lock down read-only
    const rbacSelect = screen.getByLabelText(/Active RBAC role/i);
    await user.selectOptions(rbacSelect, "viewer");
    expect(screen.getByText(/RBAC Read-Only Notice \(viewer\)/i)).toBeInTheDocument();
    expect(within(vaultSec).getByRole("button", { name: /Encrypt & Store Secret/i })).toBeDisabled();
    expect(within(whSec).getByRole("button", { name: /Register Signed Webhook/i })).toBeDisabled();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("streams live SSE execution in Agents & Automation, holds at P-10 human checkpoints, enforces RBAC on P-10 approval, and resumes on human sign-off with 0 axe violations", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });

    // 1. Agents View -> Stream Live Execution -> pauses at [p10.held]
    await user.click(within(platformNav).getByRole("button", { name: /^Agents$/i }));
    await user.click((await screen.findAllByRole("button", { name: /Stream Live Execution/i }))[0]!);

    const execConsole = await screen.findByRole("region", { name: /Live streaming execution console/i });
    expect(await within(execConsole).findByText("[p10.held]")).toBeInTheDocument();

    // Builder role cannot approve P-10 human checkpoint
    const rbacSelect = (await screen.findByLabelText(/Active RBAC role/i));
    await user.selectOptions(rbacSelect, "builder");
    expect(within(execConsole).getByRole("button", { name: /Approve P-10 & Resume Stream/i })).toBeDisabled();

    // Operator / Owner role approves P-10 & resumes stream to [run.completed · sha256:...]
    await user.selectOptions(rbacSelect, "operator");
    const approveBtn = within(execConsole).getByRole("button", { name: /Approve P-10 & Resume Stream/i });
    expect(approveBtn).toBeEnabled();
    await user.click(approveBtn);
    expect(await within(execConsole).findByText(/\[run\.completed · sha256:/i)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    // 2. Automation View -> Stream Live DAG -> Deny & Abort Run
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));
    await user.click((await screen.findAllByRole("button", { name: /Stream Live DAG/i }))[0]!);

    const dagConsole = await screen.findByRole("region", { name: /Live streaming execution console/i });
    expect(await within(dagConsole).findByText("[p10.held]")).toBeInTheDocument();
    await user.click(await within(dagConsole).findByRole("button", { name: /Deny & Abort Run/i }));
    expect(await within(dagConsole).findByText("[run.aborted]")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
