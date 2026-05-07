"use client";

/**
 * RootedHere — when the page IS a place, surface every presence rooted
 * in it.
 *
 * The body's place pages (Boulder, Aurora, Seattle, Ubud, Newport
 * Beach) sit in the graph carrying the connections of every presence
 * that's at-place there — but until now those edges flowed only one
 * way (a person's page showed their place; a place's page showed
 * nothing back). This block reads the inverse: presences rooted here.
 *
 * Visually mirrors KindredPresences and CoLocated so the sidebar reads
 * as one continuous body. Renders nothing when the place has no
 * presences yet — empty places stay quiet rather than scaffolded.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type PresenceRow = {
  presence_id: string;
  presence_name?: string;
  presence_type?: string | null;
  role?: string | null;
};

export function RootedHere({ placeId }: { placeId: string }) {
  const [items, setItems] = useState<PresenceRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${apiBase}/api/places/${encodeURIComponent(placeId)}/presences`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setLoaded(true);
          return;
        }
        const body: { items: PresenceRow[] } = await r.json();
        const presences = Array.isArray(body.items) ? body.items : [];
        if (!cancelled) {
          setItems(presences.slice(0, 24));
          setLoaded(true);
        }
      } catch {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [placeId]);

  if (!loaded || items.length === 0) return null;

  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Rooted here
      </p>
      <ul className="space-y-1.5">
        {items.map((p) => (
          <li key={p.presence_id}>
            <Link
              href={`/people/${encodeURIComponent(p.presence_id)}`}
              className="flex items-baseline justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 hover:bg-white/[0.06] transition-colors"
            >
              <span className="text-sm text-white/85 truncate">
                {p.presence_name || p.presence_id}
              </span>
              {p.role && (
                <span className="text-[10px] uppercase tracking-[0.14em] text-white/45 shrink-0">
                  {p.role}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
