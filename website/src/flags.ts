import { dedupe, flag } from "flags/next";
import { vercelAdapter } from "@flags-sdk/vercel";
import type { ReadonlyHeaders, ReadonlyRequestCookies } from "flags";
import {
  OVR_HOME_GATE_COOKIE,
  OVR_QUICKSTART_CLI_COOKIE,
  VISITOR_COOKIE,
} from "@/middleware";

export type HomeGateVariant = "control-stepper" | "interactive-p10-deck";
export type QuickstartCliVariant =
  | "code-tabs-default"
  | "interactive-tui-boot";

export interface KeelwayFlagEntities {
  user?: {
    id: string;
  };
  overrides?: {
    homeGate?: HomeGateVariant;
    quickstartCli?: QuickstartCliVariant;
  };
}

/**
 * Deterministic 32-bit FNV-1a hash for zero-network 50/50 split fallback
 * when running locally or in CI without Vercel OIDC / SDK credentials.
 */
function deterministicBucket(flagKey: string, visitorId: string): number {
  const input = `${flagKey}:${visitorId}`;
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0) % 100;
}

function parseHomeGateOverride(raw?: string | null): HomeGateVariant | undefined {
  if (raw === "control-stepper" || raw === "interactive-p10-deck") {
    return raw;
  }
  return undefined;
}

function parseQuickstartOverride(
  raw?: string | null
): QuickstartCliVariant | undefined {
  if (raw === "code-tabs-default" || raw === "interactive-tui-boot") {
    return raw;
  }
  return undefined;
}

const identifyVisitor = dedupe(
  async ({
    cookies,
    headers,
  }: {
    cookies: ReadonlyRequestCookies;
    headers: ReadonlyHeaders;
  }): Promise<KeelwayFlagEntities> => {
    const vid =
      headers.get("x-kw-vid") ??
      cookies.get(VISITOR_COOKIE)?.value ??
      "anonymous-ssr";

    const homeGate =
      parseHomeGateOverride(headers.get("x-kw-ovr-home-gate")) ??
      parseHomeGateOverride(cookies.get(OVR_HOME_GATE_COOKIE)?.value);

    const quickstartCli =
      parseQuickstartOverride(headers.get("x-kw-ovr-quickstart-cli")) ??
      parseQuickstartOverride(cookies.get(OVR_QUICKSTART_CLI_COOKIE)?.value);

    return {
      user: { id: vid },
      overrides: {
        homeGate,
        quickstartCli,
      },
    };
  }
);

function hasVercelFlagsCredentials(): boolean {
  return Boolean(process.env.FLAGS || process.env.VERCEL_OIDC_TOKEN);
}

/**
 * Experiment 1 (`exp-home-gate-v1`):
 * Tests the existing 5-stage ApprovalGateStepper (`control-stepper`) against
 * the Cursor-inspired interactive P-10 Diff & Risk-Escalation Deck (`interactive-p10-deck`).
 */
export const expHomeGateFlag = flag<HomeGateVariant, KeelwayFlagEntities>({
  key: "exp-home-gate-v1",
  description:
    "Homepage A/B experiment: 5-stage ApprovalGateStepper control vs interactive P-10 diff and escalation deck",
  defaultValue: "control-stepper",
  options: [
    { value: "control-stepper", label: "5-Stage Stepper (Control)" },
    { value: "interactive-p10-deck", label: "Interactive P-10 Escalation Deck" },
  ],
  identify: identifyVisitor,
  async decide({ entities, headers, cookies }) {
    if (entities?.overrides?.homeGate) {
      return entities.overrides.homeGate;
    }
    if (hasVercelFlagsCredentials()) {
      try {
        const adapter = vercelAdapter<HomeGateVariant, KeelwayFlagEntities>();
        const remote = await adapter.decide({
          key: "exp-home-gate-v1",
          entities,
          headers,
          cookies,
        });
        if (
          remote === "control-stepper" ||
          remote === "interactive-p10-deck"
        ) {
          return remote;
        }
      } catch {
        // Fall through cleanly when local OIDC token expires or in offline CI
      }
    }
    const vid = entities?.user?.id ?? "anonymous-ssr";
    return deterministicBucket("exp-home-gate-v1", vid) < 50
      ? "control-stepper"
      : "interactive-p10-deck";
  },
});

/**
 * Experiment 2 (`exp-quickstart-cli-v1`):
 * Tests static code snippet tabs (`code-tabs-default`) against the Claude-Code-style
 * interactive Keelway TUI boot preview (`interactive-tui-boot`).
 */
export const expQuickstartCliFlag = flag<
  QuickstartCliVariant,
  KeelwayFlagEntities
>({
  key: "exp-quickstart-cli-v1",
  description:
    "Quickstart A/B experiment: static snippet tabs vs Claude-Code-style interactive Keelway CLI TUI boot",
  defaultValue: "code-tabs-default",
  options: [
    { value: "code-tabs-default", label: "Code Snippets Default (Control)" },
    {
      value: "interactive-tui-boot",
      label: "Interactive Keelway CLI TUI Boot",
    },
  ],
  identify: identifyVisitor,
  async decide({ entities, headers, cookies }) {
    if (entities?.overrides?.quickstartCli) {
      return entities.overrides.quickstartCli;
    }
    if (hasVercelFlagsCredentials()) {
      try {
        const adapter = vercelAdapter<
          QuickstartCliVariant,
          KeelwayFlagEntities
        >();
        const remote = await adapter.decide({
          key: "exp-quickstart-cli-v1",
          entities,
          headers,
          cookies,
        });
        if (
          remote === "code-tabs-default" ||
          remote === "interactive-tui-boot"
        ) {
          return remote;
        }
      } catch {
        // Fall through cleanly when local OIDC token expires or in offline CI
      }
    }
    const vid = entities?.user?.id ?? "anonymous-ssr";
    return deterministicBucket("exp-quickstart-cli-v1", vid) < 50
      ? "code-tabs-default"
      : "interactive-tui-boot";
  },
});
