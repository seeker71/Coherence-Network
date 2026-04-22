"use client";

/**
 * PersonInspiredBy — the subject's lineage, made visible to visitors.
 *
 * Renders on /people/[id]. Read-only: shows who this person is
 * inspired-by, and lights up any cards the viewer also carries
 * (``shared_with_viewer``). The viewer's contributor id comes from
 * localStorage. When viewer and subject match, kinship highlighting
 * is suppressed (it would be everything).
 *
 * The card itself, types, weight dots, and fetch logic live in
 * ``components/inspired-by/shared``. This file only adds the header
 * copy, the shared-threads hint, and the viewer-id read.
 */

import { useEffect, useState } from "react";
import { CONTRIBUTOR_KEY } from "@/lib/identity";
import {
  InspiredByCard,
  useInspiredByList,
} from "@/components/inspired-by/shared";

export function PersonInspiredBy({ contributorId }: { contributorId: string }) {
  const [viewerId, setViewerId] = useState<string | null>(null);

  useEffect(() => {
    try {
      const v = localStorage.getItem(CONTRIBUTOR_KEY) || "";
      setViewerId(v || null);
    } catch {
      setViewerId(null);
    }
  }, []);

  const { items, sharedCount, loaded } = useInspiredByList(contributorId, viewerId);

  if (loaded && items.length === 0) return null;

  return (
    <section className="space-y-3">
      <header className="flex items-baseline gap-2 px-1">
        <h2 className="text-sm uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
          Inspired by
        </h2>
        {sharedCount != null && sharedCount > 0 && (
          <span
            className="text-[11px] text-[hsl(var(--chart-2))]"
            title="Threads you both carry"
          >
            · {sharedCount} thread{sharedCount === 1 ? "" : "s"} we share
          </span>
        )}
      </header>

      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((item) => (
          <InspiredByCard key={item.edge_id} item={item} highlightShared />
        ))}
      </ul>
    </section>
  );
}
