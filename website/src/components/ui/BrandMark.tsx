import React from "react";
import { cn } from "@/lib/utils";

export type BrandTheme = "dark" | "light";
export type BrandMarkVariant = "lockup" | "mark-only" | "tile";
export type HexColor = `#${string}`;
export type CssColorValue = HexColor | `rgba(${string})`;

export interface BrandSwatchSpec {
  readonly token: `--${string}`;
  readonly hex: HexColor;
  readonly role: string;
  readonly contrastNote?: string;
}

export interface BrandThemeTokens {
  readonly theme: BrandTheme;
  readonly bgCanvas: HexColor;
  readonly bgSurface: HexColor;
  readonly bgSurfaceElevated: HexColor;
  readonly borderSubtle: HexColor;
  readonly borderStrong: HexColor;
  readonly fgPrimary: HexColor;
  readonly fgMuted: HexColor;
  readonly fgDim: HexColor;
  readonly tealAccent: HexColor;
  readonly tealSurface: CssColorValue;
  readonly tealInk: HexColor;
  readonly danger: HexColor;
  readonly dangerInk: HexColor;
}

export interface MarkGeometrySpec {
  readonly viewBox: "0 0 48 48";
  readonly tileRx: 11;
  readonly stemPath: "M7 5h9v38H7z";
  readonly armPath: "M16 26 28 5h9L25.5 27 44 43H32L16 30z";
  readonly dotCx: 42.5;
  readonly dotCy: 9;
  readonly dotR: 4.5;
}

export const MARK_GEOMETRY: MarkGeometrySpec = {
  viewBox: "0 0 48 48",
  tileRx: 11,
  stemPath: "M7 5h9v38H7z",
  armPath: "M16 26 28 5h9L25.5 27 44 43H32L16 30z",
  dotCx: 42.5,
  dotCy: 9,
  dotR: 4.5,
} as const;

export const BRAND_PALETTE: Readonly<Record<BrandTheme, BrandThemeTokens>> = {
  dark: {
    theme: "dark",
    bgCanvas: "#09090B",
    bgSurface: "#121215",
    bgSurfaceElevated: "#18181B",
    borderSubtle: "#27272A",
    borderStrong: "#3F3F46",
    fgPrimary: "#FAFAFA",
    fgMuted: "#A1A1AA",
    fgDim: "#8E8E96",
    tealAccent: "#2DD4BF",
    tealSurface: "rgba(45, 212, 191, 0.12)",
    tealInk: "#042F2E",
    danger: "#F87171",
    dangerInk: "#2A0606",
  },
  light: {
    theme: "light",
    bgCanvas: "#FAFAFA",
    bgSurface: "#FFFFFF",
    bgSurfaceElevated: "#F4F4F5",
    borderSubtle: "#E4E4E7",
    borderStrong: "#D4D4D8",
    fgPrimary: "#09090B",
    fgMuted: "#52525B",
    fgDim: "#71717A",
    tealAccent: "#0F766E",
    tealSurface: "rgba(15, 118, 110, 0.10)",
    tealInk: "#FFFFFF",
    danger: "#B91C1C",
    dangerInk: "#FFFFFF",
  },
} as const;

export const DARK_SWATCHES: readonly BrandSwatchSpec[] = [
  { token: "--bg-canvas", hex: "#09090B", role: "Monochrome void canvas" },
  { token: "--bg-surface", hex: "#121215", role: "Primary cards & panels" },
  {
    token: "--bg-surface-elevated",
    hex: "#18181B",
    role: "Raised & hover surfaces",
  },
  {
    token: "--border-subtle",
    hex: "#27272A",
    role: "Hairline structural dividers",
  },
  {
    token: "--border-strong",
    hex: "#3F3F46",
    role: "Interactive card & input edges",
  },
  {
    token: "--fg-primary",
    hex: "#FAFAFA",
    role: "Primary ink & wordmark",
    contrastNote: "19.2:1 AAA on #09090B",
  },
  {
    token: "--fg-muted",
    hex: "#A1A1AA",
    role: "Secondary metadata & labels",
    contrastNote: "7.9:1 AAA on #09090B",
  },
  {
    token: "--teal-accent",
    hex: "#2DD4BF",
    role: "Reserved: K-dot mark, focus ring & primary CTA",
    contrastNote: "CTA ink #042F2E (8.6:1 AAA)",
  },
] as const;

export const LIGHT_SWATCHES: readonly BrandSwatchSpec[] = [
  { token: "--bg-canvas", hex: "#FAFAFA", role: "Clean monochrome canvas" },
  { token: "--bg-surface", hex: "#FFFFFF", role: "Primary card surface" },
  {
    token: "--bg-surface-elevated",
    hex: "#F4F4F5",
    role: "Raised & hover surfaces",
  },
  {
    token: "--border-subtle",
    hex: "#E4E4E7",
    role: "Hairline structural dividers",
  },
  {
    token: "--border-strong",
    hex: "#D4D4D8",
    role: "Interactive card & input edges",
  },
  {
    token: "--fg-primary",
    hex: "#09090B",
    role: "Primary ink & wordmark",
    contrastNote: "19.9:1 AAA on #FFFFFF",
  },
  {
    token: "--fg-muted",
    hex: "#52525B",
    role: "Secondary metadata & labels",
    contrastNote: "7.5:1 AAA on #FFFFFF",
  },
  {
    token: "--teal-accent",
    hex: "#0F766E",
    role: "Reserved: K-dot mark, focus ring & primary CTA",
    contrastNote: "CTA ink #FFFFFF (5.4:1 AA)",
  },
] as const;

export function getSwatchesForTheme(
  theme: BrandTheme
): readonly BrandSwatchSpec[] {
  switch (theme) {
    case "dark":
      return DARK_SWATCHES;
    case "light":
      return LIGHT_SWATCHES;
    default: {
      const _exhaustive: never = theme;
      return _exhaustive;
    }
  }
}

export function serializeWordmarkLockupSvg(
  theme: BrandTheme = "dark"
): string {
  const tokens = BRAND_PALETTE[theme];
  return `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="${MARK_GEOMETRY.viewBox}"><path d="${MARK_GEOMETRY.stemPath}" fill="${tokens.fgPrimary}"/><path d="${MARK_GEOMETRY.armPath}" fill="${tokens.fgPrimary}"/><circle cx="${MARK_GEOMETRY.dotCx}" cy="${MARK_GEOMETRY.dotCy}" r="${MARK_GEOMETRY.dotR}" fill="${tokens.tealAccent}"/></svg>`;
}

export function serializeFaviconSvg(): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${MARK_GEOMETRY.viewBox}"><rect width="48" height="48" rx="${MARK_GEOMETRY.tileRx}" fill="${BRAND_PALETTE.dark.bgCanvas}"/><path d="${MARK_GEOMETRY.stemPath}" fill="${BRAND_PALETTE.dark.fgPrimary}"/><path d="${MARK_GEOMETRY.armPath}" fill="${BRAND_PALETTE.dark.fgPrimary}"/><circle cx="${MARK_GEOMETRY.dotCx}" cy="${MARK_GEOMETRY.dotCy}" r="${MARK_GEOMETRY.dotR}" fill="${BRAND_PALETTE.dark.tealAccent}"/></svg>`;
}

export interface BrandMarkProps {
  readonly size?: number;
  readonly showWordmark?: boolean;
  readonly variant?: BrandMarkVariant;
  readonly themeOverride?: BrandTheme;
  readonly className?: string;
  readonly wordmarkClassName?: string;
  readonly "aria-label"?: string;
}

export function BrandMark({
  size = 30,
  showWordmark = false,
  variant = "lockup",
  themeOverride,
  className,
  wordmarkClassName,
  "aria-label": ariaLabel,
}: BrandMarkProps): React.JSX.Element {
  const shouldShowWordmark = showWordmark && variant !== "mark-only";
  const kFill = themeOverride
    ? BRAND_PALETTE[themeOverride].fgPrimary
    : "currentColor";
  const dotFill = themeOverride
    ? BRAND_PALETTE[themeOverride].tealAccent
    : "var(--teal-accent)";

  let svgElement: React.JSX.Element;

  switch (variant) {
    case "tile":
      svgElement = (
        <svg
          width={size}
          height={size}
          viewBox={MARK_GEOMETRY.viewBox}
          role={ariaLabel && !shouldShowWordmark ? "img" : undefined}
          aria-label={ariaLabel && !shouldShowWordmark ? ariaLabel : undefined}
          aria-hidden={ariaLabel && !shouldShowWordmark ? undefined : true}
          className={cn("shrink-0", !shouldShowWordmark && className)}
        >
          <rect
            width="48"
            height="48"
            rx={MARK_GEOMETRY.tileRx}
            fill={BRAND_PALETTE.dark.bgCanvas}
          />
          <path
            d={MARK_GEOMETRY.stemPath}
            fill={BRAND_PALETTE.dark.fgPrimary}
          />
          <path
            d={MARK_GEOMETRY.armPath}
            fill={BRAND_PALETTE.dark.fgPrimary}
          />
          <circle
            cx={MARK_GEOMETRY.dotCx}
            cy={MARK_GEOMETRY.dotCy}
            r={MARK_GEOMETRY.dotR}
            fill={BRAND_PALETTE.dark.tealAccent}
          />
        </svg>
      );
      break;
    case "lockup":
    case "mark-only":
      svgElement = (
        <svg
          width={size}
          height={size}
          viewBox={MARK_GEOMETRY.viewBox}
          role={ariaLabel && !shouldShowWordmark ? "img" : undefined}
          aria-label={ariaLabel && !shouldShowWordmark ? ariaLabel : undefined}
          aria-hidden={ariaLabel && !shouldShowWordmark ? undefined : true}
          className={cn("shrink-0", !shouldShowWordmark && className)}
        >
          <path d={MARK_GEOMETRY.stemPath} fill={kFill} />
          <path d={MARK_GEOMETRY.armPath} fill={kFill} />
          <circle
            cx={MARK_GEOMETRY.dotCx}
            cy={MARK_GEOMETRY.dotCy}
            r={MARK_GEOMETRY.dotR}
            fill={dotFill}
          />
        </svg>
      );
      break;
    default: {
      const _exhaustive: never = variant;
      return _exhaustive;
    }
  }

  if (!shouldShowWordmark) {
    return svgElement;
  }

  return (
    <span
      aria-label={ariaLabel}
      className={cn("inline-flex items-center gap-2", className)}
    >
      {svgElement}
      <span
        className={cn("font-sans font-bold tracking-tight", wordmarkClassName)}
      >
        Keelway
      </span>
    </span>
  );
}
