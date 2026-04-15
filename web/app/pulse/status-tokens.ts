// Tailwind class tokens for breath-status visuals. One file so the
// colour language is defined once and never drifts between components.

import type { BreathStatus } from "./types";

export const STATUS_LABEL: Record<BreathStatus, string> = {
  breathing: "Breathing",
  strained: "Strained",
  silent: "Silent",
  unknown: "Unknown",
};

export const STATUS_VERB: Record<BreathStatus, string> = {
  breathing: "is breathing",
  strained: "is strained",
  silent: "is silent",
  unknown: "is unheard",
};

export const STATUS_DOT: Record<BreathStatus, string> = {
  breathing: "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]",
  strained: "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]",
  silent: "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]",
  unknown: "bg-gray-500",
};

export const STATUS_TEXT: Record<BreathStatus, string> = {
  breathing: "text-emerald-400",
  strained: "text-amber-400",
  silent: "text-rose-400",
  unknown: "text-gray-400",
};

export const STATUS_BG: Record<BreathStatus, string> = {
  breathing: "bg-emerald-500",
  strained: "bg-amber-500",
  silent: "bg-rose-500",
  unknown: "bg-gray-500/50",
};

export const STATUS_BAR: Record<BreathStatus, string> = {
  breathing: "bg-emerald-500/80",
  strained: "bg-amber-500/80",
  silent: "bg-rose-500/80",
  unknown: "bg-muted-foreground/20",
};

export const STATUS_BANNER: Record<
  BreathStatus,
  { border: string; bg: string; text: string; glow: string }
> = {
  breathing: {
    border: "border-emerald-500/30",
    bg: "from-emerald-500/10 to-emerald-500/5",
    text: "text-emerald-400",
    glow: "shadow-emerald-500/20",
  },
  strained: {
    border: "border-amber-500/30",
    bg: "from-amber-500/10 to-amber-500/5",
    text: "text-amber-400",
    glow: "shadow-amber-500/20",
  },
  silent: {
    border: "border-rose-500/30",
    bg: "from-rose-500/10 to-rose-500/5",
    text: "text-rose-400",
    glow: "shadow-rose-500/20",
  },
  unknown: {
    border: "border-border/30",
    bg: "from-muted/20 to-muted/5",
    text: "text-muted-foreground",
    glow: "shadow-none",
  },
};

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  if (h < 24) return rm > 0 ? `${h}h ${rm}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return rh > 0 ? `${d}d ${rh}h` : `${d}d`;
}
