import React, { useId } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import type { ApiRequestError } from "@/lib/api";
import type { EgressTelemetryState } from "@/lib/types";

export function formatEgressBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export interface EgressDisplaySpec {
  primaryLabel: string;
  primaryToneClass: string;
  bytesLabel: string;
  badgeKind: SemanticBadgeKind;
  showCloudDetails: boolean;
}

export function resolveEgressDisplay(
  egress: EgressTelemetryState,
  offlineSetting: boolean,
  deployPending: boolean,
): EgressDisplaySpec {
  const hasMeasuredBytes = egress.bytesSent !== null && Number.isFinite(egress.bytesSent);
  const measuredBytesLabel = hasMeasuredBytes
    ? `${formatEgressBytes(egress.bytesSent!)} sent`
    : "sent: unmeasured";
  const suffix = egress.lastCheckedAt ? ` (${egress.lastCheckedAt})` : "";

  if (egress.mode === "measured_offline") {
    return {
      primaryLabel: `Offline · verified${suffix}`,
      primaryToneClass: "text-ok",
      bytesLabel: hasMeasuredBytes ? measuredBytesLabel : "0 B sent",
      badgeKind: "live",
      showCloudDetails: false,
    };
  }
  if (egress.mode === "air_gapped_verified") {
    return {
      primaryLabel: `Air-gapped · verified${suffix}`,
      primaryToneClass: "text-teal-accent",
      bytesLabel: measuredBytesLabel,
      badgeKind: "locked",
      showCloudDetails: false,
    };
  }
  if (egress.mode === "unknown_probe_failed") {
    return {
      primaryLabel: "Network: unknown (probe failed)",
      primaryToneClass: "text-warning",
      bytesLabel: measuredBytesLabel,
      badgeKind: hasMeasuredBytes ? "live" : "unmeasured",
      showCloudDetails: false,
    };
  }
  if (egress.mode === "connected_warning") {
    return {
      primaryLabel: "Connected",
      primaryToneClass: "text-fg-muted",
      bytesLabel: measuredBytesLabel,
      badgeKind: hasMeasuredBytes ? "live" : "unmeasured",
      showCloudDetails: true,
    };
  }

  const label = deployPending
    ? "Network: deploy pending, nothing sent yet"
    : offlineSetting === false
      ? "Connected"
      : "Offline (setting)";

  return {
    primaryLabel: label,
    primaryToneClass: "text-fg-muted",
    bytesLabel: measuredBytesLabel,
    badgeKind: hasMeasuredBytes ? "live" : "unmeasured",
    showCloudDetails: false,
  };
}

export interface StatusBarEgressProps {
  egress: EgressTelemetryState;
  offlineSetting: boolean;
  deployPending: boolean;
  fallbackResponseCount?: number;
  apiError?: ApiRequestError | null;
  onSwitchToLocalModel?: () => void;
  onGoOffline?: () => void;
}

export function StatusBarEgress({
  egress,
  offlineSetting,
  deployPending,
  fallbackResponseCount = 0,
  apiError = null,
  onSwitchToLocalModel,
  onGoOffline,
}: StatusBarEgressProps): React.JSX.Element {
  const egressPopoverHeadingId = useId();
  const display = resolveEgressDisplay(egress, offlineSetting, deployPending);

  return (
    <div className="flex items-center gap-2">
      <span className={display.primaryToneClass}>{display.primaryLabel}</span>
      {display.showCloudDetails ? (
        <>
          <span aria-hidden="true" className="text-fg-dim">·</span>
          <span className="font-medium text-warning">{`Cloud used (${egress.cloudCallsCount})`}</span>
        </>
      ) : null}
      <span aria-hidden="true" className="text-fg-dim">·</span>
      <span className={`font-mono tabular-nums ${display.showCloudDetails ? "text-fg" : "text-fg-muted"}`}>
        {display.bytesLabel}
      </span>
      {apiError ? (
        <>
          <span aria-hidden="true" className="text-fg-dim">·</span>
          <span
            role="status"
            aria-live="polite"
            className="font-mono text-[11px] text-danger"
            title={`${apiError.message} — check the local API is running, then retry the action.`}
          >
            {`API error: ${apiError.path}${apiError.kind === "http" && apiError.status ? ` (${apiError.status})` : ` (${apiError.kind})`}`}
          </span>
        </>
      ) : null}
      {fallbackResponseCount > 0 ? (
        <>
          <span aria-hidden="true" className="text-fg-dim">·</span>
          <span
            className="font-mono text-[11px] text-warning"
            title="One or more panels are showing bundled fallback data because the local API did not respond."
          >
            {`Offline data ×${fallbackResponseCount}`}
          </span>
        </>
      ) : null}
      <SemanticBadge kind={display.badgeKind} />
      {display.showCloudDetails ? (
        <Popover.Root>
          <Popover.Trigger asChild>
            <button
              type="button"
              className="rounded-xs border border-border-control bg-surface-elevated px-1.5 py-0 font-sans text-[11px] font-medium text-fg hover:border-fg-muted"
            >
              Details
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              side="top"
              align="end"
              sideOffset={6}
              aria-labelledby={egressPopoverHeadingId}
              className="z-50 w-80 rounded-md border border-border-strong bg-surface p-3 text-ui text-fg shadow-popover"
            >
              <div className="space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <h2 id={egressPopoverHeadingId} className="text-xs font-semibold text-fg">
                    Data sent this session
                  </h2>
                  <SemanticBadge kind={display.badgeKind} />
                </div>
                {egress.endpoints.length > 0 ? (
                  <ul className="divide-y divide-border rounded-sm border border-border bg-canvas/60">
                    {egress.endpoints.map((ep) => (
                      <li
                        key={`${ep.host}-${ep.purpose}`}
                        className="flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs"
                      >
                        <div className="min-w-0">
                          <div className="truncate font-mono text-fg">
                            <code dir="ltr" className="unicode-bidi-isolate">{ep.host}</code>
                          </div>
                          <div className="truncate text-[11px] text-fg-muted">
                            {ep.purpose}
                            {ep.modelId ? (
                              <>
                                {" · "}
                                <code dir="ltr" className="unicode-bidi-isolate">{ep.modelId}</code>
                              </>
                            ) : null}
                          </div>
                        </div>
                        <div className="shrink-0 text-end font-mono text-[11px] tabular-nums text-fg-muted">
                          <div>{`${ep.calls} ${ep.calls === 1 ? "call" : "calls"}`}</div>
                          <div>{ep.bytesSent !== null ? formatEgressBytes(ep.bytesSent) : "unmeasured"}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p className="text-[11px] text-fg-muted">Every request is also a Record entry.</p>
                <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                  <Button size="sm" variant="primary" onClick={() => onSwitchToLocalModel?.()}>
                    Switch to local model
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => onGoOffline?.()}>
                    Go offline
                  </Button>
                </div>
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      ) : null}
    </div>
  );
}
