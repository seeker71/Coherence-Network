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
import { PROVIDER_BRAND, brandFor } from "@/components/presence/brand";
import { MarkdownProse } from "@/components/markdown-prose";

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
  /** Human-readable slug (e.g. "robert-edward-grant") for routing to
   *  the internal /people/{slug} page. The API returns it on graph
   *  nodes; when present the card renders an "open page →" link
   *  alongside the canonical_url visit. */
  slug?: string | null;
  /** False on placeholder nodes minted by the resolver; undefined or
   *  true on living contributors. The card surfaces this as a soft
   *  "unclaimed" tag. */
  claimed?: boolean;
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
  community: "Community",
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
        className="w-14 h-14 rounded-lg object-cover shrink-0 border border-border/30"
      />
    );
  }
  return (
    <div className="w-14 h-14 rounded-lg bg-[hsl(var(--primary)/0.1)] text-[hsl(var(--primary))] flex items-center justify-center text-lg font-medium shrink-0">
      {(item.node.name || "·").trim().charAt(0).toUpperCase()}
    </div>
  );
}

export function PresencesRow({ presences, limit = 8 }: { presences: Presence[]; limit?: number }) {
  if (!presences || presences.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2">
      {presences.slice(0, limit).map((p) => {
        const tone = brandFor(p.provider);
        const hasIcon = !!PROVIDER_BRAND[p.provider]?.iconPath;
        if (hasIcon && tone.iconPath) {
          return (
            <a
              key={p.url}
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              title={`${tone.label} · ${p.url}`}
              aria-label={tone.label}
              className="inline-flex items-center justify-center w-7 h-7 rounded-full transition-transform hover:scale-110"
              style={{
                background: tone.gradient || tone.bg,
                color: tone.fg,
              }}
            >
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                aria-hidden="true"
                fill="currentColor"
              >
                <path d={tone.iconPath} />
              </svg>
            </a>
          );
        }
        return (
          <a
            key={p.url}
            href={p.url}
            target="_blank"
            rel="noopener noreferrer"
            title={p.url}
            className="text-[10px] uppercase tracking-[0.12em] rounded-full border border-border/40 px-2 py-0.5 text-muted-foreground hover:text-foreground hover:border-border"
          >
            {tone.label}
          </a>
        );
      })}
    </div>
  );
}

/**
 * Drop a leading `# Name` heading from a description when it just
 * duplicates the card's title. The card already shows the name above
 * the description; rendering it a second time as an `<h1>` adds noise.
 * Anything else (subheadings, italics, links, lists) is left intact for
 * MarkdownProse to render.
 */
export function dropRedundantTitle(raw: string, name?: string): string {
  let text = raw.replace(/\r\n?/g, "\n").trim();
  if (!name) return text;
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // Leading `# Name\n` or `## Name\n` etc. — drop the whole line.
  text = text.replace(
    new RegExp(`^#{1,6}\\s*${escaped}\\s*\\n+`, "i"),
    "",
  );
  // Same heading without a trailing newline (the whole description is
  // the heading plus a blob — odd but seen in the wild).
  text = text.replace(
    new RegExp(`^#{1,6}\\s*${escaped}\\s+`, "i"),
    "",
  );
  return text.trim();
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
  const rawDescription = item.node.tagline || item.node.description || "";
  const description = dropRedundantTitle(rawDescription, item.node.name);
  const baseClass = shared
    ? "border-[hsl(var(--chart-2)/0.45)] bg-[linear-gradient(135deg,hsl(var(--card))_0%,hsl(var(--card))_55%,hsl(var(--chart-2)/0.10)_100%)]"
    : "border-border/30 bg-card/50 hover:bg-card/70 hover:border-border/60";
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
      <div className="flex gap-3.5 items-start">
        <Avatar item={item} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
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
          {/* Name — wraps to a second line if needed (long titles like
              "Peaceful Heart, Warrior Spirit: The True Story…" used to
              get truncated to a single line). The body knows the full
              name; the card now shows it. */}
          <p className="text-base font-medium text-foreground leading-snug">
            {item.node.name}
          </p>
          {description ? (
            // The graph holds 300-450 chars of context for figures like
            // Goethe and Ramtha — sometimes with markdown (headings,
            // italics, links). MarkdownProse renders the small set we
            // support; the wrapper bounds height so the card stays
            // compact, with a soft fade hinting more on click-through.
            <div className="text-sm text-muted-foreground mt-1.5 leading-relaxed max-h-[6.5rem] overflow-hidden [mask-image:linear-gradient(to_bottom,black_70%,transparent_100%)] [&_p]:m-0 [&_p+p]:mt-1.5 [&_em]:italic [&_strong]:font-semibold [&_h1]:text-sm [&_h1]:font-semibold [&_h1]:text-foreground [&_h1]:mb-1 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-foreground [&_h2]:mb-1 [&_h3]:text-xs [&_h3]:font-medium [&_h3]:text-foreground [&_h3]:mb-1 [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:space-y-0.5 [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:text-[0.85em]">
              <MarkdownProse text={description} />
            </div>
          ) : null}
          <PresencesRow presences={presences} />
          <div className="flex items-center gap-3 mt-2.5 flex-wrap">
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
            {item.node.slug && (
              <a
                href={`/people/${item.node.slug}`}
                className="text-xs text-[hsl(var(--primary))] hover:opacity-80"
              >
                open page →
              </a>
            )}
            {item.node.claimed === false && (
              <span
                className="text-[10px] text-muted-foreground/70 italic ml-auto"
                title="Placeholder held open for the real person to claim"
              >
                unclaimed
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
