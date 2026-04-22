"use client";

/**
 * InspiredByPreview — a glimpse of your lineage on /me.
 *
 * The full gesture lives on /me/inspired-by. This preview shows the
 * three most recent threads so the rail breathes from the entrance:
 * you see who made you every time you open your own page, and the
 * link takes you into the editable rail when you want to add more.
 *
 * Uses the same primitives as the rail and the person page. Thin by
 * design — this wrapper only adds the "top 3 + link" slice.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { readIdentity } from "@/lib/identity";
import {
  InspiredByCard,
  useInspiredByList,
} from "@/components/inspired-by/shared";

const PREVIEW_LIMIT = 3;

export function InspiredByPreview() {
  const [contributorId, setContributorId] = useState<string>("");

  useEffect(() => {
    const ident = readIdentity();
    if (ident.contributorId) setContributorId(ident.contributorId);
  }, []);

  const { items, loaded } = useInspiredByList(contributorId);
  if (!contributorId || !loaded) return null;

  const preview = items.slice(0, PREVIEW_LIMIT);

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
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {preview.map((item) => (
            <InspiredByCard key={item.edge_id} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}
