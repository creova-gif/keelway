"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * DESIGN.md §6/§9 — fade-rise reveal, safe without JS and under reduced motion.
 * Hidden state is applied post-mount only when the element starts offscreen;
 * SSR output is fully visible. Stagger via delay={1|2} (≤3 items per §6).
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: 0 | 1 | 2;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<"visible" | "pending" | "in">("visible");

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.92 && rect.bottom > 0) return;
    setPhase("pending");
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setPhase("in");
          io.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const cls = [
    phase === "pending" ? "kw-reveal" : "",
    phase === "in" ? "kw-reveal kw-reveal-in" : "",
    delay ? `kw-reveal-delay-${delay}` : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div ref={ref} className={cls}>
      {children}
    </div>
  );
}
