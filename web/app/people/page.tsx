import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
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

export const metadata: Metadata = {
  title: "Presences — Coherence Network",
  description:
    "Every person, place, community, gathering, and practice the network carries. Type what's alive in you; the graph surfaces the web that resonates.",
};

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

function filterScannable(items: PresenceNode[]): PresenceNode[] {
  // Skip test/system/visitor identities and KB-system assets. A
  // visitor in /people wants to find humans, communities, places,
  // gatherings, and the works people put into the world — not
  // runner pipelines, auto-generated concept imagery, or platform
  // renderer components.
  return items.filter((n) => {
    if (!n.name) return false;
    if (n.id.includes(":wanderer-")) return false;
    if (n.id.includes(":presence-visitor")) return false;
    if (n.id.includes(":test-")) return false;
    const ct = (n.contributor_type || "").toUpperCase();
    if (ct === "SYSTEM" || ct === "AGENT") return false;

    // Asset filters: hide platform tissue that clutters the Works directory
    const at = (n.asset_type || "").toUpperCase();
    if (at === "RENDERER") return false; // Image Viewer v1, Audio Player v1, ...
    if (n.id.startsWith("visual-lc-")) return false; // KB auto-generated concept visuals

    return true;
  });
}

const SECTIONS: Array<{
  key: string;
  title: string;
  types: string[];
  lede: string;
}> = [
  {
    key: "humans",
    title: "People",
    types: ["contributor"],
    lede: "Artists, healers, teachers, videographers, writers — each a held-open door.",
  },
  {
    key: "communities",
    title: "Communities",
    types: ["community", "network-org"],
    lede: "Collectives, festivals, producer brands, organizations.",
  },
  {
    key: "scenes",
    title: "Places",
    types: ["scene"],
    lede: "Venues, sanctuaries, resorts, and the lands that hold them.",
  },
  {
    key: "gatherings",
    title: "Gatherings",
    types: ["event"],
    lede: "Ceremonies past and upcoming — every thread in time.",
  },
  {
    key: "practices",
    title: "Practices & Programs",
    types: ["practice", "skill"],
    lede: "Traditions, disciplines, rituals held globally and locally.",
  },
  {
    key: "works",
    title: "Works",
    types: ["asset"],
    lede: "Albums, tracks, videos, books. What was put into the world.",
  },
];

function initialFor(name: string): string {
  const c = (name || "").trim().charAt(0);
  return c ? c.toUpperCase() : "·";
}

export default async function PeopleIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string }>;
}) {
  const sp = await searchParams;
  // `?kind=humans` (or communities / scenes / gatherings / practices /
  // works) filters the page to just that section. No filter → all
  // sections render, the visitor wanders.
  const kindFilter = sp?.kind;

  // Load every presence-type node. The page groups them below; the
  // search bar overlays a resonance-based filter on top.
  const groups: Record<string, PresenceNode[]> = {};
  for (const section of SECTIONS) {
    if (kindFilter && section.key !== kindFilter) continue;
    const combined: PresenceNode[] = [];
    for (const t of section.types) {
      const items = await fetchType(t);
      combined.push(...items);
    }
    groups[section.key] = filterScannable(combined).sort((a, b) =>
      (a.name || "").localeCompare(b.name || ""),
    );
  }

  const total = Object.values(groups).reduce((sum, g) => sum + g.length, 0);

  return (
    <main className="mx-auto max-w-5xl px-4 sm:px-6 py-8 space-y-8">
      <header className="space-y-3">
        <p className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--primary))]">
          Presences
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          Everyone the field remembers
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          {total} presences in the network. Type what's alive in you below —
          the graph surfaces the web that resonates (concepts + carriers +
          existing threads between them). Or scroll through the directory
          to wander.
        </p>
      </header>

      {/* Resonance-based search surfaces the weave for any query */}
      <PeopleSearch />

      {/* Directory, grouped by kind */}
      {SECTIONS.map((section) => {
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
                        {initialFor(n.name)}
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
