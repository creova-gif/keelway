import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  exportSiemAudit,
  fetchObservabilityMetrics,
  type ObservabilityMetricsSnapshot,
  type SiemAuditExportResult,
  type SiemExportFormat,
} from "@/lib/platformEnterpriseApi";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface SiemAndObservabilityPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

const METRIC_COUNTER_KEYS = [
  "keelway_kflow_runs_total",
  "keelway_crdt_entries_total",
  "keelway_mcp_servers_total",
  "keelway_scim_active_users",
  "keelway_p10_quorum_approved_total",
  "keelway_siem_exports_total",
] as const;

export function SiemAndObservabilityPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: SiemAndObservabilityPanelProps): React.JSX.Element {
  const [siemFormat, setSiemFormat] = useState<SiemExportFormat>("ocsf");
  const [siemBatch, setSiemBatch] = useState<SiemAuditExportResult | null>(null);
  const [siemBusy, setSiemBusy] = useState(false);

  const [telemetry, setTelemetry] = useState<ObservabilityMetricsSnapshot | null>(null);
  const [telemetryBusy, setTelemetryBusy] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchObservabilityMetrics(workspaceId, "otlp_json", activeRbacRole)
      .then((snap) => { if (!cancelled) setTelemetry(snap); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const handleExportSiem = async () => {
    if (siemBusy) return;
    setSiemBusy(true);
    setErrorBanner(null);
    try {
      const batch = await exportSiemAudit(workspaceId, siemFormat, activeRbacRole);
      setSiemBatch(batch);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to export SIEM audit batch.");
    } finally {
      setSiemBusy(false);
    }
  };

  const handleRefreshTelemetry = async () => {
    if (telemetryBusy) return;
    setTelemetryBusy(true);
    setErrorBanner(null);
    try {
      const snap = await fetchObservabilityMetrics(workspaceId, "otlp_json", activeRbacRole);
      setTelemetry(snap);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to refresh OpenTelemetry & Prometheus snapshot.");
    } finally {
      setTelemetryBusy(false);
    }
  };

  return (
    <section
      aria-label="SIEM audit streaming and OpenTelemetry observability"
      className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">
            Tamper-Evident SIEM Audit Streaming &amp; OpenTelemetry Observability
          </h2>
          <p className="text-xs text-fg-muted">
            Export hash-chained Record audit events in OCSF v1.1, ArcSight CEF, or NDJSON alongside live Prometheus &amp; OTLP runtime counters.
          </p>
        </div>
        <SemanticBadge kind="live" labelOverride={`Telemetry · ${workspaceId}`} />
      </div>

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          {errorBanner}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">Tamper-Evident SIEM Audit Exporter</h3>
              <p className="font-mono text-[11px] text-fg-muted">OCSF v1.1 · ArcSight CEF · NDJSON / JSONL</p>
            </div>
            {siemBatch ? (
              <SemanticBadge kind="passed" labelOverride={`${siemBatch.format.toUpperCase()} · ${siemBatch.record_count} events`} />
            ) : null}
          </div>

          <div className="flex flex-wrap items-end justify-between gap-2">
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Export schema format</span>
              <select
                aria-label="SIEM export format"
                value={siemFormat}
                onChange={(e) => setSiemFormat(e.target.value as SiemExportFormat)}
                className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              >
                <option value="ocsf">OCSF v1.1 JSON</option>
                <option value="cef">ArcSight CEF</option>
                <option value="jsonl">NDJSON / JSONL</option>
              </select>
            </label>
            <Button size="sm" variant="primary" loading={siemBusy} onClick={() => { void handleExportSiem(); }}>
              Export SIEM Audit Batch
            </Button>
          </div>

          {siemBatch ? (
            <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                <span className="text-fg">
                  Format: <strong className="uppercase text-teal-accent">{siemBatch.format}</strong> · Records: <strong>{siemBatch.record_count}</strong>
                </span>
                <code
                  className="max-w-[240px] truncate font-mono text-xs text-teal-accent"
                  title={siemBatch.batch_sha256}
                >
                  {siemBatch.batch_sha256}
                </code>
              </div>
              <pre
                tabIndex={0}
                role="region"
                aria-label="Exported SIEM audit records preview"
                className="max-h-28 overflow-auto rounded-xs border border-border bg-chrome p-2 font-mono text-[11px] text-fg"
              >
                {siemBatch.records.join("\n")}
              </pre>
            </div>
          ) : (
            <div className="rounded-xs border border-border bg-canvas px-3 py-2 font-mono text-[11px] text-fg-muted">
              Select OCSF v1.1 JSON, ArcSight CEF, or NDJSON and click Export SIEM Audit Batch to verify batch SHA-256 provenance.
            </div>
          )}
        </div>

        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">Live Prometheus &amp; OpenTelemetry OTLP Metrics</h3>
              <p className="font-mono text-[11px] text-fg-muted">/v1/platform/observability/metrics</p>
            </div>
            <Button size="sm" variant="secondary" loading={telemetryBusy} onClick={() => { void handleRefreshTelemetry(); }}>
              Refresh Telemetry Snapshot
            </Button>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            {METRIC_COUNTER_KEYS.map((metricKey) => (
              <div key={metricKey} className="rounded-xs border border-border bg-canvas px-2.5 py-1.5 font-mono">
                <div className="truncate text-[10px] text-fg-muted" title={metricKey}>{metricKey}</div>
                <div className="mt-0.5 text-xs font-semibold text-teal-accent">
                  {telemetry ? telemetry.counters[metricKey] : 0}
                </div>
              </div>
            ))}
          </div>

          {telemetry ? (
            <pre
              tabIndex={0}
              role="region"
              aria-label="Prometheus metrics exposition preview"
              className="max-h-28 overflow-auto rounded-xs border border-border bg-canvas p-2 font-mono text-[11px] text-fg-muted"
            >
              {telemetry.prometheus_text}
            </pre>
          ) : null}
        </div>
      </div>
    </section>
  );
}
