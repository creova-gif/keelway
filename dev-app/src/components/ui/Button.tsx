import React from "react";
import { isTrustedUserEvent } from "@/lib/types";

export type ButtonVariant =
  | "primary"
  | "warning-cta"
  | "secondary"
  | "danger"
  | "danger-ghost"
  | "ghost";

export type ButtonSize = "sm" | "md" | "touch";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  clickOnly?: boolean;
  shortcutHint?: string;
  previewLocked?: boolean;
  lockReasonId?: string;
  loading?: boolean;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-teal-accent text-teal-ink border-transparent font-semibold hover:brightness-105",
  "warning-cta":
    "bg-ochre text-ochre-ink border-transparent font-semibold hover:brightness-105",
  secondary:
    "bg-surface-elevated text-fg border-border-control hover:border-fg-muted",
  danger:
    "bg-danger text-danger-ink border-transparent font-semibold hover:brightness-105",
  "danger-ghost":
    "bg-transparent text-danger border-transparent hover:bg-danger-subtle",
  ghost:
    "bg-transparent text-fg-muted border-transparent hover:text-fg hover:bg-surface-elevated",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "min-h-ctrl-sm px-2.5 py-1 text-xs",
  md: "min-h-ctrl-md px-3 py-1.5 text-ui",
  touch: "min-h-[44px] min-w-[44px] px-4 py-2 text-ui",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    clickOnly = false,
    shortcutHint,
    previewLocked = false,
    lockReasonId,
    loading = false,
    disabled,
    type = "button",
    className = "",
    onClick,
    "aria-disabled": ariaDisabledProp,
    "aria-describedby": ariaDescribedBy,
    children,
    ...rest
  },
  ref,
) {
  const isCallerAriaDisabled =
    ariaDisabledProp === true || ariaDisabledProp === "true";
  const isSoftDisabled = Boolean(previewLocked || loading || isCallerAriaDisabled);
  const isHardDisabled = Boolean(disabled);
  const isInactive = isSoftDisabled || isHardDisabled;

  const describedByIds = [ariaDescribedBy, previewLocked && lockReasonId ? lockReasonId : undefined]
    .filter(Boolean)
    .join(" ") || undefined;

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (isInactive) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    if (clickOnly && !isTrustedUserEvent(event)) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    onClick?.(event);
  };

  return (
    <button
      ref={ref}
      type={type}
      disabled={isHardDisabled}
      aria-disabled={isInactive ? "true" : undefined}
      aria-busy={loading ? "true" : undefined}
      aria-describedby={describedByIds}
      data-click-only={clickOnly ? "true" : undefined}
      onClick={handleClick}
      className={`inline-flex items-center justify-center gap-1.5 rounded-sm border transition-colors duration-150 select-none ${
        VARIANT_CLASSES[variant]
      } ${SIZE_CLASSES[size]} ${
        isInactive ? "opacity-55 cursor-not-allowed" : "cursor-pointer active:scale-[0.99]"
      } ${className}`.trim()}
      {...rest}
    >
      {loading ? (
        <span aria-hidden="true" className="font-mono text-xs leading-none">
          ↻
        </span>
      ) : null}
      <span>{children}</span>
      {!clickOnly && shortcutHint ? (
        <kbd
          aria-hidden="true"
          className="ms-1 rounded-xs border border-current/25 bg-canvas/20 px-1 py-0.5 font-mono text-[10px] leading-none opacity-85"
        >
          {shortcutHint}
        </kbd>
      ) : null}
    </button>
  );
});
