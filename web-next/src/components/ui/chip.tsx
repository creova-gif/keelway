import { cn } from "@/lib/utils";

const CHIP_VARIANTS = {
  gate: "border-accent/40 bg-accent-subtle text-accent",
  sealed: "border-ok/40 text-ok",
  denied: "border-danger/50 text-danger",
  neutral: "border-border text-fg-muted",
} as const;

export type ChipVariant = keyof typeof CHIP_VARIANTS;

export function Chip({ variant, children }: { variant: ChipVariant; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-2 py-1 font-mono text-[10px] uppercase tracking-wide",
        CHIP_VARIANTS[variant],
      )}
    >
      {children}
    </span>
  );
}
