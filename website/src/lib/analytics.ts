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
  | "cmdk_result_selected"
  | "demo_video_toggled"
  | "benchmark_chart_inspected"
  | "live_sandbox_executed";

/**
 * Privacy-respecting telemetry helper for high-value product interactions.
 * Dispatches to Vercel Analytics and forwards to PostHog if configured on window.
 */
export function trackEvent(
  name: KeelwayAnalyticsEvent,
  properties?: Record<string, string | number | boolean>
): void {
  try {
    track(name, properties);
    if (typeof window !== "undefined") {
      const ph = (window as unknown as { posthog?: { capture?: (e: string, p?: unknown) => void } })
        .posthog;
      if (ph && typeof ph.capture === "function") {
        ph.capture(name, properties);
      }
    }
  } catch {
    // Telemetry is strictly non-blocking
  }
}
