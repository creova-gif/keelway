import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import earlyAccessHandler from "../../../api/early-access.js";

function createResponseRecorder() {
  let statusCode = 200;
  let bodyText = "";
  const headers: Record<string, string> = {};

  return {
    res: {
      status(code: number) {
        statusCode = code;
        return this;
      },
      setHeader(key: string, value: string) {
        headers[key.toLowerCase()] = value;
      },
      end(chunk = "") {
        bodyText = chunk;
      },
    },
    getStatus: () => statusCode,
    getHeaders: () => headers,
    getJson: () => (bodyText ? (JSON.parse(bodyText) as Record<string, unknown>) : null),
  };
}

describe("api/early-access.js PII & security boundary", () => {
  beforeEach(() => {
    earlyAccessHandler._resetRateLimitForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("never dispatches submitter emails to api.github.com/repos/.../issues and fails closed (503) without private webhook", async () => {
    vi.stubEnv("EARLY_ACCESS_WEBHOOK_URL", "");
    vi.stubEnv("EARLY_ACCESS_GH_TOKEN", `ghp_${"0".repeat(36)}`);

    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { res, getStatus, getJson } = createResponseRecorder();
    await earlyAccessHandler(
      {
        method: "POST",
        headers: { origin: "https://keelway.dev", "x-forwarded-for": "198.51.100.10" },
        body: { email: "security.lead@enterprise.example", role: "security_lead", interest: "vpc", region: "us" },
      },
      res
    );

    expect(getStatus()).toBe(503);
    expect(getJson()).toEqual({ ok: false, error: "early access intake is temporarily unavailable" });
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(JSON.stringify(errorSpy.mock.calls)).not.toContain("security.lead@enterprise.example");
  });

  it("blocks GitHub Issues endpoints and SSRF hosts even if misconfigured in EARLY_ACCESS_WEBHOOK_URL", async () => {
    vi.stubEnv("EARLY_ACCESS_WEBHOOK_URL", "https://api.github.com/repos/creova-gif/keelway/issues");
    vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const { res, getStatus } = createResponseRecorder();
    await earlyAccessHandler(
      {
        method: "POST",
        headers: { origin: "https://keelway.dev", "x-forwarded-for": "198.51.100.11" },
        body: { email: "founder@acme.io", role: "cto_vp", interest: "hybrid_routing", region: "eu" },
      },
      res
    );

    expect(getStatus()).toBe(503);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(earlyAccessHandler.validatePrivateWebhookUrl("https://169.254.169.254/latest/meta-data")).toBeNull();
    expect(earlyAccessHandler.validatePrivateWebhookUrl("https://[fc00::1]/intake")).toBeNull();
    expect(earlyAccessHandler.validatePrivateWebhookUrl("https://[fd12:3456::1]/intake")).toBeNull();
    expect(earlyAccessHandler.validatePrivateWebhookUrl("http://hooks.example.com/intake")).toBeNull();
    expect(earlyAccessHandler.validatePrivateWebhookUrl("https://fc-intake.example.com/webhook")).toBe(
      "https://fc-intake.example.com/webhook"
    );
    expect(earlyAccessHandler.validatePrivateWebhookUrl("https://fd-crm.example.com/webhook")).toBe(
      "https://fd-crm.example.com/webhook"
    );
  });

  it("enforces Origin allowlist (403), 4KB payload cap (413), and strict email/field bounds (400)", async () => {
    // Disallowed origin -> 403
    const untrusted = createResponseRecorder();
    await earlyAccessHandler(
      {
        method: "POST",
        headers: { origin: "https://attacker.example", "x-forwarded-for": "198.51.100.12" },
        body: { email: "user@company.com" },
      },
      untrusted.res
    );
    expect(untrusted.getStatus()).toBe(403);

    // Payload > 4096 bytes -> 413
    const oversized = createResponseRecorder();
    await earlyAccessHandler(
      {
        method: "POST",
        headers: { origin: "https://keelway.dev", "x-forwarded-for": "198.51.100.13" },
        body: JSON.stringify({ email: "user@company.com", pad: "a".repeat(earlyAccessHandler.MAX_BODY_BYTES + 64) }),
      },
      oversized.res
    );
    expect(oversized.getStatus()).toBe(413);

    // Invalid email -> 400
    const badEmail = createResponseRecorder();
    await earlyAccessHandler(
      {
        method: "POST",
        headers: { origin: "https://keelway.dev", "x-forwarded-for": "198.51.100.14" },
        body: { email: "not-an-email@localhost" },
      },
      badEmail.res
    );
    expect(badEmail.getStatus()).toBe(400);
  });

  it("delivers validated requests exclusively to a private HTTPS webhook", async () => {
    vi.stubEnv("EARLY_ACCESS_WEBHOOK_URL", "https://intake.sorvex.example/v1/early-access");
    vi.stubEnv("EARLY_ACCESS_WEBHOOK_SECRET", "whsec_unit_test_secret");

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ received: true }), { status: 200 })
    );

    const { res, getStatus, getJson } = createResponseRecorder();
    await earlyAccessHandler(
      {
        method: "POST",
        headers: { origin: "https://keelway.dev", "x-forwarded-for": "198.51.100.15" },
        body: { email: "architect@company.com", role: "ai_engineer", interest: "agent", region: "ca-central" },
      },
      res
    );

    expect(getStatus()).toBe(200);
    const json = getJson();
    expect(json?.ok).toBe(true);
    expect(String(json?.referenceId)).toMatch(/^KW-[0-9A-F]{8}$/);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy.mock.calls[0]?.[0]).toBe("https://intake.sorvex.example/v1/early-access");
  });
});
