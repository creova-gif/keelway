import { useSyncExternalStore } from "react";

export type ToastTone = "ok" | "danger" | "accent" | "info";

export interface ToastItem {
  id: number;
  tone: ToastTone;
  label: string;
  detail?: string;
}

const MAX_VISIBLE = 3;
const AUTO_DISMISS_MS = 6_000;

const listeners = new Set<() => void>();
let items: ToastItem[] = [];
let nextId = 1;
const dismissTimers = new Map<number, ReturnType<typeof setTimeout>>();

function emit(): void {
  listeners.forEach((fn) => fn());
}

export function pushToast(tone: ToastTone, label: string, detail?: string): void {
  const id = nextId++;
  items = [...items, { id, tone, label, detail }].slice(-MAX_VISIBLE);
  dismissTimers.set(
    id,
    setTimeout(() => dismissToast(id), AUTO_DISMISS_MS),
  );
  emit();
}

export function dismissToast(id: number): void {
  const timer = dismissTimers.get(id);
  if (timer) {
    clearTimeout(timer);
    dismissTimers.delete(id);
  }
  if (!items.some((t) => t.id === id)) return;
  items = items.filter((t) => t.id !== id);
  emit();
}

export function subscribeToasts(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getToastsSnapshot(): ToastItem[] {
  return items;
}

export function useToasts(): ToastItem[] {
  return useSyncExternalStore(subscribeToasts, getToastsSnapshot);
}
