"use client";

/**
 * InspiredByPreview — a glimpse of your lineage on /me.
 *
 * The full gesture lives on /me/inspired-by. This preview shows the
 * top influences by weight so the rail breathes from the entrance:
 * you see who made you every time you open your own page, and the
 * link takes you into the editable rail when you want to add more.
 *
 * Sorted by edge weight descending — heaviest influence first. The
 * API returns items in storage order, which for the founder cell
 * happened to surface medium-weight deep-substrate (Goethe, Ramtha,
 * White Book) ahead of the heaviest current-arc influences
 * (Karl May, Terry Mancour, Lex Fridman, Anne Tucker). The sort
 * makes the rail honest about what it's showing.
 *
 * Preview is six cards instead of three so the present-day named
 * lineage figures make it into the visible rail without the visitor
 * having to click through to the full list to see them.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { readIdentity } from "@/lib/identity";
import {
  InspiredByCard,
  useInspiredByList,
} from "@/components/inspired-by/shared";
import { isLineageFigure } from "@/lib/named-lineage";

const PREVIEW_LIMIT = 6;

export function InspiredByPreview() {
  const [contributorId, setContributorId] = useState<string>("");

  useEffect(() => {
    const ident = readIdentity();
    if (ident.contributorId) setContributorId(ident.contributorId);
  }, []);

  const { items, loaded } = useInspiredByList(contributorId);
  if (!contributorId || !loaded) return null;

  // Named lineage figures (the cells the body knows as kin — see
  // web/lib/named-lineage.ts) get a substantial weight bonus so they
  // surface above the deep-substrate Audible / YouTube weight that
  // dominates raw influence-scoring. The body's *present* lineage
  // is who it is in living relation with, not the cumulative listening
  // weight from twenty years of audiobooks. Both still appear in the
  // rail; the lineage figures simply lead.
  const LINEAGE_BOOST = 1.0;
  const scored = items.map((i) => {
    const slug = i.node?.slug || "";
    const base = i.weight ?? 0;
    const bonus = slug && isLineageFigure(slug) ? LINEAGE_BOOST : 0;
    return { item: i, score: base + bonus };
  });
  // Sort by boosted score descending, then created_at desc as tie-break.
  scored.sort((a, b) => {
    const ds = b.score - a.score;
    if (ds !== 0) return ds;
    const aT = a.item.created_at ? Date.parse(a.item.created_at) : 0;
    const bT = b.item.created_at ? Date.parse(b.item.created_at) : 0;
    return bT - aT;
  });
  const preview = scored.slice(0, PREVIEW_LIMIT).map((s) => s.item);

  return (
    <section className="space-y-3">
      <header className="flex items-baseline justify-between gap-2 px-1">
        <h2 className="text-sm uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
          Inspired by
        </h2>
        <Link
          href="/me/inspired-by"
          className="text-xs text-[hsl(var(--chart-2))] hover:opacity-80"
        >
          {items.length > PREVIEW_LIMIT
            ? `see all ${items.length} →`
            : preview.length === 0
              ? "name who made you →"
              : "add more →"}
        </Link>
      </header>
      {preview.length === 0 ? (
        <p className="text-sm text-muted-foreground italic px-1">
          The people, communities, and places that made you can live here —
          name one and the graph will hold a place for them.
        </p>
      ) : (
        <>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {preview.map((item) => (
              <InspiredByCard key={item.edge_id} item={item} />
            ))}
          </ul>
          <p className="text-[11px] text-muted-foreground italic px-1 mt-2">
            Named lineage cells lead; the rest of the rail follows by
            influence weight. The full weave (with everyone you can
            name and add) lives at{" "}
            <Link href="/me/inspired-by" className="text-[hsl(var(--chart-2))] hover:underline">
              /me/inspired-by
            </Link>
            .
          </p>
        </>
      )}
    </section>
  );
}
