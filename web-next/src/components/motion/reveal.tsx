"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

const CLS =
  "transition-[opacity,transform] [transition-duration:var(--dur-base)] [transition-timing-function:var(--ease-settle)]";

/**
 * Fade-rise reveal, safe without JS and under reduced motion.
 * Hidden state is applied post-mount only when the element starts offscreen;
 * SSR output is fully visible. Stagger via delay={1|2}.
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
  const [shown, setShown] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.92 && rect.bottom > 0) return;
    setShown(false);
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`${CLS} ${shown ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"} ${className}`}
      style={delay ? { transitionDelay: `${delay * 80}ms` } : undefined}
    >
      {children}
    </div>
  );
}
