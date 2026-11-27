import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { resetLocalKbrainState } from "@/lib/platformKbrainApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetLocalKbrainState();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 10C — KBrain Scope-Governed Memory Graph & KHub Air-Gapped Mirror UI", () => {
  it("records KBrain facts, runs hybrid BM25 + 3-gram search, blocks DLP secrets, enforces P-10 conflict resolution RBAC, and passes axe WCAG 2.2 AA on Documentation view", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = await screen.findByRole("navigation", { name: "Unified platform views" });
    await user.click(await within(platformNav).findByRole("button", { name: /^Documentation$/i }));

    const kbrainSection = (await screen.findByRole("region", {
      name: /KBrain scope-governed memory graph and hybrid BM25 search/i,
    }));

    const keyInput = await within(kbrainSection).findByLabelText("KBrain fact key") as HTMLInputElement;
    const scopeSelect = await within(kbrainSection).findByLabelText("KBrain memory scope") as HTMLSelectElement;
    const statementInput = await within(kbrainSection).findByLabelText("KBrain fact statement") as HTMLTextAreaElement;
    const recordBtn = await within(kbrainSection).findByRole("button", { name: /Record Memory Fact/i });

    expect(keyInput.value).toBe("arch.storage_engine");
    expect(scopeSelect.value).toBe("project");
    expect(statementInput.value).toBe("");

    // 1. Record a clean scope-governed memory fact
    await user.type(
      statementInput,
      "All sovereign tables enforce SQLite WAL and SHA-256 provenance.",
    );
    await user.click(recordBtn);

    const factsList = await within(kbrainSection).findByRole("list", {
      name: /KBrain retrieved memory facts/i,
    });
    expect(
      await within(factsList).findByText(/All sovereign tables enforce SQLite WAL and SHA-256 provenance\./i),
    ).toBeInTheDocument();
    expect(await within(factsList).findByText("arch.storage_engine")).toBeInTheDocument();

    // 2. Hybrid BM25 + 3-gram search filters and scores matching facts
    const searchInput = await within(kbrainSection).findByLabelText("KBrain hybrid search query") as HTMLInputElement;
    const maxScopeSelect = await within(kbrainSection).findByLabelText("Max retrieval scope") as HTMLSelectElement;
    const searchBtn = await within(kbrainSection).findByRole("button", { name: /Search KBrain Memory/i });

    expect(maxScopeSelect.value).toBe("org");
    await user.type(searchInput, "SQLite WAL");
    await user.click(searchBtn);

    expect(await within(factsList).findByText("arch.storage_engine")).toBeInTheDocument();
    expect(await within(factsList).findByText(/score:\s*[0-9]+\.[0-9]{2}/i)).toBeInTheDocument();
    const shaEl = await within(factsList).findByText(/^sha256:[0-9a-f]+/i);
    expect(shaEl).toHaveClass("max-w-[220px]", "truncate");

    // 3. DLP secret scanner blocks sk- / ghp_ credentials with role="alert"
    await user.type(statementInput, "Never store raw credential sk-proj-9876543210secretvalue");
    await user.click(recordBtn);
    const dlpAlert = await within(kbrainSection).findByRole("alert");
    expect(dlpAlert).toHaveTextContent(/DLP Blocked/i);

    // 4. Recording a diverging statement for the same key + scope flags status="conflict" + role="alert"
    await user.clear(statementInput);
    await user.type(statementInput, "Migrate primary persistence to ephemeral unencrypted cache.");
    await user.click(recordBtn);

    const conflictAlert = await within(kbrainSection).findByRole("alert");
    expect(conflictAlert).toHaveTextContent(/Conflict detected on "arch\.storage_engine"/i);
    expect(await within(factsList).findByText("conflict")).toBeInTheDocument();

    const resolveBtn = await within(kbrainSection).findByRole("button", {
      name: /Resolve Conflict \(P-10 Approve\)/i,
    });
    expect(resolveBtn).toBeEnabled();

    // 5. RBAC gating across viewer, builder, admin, and operator
    const rbacSelect = await screen.findByLabelText(/Active RBAC role/i);

    await user.selectOptions(rbacSelect, "viewer");
    expect(await within(kbrainSection).findByRole("button", { name: /Record Memory Fact/i })).toBeDisabled();
    expect(
      await within(kbrainSection).findByRole("button", { name: /Resolve Conflict \(P-10 Approve\)/i }),
    ).toBeDisabled();

    await user.selectOptions(rbacSelect, "builder");
    expect(await within(kbrainSection).findByRole("button", { name: /Record Memory Fact/i })).toBeEnabled();
    expect(
      await within(kbrainSection).findByRole("button", { name: /Resolve Conflict \(P-10 Approve\)/i }),
    ).toBeDisabled();

    await user.selectOptions(rbacSelect, "admin");
    expect(await within(kbrainSection).findByRole("button", { name: /Record Memory Fact/i })).toBeEnabled();
    expect(
      await within(kbrainSection).findByRole("button", { name: /Resolve Conflict \(P-10 Approve\)/i }),
    ).toBeDisabled();

    // Operator can sign P-10 conflict resolution
    await user.selectOptions(rbacSelect, "operator");
    const operatorResolveBtn = await within(kbrainSection).findByRole("button", {
      name: /Resolve Conflict \(P-10 Approve\)/i,
    });
    expect(operatorResolveBtn).toBeEnabled();
    await user.click(operatorResolveBtn);

    expect(await within(kbrainSection).findByRole("status")).toHaveTextContent(/P-10 Conflict Resolved/i);
    expect(within(factsList).queryByText("conflict")).not.toBeInTheDocument();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("displays KHub built-in kstack_builtin skills, verifies air-gapped mirror roundtrip digests, enforces viewer RBAC, and passes axe WCAG 2.2 AA on Marketplace view", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = await screen.findByRole("navigation", { name: "Unified platform views" });
    await user.click(await within(platformNav).findByRole("button", { name: /^Marketplace$/i }));

    const khubSection = (await screen.findByRole("region", {
      name: /KHub air-gapped skill registry and mirror verifier/i,
    }));

    expect(await within(khubSection).findByText(/kstack_builtin · 8 Verified/i)).toBeInTheDocument();
    expect(await within(khubSection).findByText("air_gap_compliant")).toBeInTheDocument();
    expect(await within(khubSection).findByText("kstack.investigate")).toBeInTheDocument();
    expect(await within(khubSection).findByText("kstack.security")).toBeInTheDocument();

    const catalogDigestEl = (await within(khubSection).findAllByText(/^sha256:[0-9a-f]+/i))[0]!;
    expect(catalogDigestEl).toHaveClass("max-w-[240px]", "truncate");

    const verifyBtn = await within(khubSection).findByRole("button", {
      name: /Verify Air-Gapped Skill Mirror/i,
    });
    expect(verifyBtn).toBeEnabled();
    await user.click(verifyBtn);

    const verifyStatus = await within(khubSection).findByRole("status");
    expect(verifyStatus).toHaveTextContent(/khub-airgap-mirror-v1 · Verified/i);
    expect(verifyStatus).toHaveTextContent(/skills_verified:\s*8/i);

    // Viewer role cannot execute KHub mirror verification
    const rbacSelect = await screen.findByLabelText(/Active RBAC role/i);
    await user.selectOptions(rbacSelect, "viewer");
    expect(
      await within(khubSection).findByRole("button", { name: /Verify Air-Gapped Skill Mirror/i }),
    ).toBeDisabled();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("wires exact /v1/platform/kbrain/* and /v1/platform/khub/* routes with session token & X-Keelway-Role headers and propagates HTTP 4xx errors", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase10-kb-tok");
    const calls: Array<{ pathname: string; method: string; url: string; role: string | null }> = [];
    let rejectDlp = false;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      calls.push({ pathname, method, url, role: hdrs.get("X-Keelway-Role") });

      if (pathname === "/v1/platform/kbrain/search" && method === "GET") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            results: [
              {
                id: "fact-conflict-42",
                key: "arch.storage_engine",
                scope: "project",
                statement: "Conflicting backend statement awaiting P-10 review.",
                status: "conflict",
                hybrid_score: 0.91,
                fact_sha256: "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/kbrain/facts" && method === "POST") {
        if (rejectDlp) {
          return new Response(
            JSON.stringify({ detail: "DLP Policy Violation: Secret token detected in KBrain payload." }),
            { status: 400, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify({
            fact: {
              id: "fact-live-99",
              key: "arch.storage_engine",
              scope: "project",
              statement: "Verified SQLite WAL engine.",
              status: "approved",
              hybrid_score: 1.0,
              fact_sha256: "sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/kbrain/facts/fact-conflict-42/resolve" && method === "POST") {
        return new Response(
          JSON.stringify({
            fact: {
              id: "fact-conflict-42",
              key: "arch.storage_engine",
              scope: "project",
              statement: "Conflicting backend statement awaiting P-10 review.",
              status: "approved",
              revision: 2,
              hybrid_score: 0.91,
              fact_sha256: "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/khub/skills" && method === "GET") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            source: "kstack_builtin",
            air_gap_compliant: true,
            builtin_verified_count: 2,
            catalog_digest_sha256: "sha256:2222333344445555666677778888999900001111222233334444555566667777",
            skills: [
              {
                skill_id: "kstack.review",
                name: "Gate Integrity Review",
                source_type: "kstack_builtin",
                bundle_digest_sha256: "sha256:aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff66660000777788889999",
              },
              {
                skill_id: "kstack.ship",
                name: "Release Shipper",
                source_type: "kstack_builtin",
                bundle_digest_sha256: "sha256:bbbb2222cccc3333dddd4444eeee5555ffff66660000777788889999aaaa1111",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/khub/mirror/verify" && method === "POST") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            mirror_format: "khub-airgap-mirror-v1",
            verified: true,
            air_gap_compliant: true,
            skills_verified: 2,
            mirror_digest_sha256: "sha256:9999888877776666555544443333222211110000ffffeeeeddddccccbbbbaaaa",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = await screen.findByRole("navigation", { name: "Unified platform views" });

    // Documentation -> KBrain resolve + HTTP 400 DLP error propagation
    await user.click(await within(platformNav).findByRole("button", { name: /^Documentation$/i }));
    const kbrainSection = (await screen.findByRole("region", {
      name: /KBrain scope-governed memory graph and hybrid BM25 search/i,
    }));
    const resolveBtn = await within(kbrainSection).findByRole("button", {
      name: /Resolve Conflict \(P-10 Approve\)/i,
    });
    await user.click(resolveBtn);
    expect(await within(kbrainSection).findByRole("status")).toHaveTextContent(/P-10 Conflict Resolved/i);

    rejectDlp = true;
    await user.type(await within(kbrainSection).findByLabelText("KBrain fact statement"), "test secret payload");
    await user.click(await within(kbrainSection).findByRole("button", { name: /Record Memory Fact/i }));
    expect(await within(kbrainSection).findByRole("alert")).toHaveTextContent(
      /DLP Policy Violation: Secret token detected/i,
    );

    // Marketplace -> KHub catalog + mirror verify
    await user.click(await within(platformNav).findByRole("button", { name: /^Marketplace$/i }));
    const khubSection = (await screen.findByRole("region", {
      name: /KHub air-gapped skill registry and mirror verifier/i,
    }));
    expect(await within(khubSection).findByText(/kstack_builtin · 2 Verified/i)).toBeInTheDocument();
    await user.click(await within(khubSection).findByRole("button", { name: /Verify Air-Gapped Skill Mirror/i }));
    expect(await within(khubSection).findByRole("status")).toHaveTextContent(/skills_verified:\s*2/i);

    expect(
      calls.some(
        (c) =>
          c.pathname === "/v1/platform/kbrain/search" &&
          c.url.includes("token=phase10-kb-tok") &&
          c.url.includes("max_scope=org") &&
          c.role === "owner",
      ),
    ).toBe(true);
    expect(
      calls.some(
        (c) =>
          c.pathname === "/v1/platform/kbrain/facts/fact-conflict-42/resolve" &&
          c.method === "POST" &&
          c.role === "owner",
      ),
    ).toBe(true);
    expect(
      calls.some(
        (c) =>
          c.pathname === "/v1/platform/khub/mirror/verify" &&
          c.method === "POST" &&
          c.role === "owner",
      ),
    ).toBe(true);
  });
});
