import { dismissToast, useToasts, type ToastTone } from "@/lib/toasts";

const TONE_CLASS: Record<ToastTone, string> = {
  ok: "border-ok/40 bg-ok-subtle text-ok",
  danger: "border-danger/40 bg-danger-subtle text-danger",
  accent: "border-accent/40 bg-accent-subtle text-accent",
  info: "border-running/40 bg-running-subtle text-running",
};

const TONE_GLYPH: Record<ToastTone, string> = {
  ok: "✓",
  danger: "✗",
  accent: "●",
  info: "ⓘ",
};

export function ToastViewport(): React.JSX.Element | null {
  const toasts = useToasts();
  if (toasts.length === 0) return null;
  return (
    <div
      aria-label="Notifications"
      className="pointer-events-none fixed right-3 top-12 z-50 flex w-72 flex-col items-end gap-1.5"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={`kw-fade-fast pointer-events-auto flex w-full items-start gap-2 rounded-sm border px-2.5 py-1.5 font-mono text-[11px] shadow-popover ${TONE_CLASS[toast.tone]}`}
        >
          <span aria-hidden="true">{TONE_GLYPH[toast.tone]}</span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{toast.label}</div>
            {toast.detail ? <div className="mt-0.5 text-fg-muted">{toast.detail}</div> : null}
          </div>
          <button
            type="button"
            aria-label={`Dismiss notification: ${toast.label}`}
            onClick={() => dismissToast(toast.id)}
            className="shrink-0 text-fg-dim hover:text-fg"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
