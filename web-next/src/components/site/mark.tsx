export function Mark({ size = 20 }: { size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex items-center justify-center rounded-sm border border-border-strong bg-surface-raised font-[640] text-fg"
      style={{ width: size + 10, height: size + 10, fontSize: size * 0.8 }}
    >
      K<span className="text-accent">&#8242;</span>
    </span>
  );
}
