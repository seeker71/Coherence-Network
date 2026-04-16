"use client";

/**
 * Contributor frequency spectrum — shaped by attention, not assignment.
 *
 * Every new contributor begins from stillness and presence. As they
 * wander through the vision — reading concepts, sitting with stories,
 * following cross-references — their spectrum forms. What they gave
 * their attention to becomes visible as their unique frequency.
 *
 * The spectrum isn't a profile they fill out. It's a living map of
 * what resonated with them. It changes as they change.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

interface ConceptTouch {
  concept_id: string;
  concept_name: string;
  hz: number;
  views: number;
  last_visited: string;
}

interface SpectrumData {
  contributor_id: string;
  touches: ConceptTouch[];
  total_concepts_visited: number;
  dominant_frequency: number | null;
  spectrum_description: string;
}

interface FrequencySpectrumProps {
  contributorId: string;
}

// Hz → color only. Band names come from the concepts the contributor visited.
// No hardcoded labels — the concepts name themselves.
const HZ_COLORS: Record<number, string> = {
  174: "#ef4444",
  285: "#f97316",
  396: "#eab308",
  417: "#84cc16",
  432: "#22c55e",
  528: "#06b6d4",
  639: "#3b82f6",
  741: "#8b5cf6",
  852: "#a855f7",
  963: "#ec4899",
};

function hzColor(hz: number): string {
  // Find nearest mapped color or interpolate
  const keys = Object.keys(HZ_COLORS).map(Number).sort((a, b) => a - b);
  const exact = HZ_COLORS[hz];
  if (exact) return exact;
  // Nearest
  let closest = keys[0];
  for (const k of keys) {
    if (Math.abs(k - hz) < Math.abs(closest - hz)) closest = k;
  }
  return HZ_COLORS[closest] || "#9ca3af";
}

export function FrequencySpectrum({ contributorId }: FrequencySpectrumProps) {
  const [spectrum, setSpectrum] = useState<SpectrumData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(
          `${getApiBase()}/api/views/contributor/${encodeURIComponent(contributorId)}?limit=200`
        );
        if (!res.ok) return;
        const history = await res.json();

        // Count views per concept
        const conceptViews: Record<string, number> = {};
        const lastVisited: Record<string, string> = {};
        for (const h of history) {
          const id = h.asset_id;
          if (!id?.startsWith("lc-")) continue;
          conceptViews[id] = (conceptViews[id] || 0) + 1;
          if (!lastVisited[id] || h.created_at > lastVisited[id]) {
            lastVisited[id] = h.created_at;
          }
        }

        // Fetch concept details for Hz and name
        const touches: ConceptTouch[] = [];
        for (const [cid, views] of Object.entries(conceptViews)) {
          try {
            const cRes = await fetch(`${getApiBase()}/api/concepts/${cid}`);
            if (cRes.ok) {
              const concept = await cRes.json();
              touches.push({
                concept_id: cid,
                concept_name: concept.name || cid.replace("lc-", ""),
                hz: concept.sacred_frequency?.hz || 432,
                views,
                last_visited: lastVisited[cid] || "",
              });
            }
          } catch {
            // Skip concepts we can't fetch
          }
        }

        // Sort by views (most visited first)
        touches.sort((a, b) => b.views - a.views);

        // Find dominant frequency
        const hzCounts: Record<number, number> = {};
        for (const t of touches) {
          hzCounts[t.hz] = (hzCounts[t.hz] || 0) + t.views;
        }
        const dominant = Object.entries(hzCounts).sort((a, b) => Number(b[1]) - Number(a[1]))[0];

        // Generate description
        const desc = touches.length === 0
          ? "This contributor's spectrum is forming. Each concept they sit with adds to the frequency."
          : touches.length < 3
            ? "The first frequencies are arriving. The spectrum is beginning to take shape."
            : `A unique frequency pattern is forming across ${touches.length} concepts.`;

        if (!cancelled) {
          setSpectrum({
            contributor_id: contributorId,
            touches,
            total_concepts_visited: touches.length,
            dominant_frequency: dominant ? Number(dominant[0]) : null,
            spectrum_description: desc,
          });
        }
      } catch {
        // Spectrum data is supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [contributorId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-border/30 bg-card/30 p-6 animate-pulse">
        <div className="h-4 w-40 bg-muted/50 rounded mb-4" />
        <div className="h-32 bg-muted/30 rounded" />
      </div>
    );
  }

  if (!spectrum) return null;

  // Build frequency band histogram from actual concepts visited
  const bandTotals: Record<number, number> = {};
  const bandConcepts: Record<number, ConceptTouch[]> = {};
  for (const t of spectrum.touches) {
    bandTotals[t.hz] = (bandTotals[t.hz] || 0) + t.views;
    if (!bandConcepts[t.hz]) bandConcepts[t.hz] = [];
    bandConcepts[t.hz].push(t);
  }
  const maxBandViews = Math.max(...Object.values(bandTotals), 1);

  // Only show bands the contributor has actually touched
  const activeBands = Object.keys(bandTotals).map(Number).sort((a, b) => a - b);

  return (
    <section className="rounded-2xl border border-violet-500/20 bg-gradient-to-b from-violet-500/5 to-card/30 p-6 sm:p-8 space-y-5">
      <div>
        <p className="text-xs uppercase tracking-widest text-violet-400">
          Frequency Spectrum
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          {spectrum.spectrum_description}
        </p>
      </div>

      {/* Spectrum — only bands the contributor has touched */}
      <div className="space-y-3">
        {activeBands.map((hz) => {
          const total = bandTotals[hz] || 0;
          const width = Math.max(8, (total / maxBandViews) * 100);
          const concepts = bandConcepts[hz] || [];
          const color = hzColor(hz);
          // The band names itself from the concepts visited at this frequency
          const bandLabel = concepts.map((c) => c.concept_name).join(", ");

          return (
            <div key={hz}>
              <div className="flex items-center gap-3">
                <span className="w-16 text-right font-mono text-xs text-muted-foreground">
                  {hz} Hz
                </span>
                <div className="flex-1 h-5 rounded-full bg-muted/20 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${width}%`,
                      backgroundColor: color,
                      opacity: 0.7,
                    }}
                  />
                </div>
              </div>
              {/* Concepts at this frequency — the band names itself */}
              <div className="ml-[76px] mt-1 flex flex-wrap gap-1">
                {concepts.map((c) => (
                  <a
                    key={c.concept_id}
                    href={`/vision/${c.concept_id}`}
                    className="text-xs px-2 py-0.5 rounded-full border border-border/30 text-muted-foreground hover:text-foreground hover:border-border/60 transition-colors"
                  >
                    {c.concept_name}
                    {c.views > 1 && (
                      <span className="ml-1 text-muted-foreground/50">×{c.views}</span>
                    )}
                  </a>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Dominant frequency — named by the concepts at that Hz */}
      {spectrum.dominant_frequency && (
        <div className="pt-2 border-t border-border/20">
          <p className="text-xs text-muted-foreground">
            Strongest resonance:{" "}
            <span style={{ color: hzColor(spectrum.dominant_frequency) }}>
              {spectrum.dominant_frequency} Hz
            </span>
          </p>
          {bandConcepts[spectrum.dominant_frequency] && (
            <p className="text-xs text-muted-foreground/60 mt-0.5">
              {bandConcepts[spectrum.dominant_frequency].map((c) => c.concept_name).join(", ")}
            </p>
          )}
        </div>
      )}

      {/* Starting point reminder */}
      {spectrum.total_concepts_visited === 0 && (
        <div className="rounded-xl bg-muted/10 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            Every frequency spectrum begins from stillness.
          </p>
          <a
            href="/vision/lc-stillness"
            className="mt-2 inline-block text-xs text-violet-400 hover:text-violet-300 transition-colors"
          >
            Begin with stillness →
          </a>
        </div>
      )}
    </section>
  );
}
