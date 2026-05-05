"use client";

/**
 * KindredPresences — the constellation around this person.
 *
 * For every concept this presence resonates with, we ask the graph
 * which other presences also carry it. We aggregate across all those
 * concepts: the presences that share the most concepts with this
 * person rise to the top — that's the felt-sense of who lives near
 * them in the field.
 *
 * Renders nothing if no overlap exists (better honest emptiness than
 * a placeholder list). When it does render, each chip links to the
 * other presence's page and shows the overlap count, so the visitor
 * can wander the constellation by following thickness.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type Resonance = {
  concept_id: string;
  concept_name: string;
};

// The /api/concepts/{id}/carried-by endpoint returns a flat shape:
//   { items: [{ presence_id, presence_name, presence_type, image_url,
//                score, shared_tokens, method }] }
// — not a nested presence object. An earlier draft of this component
// assumed nested {presence: {id, name}} which silently produced an
// empty kindred list for every page (the !o.presence?.id guard always
// hit). Match the real API shape.
type CarriedByItem = {
  presence_id: string;
  presence_name?: string;
  presence_type?: string;
  image_url?: string | null;
  score?: number;
};

type Kindred = {
  id: string;
  name: string;
  shared: number;
  shared_concepts: string[];
};

export function KindredPresences({ presenceId }: { presenceId: string }) {
  const [items, setItems] = useState<Kindred[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    let cancelled = false;
    (async () => {
      try {
        // Fetch this presence's concepts
        const r = await fetch(
          `${apiBase}/api/presences/${encodeURIComponent(presenceId)}/resonances`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setLoaded(true);
          return;
        }
        const body: { items: Resonance[] } = await r.json();
        const concepts = body.items || [];
        if (concepts.length === 0) {
          if (!cancelled) setLoaded(true);
          return;
        }

        // Fetch the other presences carrying each concept, aggregating
        // shared count by presence id. Bound the fan-out — if this
        // person has 30 concepts we'd hammer 30 endpoints; cap at 12.
        const sample = concepts.slice(0, 12);
        const responses = await Promise.all(
          sample.map((c) =>
            fetch(
              `${apiBase}/api/concepts/${encodeURIComponent(c.concept_id)}/carried-by`,
              { cache: "no-store" },
            )
              .then((res) => (res.ok ? res.json() : null))
              .catch(() => null),
          ),
        );

        const byPresence = new Map<string, Kindred>();
        responses.forEach((resp, i) => {
          const others: CarriedByItem[] = (resp && resp.items) || [];
          others.forEach((o) => {
            if (!o.presence_id || o.presence_id === presenceId) return;
            const existing = byPresence.get(o.presence_id);
            const conceptName = sample[i]?.concept_name || sample[i]?.concept_id || "";
            if (existing) {
              existing.shared += 1;
              if (
                conceptName &&
                !existing.shared_concepts.includes(conceptName)
              ) {
                existing.shared_concepts.push(conceptName);
              }
            } else {
              byPresence.set(o.presence_id, {
                id: o.presence_id,
                name: o.presence_name || o.presence_id,
                shared: 1,
                shared_concepts: conceptName ? [conceptName] : [],
              });
            }
          });
        });

        const ranked = Array.from(byPresence.values())
          .sort((a, b) => b.shared - a.shared || a.name.localeCompare(b.name))
          .slice(0, 8);
        if (!cancelled) {
          setItems(ranked);
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

  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Kindred — who lives near them in the field
      </p>
      <ul className="space-y-1.5">
        {items.map((k) => (
          <li key={k.id}>
            <Link
              href={`/people/${encodeURIComponent(k.id)}`}
              title={
                k.shared_concepts.length > 0
                  ? k.shared_concepts.join(" · ")
                  : undefined
              }
              className="flex items-baseline justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 hover:bg-white/[0.06] transition-colors"
            >
              <span className="text-sm text-white/85 truncate">{k.name}</span>
              <span className="text-[10px] uppercase tracking-[0.14em] text-white/45 shrink-0">
                {k.shared} shared
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
