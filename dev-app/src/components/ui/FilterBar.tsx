import React, { useId } from "react";

/**
 * Filter strip: container row for the search field, filter selects, chip
 * groups, and result counts that recur above list/table views.
 */
export function FilterBar({ className, ...rest }: React.HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={["flex flex-wrap items-end gap-2.5", className].filter(Boolean).join(" ")}
      {...rest}
    />
  );
}

const SEARCH_INPUT_CLASSES =
  "min-h-ctrl-sm w-full rounded-sm border border-border-control bg-surface px-2.5 py-1 text-xs text-fg placeholder:text-fg-dim";

export interface SearchFieldProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "id" | "type"> {
  /** Accessible label content; visually hidden by default */
  label: React.ReactNode;
  /** Set a class (e.g. `block mb-1 text-[11px] font-medium text-fg-muted`) to show the label */
  labelClassName?: string;
  /** Classes for the wrapping <label> (default `block`) */
  className?: string;
  /** Extra classes merged onto the input (avoid conflicting width/radius tokens) */
  inputClassName?: string;
  id?: string;
}

/**
 * Search input with associated label (`htmlFor` + `useId`). The label is
 * `sr-only` by default; pass `labelClassName` for a visible caption.
 */
export function SearchField({
  label,
  labelClassName = "sr-only",
  className,
  inputClassName,
  id,
  ...rest
}: SearchFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <label htmlFor={inputId} className={["block", className].filter(Boolean).join(" ")}>
      <span className={labelClassName}>{label}</span>
      <input
        id={inputId}
        type="search"
        className={[SEARCH_INPUT_CLASSES, inputClassName].filter(Boolean).join(" ")}
        {...rest}
      />
    </label>
  );
}

export interface FilterChipOption<T extends string> {
  value: T;
  label: React.ReactNode;
}

export interface FilterChipsProps<T extends string> {
  /** `aria-label` for the `role="group"` wrapper */
  label: string;
  options: ReadonlyArray<FilterChipOption<T>>;
  value: T;
  onChange: (next: T) => void;
  className?: string;
}

/**
 * Single-select toggle-chip group (`role="group"` + `aria-pressed` buttons).
 * Accent chrome on the active chip, muted surface on the rest.
 */
export function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: FilterChipsProps<T>) {
  return (
    <div
      role="group"
      aria-label={label}
      className={["flex flex-wrap items-center gap-1.5", className].filter(Boolean).join(" ")}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          aria-pressed={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-sm border px-2.5 py-1 text-xs font-medium ${
            value === opt.value
              ? "border-accent/50 bg-accent-subtle text-accent"
              : "border-border bg-surface text-fg-muted hover:text-fg"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export interface FilterSelectOption<T extends string> {
  value: T;
  label: React.ReactNode;
}

export interface FilterSelectProps<T extends string> {
  label: string;
  value: T;
  options: ReadonlyArray<FilterSelectOption<T>>;
  onChange: (next: T) => void;
  className?: string;
}

/** Labeled enum `<select>` — the dropdown counterpart to FilterChips. */
export function FilterSelect<T extends string>({
  label,
  value,
  options,
  onChange,
  className,
}: FilterSelectProps<T>) {
  const id = useId();
  return (
    <div className={["flex flex-col gap-1", className].filter(Boolean).join(" ")}>
      <label htmlFor={id} className="text-[11px] font-medium text-fg-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => {
          const matched = options.find((opt) => opt.value === e.target.value);
          if (matched) onChange(matched.value);
        }}
        className="min-h-ctrl-sm rounded-xs border border-border-control bg-surface px-2 py-1 text-xs text-fg"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
