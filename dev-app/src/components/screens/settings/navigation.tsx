import React from "react";
import type {
  DensityMode,
  LocaleCode,
  SettingsSubSection,
  ThemeMode,
} from "@/lib/types";

export const SETTINGS_SUB_SECTIONS: ReadonlyArray<{
  id: SettingsSubSection;
  label: string;
}> = [
  { id: "permissions", label: "Permissions & Manifests" },
  { id: "models", label: "Models & 4D Routing" },
  { id: "governance", label: "Governance & Keys" },
  { id: "network", label: "Network & Egress" },
  { id: "appearance", label: "Appearance & Density" },
  { id: "labs", label: "Labs" },
  { id: "billing", label: "Plan & Billing" },
  { id: "general", label: "General & Workspace" },
  { id: "keyboard", label: "Keyboard Shortcuts" },
];

export function isEditableKeyboardTarget(target: EventTarget | null): boolean {
  const candidates: Array<Element | null> = [
    target instanceof Element ? target : null,
    typeof document !== "undefined" ? document.activeElement : null,
  ];
  for (const el of candidates) {
    if (!el) continue;
    const tag = el.tagName.toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      return true;
    }
    if ((el instanceof HTMLElement && el.isContentEditable) || el.closest('[contenteditable="true"]')) {
      return true;
    }
  }
  return false;
}

export function applyThemeToDocument(mode: ThemeMode): void {
  if (typeof document === "undefined") return;
  let resolved: "dark" | "light" = "dark";
  if (mode === "light") {
    resolved = "light";
  } else if (
    mode === "system" &&
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
  ) {
    resolved = "light";
  }
  document.documentElement.dataset.theme = resolved;
}

export function applyDensityToDocument(density: DensityMode): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.density = density;
}

export function applyLocaleToDocument(locale: LocaleCode): void {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale;
  document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
}

export function applyReduceMotionToDocument(reduce: boolean): void {
  if (typeof document === "undefined") return;
  if (reduce) {
    document.documentElement.setAttribute("data-reduce-motion", "true");
  } else {
    document.documentElement.removeAttribute("data-reduce-motion");
  }
}

export interface SettingsSubNavProps {
  activeSubSection: SettingsSubSection;
  onSelectSubSection: (sub: SettingsSubSection) => void;
  driftedRulesCount?: number;
}

export function SettingsSubNav({
  activeSubSection,
  onSelectSubSection,
  driftedRulesCount = 0,
}: SettingsSubNavProps): React.JSX.Element {
  return (
    <nav aria-label="Settings sections" className="flex h-full flex-col overflow-y-auto py-5">
      <div className="px-5 pb-3.5 font-mono text-[11px] uppercase tracking-[0.14em] text-fg-dim">
        Settings
      </div>
      <div>
        {SETTINGS_SUB_SECTIONS.map((item) => {
          const isActive = item.id === activeSubSection;
          return (
            <button
              key={item.id}
              type="button"
              aria-current={isActive ? "page" : undefined}
              onClick={() => onSelectSubSection(item.id)}
              className={`flex w-full items-center justify-between gap-2 border-s-2 pe-5 ps-[18px] py-[7px] text-start text-[13px] transition-colors duration-fast ease-state ${
                isActive
                  ? "border-s-accent text-fg"
                  : "border-s-transparent text-fg-muted hover:bg-surface-elevated hover:text-fg"
              }`}
            >
              <span className="truncate">{item.label}</span>
              {item.id === "permissions" && driftedRulesCount > 0 ? (
                <span className="font-mono text-[11px] text-ochre">{driftedRulesCount}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
