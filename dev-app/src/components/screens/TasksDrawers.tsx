import React, { useId, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import type { LogsDrawerTab } from "@/components/shell/DevAppShell";
import { DiffLinesView } from "@/components/screens/P10ApprovalCard";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type { EgressBarMode, FileDiffHunk } from "@/lib/types";

export interface TerminalExecEntry {
  id: string;
  command: string;
  stdout: string;
  stderr: string;
  exitCode: number;
  durationMs: number;
}

export interface ReviewChangesContentProps {
  hunks: FileDiffHunk[];
  reviewStatus: "pending" | "kept" | "reverted";
  onKeepChanges: () => void;
  onRevertAll: () => void;
  onAskForChanges: (hunk: FileDiffHunk) => void;
}

export function ReviewChangesContent({
  hunks,
  reviewStatus,
  onKeepChanges,
  onRevertAll,
  onAskForChanges,
}: ReviewChangesContentProps): React.JSX.Element {
  const totalAdded = hunks.reduce((sum, h) => sum + h.additions, 0);
  const totalDeleted = hunks.reduce((sum, h) => sum + h.deletions, 0);
  const agentWrote = hunks.some((h) => typeof h.aiRecordSeq === "number");
  const [openDiffs, setOpenDiffs] = useState<Record<string, boolean>>({});
  const fileCount = `${hunks.length} ${hunks.length === 1 ? "file" : "files"}`;

  return (
    <div className="flex h-full flex-col text-ui text-fg">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2 text-xs">
        <span className="font-mono tabular-nums text-fg-muted">
          {`${fileCount}${agentWrote ? " · agent wrote" : ""}`}
        </span>
        <span className="font-mono tabular-nums text-fg-muted">
          <span className="text-ok">{`+${totalAdded}`}</span>
          <span aria-hidden="true" className="mx-1 text-fg-dim">/</span>
          <span className="text-danger">{`-${totalDeleted}`}</span>
        </span>
      </div>

      {reviewStatus !== "pending" ? (
        <div
          role="status"
          className="mt-2 rounded-sm border border-border-strong bg-surface-elevated px-2.5 py-1.5 text-xs text-fg-muted"
        >
          {reviewStatus === "kept"
            ? "Changes kept in working tree."
            : "Working tree changes reverted."}
        </div>
      ) : null}

      {hunks.length === 0 ? (
        <p className="py-4 text-xs text-fg-muted">No uncommitted changes in working tree.</p>
      ) : (
        <ul className="min-h-0 flex-1 divide-y divide-border overflow-y-auto">
          {hunks.map((hunk) => {
            const hunkKey = `${hunk.path}-${hunk.newStart}`;
            const isOpen = Boolean(openDiffs[hunkKey]);
            return (
              <li key={hunkKey}>
                <div className="flex flex-wrap items-center justify-between gap-2 py-2 text-xs">
                  <div className="flex min-w-0 items-center gap-2">
                    <code dir="ltr" className="unicode-bidi-isolate truncate font-mono text-fg">
                      {hunk.path}
                    </code>
                    {typeof hunk.aiRecordSeq === "number" ? (
                      <SemanticBadge kind="ai" detail={`#${hunk.aiRecordSeq}`} />
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <span className="font-mono tabular-nums text-fg-muted">
                      <span className="text-ok">{`+${hunk.additions}`}</span>{" "}
                      <span className="text-danger">{`-${hunk.deletions}`}</span>
                    </span>
                    <button
                      type="button"
                      aria-expanded={isOpen}
                      onClick={() =>
                        setOpenDiffs((prev) => ({ ...prev, [hunkKey]: !isOpen }))
                      }
                      className="kw-underline text-xs text-fg-muted transition-colors duration-fast ease-state hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
                    >
                      {isOpen ? "hide diff" : "view diff"}
                    </button>
                    <Button size="sm" variant="ghost" onClick={() => onAskForChanges(hunk)}>
                      Ask for changes
                    </Button>
                  </div>
                </div>
                {isOpen ? (
                  <div className="mb-2 overflow-hidden rounded-sm border border-border-strong bg-canvas">
                    <DiffLinesView lines={hunk.lines} />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-auto space-y-2 border-t border-border pt-2.5">
        <p className="text-[11px] text-fg-dim">
          keep/revert writes a receipt — reviewed changes are audited, not silent
        </p>
        <div className="flex items-center justify-between gap-2">
          <Button size="sm" variant="ghost" onClick={onRevertAll}>
            Revert all
          </Button>
          <Button size="sm" variant="primary" onClick={onKeepChanges}>
            Keep all
          </Button>
        </div>
      </div>
    </div>
  );
}

export interface LogsDrawerPanelsProps {
  logLines: string[];
  terminalCommand: string;
  onTerminalCommandChange: (val: string) => void;
  terminalRunning: boolean;
  terminalHistory: TerminalExecEntry[];
  onRunTerminal: (event: React.FormEvent) => void;
  egressMode: EgressBarMode;
  airGapEnabled: boolean;
  onToggleAirGap: () => void;
}

function TerminalTabPanel({
  terminalCommand,
  onTerminalCommandChange,
  terminalRunning,
  terminalHistory,
  onRunTerminal,
}: Pick<
  LogsDrawerPanelsProps,
  "terminalCommand" | "onTerminalCommandChange" | "terminalRunning" | "terminalHistory" | "onRunTerminal"
>): React.JSX.Element {
  const terminalInputId = useId();

  return (
    <div className="flex flex-col gap-2">
      <form onSubmit={onRunTerminal} className="flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1">
          <label htmlFor={terminalInputId} className="mb-1 block text-[11px] font-medium text-fg-muted">
            Sandbox command
          </label>
          <input
            id={terminalInputId}
            type="text"
            dir="ltr"
            value={terminalCommand}
            onChange={(e) => onTerminalCommandChange(e.target.value)}
            placeholder="pytest -q"
            className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-surface px-2.5 py-1 font-mono text-xs text-fg"
          />
        </div>
        <Button type="submit" size="sm" variant="secondary" loading={terminalRunning}>
          Run in sandbox
        </Button>
      </form>
      <div className="space-y-2 font-mono text-xs">
        {terminalHistory.map((entry) => (
          <div key={entry.id} className="rounded-xs border border-border bg-surface/60 p-2 text-fg">
            <div className="flex items-center justify-between text-fg-muted">
              <code dir="ltr" className="unicode-bidi-isolate">{`$ ${entry.command}`}</code>
              <span>{`exit ${entry.exitCode}`}</span>
            </div>
            {entry.stdout ? <pre className="mt-1 whitespace-pre-wrap text-fg">{entry.stdout}</pre> : null}
            {entry.stderr ? <pre className="mt-1 whitespace-pre-wrap text-danger">{entry.stderr}</pre> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export function buildLogsDrawerTabPanels(
  props: LogsDrawerPanelsProps,
): Record<LogsDrawerTab, React.ReactNode> {
  const {
    logLines,
    terminalCommand,
    onTerminalCommandChange,
    terminalRunning,
    terminalHistory,
    onRunTerminal,
    egressMode,
    airGapEnabled,
    onToggleAirGap,
  } = props;

  return {
    logs: (
      <div className="space-y-1 font-mono text-xs text-fg-muted">
        {logLines.map((line, idx) => (
          <div key={`${idx}-${line}`}>{line}</div>
        ))}
      </div>
    ),
    terminal: (
      <TerminalTabPanel
        terminalCommand={terminalCommand}
        onTerminalCommandChange={onTerminalCommandChange}
        terminalRunning={terminalRunning}
        terminalHistory={terminalHistory}
        onRunTerminal={onRunTerminal}
      />
    ),
    network: (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-surface p-3 text-xs">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2 font-medium text-fg">
            <span>
              {egressMode === "air_gapped_verified"
                ? "Air-gapped · verified"
                : "Network · unmeasured"}
            </span>
            <span aria-hidden="true" className="text-fg-dim">·</span>
            <span className="font-mono text-fg-muted">sent: unmeasured</span>
            <SemanticBadge kind={egressMode === "air_gapped_verified" ? "locked" : "unmeasured"} />
          </div>
          <p className="text-[11px] text-fg-muted">
            Loopback byte counter is not active yet. Enable Air-Gap to block all outbound sockets at the runtime gate.
          </p>
        </div>
        <Button
          size="sm"
          variant={airGapEnabled ? "primary" : "secondary"}
          aria-pressed={airGapEnabled}
          onClick={onToggleAirGap}
        >
          {airGapEnabled ? "Disable Air-Gap" : "Lock Air-Gap"}
        </Button>
      </div>
    ),
  };
}

export interface LogsDrawerSectionProps extends LogsDrawerPanelsProps {
  tab: LogsDrawerTab;
  onTabChange: (next: LogsDrawerTab) => void;
  onClose: () => void;
}

export function LogsDrawerSection(props: LogsDrawerSectionProps): React.JSX.Element {
  const { tab, onTabChange, onClose } = props;
  const panels = buildLogsDrawerTabPanels(props);

  return (
    <section
      aria-label="Logs and terminal"
      tabIndex={-1}
      data-programmatic-focus="true"
      className="flex h-[300px] shrink-0 flex-col border-t border-border-strong bg-chrome"
    >
      <Tabs.Root
        value={tab}
        onValueChange={(v) => onTabChange(v as LogsDrawerTab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex items-center justify-between border-b border-border px-3 py-1">
          <Tabs.List aria-label="Workspace output tabs" className="flex items-center gap-1">
            {(["logs", "terminal", "network"] as const).map((t) => (
              <Tabs.Trigger
                key={t}
                value={t}
                className="rounded-xs px-2.5 py-1 text-xs font-medium capitalize text-fg-muted data-[state=active]:bg-surface-elevated data-[state=active]:text-fg"
              >
                {t}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Button size="sm" variant="ghost" aria-label="Close logs drawer" onClick={onClose}>
            Close
          </Button>
        </div>

        <Tabs.Content value="logs" className="min-h-0 flex-1 overflow-y-auto bg-code p-3">
          {panels.logs}
        </Tabs.Content>

        <Tabs.Content value="terminal" className="min-h-0 flex-1 overflow-y-auto bg-code p-3">
          {panels.terminal}
        </Tabs.Content>

        <Tabs.Content value="network" className="min-h-0 flex-1 overflow-y-auto bg-code p-3">
          {panels.network}
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}
