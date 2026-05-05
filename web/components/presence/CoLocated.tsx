"use client";

/**
 * CoLocated — others rooted in the same ground.
 *
 * For each place this presence is rooted in, fetch the other presences
 * also rooted there. Aggregate, dedupe (skip self), and surface the
 * top 8 — a visitor reading Liquid Bloom's page sees Random Rab, Tipper,
 * the Boulder ecstatic-dance scene appear in one block, and can wander
 * laterally into the local field.
 *
 * Heading carries the place name when there's only one place — most
 * common case. When there are several places, the heading goes generic:
 * "Others rooted nearby". Visual style mirrors KindredPresences so the
 * sidebar reads as one consistent voice.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type PlaceRow = {
  place_id: string;
  place_name: string;
};

type PresenceRow = {
  presence_id: string;
  presence_name?: string;
  presence_type?: string | null;
  role?: string | null;
};

type Aggregated = {
  id: string;
  name: string;
  shared_places: string[];
};

export function CoLocated({ presenceId }: { presenceId: string }) {
  const [items, setItems] = useState<Aggregated[]>([]);
  const [headingPlace, setHeadingPlace] = useState<string | null>(null);
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
        const places = Array.isArray(body.items) ? body.items : [];
        if (places.length === 0) {
          if (!cancelled) setLoaded(true);
          return;
        }

        // Bound the fan-out — most presences root in one place; cap at 4.
        const sample = places.slice(0, 4);
        const responses = await Promise.all(
          sample.map((p) =>
            fetch(
              `${apiBase}/api/places/${encodeURIComponent(p.place_id)}/presences`,
              { cache: "no-store" },
            )
              .then((res) => (res.ok ? res.json() : null))
              .catch(() => null),
          ),
        );

        const agg = new Map<string, Aggregated>();
        responses.forEach((resp, i) => {
          const others: PresenceRow[] = (resp && resp.items) || [];
          const placeName = sample[i]?.place_name || "";
          others.forEach((o) => {
            // Dedupe self — the place's presence list includes the
            // current presence; the page wants "others", not "you and
            // others".
            if (!o.presence_id || o.presence_id === presenceId) return;
            const existing = agg.get(o.presence_id);
            if (existing) {
              if (placeName && !existing.shared_places.includes(placeName)) {
                existing.shared_places.push(placeName);
              }
            } else {
              agg.set(o.presence_id, {
                id: o.presence_id,
                name: o.presence_name || o.presence_id,
                shared_places: placeName ? [placeName] : [],
              });
            }
          });
        });

        const ranked = Array.from(agg.values())
          .sort(
            (a, b) =>
              b.shared_places.length - a.shared_places.length ||
              a.name.localeCompare(b.name),
          )
          .slice(0, 8);

        if (!cancelled) {
          setItems(ranked);
          setHeadingPlace(sample.length === 1 ? sample[0].place_name : null);
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

  const heading = headingPlace
    ? `Others rooted in ${headingPlace}`
    : "Others rooted nearby";

  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        {heading}
      </p>
      <ul className="space-y-1.5">
        {items.map((k) => (
          <li key={k.id}>
            <Link
              href={`/people/${encodeURIComponent(k.id)}`}
              title={
                k.shared_places.length > 0
                  ? k.shared_places.join(" · ")
                  : undefined
              }
              className="flex items-baseline justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 hover:bg-white/[0.06] transition-colors"
            >
              <span className="text-sm text-white/85 truncate">{k.name}</span>
              {k.shared_places.length > 1 && (
                <span className="text-[10px] uppercase tracking-[0.14em] text-white/45 shrink-0">
                  {k.shared_places.length} shared
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
