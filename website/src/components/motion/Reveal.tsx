"use client";

import React, { useEffect, useRef, type ReactNode } from "react";

interface RevealProps {
  children: ReactNode;
  className?: string;
  delay?: 0 | 1 | 2;
}

/**
 * Intentional scroll reveal (DESIGN.md v1.1): fade-rise 200ms ease-out.
 * Hidden state is applied only after mount and only for offscreen
 * elements — without JS the content renders fully visible.
 */
export function Reveal({ children, className, delay = 0 }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      el.classList.add("kw-reveal", "is-visible");
      return;
    }
    el.classList.add("kw-reveal");
    if (delay > 0) el.classList.add(`kw-reveal-delay-${delay}`);
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.disconnect();
          }
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [delay]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
