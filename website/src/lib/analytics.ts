"use client";

import { track } from "@vercel/analytics";

export type KeelwayAnalyticsEvent =
  | "cta_quickstart_clicked"
  | "cta_early_access_clicked"
  | "cockpit_lens_switched"
  | "approval_gate_decision"
  | "architecture_layer_selected"
  | "workflow_step_selected"
  | "hash_chain_verified"
  | "code_snippet_copied"
  | "early_access_submitted"
  | "model_filter_changed"
  | "model_hardware_profile_changed"
  | "model_inspector_opened"
  | "lora_adapter_toggled"
  | "routing_simulator_updated"
  | "redaction_sandbox_tested"
  | "scoped_key_preview_minted"
  | "pricing_billing_toggled"
  | "pricing_faq_opened"
  | "brand_token_copied"
  | "brand_svg_copied"
  | "docs_section_jumped"
  | "api_endpoint_selected"
  | "api_catalog_searched"
  | "cmdk_opened"
  | "cmdk_prefix_switched"
  | "cmdk_result_selected"
  | "demo_video_toggled"
  | "benchmark_chart_inspected"
  | "live_sandbox_executed"
  | "experiment_exposed"
  | "experiment_variant_switched"
  | "p10_deck_action"
  | "p10_escalation_triggered"
  | "record_tamper_simulated"
  | "record_chain_repaired"
  | "governance_tamper_simulated"
  | "governance_chain_verified"
  | "manifest_drift_tested"
  | "marketplace_package_scanned"
  | "cli_tui_command_simulated"
  | "pricing_byom_inspected"
  | "golden_thread_stage_switched"
  | "golden_thread_code_synced"
  | "golden_thread_tape_scrubbed"
  | "golden_thread_prompt_gated"
  | "settlement_rail_selected"
  | "spec_decoding_k_changed"
  | "self_healing_demo_run"
  | "airgap_enabled"
  | "airgap_disabled";

export type EvaluatedExperimentMap = Record<string, string | boolean | number>;

interface AnalyticsWindowHooks {
  posthog?: {
    capture?: (
      eventName: string,
      properties?: Record<string, string | number | boolean>
    ) => void;
  };
  plausible?: (
    eventName: string,
    options?: { props?: Record<string, string | number | boolean> }
  ) => void;
}

const activeExperimentState: EvaluatedExperimentMap = {};
const exposedSessionKeys = new Set<string>();

/**
 * Registers server-evaluated Vercel Flags on the client session and emits
 * deduplicated exposure events to Vercel Web Analytics, PostHog, and Plausible.
 */
export function registerEvaluatedExperiments(
  evaluated: EvaluatedExperimentMap,
  surface: string = "home"
): void {
  for (const [flagKey, variant] of Object.entries(evaluated)) {
    activeExperimentState[flagKey] = variant;

    const dedupeKey = `${surface}:${flagKey}:${String(variant)}`;
    if (exposedSessionKeys.has(dedupeKey)) continue;
    exposedSessionKeys.add(dedupeKey);

    try {
      track("experiment_exposed", {
        flag_key: flagKey,
        variant: String(variant),
        surface,
      });

      if (typeof window !== "undefined") {
        const w = window as unknown as AnalyticsWindowHooks;
        if (w.posthog && typeof w.posthog.capture === "function") {
          w.posthog.capture("$feature_flag_called", {
            $feature_flag: flagKey,
            $feature_flag_response: String(variant),
            surface,
          });
        }
        if (typeof w.plausible === "function") {
          w.plausible("experiment_exposed", {
            props: { flag_key: flagKey, variant: String(variant), surface },
          });
        }
      }
    } catch {
      // Non-blocking telemetry
    }
  }
}

export function getActiveExperiments(): EvaluatedExperimentMap {
  return { ...activeExperimentState };
}

/**
 * Privacy-respecting funnel & interaction helper.
 * Automatically attaches active A/B experiment variants (`exp_home_gate_v1`,
 * `exp_quickstart_cli_v1`) to every conversion event across Vercel Web Analytics,
 * PostHog, and Plausible.
 */
export function trackEvent(
  name: KeelwayAnalyticsEvent,
  properties?: Record<string, string | number | boolean>
): void {
  try {
    const expProps: Record<string, string | number | boolean> = {};
    for (const [k, v] of Object.entries(activeExperimentState)) {
      const normalizedKey = k.replace(/-/g, "_");
      expProps[normalizedKey] = v;
    }

    const mergedProps: Record<string, string | number | boolean> = {
      ...expProps,
      ...(properties ?? {}),
    };

    track(name, mergedProps);

    if (typeof window !== "undefined") {
      const w = window as unknown as AnalyticsWindowHooks;
      if (w.posthog && typeof w.posthog.capture === "function") {
        w.posthog.capture(name, mergedProps);
      }
      if (typeof w.plausible === "function") {
        w.plausible(name, { props: mergedProps });
      }
    }
  } catch {
    // Telemetry is strictly non-blocking
  }
}
