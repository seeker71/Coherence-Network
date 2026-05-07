"use client";

/**
 * WanderInto — closing doorway block on every presence page.
 *
 * Reaching the bottom of a presence page should always offer somewhere
 * to wander next, not a dead-end. Pulls a small mix of nearby presences
 * from the body's actual edges:
 *
 *   · 1 place (where they're rooted)
 *   · 1-2 events (gatherings they hosted or kindred to)
 *   · 1-2 kindred presences (concept overlap)
 *   · 1 inspired-by (lineage)
 *
 * Each link reads as an invitation, not a CTA. The visual register is
 * quieter than the sidebar — small chip-row at the bottom, no heavy
 * heading.
 *
 * Renders nothing if no edges surface — empty presences stay quiet.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type WanderItem = {
  id: string;
  name: string;
  kind: "place" | "gathering" | "kindred" | "lineage";
};

type EdgeRow = {
  from_id?: string;
  to_id?: string;
  type: string;
  to_node?: { id: string; name: string; type: string };
  from_node?: { id: string; name: string; type: string };
  properties?: { kind?: string } & Record<string, unknown>;
};

export function WanderInto({ presenceId }: { presenceId: string }) {
  const [items, setItems] = useState<WanderItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    let cancelled = false;
    (async () => {
      try {
        // Pull outgoing edges in one shot — we'll filter by type below.
        const r = await fetch(
          `${apiBase}/api/edges?from_id=${encodeURIComponent(presenceId)}&limit=80`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setLoaded(true);
          return;
        }
        const body: { items: EdgeRow[] } = await r.json();
        const edges = body.items || [];

        const out: WanderItem[] = [];
        const seen = new Set<string>();
        const add = (item: WanderItem) => {
          if (seen.has(item.id) || item.id === presenceId) return;
          seen.add(item.id);
          out.push(item);
        };

        // 1 place
        const place = edges.find(
          (e) => e.type === "at-place" && e.to_node?.type === "place",
        );
        if (place && place.to_node) {
          add({
            id: place.to_node.id,
            name: place.to_node.name,
            kind: "place",
          });
        }

        // up to 2 events (contributes-to → event)
        const events = edges
          .filter(
            (e) => e.type === "contributes-to" && e.to_node?.type === "event",
          )
          .slice(0, 2);
        for (const e of events) {
          if (e.to_node) {
            add({ id: e.to_node.id, name: e.to_node.name, kind: "gathering" });
          }
        }

        // 1 inspired-by
        const lineage = edges.find(
          (e) => e.type === "inspired-by" && e.to_node?.id,
        );
        if (lineage && lineage.to_node) {
          add({
            id: lineage.to_node.id,
            name: lineage.to_node.name,
            kind: "lineage",
          });
        }

        // Up to 2 kindred — fall back to /api/presences/{id}/resonances
        // pivot to other presences. Light fetch only when above didn't
        // fill 4+ items.
        if (out.length < 4) {
          const kindredR = await fetch(
            `${apiBase}/api/presences/${encodeURIComponent(presenceId)}/resonances?limit=4`,
            { cache: "no-store" },
          ).catch(() => null);
          if (kindredR && kindredR.ok) {
            const kbody: { items: { concept_id: string; concept_name: string }[] } =
              await kindredR.json();
            // Take up to 2 concepts and link the visitor toward the
            // concept page itself — wandering laterally through ideas.
            for (const c of (kbody.items || []).slice(0, 2)) {
              add({
                id: c.concept_id,
                name: c.concept_name,
                kind: "kindred",
              });
              if (out.length >= 5) break;
            }
          }
        }

        if (!cancelled) {
          setItems(out.slice(0, 5));
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
    <section className="border-t border-white/10 pt-8 mt-12">
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-4">
        Wander into
      </p>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => {
          const href =
            item.kind === "kindred"
              ? `/vision/${encodeURIComponent(item.id)}`
              : `/people/${encodeURIComponent(item.id)}`;
          const eyebrow = labelForKind(item.kind);
          return (
            <Link
              key={item.id}
              href={href}
              className="group inline-flex items-baseline gap-2 rounded-full border border-white/15 bg-white/[0.03] px-3 py-1.5 text-sm text-white/80 hover:bg-white/[0.08] hover:border-white/30 transition-colors"
            >
              <span className="text-[9px] uppercase tracking-[0.14em] text-white/40 group-hover:text-white/60">
                {eyebrow}
              </span>
              <span>{item.name}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function labelForKind(kind: WanderItem["kind"]): string {
  switch (kind) {
    case "place":
      return "place";
    case "gathering":
      return "gathering";
    case "kindred":
      return "concept";
    case "lineage":
      return "lineage";
  }
}
