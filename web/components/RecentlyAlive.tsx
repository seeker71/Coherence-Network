"use client";

/**
 * RecentlyAlive — where the body's attention has been this week.
 *
 * Fetches /api/views/trending and surfaces the concepts that have
 * gathered the most attention in the last seven days, filtered to
 * Living Collective concepts (lc-*). The witness-trace records every
 * read; this component returns that record to the visitor as a small
 * chip strip — they see they are not alone.
 *
 * Designed to fail quietly: if the API is unreachable or returns no
 * concepts, the component renders nothing. The page below remains
 * intact.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

interface TrendingItem {
  asset_id: string;
  view_count: number;
  unique_viewers?: number;
}

interface Props {
  days?: number;
  limit?: number;
}

export function RecentlyAlive({ days = 7, limit = 8 }: Props) {
  const [items, setItems] = useState<TrendingItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${getApiBase()}/api/views/trending?days=${days}&limit=${limit + 4}`,
          { cache: "no-store" },
        );
        if (!res.ok) return;
        const data = (await res.json()) as TrendingItem[];
        // Only Living Collective concepts — the lc-* prefix marks them.
        // Non-concept rows (page:*, asset:*) are dropped so the surface
        // stays focused on visions a visitor can step into.
        const concepts = (Array.isArray(data) ? data : [])
          .filter((d) => typeof d.asset_id === "string" && d.asset_id.startsWith("lc-"))
          .slice(0, limit);
        if (!cancelled) {
          setItems(concepts);
          setLoaded(true);
        }
      } catch {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [days, limit]);

  if (!loaded || items.length === 0) return null;

  // Format the asset_id back into a readable label — lc-deeper-pattern
  // becomes "deeper pattern". The visitor lands on the canonical
  // /vision/{id} page when they click.
  const labelize = (assetId: string) =>
    assetId.replace(/^lc-/, "").replace(/-/g, " ");

  return (
    <section className="max-w-3xl mx-auto px-6 pb-12" aria-label="Recently alive">
      <p className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-3 font-medium">
        Where attention has been this week
      </p>
      <div className="flex flex-wrap gap-2">
        {items.map((it) => (
          <Link
            key={it.asset_id}
            href={`/vision/${it.asset_id}`}
            className="group inline-flex items-baseline gap-2 rounded-full border border-stone-700/40 bg-stone-900/30 px-3 py-1.5 text-sm text-stone-300 hover:text-amber-200 hover:border-amber-500/40 hover:bg-amber-500/5 transition-colors"
          >
            <span>{labelize(it.asset_id)}</span>
            <span className="text-[11px] text-stone-500 group-hover:text-amber-400/70 font-mono transition-colors">
              {it.view_count}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
