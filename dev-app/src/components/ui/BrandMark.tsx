import React from "react";

export type BrandMarkVariant = "lockup" | "mark-only" | "tile";

export interface BrandMarkProps {
  size?: number;
  showWordmark?: boolean;
  variant?: BrandMarkVariant;
  className?: string;
  wordmarkClassName?: string;
  "aria-label"?: string;
}

export const KEELWAY_K_STEM_PATH = "M7 5h9v38H7z" as const;
export const KEELWAY_K_ARM_PATH = "M16 26 28 5h9L25.5 27 44 43H32L16 30z" as const;
export const KEELWAY_DOT_SPEC = { cx: 42.5, cy: 9, r: 4.5 } as const;

export function BrandMark({
  size = 20,
  showWordmark,
  variant = "lockup",
  className = "",
  wordmarkClassName = "",
  "aria-label": ariaLabel,
}: BrandMarkProps): React.JSX.Element {
  const effectiveShowWordmark = showWordmark ?? variant === "lockup";

  const renderSvg = (): React.JSX.Element => {
    switch (variant) {
      case "tile":
        return (
          <svg
            width={size}
            height={size}
            viewBox="0 0 48 48"
            role={ariaLabel ? "img" : undefined}
            aria-label={ariaLabel}
            aria-hidden={ariaLabel ? undefined : "true"}
            className="shrink-0"
          >
            <rect width="48" height="48" rx="11" fill="#09090b" />
            <path d={KEELWAY_K_STEM_PATH} fill="#fafafa" />
            <path d={KEELWAY_K_ARM_PATH} fill="#fafafa" />
            <circle cx={KEELWAY_DOT_SPEC.cx} cy={KEELWAY_DOT_SPEC.cy} r={KEELWAY_DOT_SPEC.r} fill="#2dd4bf" />
          </svg>
        );
      case "lockup":
      case "mark-only":
        return (
          <svg
            width={size}
            height={size}
            viewBox="0 0 48 48"
            role={ariaLabel ? "img" : undefined}
            aria-label={ariaLabel}
            aria-hidden={ariaLabel ? undefined : "true"}
            className="shrink-0"
          >
            <path d={KEELWAY_K_STEM_PATH} fill="currentColor" />
            <path d={KEELWAY_K_ARM_PATH} fill="currentColor" />
            <circle cx={KEELWAY_DOT_SPEC.cx} cy={KEELWAY_DOT_SPEC.cy} r={KEELWAY_DOT_SPEC.r} fill="var(--teal-accent)" />
          </svg>
        );
      default: {
        const _exhaustive: never = variant;
        return _exhaustive;
      }
    }
  };

  if (!effectiveShowWordmark) {
    return className ? <span className={`inline-flex items-center ${className}`}>{renderSvg()}</span> : renderSvg();
  }

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`.trim()}>
      {renderSvg()}
      <span className={`font-sans font-bold tracking-tight text-fg ${wordmarkClassName}`.trim()}>
        Keelway
      </span>
    </span>
  );
}
