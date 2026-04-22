"use client";

/**
 * ResonatesWith — the threads from this presence into the vision.
 *
 * Each Living Collective concept (ceremony, breath, nervous-system,
 * attunement, instruments, nourishing…) has its own page and its own
 * spectrum. When a presence's signal overlaps a concept's — the words
 * describing what they make or hold echo in the concept's story — a
 * ``resonates-with`` edge is laid between them by
 * /api/presences/{id}/resonances/attune. This component reads those
 * edges and surfaces them as a small chip-row: each chip links to the
 * concept's vision page, carries the resonance score as a title
 * (hover), and quietly weighs the brightness by score.
 *
 * The visitor wandering Liquid Bloom's page discovers ceremony as a
 * concept the organism holds and can walk from here into the vision.
 * The visitor reading ceremony will eventually see the presences
 * carrying it — when that concept-side render arrives.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type Resonance = {
  concept_id: string;
  concept_name: string;
  /** Sacred frequency in Hz, when the concept carries one. 432Hz /
   *  528Hz / 639Hz / 741Hz / 852Hz / 963Hz are the solfeggio rungs;
   *  other concepts use other carriers. Drives chip colour below. */
  hz: number | null;
  score: number;
  shared_tokens: string[];
  method: string;
};

/**
 * Map a sacred-frequency Hz value to an HSL hue. The low-Hz end
 * (around 396/432) paints warm red/orange — grounding, liberation;
 * mid-range (528/639) paints green/teal — heart, relationship; the
 * upper solfeggio rungs (741/852/963) paint blue/indigo/violet —
 * awakening, order, unity. Concepts without an hz default to the
 * accent teal so the row still reads as a spectrum.
 */
function hzToHue(hz: number | null | undefined): number {
  if (typeof hz !== "number" || !Number.isFinite(hz)) return 175;
  // 396Hz → 0° (red), 963Hz → 280° (violet). Linear between.
  const clamped = Math.max(300, Math.min(1000, hz));
  return Math.round(((clamped - 396) / (963 - 396)) * 280);
}

export function ResonatesWith({ presenceId }: { presenceId: string }) {
  const [items, setItems] = useState<Resonance[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    (async () => {
      try {
        const r = await fetch(
          `${apiBase}/api/presences/${encodeURIComponent(presenceId)}/resonances`,
          { cache: "no-store" },
        );
        if (!r.ok) return;
        const body: { items: Resonance[] } = await r.json();
        setItems(Array.isArray(body.items) ? body.items : []);
      } catch {
        /* transient */
      } finally {
        setLoaded(true);
      }
    })();
  }, [presenceId]);

  if (!loaded || items.length === 0) return null;

  return (
    <section className="px-6 pt-8">
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Resonates with
      </p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((r) => {
          // Colour comes from the concept's own sacred frequency (hz).
          // Ceremony at 963Hz paints violet; Nervous System at 432Hz
          // paints warm red — the row reads as the actual frequency
          // spectrum this presence lives inside, not a uniform accent.
          // Brightness still scales with resonance score.
          const hue = hzToHue(r.hz);
          const strength = Math.min(0.95, 0.35 + r.score * 2.5);
          const hzLabel = r.hz ? `${r.hz} Hz` : null;
          return (
            <Link
              key={r.concept_id}
              href={`/vision/${encodeURIComponent(r.concept_id)}`}
              title={[
                hzLabel,
                r.shared_tokens.length ? r.shared_tokens.join(" · ") : null,
                `(${r.method})`,
              ]
                .filter(Boolean)
                .join("\n")}
              className="rounded-full border px-3 py-1 text-xs transition-colors hover:bg-white/10"
              style={{
                borderColor: `hsl(${hue} 55% 45% / ${strength * 0.55})`,
                color: `hsl(${hue} 70% 78% / ${strength})`,
                background: `hsl(${hue} 45% 22% / ${strength * 0.16})`,
              }}
            >
              {r.concept_name}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
