import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { resolveRequestLocale } from "@/lib/request-locale";
import {
  formatPresenceCopy,
  getPeopleDirectorySections,
  getPeopleFilterRules,
  getPeoplePageCopy,
} from "../presence-walk/data";
import { PeopleSearch } from "./_components/PeopleSearch";
import { lineageFigureRank } from "@/lib/named-lineage";

/**
 * /people — the directory of every presence the network holds.
 *
 * Each node the resolver has ever minted is reachable from here:
 * humans with their cross-platform constellations, sanctuaries,
 * festivals, events, co-presented gatherings, practices, and
 * programs. Grouped by type so the eye can scan; the search field
 * at the top calls /api/resolve/query to surface the weave that
 * resonates with any free-text query.
 */

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const copy = getPeoplePageCopy(await resolveRequestLocale());
  return {
    title: copy.metadataTitle,
    description: copy.metadataDescription,
  };
}

type PresenceNode = {
  id: string;
  name: string;
  type: string;
  description?: string;
  canonical_url?: string;
  image_url?: string | null;
  provider?: string;
  contributor_type?: string;
  asset_type?: string;
  slug?: string | null;
};

/**
 * Canonical href for a presence — slug when the graph node carries
 * one, falling back to the graph id encoded in the path. The mapping
 * lives in the graph as data, never in this codebase.
 */
function presenceHref(n: PresenceNode): string {
  if (n.slug && typeof n.slug === "string") return `/people/${n.slug}`;
  return `/people/${encodeURIComponent(n.id)}`;
}

// Walk every page of /api/graph/nodes for this type so the directory
// reflects the body's actual count, not whatever fits in one slice. The
// graph endpoint caps `limit` at 500; most types have well under that,
// but `contributor` is already past 200 and growing — without the walk,
// /people silently truncates lineage.
async function fetchType(type: string): Promise<PresenceNode[]> {
  const PAGE = 500;
  const HARD_CAP_PAGES = 20; // safety valve at 10k items
  const all: PresenceNode[] = [];
  for (let page = 0; page < HARD_CAP_PAGES; page++) {
    try {
      const offset = page * PAGE;
      const res = await fetch(
        `${getApiBase()}/api/graph/nodes?type=${encodeURIComponent(type)}&offset=${offset}&limit=${PAGE}`,
        { next: { revalidate: 30 } },
      );
      if (!res.ok) break;
      const data = await res.json();
      const items = (data.items || []) as PresenceNode[];
      all.push(...items);
      const total = typeof data.total === "number" ? data.total : null;
      if (items.length < PAGE) break;
      if (total !== null && all.length >= total) break;
    } catch {
      break;
    }
  }
  return all;
}

function filterScannable(
  items: PresenceNode[],
  filterRules: ReturnType<typeof getPeopleFilterRules>,
): PresenceNode[] {
  // Skip test/system/visitor identities and KB-system assets. A
  // visitor in /people wants humans, communities, places, gatherings,
  // practices, and works rather than runner pipelines or renderer
  // components.
  return items.filter((n) => {
    if (!n.name) return false;
    if (filterRules.ignoredIdIncludes.some((needle) => n.id.includes(needle))) {
      return false;
    }
    if (filterRules.ignoredIdExact?.includes(n.id)) {
      return false;
    }
    const ct = (n.contributor_type || "").toUpperCase();
    if ((filterRules.excludedContributorTypes as readonly string[]).includes(ct)) {
      return false;
    }

    // Asset filters: hide platform tissue that clutters the Works directory
    const at = (n.asset_type || "").toUpperCase();
    if (at === "RENDERER") return false; // Image Viewer v1, Audio Player v1, ...
    if (n.id.startsWith("visual-lc-")) return false; // KB auto-generated concept visuals
    return true;
  });
}

function initialFor(name: string, fallback: string): string {
  const c = (name || "").trim().charAt(0);
  return c ? c.toUpperCase() : fallback;
}

// When a section has dozens of items (the Works section in particular
// is dominated by 170+ audiobook nodes), the alphabetic flood drowns
// the rest of the directory. Cap the default render so each section
// stays scannable; the section header already links to ?kind={key}
// for the full list, and that filtered view shows everything.
const PREVIEW_PER_SECTION = 16;

export default async function PeopleIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string }>;
}) {
  const sp = await searchParams;
  const lang = await resolveRequestLocale();
  const pageCopy = getPeoplePageCopy(lang);
  const filterRules = getPeopleFilterRules(lang);
  const directorySections = getPeopleDirectorySections(lang);
  // `?kind=humans` (or communities / scenes / gatherings / practices /
  // works) filters the page to just that section. No filter → all
  // sections render, the visitor wanders.
  const kindFilter = sp?.kind;

  // Load every presence-type node. The page groups them below; the
  // search bar overlays a resonance-based filter on top.
  const groups: Record<string, PresenceNode[]> = {};
  for (const section of directorySections) {
    if (kindFilter && section.key !== kindFilter) continue;
    const combined: PresenceNode[] = [];
    for (const t of section.types) {
      const items = await fetchType(t);
      combined.push(...items);
    }
    // Within-section ordering — named lineage figures (the humans who
    // actually shaped this work) rank first in their lineage order,
    // then everyone else alphabetically by display name. Without this
    // ranking, the alphabetic sort buries Anne Tucker / Liquid Bloom /
    // Steve G. Bjorg under hundreds of auto-resolved book authors and
    // YouTube-channel-id rows that share the same section.
    groups[section.key] = filterScannable(combined, filterRules).sort((a, b) => {
      const aSlug = a.slug || a.id;
      const bSlug = b.slug || b.id;
      const aRank = lineageFigureRank(aSlug);
      const bRank = lineageFigureRank(bSlug);
      if (aRank !== null && bRank !== null) return aRank - bRank;
      if (aRank !== null) return -1;
      if (bRank !== null) return 1;
      return (a.name || "").localeCompare(b.name || "");
    });
  }

  const total = Object.values(groups).reduce((sum, g) => sum + g.length, 0);

  return (
    <main className="mx-auto max-w-5xl px-4 sm:px-6 py-8 space-y-8">
      <header className="space-y-3">
        <p className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--primary))]">
          {pageCopy.eyebrow}
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {pageCopy.title}
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          {formatPresenceCopy(pageCopy.totalDescriptionTemplate, { total })}
        </p>
        <Link
          href={pageCopy.presenceWalkHref}
          className="inline-flex rounded-md border border-border/50 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-border hover:text-foreground"
        >
          {pageCopy.presenceWalkCta}
        </Link>
      </header>

      {/* Resonance-based search surfaces the weave for any query */}
      <PeopleSearch />

      {/* Directory, grouped by kind */}
      {directorySections.map((section) => {
        const items = groups[section.key] || [];
        if (items.length === 0) return null;
        // Each section header doubles as a filter link — clicking
        // it narrows the listing to just that section. Same view
        // as visiting /people?kind={key} directly. When already
        // filtered to that section, the link goes back to the full
        // directory.
        const isCurrentlyFiltered = kindFilter === section.key;
        const linkHref = isCurrentlyFiltered
          ? "/people"
          : `/people?kind=${encodeURIComponent(section.key)}`;
        // Default view caps each section at PREVIEW_PER_SECTION so a
        // long catalog (Works has 170+ audiobook nodes) doesn't bury
        // the smaller sections. When a kind-filter is active, the
        // visitor asked for the full list — show everything.
        const visibleItems = isCurrentlyFiltered
          ? items
          : items.slice(0, PREVIEW_PER_SECTION);
        const hiddenCount = items.length - visibleItems.length;
        return (
          <section key={section.key} className="space-y-4">
            <div>
              <Link
                href={linkHref}
                className="group inline-flex items-baseline gap-2 hover:opacity-80 transition-opacity"
                aria-label={
                  isCurrentlyFiltered
                    ? `Show all sections`
                    : `Show only ${section.title}`
                }
              >
                <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
                  {section.title} · {items.length}
                </h2>
                <span className="text-[10px] text-muted-foreground/60 group-hover:text-foreground/80 transition-colors">
                  {isCurrentlyFiltered ? "← all" : "→ filter"}
                </span>
              </Link>
              <p className="text-xs text-muted-foreground/80 italic mt-1">
                {section.lede}
              </p>
            </div>
            <ul className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {visibleItems.map((n) => (
                <li key={n.id}>
                  <Link
                    href={presenceHref(n)}
                    className="group flex items-center gap-3 rounded-xl border border-border/30 bg-card/40 hover:bg-card/70 hover:border-border p-3 transition-colors"
                  >
                    {n.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={n.image_url}
                        alt=""
                        className="w-10 h-10 rounded-full object-cover border border-border/40 shrink-0"
                      />
                    ) : (
                      <span className="w-10 h-10 rounded-full bg-[hsl(var(--primary)/0.12)] text-[hsl(var(--primary))] flex items-center justify-center text-sm font-medium shrink-0">
                        {initialFor(n.name, filterRules.initialFallback)}
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="text-sm text-foreground/90 truncate group-hover:text-foreground">
                        {n.name}
                      </p>
                      {n.provider && (
                        <p className="text-[10px] text-muted-foreground/80 truncate">
                          {n.provider}
                        </p>
                      )}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
            {hiddenCount > 0 && (
              <Link
                href={linkHref}
                className="inline-flex items-center text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Show all {items.length} {section.title.toLowerCase()} →
              </Link>
            )}
          </section>
        );
      })}
    </main>
  );
}
