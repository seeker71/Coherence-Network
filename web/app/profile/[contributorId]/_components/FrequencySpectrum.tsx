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

// Hz → frequency band name and color
const FREQUENCY_BANDS: Record<number, { name: string; color: string; quality: string }> = {
  174: { name: "Root", color: "#ef4444", quality: "Grounding, nourishment, physical tending" },
  285: { name: "Healing", color: "#f97316", quality: "Composting, health, cellular renewal" },
  396: { name: "Liberation", color: "#eab308", quality: "Play, harmonizing, rebalancing" },
  417: { name: "Change", color: "#84cc16", quality: "Energy, phase transitions, edges" },
  432: { name: "Presence", color: "#22c55e", quality: "Pulse, attunement, rhythm, stillness" },
  528: { name: "Transformation", color: "#06b6d4", quality: "Vitality, resonance, offering" },
  639: { name: "Connection", color: "#3b82f6", quality: "Network, intimacy, instruments" },
  741: { name: "Expression", color: "#8b5cf6", quality: "Sensing, expressing, freedom" },
  852: { name: "Intuition", color: "#a855f7", quality: "Elders, transmission, discovery" },
  963: { name: "Unity", color: "#ec4899", quality: "Ceremony, beauty, the whole field" },
};

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

  // Build frequency band histogram
  const bandTotals: Record<number, number> = {};
  for (const t of spectrum.touches) {
    bandTotals[t.hz] = (bandTotals[t.hz] || 0) + t.views;
  }
  const maxBandViews = Math.max(...Object.values(bandTotals), 1);

  // All possible bands
  const allBands = Object.keys(FREQUENCY_BANDS).map(Number).sort((a, b) => a - b);

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

      {/* Spectrum visualization — vertical bars per Hz band */}
      <div className="space-y-2">
        {allBands.map((hz) => {
          const band = FREQUENCY_BANDS[hz];
          const total = bandTotals[hz] || 0;
          const width = total > 0 ? Math.max(4, (total / maxBandViews) * 100) : 0;
          const conceptsAtHz = spectrum.touches.filter((t) => t.hz === hz);

          return (
            <div key={hz} className="group">
              <div className="flex items-center gap-3">
                <span className="w-16 text-right font-mono text-xs text-muted-foreground">
                  {hz} Hz
                </span>
                <div className="flex-1 h-5 rounded-full bg-muted/20 overflow-hidden">
                  {width > 0 && (
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${width}%`,
                        backgroundColor: band.color,
                        opacity: 0.7,
                      }}
                    />
                  )}
                </div>
                <span className="w-20 text-xs text-muted-foreground">
                  {band.name}
                </span>
              </div>

              {/* Expanded concept list on hover/focus */}
              {conceptsAtHz.length > 0 && (
                <div className="ml-[76px] mt-1 hidden group-hover:block">
                  <div className="flex flex-wrap gap-1">
                    {conceptsAtHz.map((c) => (
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
              )}
            </div>
          );
        })}
      </div>

      {/* Dominant frequency */}
      {spectrum.dominant_frequency && (
        <div className="pt-2 border-t border-border/20">
          <p className="text-xs text-muted-foreground">
            Dominant frequency:{" "}
            <span style={{ color: FREQUENCY_BANDS[spectrum.dominant_frequency]?.color }}>
              {spectrum.dominant_frequency} Hz — {FREQUENCY_BANDS[spectrum.dominant_frequency]?.name}
            </span>
          </p>
          <p className="text-xs text-muted-foreground/60 mt-0.5">
            {FREQUENCY_BANDS[spectrum.dominant_frequency]?.quality}
          </p>
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
