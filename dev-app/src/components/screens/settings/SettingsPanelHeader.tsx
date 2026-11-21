import React from "react";

export interface SettingsPanelHeaderProps {
  title: string;
  purpose: React.ReactNode;
  status?: React.ReactNode;
}

export function SettingsPanelHeader({
  title,
  purpose,
  status,
}: SettingsPanelHeaderProps): React.JSX.Element {
  return (
    <header className="flex items-baseline justify-between gap-4 border-b border-border pb-4">
      <div className="flex min-w-0 flex-col gap-1">
        <h2 className="text-[17px] font-semibold leading-[22px] text-fg">{title}</h2>
        <p className="text-[13px] leading-4 text-fg-muted">{purpose}</p>
      </div>
      {status !== undefined && status !== null ? (
        <span className="shrink-0 font-mono text-[11px] leading-[14px] text-fg-dim">{status}</span>
      ) : null}
    </header>
  );
}
