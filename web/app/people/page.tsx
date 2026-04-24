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
};

async function fetchType(type: string, limit = 200): Promise<PresenceNode[]> {
  try {
    const res = await fetch(
      `${getApiBase()}/api/graph/nodes?type=${encodeURIComponent(type)}&limit=${limit}`,
      { next: { revalidate: 30 } },
    );
    if (!res.ok) return [];
    const data = await res.json();
    return (data.items || []) as PresenceNode[];
  } catch {
    return [];
  }
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
    groups[section.key] = filterScannable(combined, filterRules).sort((a, b) =>
      (a.name || "").localeCompare(b.name || ""),
    );
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
        return (
          <section key={section.key} className="space-y-4">
            <div>
              <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
                {section.title} · {items.length}
              </h2>
              <p className="text-xs text-muted-foreground/80 italic mt-1">
                {section.lede}
              </p>
            </div>
            <ul className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {items.map((n) => (
                <li key={n.id}>
                  <Link
                    href={`/people/${encodeURIComponent(n.id)}`}
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
          </section>
        );
      })}
    </main>
  );
}
