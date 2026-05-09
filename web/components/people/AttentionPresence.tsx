"use client";

/**
 * AttentionPresence — surfaces witness-trace attention for any asset.
 *
 * Sibling to ReaderPresence on /vision/{conceptId}, but generic across
 * any asset_id the witness-trace records (people, works, gatherings,
 * communities). When the visitor lands on /people/quark-virtual-dom,
 * this returns "47 people have sat with this · 12 contributors" — the
 * body's attention reflected back, instead of a silent leaf.
 *
 * Fails quietly: if the API returns 0 or errors, the component renders
 * nothing and the page below stays intact.
 */

import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";

interface Props {
  assetId: string;
  // Lookback window in days. Default 365 so a slow-burning page still
  // reflects the attention that has touched it across the year.
  days?: number;
}

export function AttentionPresence({ assetId, days = 365 }: Props) {
  const [views, setViews] = useState<number | null>(null);
  const [contributors, setContributors] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${getApiBase()}/api/views/stats/${encodeURIComponent(assetId)}?days=${days}`,
          { cache: "no-store" },
        );
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          setViews(data.total_views ?? 0);
          setContributors(data.unique_contributors ?? 0);
        }
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [assetId, days]);

  if (views === null || views === 0) return null;

  const text =
    contributors > 0
      ? `${views} ${views === 1 ? "person has" : "people have"} sat with this · ${contributors} ${contributors === 1 ? "contributor" : "contributors"}`
      : `${views} ${views === 1 ? "person has" : "people have"} sat with this`;

  return <p className="text-xs text-muted-foreground/70">{text}</p>;
}
