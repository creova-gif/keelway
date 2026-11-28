import React from "react";

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Short headline, e.g. "No entries recorded yet" */
  title: string;
  /** Reassuring context per DESIGN.md §4 — what will appear here and why */
  body?: string;
  /** Optional recovery action rendered under the copy (e.g. a Button) */
  action?: React.ReactNode;
}

export function EmptyState({ title, body, action, className, ...rest }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={["flex flex-col items-center justify-center gap-2 py-12 text-center", className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      <p className="text-sm font-medium text-fg">{title}</p>
      {body ? <p className="max-w-md text-xs text-fg-muted">{body}</p> : null}
      {action}
    </div>
  );
}
