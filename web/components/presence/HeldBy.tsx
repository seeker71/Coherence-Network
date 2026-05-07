"use client";

/**
 * HeldBy — when the page IS an event, surface every presence that
 * hosted, performed, or co-led it.
 *
 * The graph stores contributes-to edges from each host into the event,
 * so reading them as incoming edges into the event yields the hosts.
 * Each host link is a doorway off the event page back into the
 * lineage that brought the gathering into being.
 *
 * Visual style mirrors KindredPresences/RootedHere so the sidebar
 * reads as one continuous body. Empty events (no hosts in the graph
 * yet) render nothing — quiet honesty over scaffolded placeholders.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type Host = {
  id: string;
  name: string;
  role?: string;
};

type EdgeRow = {
  from_id: string;
  type: string;
  from_node?: { id: string; name: string; type: string };
  properties?: { kind?: string; role?: string } & Record<string, unknown>;
};

export function HeldBy({ eventId }: { eventId: string }) {
  const [items, setItems] = useState<Host[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${apiBase}/api/edges?to_id=${encodeURIComponent(eventId)}&type=contributes-to&limit=50`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setLoaded(true);
          return;
        }
        const body: { items: EdgeRow[] } = await r.json();
        const seen = new Set<string>();
        const hosts: Host[] = [];
        for (const e of body.items || []) {
          const id = e.from_id;
          // The host edge lives between a presence (contributor /
          // community / scene / network-org) and the event. Filter to
          // those types — concepts and assets sometimes carry the same
          // edge type but aren't hosts.
          const fromType = e.from_node?.type || "";
          if (
            !["contributor", "community", "scene", "network-org"].includes(
              fromType,
            )
          ) {
            continue;
          }
          if (!id || seen.has(id)) continue;
          seen.add(id);
          hosts.push({
            id,
            name: e.from_node?.name || id,
            role:
              (e.properties?.role as string) ||
              undefined,
          });
        }
        if (!cancelled) {
          setItems(hosts);
          setLoaded(true);
        }
      } catch {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  if (!loaded || items.length === 0) return null;

  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Held by
      </p>
      <ul className="space-y-1.5">
        {items.map((h) => (
          <li key={h.id}>
            <Link
              href={`/people/${encodeURIComponent(h.id)}`}
              className="flex items-baseline justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 hover:bg-white/[0.06] transition-colors"
            >
              <span className="text-sm text-white/85 truncate">{h.name}</span>
              {h.role && h.role !== "primary" && (
                <span className="text-[10px] uppercase tracking-[0.14em] text-white/45 shrink-0">
                  {h.role}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
