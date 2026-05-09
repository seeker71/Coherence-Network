import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";
import { resolveRequestLocale } from "@/lib/request-locale";
import { createTranslator } from "@/lib/i18n";

export const dynamic = "force-dynamic";

/**
 * /people/{id}/lineage — every contributor's chronological lineage.
 *
 * Data-driven sibling of the hand-curated /people/urs/lineage. Walks
 * the contributor's contributes-to edges to assets, sorts them by
 * an era/year property when present, and renders a master timeline
 * SVG plus a chronological list of work cards. Below the works, a
 * summary of inspired-by edges grouped by source (the same shape the
 * BodyOfEvidence component renders, but specifically scoped to the
 * "streams of attention that ran alongside" framing the lineage
 * needs).
 *
 * Hand-curated routes like /people/urs/lineage take precedence in
 * Next.js routing — this page renders for everyone else automatically.
 */

type GraphNode = {
  id: string;
  type: string;
  name?: string;
  description?: string;
  slug?: string | null;
  image_url?: string | null;
  era?: string;
  year?: string | number;
  company?: string;
  title?: string;
  location?: string;
  substrate?: string;
  creation_kind?: string;
  canonical_url?: string;
};

type Edge = {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  strength?: number;
  properties?: Record<string, unknown>;
  to_node?: { id: string; type: string; name?: string; slug?: string | null };
  from_node?: { id: string; type: string; name?: string; slug?: string | null };
};

async function fetchJson<T>(path: string, lang?: string): Promise<T | null> {
  // Forward the caller's locale to the API so locale-projection in
  // /api/graph/nodes and /api/edges projects name+description into the
  // visitor's language. Without this query-param the API falls back to
  // Accept-Language; server components don't forward that header by
  // default, so we pass lang explicitly.
  const url = new URL(`${getApiBase()}${path}`);
  if (lang) url.searchParams.set("lang", lang);
  try {
    const r = await fetch(url.toString(), { next: { revalidate: 30 } });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

const yearFromEra = (era?: string): number => {
  if (!era) return 9999;
  const m = era.match(/(\b(?:19|20)\d{2}\b)/);
  return m ? Number(m[1]) : 9999;
};

const slugDoor = (n: { slug?: string | null; id: string }) =>
  n.slug ? `/people/${encodeURIComponent(n.slug)}` : `/people/${encodeURIComponent(n.id)}`;

const SOURCE_LABELS: Record<string, string> = {
  audible_listening_history: "Audible · cumulative-author",
  audible_book_listening: "Audible · per-book",
  youtube_watch_clusters: "YouTube",
  lineage_seed: "Named lineage",
  lineage_seed_books: "Physical reading",
  ramtha_lineage_reading: "Physical reading · Ramtha",
  goodreads_history: "Physical reading",
  in_person_event: "In-person encounter",
  retreat: "Retreat",
};

function labelSource(s?: string): string {
  if (!s) return "Other";
  return SOURCE_LABELS[s] ?? s.replace(/_/g, " ");
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const node = await fetchJson<GraphNode>(
    `/api/graph/nodes/${encodeURIComponent(decodeURIComponent(id))}`,
  );
  if (!node) return { title: "Lineage not found" };
  return {
    title: `${node.name || node.id} — lineage of works and influences`,
    description:
      `Chronological lineage of every work ${node.name || node.id} has contributed to, woven with the streams of attention that ran alongside.`,
  };
}

export default async function ContributorLineagePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const decoded = decodeURIComponent(id);
  const lang = await resolveRequestLocale();
  const t = createTranslator(lang);
  const contributor = await fetchJson<GraphNode>(
    `/api/graph/nodes/${encodeURIComponent(decoded)}`,
    lang,
  );
  if (!contributor) notFound();

  // Resolve to a stable id for edge queries (some inputs are slugs).
  const stableId = contributor.id;

  const [contributesEnv, inspiredEnv] = await Promise.all([
    fetchJson<{ items?: Edge[] }>(
      `/api/edges?from_id=${encodeURIComponent(stableId)}&type=contributes-to&limit=200`,
      lang,
    ),
    fetchJson<{ items?: Edge[] }>(
      `/api/edges?from_id=${encodeURIComponent(stableId)}&type=inspired-by&limit=300`,
      lang,
    ),
  ]);

  const contributesEdges: Edge[] = contributesEnv?.items ?? [];
  const inspiredEdges: Edge[] = inspiredEnv?.items ?? [];

  // Hydrate every work node so we get era / company / location / description.
  const works: GraphNode[] = (
    await Promise.all(
      contributesEdges.map((e) =>
        fetchJson<GraphNode>(`/api/graph/nodes/${encodeURIComponent(e.to_id)}`, lang),
      ),
    )
  ).filter((n): n is GraphNode => Boolean(n));

  works.sort((a, b) => {
    const ay = yearFromEra(a.era);
    const by = yearFromEra(b.era);
    if (ay !== by) return ay - by;
    return (a.name || a.id).localeCompare(b.name || b.id);
  });

  // Group inspired-by edges by source for the streams-of-attention view.
  type StreamRow = { sourceLabel: string; targetName: string; targetHref: string; metric: string };
  const streamRows: StreamRow[] = inspiredEdges
    .map((e): StreamRow | null => {
      const to = e.to_node;
      if (!to) return null;
      const props = (e.properties ?? {}) as Record<string, unknown>;
      const audibleHours = Number(props.audible_hours ?? 0);
      const watchHours = Number(props.watch_hours ?? 0);
      const physical = Number(props.physical_read_hours ?? 0);
      const totalH = audibleHours + watchHours + physical;
      const metric =
        totalH > 0
          ? `${totalH.toFixed(0)}h`
          : typeof e.strength === "number"
            ? `s=${e.strength.toFixed(2)}`
            : "";
      return {
        sourceLabel: labelSource(props.source as string | undefined),
        targetName: to.name || to.id,
        targetHref: slugDoor(to),
        metric,
      };
    })
    .filter((r): r is StreamRow => Boolean(r));

  // Bucket streamRows by source label
  const streamBuckets = new Map<string, StreamRow[]>();
  for (const r of streamRows) {
    if (!streamBuckets.has(r.sourceLabel)) streamBuckets.set(r.sourceLabel, []);
    streamBuckets.get(r.sourceLabel)!.push(r);
  }
  const streamBucketsSorted = [...streamBuckets.entries()].sort(
    ([, a], [, b]) => b.length - a.length,
  );

  // Group works by year for the swimlane visualisation. Multiple
  // works in the same year stack vertically rather than colliding.
  const knownYearWorks = works.filter((w) => yearFromEra(w.era) !== 9999);
  const unknownYearWorks = works.filter((w) => yearFromEra(w.era) === 9999);
  const yearBuckets = new Map<number, GraphNode[]>();
  for (const w of knownYearWorks) {
    const y = yearFromEra(w.era);
    if (!yearBuckets.has(y)) yearBuckets.set(y, []);
    yearBuckets.get(y)!.push(w);
  }
  const sortedYears = [...yearBuckets.keys()].sort((a, b) => a - b);
  const minYear = sortedYears.length ? sortedYears[0] : 1980;
  const maxYear = sortedYears.length
    ? Math.max(sortedYears[sortedYears.length - 1], 2026)
    : 2026;

  return (
    <main className="relative">
      <section
        className="relative min-h-[40vh] flex flex-col justify-end overflow-hidden"
        style={{
          background:
            "linear-gradient(135deg, hsl(220 30% 8%), hsl(280 35% 14%) 40%, hsl(195 35% 16%))",
        }}
      >
        <div
          className="absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30"
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-4xl mx-auto px-6 py-12 sm:py-14 w-full">
          <nav
            className="text-sm text-muted-foreground mb-6 flex items-center gap-2"
            aria-label="breadcrumb"
          >
            <Link href="/" className="hover:text-primary">{t("personProfile.breadcrumb.home")}</Link>
            <span className="text-muted-foreground/50">/</span>
            <Link href="/people" className="hover:text-primary">{t("personProfile.breadcrumb.people")}</Link>
            <span className="text-muted-foreground/50">/</span>
            <Link href={slugDoor(contributor)} className="hover:text-primary">
              {contributor.name || contributor.id}
            </Link>
            <span className="text-muted-foreground/50">/</span>
            <span className="text-foreground/80">{t("people.lineage.breadcrumb")}</span>
          </nav>
          <p className="text-xs uppercase tracking-[0.18em] mb-3 text-[hsl(var(--primary))]">
            {t(
              works.length === 1 ? "people.lineage.eyebrowWorkSingular" : "people.lineage.eyebrowWorks",
              { n: String(works.length) },
            )}
            {streamRows.length > 0
              ? ` · ${t(
                  streamRows.length === 1 ? "people.lineage.eyebrowEdgeSingular" : "people.lineage.eyebrowEdges",
                  { n: String(streamRows.length) },
                )}`
              : ""}
          </p>
          <h1 className="text-3xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
            {t("people.lineage.title", { name: contributor.name || contributor.id })}
          </h1>
          <p className="text-base md:text-lg text-foreground/85 leading-relaxed max-w-2xl">
            {t("people.lineage.welcome")}
          </p>
        </div>
      </section>

      <div className="max-w-4xl mx-auto px-6 py-10 space-y-12">
        {works.length === 0 ? (
          <section>
            <p className="text-sm text-muted-foreground italic">
              {t("people.lineage.empty")}
            </p>
          </section>
        ) : (
          <>
            <section>
              <h2 className="text-xl font-light text-foreground mb-4">
                {t("people.lineage.arcAtAGlance")}
              </h2>
              <figure className="rounded-xl border border-border/40 bg-card/30 p-5 overflow-hidden">
                <ol className="relative border-l border-border/50 pl-6 space-y-3">
                  {sortedYears.map((year) => {
                    const bucket = yearBuckets.get(year)!;
                    return (
                      <li key={year} className="relative">
                        <span
                          className="absolute -left-[33px] top-0.5 inline-flex items-center justify-center w-12 h-5 rounded-md bg-card border border-border/50 text-[10px] text-[hsl(var(--primary))] font-mono"
                          aria-hidden="true"
                        >
                          {year}
                        </span>
                        <ul className="ml-2 space-y-1">
                          {bucket.map((w) => (
                            <li key={w.id} className="flex items-baseline gap-2">
                              <span
                                className="inline-block w-2 h-2 rounded-full bg-[hsl(195_60%_60%)] shrink-0 translate-y-[1px]"
                                aria-hidden="true"
                              />
                              <Link
                                href={slugDoor(w)}
                                className="text-sm text-foreground/90 hover:text-[hsl(var(--primary))] leading-tight"
                              >
                                {w.name || w.id}
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </li>
                    );
                  })}
                  {unknownYearWorks.length > 0 ? (
                    <li className="relative pt-2 border-t border-border/30">
                      <span className="absolute -left-[33px] top-2.5 inline-flex items-center justify-center w-12 h-5 rounded-md bg-card border border-border/50 text-[10px] text-muted-foreground font-mono">
                        —
                      </span>
                      <p className="text-xs text-muted-foreground italic mb-1.5 ml-2">
                        {t("people.lineage.yearNotRecorded")}
                      </p>
                      <ul className="ml-2 space-y-1">
                        {unknownYearWorks.map((w) => (
                          <li key={w.id} className="flex items-baseline gap-2">
                            <span
                              className="inline-block w-2 h-2 rounded-full bg-muted-foreground/50 shrink-0 translate-y-[1px]"
                              aria-hidden="true"
                            />
                            <Link
                              href={slugDoor(w)}
                              className="text-sm text-foreground/85 hover:text-[hsl(var(--primary))] leading-tight"
                            >
                              {w.name || w.id}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ) : null}
                </ol>
                <figcaption className="text-xs text-muted-foreground mt-4 pt-3 border-t border-border/30">
                  {sortedYears.length > 0
                    ? t(
                        knownYearWorks.length === 1
                          ? "people.lineage.figcaptionRangeSingular"
                          : "people.lineage.figcaptionRange",
                        {
                          n: String(knownYearWorks.length),
                          from: String(minYear),
                          to: maxYear === new Date().getFullYear() ? t("people.lineage.now") : String(maxYear),
                        },
                      )
                    : ""}
                  {unknownYearWorks.length > 0
                    ? " · " + t("people.lineage.figcaptionUnknownYears", { n: String(unknownYearWorks.length) })
                    : ""}
                </figcaption>
              </figure>
            </section>

            <section>
              <h2 className="text-xl font-light text-foreground mb-4">
                {t("people.lineage.worksHeading")}
              </h2>
              <ul className="space-y-3">
                {works.map((w) => {
                  const y = yearFromEra(w.era);
                  return (
                    <li
                      key={w.id}
                      className="rounded-xl border border-border/40 bg-card/30 px-4 py-3 hover:border-[hsl(var(--primary))/0.4] transition-colors"
                    >
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="text-xs text-[hsl(var(--primary))] font-mono shrink-0">
                          {y === 9999 ? "—" : y}
                        </span>
                        <Link
                          href={slugDoor(w)}
                          className="text-base text-foreground hover:text-[hsl(var(--primary))] font-light"
                        >
                          {w.name || w.id}
                        </Link>
                        {w.era ? (
                          <span className="text-xs text-muted-foreground">
                            {w.era}
                          </span>
                        ) : null}
                      </div>
                      {w.description ? (
                        <p className="text-sm text-foreground/80 mt-1.5 leading-relaxed">
                          {w.description.length > 280
                            ? w.description.slice(0, 280).trim() + "…"
                            : w.description}
                        </p>
                      ) : null}
                      {(w.company || w.location || w.substrate) ? (
                        <p className="text-xs text-muted-foreground mt-1.5 italic">
                          {[w.company, w.location, w.substrate]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </section>
          </>
        )}

        {streamBucketsSorted.length > 0 && (
          <section>
            <h2 className="text-xl font-light text-foreground mb-4">
              {t("people.lineage.streamsHeading")}
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              {t("people.lineage.streamsLede")}{" "}
              <Link href={slugDoor(contributor)} className="text-primary hover:underline">
                {contributor.name || contributor.id}
              </Link>
              .
            </p>
            <div className="space-y-4">
              {streamBucketsSorted.map(([source, rows]) => (
                <div key={source}>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-2">
                    {source} · {rows.length}
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {rows.slice(0, 24).map((r, i) => (
                      <li key={i}>
                        <Link
                          href={r.targetHref}
                          className="inline-flex items-baseline gap-1.5 px-2.5 py-1 rounded-md border border-border/40 bg-card/30 hover:border-[hsl(var(--primary))/0.4] text-xs"
                        >
                          <span className="text-foreground/85">{r.targetName}</span>
                          {r.metric ? (
                            <span className="text-muted-foreground font-mono text-[10px]">
                              {r.metric}
                            </span>
                          ) : null}
                        </Link>
                      </li>
                    ))}
                    {rows.length > 24 ? (
                      <li className="text-xs text-muted-foreground italic self-center">
                        + {rows.length - 24} more
                      </li>
                    ) : null}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="pt-6 border-t border-border/40">
          <p className="text-sm text-muted-foreground">
            {t("people.lineage.footerLede")}{" "}
            <Link href={slugDoor(contributor)} className="text-primary hover:underline">
              {contributor.name || contributor.id}
            </Link>
            <code className="ml-2 text-foreground/80 text-xs">
              GET /api/edges?from_id={stableId}&type=contributes-to
            </code>
          </p>
        </section>
      </div>
    </main>
  );
}
