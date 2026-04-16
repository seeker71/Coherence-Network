"use client";

/**
 * World signals — live events from reality resonating with this concept.
 *
 * The world is already contributing to the vision by existing.
 * This component shows recent news events that have been sensed
 * through the new earth lens and linked to this concept.
 *
 * Each signal carries:
 * - A reflection written in living frequency
 * - The frequency quality (joyful, curious, tender, fierce...)
 * - A link to the source
 * - When it was sensed
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

interface WorldSignal {
  id: string;
  summary: string;
  content: string;
  source: string;
  observed_at: string;
  metadata: {
    lens?: string;
    frequency_quality?: string;
    source_url?: string;
  };
}

interface WorldSignalsProps {
  conceptId: string;
}

const QUALITY_COLORS: Record<string, string> = {
  joyful: "border-amber-500/20 bg-amber-500/5",
  curious: "border-green-500/20 bg-green-500/5",
  tender: "border-rose-500/20 bg-rose-500/5",
  fierce: "border-red-500/20 bg-red-500/5",
  playful: "border-violet-500/20 bg-violet-500/5",
  quiet: "border-stone-500/20 bg-stone-500/5",
  warm: "border-orange-500/20 bg-orange-500/5",
  alive: "border-emerald-500/20 bg-emerald-500/5",
};

export function WorldSignals({ conceptId }: WorldSignalsProps) {
  const [signals, setSignals] = useState<WorldSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        // Fetch sensings linked to this concept
        const res = await fetch(
          `${getApiBase()}/api/sensings?kind=skin&limit=10`
        );
        if (!res.ok) return;
        const data = await res.json();
        const items: WorldSignal[] = (data.items || []).filter(
          (s: any) =>
            s.metadata?.lens === "new_earth" &&
            (s.related_to || []).includes(conceptId)
        );
        if (!cancelled) setSignals(items);
      } catch {
        // World signals are supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [conceptId]);

  if (loading) return null;
  if (signals.length === 0) return null;

  return (
    <section className="pt-8 space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">
        The world is already living this
      </h2>
      <div className="space-y-3">
        {signals.map((signal) => {
          const quality = signal.metadata?.frequency_quality || "curious";
          const colorClass = QUALITY_COLORS[quality] || QUALITY_COLORS.curious;
          const sourceUrl = signal.metadata?.source_url;
          const timeAgo = formatTimeAgo(signal.observed_at);

          return (
            <div
              key={signal.id}
              className={`rounded-xl border p-4 ${colorClass}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-stone-200">
                    {signal.summary}
                  </p>
                  <p className="mt-2 text-sm text-stone-400 leading-relaxed">
                    {signal.content}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-3 text-xs text-stone-500">
                <span className="capitalize">{quality}</span>
                <span>·</span>
                <span>{timeAgo}</span>
                {sourceUrl && (
                  <>
                    <span>·</span>
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-stone-400 hover:text-amber-400/80 transition-colors"
                    >
                      Source →
                    </a>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function formatTimeAgo(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
