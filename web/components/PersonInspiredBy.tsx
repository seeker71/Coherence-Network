"use client";

/**
 * PersonInspiredBy — the subject's lineage, made visible to visitors.
 *
 * Renders on every /people/[id] page. It does two things at once:
 *
 *   · shows who this person is inspired-by (a gratitude rail,
 *     claimable identities, cross-platform presences)
 *   · lights up the threads you share with them — the cards you
 *     both carry get a small "we share this" badge.
 *
 * The viewer's contributor id is read from localStorage (soft
 * identity). The subject's id comes from the page. When they match,
 * we hide the kinship UI since it would just be everything.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { CONTRIBUTOR_KEY } from "@/lib/identity";

type Presence = { provider: string; url: string };

type Node = {
  id: string;
  name: string;
  description?: string;
  type: string;
  canonical_url?: string;
  image_url?: string | null;
  provider?: string;
  tagline?: string;
  presences?: Presence[];
};

type Item = {
  edge_id: string;
  weight: number;
  node: Node;
  shared_with_viewer?: boolean;
};

const TYPE_LABEL: Record<string, string> = {
  contributor: "Person",
  community: "Community / Place",
  "network-org": "Project",
  asset: "Work",
};

function WeightDots({ weight }: { weight: number }) {
  const filled = Math.max(1, Math.min(5, Math.round(weight * 5)));
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`weight ${weight.toFixed(2)}`}
      title={`weight ${weight.toFixed(2)}`}
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

export function PersonInspiredBy({ contributorId }: { contributorId: string }) {
  const apiBase = getApiBase();
  const [items, setItems] = useState<Item[]>([]);
  const [sharedCount, setSharedCount] = useState<number | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let viewer = "";
    try {
      viewer = localStorage.getItem(CONTRIBUTOR_KEY) || "";
    } catch {
      /* ignore */
    }
    const params = new URLSearchParams({ contributor_id: contributorId });
    if (viewer && viewer !== contributorId) params.set("viewer_id", viewer);
    fetch(`${apiBase}/api/inspired-by?${params.toString()}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => {
        if (!body) return;
        setItems(Array.isArray(body.items) ? body.items : []);
        setSharedCount(
          typeof body.shared_count === "number" ? body.shared_count : null,
        );
      })
      .catch(() => {
        /* transient */
      })
      .finally(() => setLoaded(true));
  }, [apiBase, contributorId]);

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
        {items.map((it) => {
          const shared = !!it.shared_with_viewer;
          const presences = Array.isArray(it.node.presences) ? it.node.presences : [];
          return (
            <li
              key={it.edge_id}
              className={`relative rounded-2xl border p-4 transition-colors ${
                shared
                  ? "border-[hsl(var(--chart-2)/0.45)] bg-[linear-gradient(135deg,hsl(var(--card))_0%,hsl(var(--card))_55%,hsl(var(--chart-2)/0.10)_100%)]"
                  : "border-border/30 bg-card/50"
              }`}
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
                {it.node.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={it.node.image_url}
                    alt=""
                    className="w-12 h-12 rounded-lg object-cover shrink-0 border border-border/30"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-lg bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] flex items-center justify-center font-medium shrink-0">
                    {(it.node.name || "·").trim().charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      {TYPE_LABEL[it.node.type] || it.node.type}
                    </span>
                    {it.node.provider && (
                      <span className="text-[10px] text-muted-foreground/70">
                        · {it.node.provider}
                      </span>
                    )}
                    <span className="ml-auto">
                      <WeightDots weight={it.weight} />
                    </span>
                  </div>
                  <p className="font-medium text-foreground truncate">
                    {it.node.name}
                  </p>
                  {it.node.tagline || it.node.description ? (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {it.node.tagline || it.node.description}
                    </p>
                  ) : null}
                  {presences.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {presences.slice(0, 5).map((p) => (
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
                  )}
                  {it.node.canonical_url && (
                    <a
                      href={it.node.canonical_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block mt-2 text-xs text-[hsl(var(--chart-2))] hover:opacity-80"
                    >
                      visit →
                    </a>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
