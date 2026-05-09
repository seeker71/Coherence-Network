"use client";

/**
 * InfluenceLineageStrip — surfaces cross-layer connections at the top
 * of /people/{slug} pages. The graph holds rich edges (inspired-by,
 * contributes-to, resonates-with) but BodyOfEvidence renders them
 * deep in the page. A new visitor arriving at quark-virtual-dom
 * doesn't immediately see "this was inspired by BML, and inspired
 * Living-Resonance-Codex." This strip puts that one click away.
 *
 * Three chip groups when present:
 *   · "Inspired by" — works/concepts/people that shaped this one
 *   · "Inspires" — works that grew out of this one
 *   · "Contributed by" — the cells whose hands shaped it
 *
 * Quiet on a fresh node: returns null when nothing is wired yet.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

interface Edge {
  type: string;
  from_id: string;
  to_id: string;
  strength?: number;
  from_node: { id: string; type: string; name: string; slug?: string | null };
  to_node: { id: string; type: string; name: string; slug?: string | null };
}

interface Chip {
  slug: string;
  name: string;
  type: string;
  strength?: number;
}

function nodeHref(type: string, slug: string): string {
  if (type === "concept") return `/vision/${slug}`;
  return `/people/${slug}`;
}

// Use the to_node/from_node side that ISN'T the current page.
function otherSide(e: Edge, selfSlug: string, selfId: string): Chip | null {
  const fromIsSelf = e.from_node.slug === selfSlug || e.from_id === selfId || e.from_id === `asset:${selfSlug}` || e.from_id === `contributor:${selfSlug}`;
  const other = fromIsSelf ? e.to_node : e.from_node;
  if (!other.slug || !other.name) return null;
  return { slug: other.slug, name: other.name, type: other.type, strength: e.strength };
}

export function InfluenceLineageStrip({ slug }: { slug?: string }) {
  const [edges, setEdges] = useState<Edge[] | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${getApiBase()}/api/graph/nodes/${encodeURIComponent(slug)}/edges`,
          { cache: "no-store" },
        );
        if (!r.ok) return;
        const data = await r.json();
        const items = Array.isArray(data) ? data : data.items || [];
        if (!cancelled) setEdges(items);
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (!slug || !edges || edges.length === 0) return null;

  // Self-id resolution: each edge endpoint may carry the bare slug
  // ("quark-virtual-dom") or a prefixed graph id ("asset:quark-virtual-dom").
  // Pick the prefixed self-id from any edge that mentions the slug.
  const selfId =
    edges.find((e) => e.from_node.slug === slug)?.from_id ||
    edges.find((e) => e.to_node.slug === slug)?.to_id ||
    slug;

  const inspiredBy: Chip[] = [];
  const inspires: Chip[] = [];
  const contributors: Chip[] = [];
  for (const e of edges) {
    if (e.type === "inspired-by") {
      const fromIsSelf =
        e.from_node.slug === slug ||
        e.from_id === selfId ||
        e.from_id === `asset:${slug}`;
      const chip = otherSide(e, slug, selfId);
      if (!chip) continue;
      // "X inspired-by Y" means Y inspired X. So if this page is X,
      // Y is who inspired us; if this page is Y, X is who we inspired.
      if (fromIsSelf) inspires.push(chip);
      else inspiredBy.push(chip);
    } else if (e.type === "contributes-to") {
      // contributor → asset; so if this page is the asset, the from
      // side is the contributor. If this page is a contributor (Urs),
      // the to side is the work they shaped.
      const fromIsSelf =
        e.from_node.slug === slug ||
        e.from_id === selfId ||
        e.from_id === `contributor:${slug}`;
      const chip = otherSide(e, slug, selfId);
      if (!chip) continue;
      if (fromIsSelf) inspires.push(chip);
      else contributors.push(chip);
    }
  }

  // Dedupe by slug, sort by strength descending
  const dedupe = (chips: Chip[]) => {
    const seen = new Set<string>();
    return chips
      .filter((c) => {
        if (seen.has(c.slug)) return false;
        seen.add(c.slug);
        return true;
      })
      .sort((a, b) => (b.strength ?? 0) - (a.strength ?? 0));
  };

  const ib = dedupe(inspiredBy).slice(0, 5);
  const is = dedupe(inspires).slice(0, 5);
  const co = dedupe(contributors).slice(0, 5);

  if (ib.length + is.length + co.length === 0) return null;

  return (
    <div className="mb-6 space-y-2 rounded-xl border border-border/30 bg-card/20 px-4 py-3">
      {ib.length > 0 && (
        <ChipRow label="Inspired by" chips={ib} hue="hsl(220 60% 65%)" />
      )}
      {is.length > 0 && (
        <ChipRow label="Inspires" chips={is} hue="hsl(38 80% 60%)" />
      )}
      {co.length > 0 && (
        <ChipRow label="Contributed by" chips={co} hue="hsl(280 60% 65%)" />
      )}
    </div>
  );
}

function ChipRow({ label, chips, hue }: { label: string; chips: Chip[]; hue: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <span
        className="text-[10px] uppercase tracking-[0.16em] font-medium shrink-0"
        style={{ color: hue }}
      >
        {label}
      </span>
      {chips.map((c) => (
        <Link
          key={c.slug}
          href={nodeHref(c.type, c.slug)}
          className="text-xs rounded-full border px-2.5 py-1 text-foreground/85 hover:text-foreground transition-colors"
          style={{
            borderColor: hue.replace(")", " / 0.35)"),
            backgroundColor: hue.replace(")", " / 0.05)"),
          }}
          title={c.name}
        >
          {c.name.length > 50 ? `${c.name.slice(0, 50)}…` : c.name}
        </Link>
      ))}
    </div>
  );
}
