export function Mark({ size = 22 }: { size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex items-center justify-center rounded-md border border-[var(--rule-strong)] bg-[var(--fog-4)] font-bold text-[var(--ink)]"
      style={{ width: size + 10, height: size + 10, fontSize: size * 0.8 }}
    >
      K<span className="text-[var(--accent)]">&#8242;</span>
    </span>
  );
}
