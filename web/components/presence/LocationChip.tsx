"use client";

/**
 * LocationChip — where this presence is rooted.
 *
 * Reads /api/presences/{id}/places. Each place becomes a small chip
 * showing "📍 Place, Region/Country" so a visitor can see at a glance
 * that Liquid Bloom is rooted in Boulder, CO; Pyramids of Chi in Bali,
 * Indonesia. When the presence has no place, the block hides — better
 * honest emptiness than a placeholder.
 *
 * Cap at 3 to keep the sidebar quiet — most presences root in one or
 * two places. The chip pattern mirrors the inspired-by row so the
 * whole sidebar reads as one consistent sequence of small typed chips.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type PlaceRow = {
  place_id: string;
  place_name: string;
  region: string | null;
  country: string | null;
  role: string;
};

const MAX_VISIBLE = 3;

function locationLabel(p: PlaceRow): string {
  const tail = p.region || p.country || null;
  return tail ? `${p.place_name}, ${tail}` : p.place_name;
}

export function LocationChip({ presenceId }: { presenceId: string }) {
  const [items, setItems] = useState<PlaceRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${apiBase}/api/presences/${encodeURIComponent(presenceId)}/places`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setLoaded(true);
          return;
        }
        const body: { items: PlaceRow[] } = await r.json();
        if (!cancelled) {
          setItems(Array.isArray(body.items) ? body.items : []);
          setLoaded(true);
        }
      } catch {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [presenceId]);

  if (!loaded || items.length === 0) return null;

  const visible = items.slice(0, MAX_VISIBLE);
  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Rooted in
      </p>
      <div className="flex flex-wrap gap-1.5">
        {visible.map((p) => (
          <span
            key={p.place_id}
            title={p.role ? `role: ${p.role}` : undefined}
            className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80"
          >
            <span aria-hidden="true">📍</span>
            <span>{locationLabel(p)}</span>
          </span>
        ))}
      </div>
    </section>
  );
}
