import type { Silence } from "./types";

/**
 * Pick the silences that overlap a given YYYY-MM-DD (UTC) window.
 *
 * Kept in its own plain-TS module (no "use client" directive) so it can
 * be called from both server components and client components without
 * tripping Next's client/server boundary.
 */
export function silencesOnDay(silences: Silence[], dateIso: string): Silence[] {
  const dayStart = new Date(`${dateIso}T00:00:00Z`).getTime();
  const dayEnd = dayStart + 24 * 60 * 60 * 1000;
  return silences.filter((s) => {
    const start = new Date(s.started_at).getTime();
    const end = s.ended_at ? new Date(s.ended_at).getTime() : Date.now();
    return start < dayEnd && end >= dayStart;
  });
}
