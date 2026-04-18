"use client";

/**
 * Shared primitives for the inspired-by surface.
 *
 * Two places render the same cards: the editable rail on
 * /me/inspired-by and the read-only lineage on /people/[id]. Rather
 * than duplicate the card, the weight indicator, the type label, or
 * the fetch logic, everything lives here. The wrappers are thin —
 * they add the input + delete gestures (rail) or the shared-thread
 * highlighting (person) on top.
 */

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────

export type Presence = { provider: string; url: string };

export type InspiredByNode = {
  id: string;
  name: string;
  description?: string;
  type: string;
  canonical_url?: string;
  image_url?: string | null;
  provider?: string;
  tagline?: string;
  claimable?: boolean;
  presences?: Presence[];
};

export type InspiredByItem = {
  edge_id: string;
  weight: number;
  node: InspiredByNode;
  created_at?: string | null;
  shared_with_viewer?: boolean;
};

export type InspiredByListResponse = {
  items: InspiredByItem[];
  count: number;
  shared_count: number | null;
};

export const TYPE_LABEL: Record<string, string> = {
  contributor: "Person",
  community: "Community / Place",
  "network-org": "Project",
  asset: "Work",
};

// ── Small visual primitives ───────────────────────────────────────────

export function WeightDots({ weight }: { weight: number }) {
  // 0.4 → 2 dots, 0.7 → 4 dots, 1.0 → 5 dots.
  const filled = Math.max(1, Math.min(5, Math.round(weight * 5)));
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`weight ${weight.toFixed(2)}`}
      title={`weight ${weight.toFixed(2)} — from discovery signals`}
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={`w-1 h-1 rounded-full ${
            i < filled ? "bg-[hsl(var(--primary))]" : "bg-border"
          }`}
        />
      ))}
    </span>
  );
}

export function Avatar({ item }: { item: InspiredByItem }) {
  if (item.node.image_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={item.node.image_url}
        alt=""
        className="w-12 h-12 rounded-lg object-cover shrink-0 border border-border/30"
      />
    );
  }
  return (
    <div className="w-12 h-12 rounded-lg bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] flex items-center justify-center font-medium shrink-0">
      {(item.node.name || "·").trim().charAt(0).toUpperCase()}
    </div>
  );
}

export function PresencesRow({ presences, limit = 6 }: { presences: Presence[]; limit?: number }) {
  if (!presences || presences.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {presences.slice(0, limit).map((p) => (
        <a
          key={p.url}
          href={p.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] uppercase tracking-[0.12em] rounded-full border border-border/40 px-2 py-0.5 text-muted-foreground hover:text-foreground hover:border-border"
        >
          {p.provider}
        </a>
      ))}
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────

export type CardProps = {
  item: InspiredByItem;
  /** Render a hover-reveal × affordance. */
  onRemove?: (edgeId: string) => void;
  /** Render the "· shared" badge and the teal gradient. */
  highlightShared?: boolean;
};

export function InspiredByCard({ item, onRemove, highlightShared }: CardProps) {
  const shared = highlightShared && !!item.shared_with_viewer;
  const presences = Array.isArray(item.node.presences) ? item.node.presences : [];
  const baseClass = shared
    ? "border-[hsl(var(--chart-2)/0.45)] bg-[linear-gradient(135deg,hsl(var(--card))_0%,hsl(var(--card))_55%,hsl(var(--chart-2)/0.10)_100%)]"
    : "border-border/30 bg-card/50 hover:bg-card/70";
  return (
    <li
      className={`group relative rounded-2xl border p-4 transition-colors ${baseClass}`}
    >
      {shared && (
        <span
          className="absolute top-2 right-2 text-[10px] uppercase tracking-[0.14em] font-semibold text-[hsl(var(--chart-2))]"
          aria-label="We share this thread"
        >
          · shared
        </span>
      )}
      <div className="flex gap-3 items-start">
        <Avatar item={item} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              {TYPE_LABEL[item.node.type] || item.node.type}
            </span>
            {item.node.provider && (
              <span className="text-[10px] text-muted-foreground/70">
                · {item.node.provider}
              </span>
            )}
            <span className="ml-auto">
              <WeightDots weight={item.weight} />
            </span>
          </div>
          <p className="font-medium text-foreground truncate">{item.node.name}</p>
          {item.node.tagline || item.node.description ? (
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
              {item.node.tagline || item.node.description}
            </p>
          ) : null}
          <PresencesRow presences={presences} />
          <div className="flex items-center gap-3 mt-2">
            {item.node.canonical_url && (
              <a
                href={item.node.canonical_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[hsl(var(--chart-2))] hover:opacity-80"
              >
                visit →
              </a>
            )}
            {item.node.claimable && (
              <span className="text-[10px] text-muted-foreground/70 italic">
                claimable
              </span>
            )}
          </div>
        </div>
        {onRemove && (
          <button
            type="button"
            onClick={() => onRemove(item.edge_id)}
            aria-label={`Remove ${item.node.name}`}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground text-sm w-6 h-6 rounded-full flex items-center justify-center"
          >
            ×
          </button>
        )}
      </div>
    </li>
  );
}

// ── Data hook ─────────────────────────────────────────────────────────

export function useInspiredByList(subjectId: string, viewerId?: string | null) {
  const apiBase = getApiBase();
  const [items, setItems] = useState<InspiredByItem[]>([]);
  const [sharedCount, setSharedCount] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!subjectId) return;
    const params = new URLSearchParams({ contributor_id: subjectId });
    if (viewerId && viewerId !== subjectId) params.set("viewer_id", viewerId);
    try {
      const r = await fetch(`${apiBase}/api/inspired-by?${params.toString()}`, {
        cache: "no-store",
      });
      if (!r.ok) return;
      const body: InspiredByListResponse = await r.json();
      setItems(Array.isArray(body.items) ? body.items : []);
      setSharedCount(typeof body.shared_count === "number" ? body.shared_count : null);
    } catch {
      /* transient */
    }
  }, [apiBase, subjectId, viewerId]);

  useEffect(() => {
    load().finally(() => setLoaded(true));
  }, [load]);

  return { items, setItems, sharedCount, loaded, reload: load, apiBase };
}
