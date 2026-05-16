import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cookies, headers } from "next/headers";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { Panel, VoiceQuote } from "@/components/Panel";
import { PersonInspiredBy } from "@/components/PersonInspiredBy";
import {
  PresencePage,
  type Creation,
  type Presence,
  type PresenceIdentity,
} from "@/components/presence/PresencePage";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import {
  pickLocaleContent,
  toPersonProfileContent,
  type PresenceContent,
  type PresenceContentByLocale,
} from "@/lib/presence-content";

/**
 * /people/[id] — a warm public garden view of a contributor.
 *
 * When a reader encounters Mama's voice on a concept and wants to know
 * "who is this", this is where they land. The page honors her:
 *
 *   · a generous greeting with her name
 *   · the voices she has given, each quoted and attributed to the
 *     concept where she offered it
 *   · the warmth that has come back to her — reactions that others
 *     laid on her voices, gathered here as a felt register
 *   · a quiet doorway forward ("meet her here →")
 *
 * This is the companion to /profile/[contributorId], which stays the
 * deeper technical view (public-key fingerprint, frequency profile,
 * assets). /people speaks to the community; /profile speaks to
 * contributors who want the data.
 */

export const dynamic = "force-dynamic";

type ContributorNode = {
  id?: string;
  name?: string;
  properties?: Record<string, unknown>;
  [key: string]: unknown;
};

type FeedItem = {
  entity_type: string;
  entity_id: string;
  kind: string;
  title: string;
  snippet: string;
  actor_name: string | null;
  reason: string;
  reason_label: string;
  created_at: string | null;
};

type FeedResponse = {
  items: FeedItem[];
  count: number;
  locale: string;
};

/**
 * Pull the `presence_content` property off the graph node and return
 * the locale-appropriate slice, if any. Returns null when:
 *   · the node has no `presence_content` property
 *   · the property isn't a JSON object
 *   · no locale (including `en`) has authored content
 *
 * Accepts either a per-locale envelope (`{en: {...}, de: {...}}`) or
 * a single PresenceContent (which is treated as the `en` variant).
 */
function pickPresenceContent(
  node: Record<string, unknown> | null,
  lang: string,
): PresenceContent | null {
  if (!node) return null;
  const raw = (node as Record<string, unknown>).presence_content;
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  // Envelope shape: presence of any known locale key signals the
  // per-locale layout. A bare PresenceContent has `hero` at the top
  // level instead.
  const looksLikeEnvelope =
    typeof obj.en === "object" ||
    typeof obj.de === "object" ||
    typeof obj.es === "object" ||
    typeof obj.id === "object";
  if (looksLikeEnvelope) {
    return pickLocaleContent(obj as PresenceContentByLocale, lang);
  }
  if (typeof obj.hero === "object" && obj.hero) {
    return obj as unknown as PresenceContent;
  }
  return null;
}

async function fetchContributor(id: string): Promise<ContributorNode | null> {
  const base = getApiBase();
  return fetchJsonOrNull<ContributorNode>(
    `${base}/api/contributors/${encodeURIComponent(id)}`,
    {},
    5000,
  );
}

/**
 * Fetch the raw graph node for this identity — properties like
 * canonical_url, presences[], tagline, image_url live here, not on
 * the Contributor model. We need them to decide whether to render
 * the polished presence view or the warm garden view.
 */
async function fetchGraphNode(id: string): Promise<Record<string, unknown> | null> {
  const base = getApiBase();
  const node = await fetchJsonOrNull<Record<string, unknown>>(
    `${base}/api/graph/nodes/${encodeURIComponent(id)}`,
    {},
    5000,
  );
  if (node) return node;

  // The id might be a bare slug without the "contributor:" prefix
  // (that's what /contributors/graduate returns, and what lives in
  // localStorage). Try that shape too.
  if (!id.includes(":")) {
    const prefixed = await fetchJsonOrNull<Record<string, unknown>>(
      `${base}/api/graph/nodes/${encodeURIComponent(`contributor:${id}`)}`,
      {},
      5000,
    );
    if (prefixed) return prefixed;
  }

  // Last fallback: the id is `contributor:{slug}` but the graph node
  // for that presence is stored under a non-standard stable id —
  // commonly `contributor:{16-hex}` from older auto-create flows.
  // Such nodes still carry the human-readable slug in their `slug`
  // field, so search the contributor list and match on that.
  //
  // This closes the gap where /people/contributor:michael-levin and
  // similar URLs returned a sparse fallback page instead of the rich
  // description body, because Levin's stable id is
  // contributor:3f42d44094e36ce5 not contributor:michael-levin.
  if (id.startsWith("contributor:")) {
    const slug = id.slice("contributor:".length);
    if (slug && !slug.match(/^[0-9a-f]{12,}$/)) {
      const list = await fetchJsonOrNull<{ items: Record<string, unknown>[] }>(
        `${base}/api/graph/nodes?type=contributor&limit=500`,
        {},
        5000,
      );
      const match = list?.items?.find(
        (n) => typeof n.slug === "string" && n.slug === slug,
      );
      if (match) return match;
    }
  }

  // Alias match: a node's `aliases` list names every handle this cell
  // answers to — all alive, none deprecated. Urs's contributor:seeker71
  // carries ["seeker71","urs-muff","ursmuff","urs"]; any of those URL
  // forms lands on the same cell. Match against the bare id (no
  // contributor: prefix) so /people/seeker71, /people/urs, etc. resolve
  // even when a request reaches this handler directly.
  {
    const list = await fetchJsonOrNull<{ items: Record<string, unknown>[] }>(
      `${base}/api/graph/nodes?type=contributor&limit=500`,
      {},
      5000,
    );
    const bareId = id.startsWith("contributor:") ? id.slice("contributor:".length) : id;
    const match = list?.items?.find((n) => {
      const aliases = Array.isArray(n.aliases) ? (n.aliases as unknown[]) : [];
      return aliases.some((a) => typeof a === "string" && a === bareId);
    });
    if (match) return match;
  }

  return null;
}

type EdgeRow = {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  from_node?: { id: string; name: string; type: string };
  to_node?: { id: string; name: string; type: string };
  properties?: { kind?: string } & Record<string, unknown>;
};

async function fetchCreations(nodeId: string): Promise<Creation[]> {
  const base = getApiBase();
  const res = await fetchJsonOrNull<{ items: EdgeRow[] }>(
    `${base}/api/edges?from_id=${encodeURIComponent(nodeId)}&type=contributes-to&limit=50`,
    {},
    5000,
  );
  if (!res?.items) return [];
  const creations: Creation[] = [];
  for (const edge of res.items) {
    if (edge.to_node?.type !== "asset") continue;
    const fullAsset = await fetchJsonOrNull<Record<string, unknown>>(
      `${base}/api/graph/nodes/${encodeURIComponent(edge.to_id)}`,
      {},
      5000,
    );
    const kind = (edge.properties?.kind as Creation["kind"]) ||
      (fullAsset?.creation_kind as Creation["kind"]) ||
      "work";
    const slug = (fullAsset?.slug as string) || null;
    const internalUrl = slug ? `/people/${slug}` : null;
    const canonical = (fullAsset?.canonical_url as string) || null;
    const era = (fullAsset?.era as string)
      || (edge.properties?.era as string)
      || null;
    // Convention fallback: when an asset doesn't carry an explicit
    // image_url in the graph, look for a generated emblem at
    // /works/generated/{slug}.jpg. The CSS gradient sits beneath the
    // image so a 404 still leaves the era-tinted phase showing —
    // a missing image never produces a black square.
    const conventionImage = slug ? `/works/generated/${slug}.jpg` : null;
    creations.push({
      kind,
      name: (fullAsset?.name as string) || edge.to_node?.name || "Untitled",
      url: internalUrl ?? canonical,
      internal: Boolean(internalUrl),
      image_url: (fullAsset?.image_url as string) || conventionImage,
      era,
    });
  }
  return creations;
}

async function fetchIdentityInspiredBy(
  nodeId: string,
): Promise<{ id: string; name: string; provider?: string }[]> {
  const base = getApiBase();
  const res = await fetchJsonOrNull<{
    items: { node: { id: string; name: string; provider?: string } }[];
  }>(
    `${base}/api/inspired-by?contributor_id=${encodeURIComponent(nodeId)}`,
    {},
    5000,
  );
  if (!res?.items) return [];
  return res.items.map((it) => ({
    id: it.node.id,
    name: it.node.name,
    provider: it.node.provider,
  }));
}

function nodeToPresenceIdentity(
  node: Record<string, unknown>,
  creations: Creation[],
  inspiredBy: { id: string; name: string; provider?: string }[],
): PresenceIdentity {
  const rawPresences = Array.isArray(node.presences) ? node.presences : [];
  const presences: Presence[] = rawPresences
    .filter((p): p is Presence =>
      typeof p === "object" && p !== null &&
      typeof (p as Presence).provider === "string" &&
      typeof (p as Presence).url === "string",
    );
  const categoryMap: Record<string, string> = {
    contributor: "Artist",
    community: "Community",
    "network-org": "Project",
    asset: "Work",
    event: "Gathering",
    scene: "Place",
    practice: "Practice",
    place: "Place",
    concept: "Concept",
    skill: "Skill",
  };
  const nodeType = (node.type as string) || "contributor";
  // tagline comes from the node's `tagline` property only — never
  // from `description`. Description is the long-form scraped metadata
  // (og:description, often a third-party bio); tagline is the felt
  // sentence rendered in the hero. Falling back would leak
  // platform-authored blurbs into a slot that's meant for the
  // identity's own voice.
  const tagline =
    typeof node.tagline === "string" && node.tagline.trim()
      ? (node.tagline as string)
      : undefined;
  // The graph holds a node's narrative in two distinct slots:
  //   · `note` — event-specific story ("What this gathering held")
  //   · `description` — long-form prose about a presence (often
  //                      thousands of characters of body-of-fire
  //                      writing for artists/teachers)
  //
  // Earlier the mapper promoted description into note universally, so
  // Liquid Bloom's beautiful prose rendered under the gathering-shaped
  // "What this gathering held" heading. Now they stay separate. For
  // event-type nodes, description still falls through to note when
  // note is absent (older events store their history there). For all
  // other types, description rides its own slot.
  const isEvent = nodeType === "event";
  const rawDescription =
    typeof node.description === "string" ? node.description.trim() : "";
  const nameTrim = typeof node.name === "string" ? node.name.trim() : "";
  // Description is "substantive" when it isn't just a name-echo or a
  // test-leak ("TESTING" etc) shorter than ~24 chars.
  const descriptionIsSubstantive =
    !!rawDescription &&
    rawDescription !== nameTrim &&
    rawDescription.length >= 24;
  const note: string | undefined = (() => {
    const n = node.note;
    if (typeof n === "string" && n.trim()) return n.trim();
    if (isEvent && descriptionIsSubstantive) return rawDescription;
    return undefined;
  })();
  const description: string | undefined =
    !isEvent && descriptionIsSubstantive && rawDescription !== (tagline || "")
      ? rawDescription
      : undefined;
  // The body's authored markdown for this presence, when the cell has
  // moved off a static page. Lives on the contributor node as
  // `presence_story` and takes precedence over note/description in
  // PresencePage rendering.
  const presence_story: string | undefined =
    typeof node.presence_story === "string" && (node.presence_story as string).trim()
      ? (node.presence_story as string).trim()
      : undefined;
  const when_text =
    typeof node.when === "string" && node.when.trim()
      ? (node.when as string)
      : undefined;
  const where_text =
    typeof node.where === "string" && node.where.trim()
      ? (node.where as string)
      : undefined;
  return {
    id: (node.id as string) || "",
    slug: typeof node.slug === "string" && node.slug ? (node.slug as string) : null,
    name: (node.name as string) || "",
    category: categoryMap[nodeType] || nodeType,
    tagline,
    canonical_url: (node.canonical_url as string) || "",
    provider: (node.provider as string) || "web",
    image_url: (node.image_url as string) || null,
    claimed: node.claimed === false ? false : undefined,
    presences,
    creations,
    inspired_by: inspiredBy,
    when_text,
    where_text,
    note,
    description,
    presence_story,
  };
}

async function fetchFeed(id: string, lang: LocaleCode): Promise<FeedResponse | null> {
  const base = getApiBase();
  return fetchJsonOrNull<FeedResponse>(
    `${base}/api/feed/personal?contributor_id=${encodeURIComponent(id)}&limit=40&lang=${lang}`,
    {},
    5000,
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id: rawId } = await params;
  const id = decodeRouteParam(rawId);
  // Declare the canonical URL when the graph node carries a slug.
  // One presence, one doorway: shared link previews and search
  // engines converge on `/people/{slug}` even when an inbound link
  // arrives at the graph-id form. The mapping lives in the graph.
  const node = await fetchGraphNode(id);
  const slug = node && typeof node.slug === "string" ? node.slug : null;
  const name = node && typeof node.name === "string" ? node.name : null;
  const display = name || id.replace(/-[a-z0-9]{6,}$/, "").replace(/-/g, " ");
  return {
    title: `${display} — Coherence Network`,
    description: `A corner of the organism held by ${display}.`,
    alternates: slug ? { canonical: `/people/${slug}` } : undefined,
  };
}

function decodeRouteParam(rawId: string): string {
  try {
    return decodeURIComponent(rawId);
  } catch {
    return rawId;
  }
}

function initialFromName(name: string): string {
  const first = (name || "").trim().charAt(0);
  return first ? first.toUpperCase() : "·";
}

function displayName(
  node: ContributorNode | null,
  voiceAuthorName: string | null,
  fallback: string,
): string {
  // The voice's author_name is the real human name (e.g. "TestSoul",
  // "Mama") that the person typed when they spoke their first voice.
  // That's the warmest display option. Fall back to the contributor
  // node's slug name (with the fingerprint suffix trimmed) or the
  // raw id only when no voice author_name is available.
  if (voiceAuthorName && voiceAuthorName.trim()) return voiceAuthorName.trim();
  const raw = (node?.name as string) || fallback;
  return raw.replace(/-[a-z0-9]{6,}$/, "");
}

function groupByConcept(items: FeedItem[]): Map<string, FeedItem[]> {
  const map = new Map<string, FeedItem[]>();
  for (const it of items) {
    const key = it.entity_id;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }
  return map;
}

export default async function PersonPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: rawId } = await params;
  // Next 15 preserves percent-encoding in dynamic route params — a link
  // to /people/contributor%3Aliquid-bloom-xxx arrives here with the
  // literal `%3A` still in place. Decode once so downstream fetches
  // don't re-encode into `%253A` and miss the node.
  const id = decodeRouteParam(rawId);
  // The graph-id → human-slug redirect lives in middleware.ts;
  // requests reaching this handler use either the slug directly
  // (resolved here) or a graph id with no slug registered.

  const cookieLang = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  const lang: LocaleCode = isSupportedLocale(cookieLang)
    ? cookieLang
    : isSupportedLocale(headerLang)
    ? headerLang
    : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const graphNode = await fetchGraphNode(id);

  // First dispatch: the graph node carries a structured `presence_content`
  // JSON — the body's authored content for this cell, in the same shape
  // a static `web/content/people/{slug}/{locale}.tsx` would carry. Render
  // it through the same template the static directories use, so the
  // visual identity is identical regardless of whether content lives on
  // disk or in the graph. This is the path a composted static cell
  // moves onto.
  const presenceContent = pickPresenceContent(graphNode, lang);
  if (graphNode && presenceContent) {
    const nodeId = (graphNode.id as string) || id;
    const slug = typeof graphNode.slug === "string" ? graphNode.slug : null;
    return (
      <PersonProfileTemplate
        content={toPersonProfileContent(presenceContent)}
        lang={lang}
        graphSlug={slug || nodeId}
      />
    );
  }

  // When the graph node carries a canonical_url, this identity has an
  // outward-facing presence. Render the polished presence page —
  // hero, platforms, creations, lineage — before calling contributor
  // endpoints that only apply to local human profiles.
  if (graphNode && typeof graphNode.canonical_url === "string" && graphNode.canonical_url) {
    const nodeId = (graphNode.id as string) || id;
    const [creations, inspiredBy] = await Promise.all([
      fetchCreations(nodeId),
      fetchIdentityInspiredBy(nodeId),
    ]);
    return (
      <PresencePage identity={nodeToPresenceIdentity(graphNode, creations, inspiredBy)} lang={lang} />
    );
  }

  const [contributor, feed] = await Promise.all([
    fetchContributor(id),
    fetchFeed(id, lang),
  ]);

  const items = feed?.items || [];
  const voices = items.filter((it) => it.reason === "i_voiced");
  const warmth = items.filter(
    (it) =>
      it.reason === "reaction_on_my_voice" ||
      it.reason === "replied_to_me",
  );

  // If we know nothing about this contributor — no node, no voices,
  // no reactions — render a gentle not-found rather than a scary 404.
  if (!contributor && !graphNode && items.length === 0) {
    notFound();
  }

  // When the graph node has outward-facing presence (canonical_url) OR
  // is one of the field types whose own properties carry the rendered
  // content (events, scenes, places, communities, network-orgs,
  // practices), render the polished presence page. Earlier the gate
  // was canonical_url-only, which meant gatherings with rich `note`,
  // `when`, `where` fields fell through to the warm-garden view that
  // expects voices — and rendered as empty scaffolds, hiding the
  // history alive in the graph.
  const NODE_TYPES_THAT_RENDER_AS_PRESENCE = new Set([
    "contributor",
    "interested-person",
    "event",
    "scene",
    "place",
    "community",
    "network-org",
    "practice",
    "asset",
  ]);
  const graphNodeType = (graphNode?.type as string) || "";
  const hasCanonicalUrl =
    !!graphNode &&
    typeof graphNode.canonical_url === "string" &&
    !!graphNode.canonical_url;
  if (graphNode && (hasCanonicalUrl || NODE_TYPES_THAT_RENDER_AS_PRESENCE.has(graphNodeType))) {
    const nodeId = (graphNode.id as string) || id;
    const [creations, inspiredBy] = await Promise.all([
      fetchCreations(nodeId),
      fetchIdentityInspiredBy(nodeId),
    ]);
    return (
      <PresencePage identity={nodeToPresenceIdentity(graphNode, creations, inspiredBy)} lang={lang} />
    );
  }

  // Prefer the author_name from one of her own voices (real human name
  // like "TestSoul") over the contributor-node slug (like
  // "testsoul-test-fp-cycle-o").
  const voiceAuthorName =
    voices.find((v) => v.actor_name)?.actor_name ||
    items.find((i) => i.reason === "i_voiced" && i.actor_name)?.actor_name ||
    null;
  const name = displayName(contributor, voiceAuthorName, id);
  const initial = initialFromName(name);

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-10 space-y-6">
      {/* Greeting */}
      <Panel variant="warm" className="flex items-start gap-4">
        <div
          className="shrink-0 w-14 h-14 rounded-full flex items-center justify-center text-2xl font-light bg-[hsl(var(--primary)/0.2)] text-[hsl(var(--primary))] border border-[hsl(var(--primary)/0.3)]"
          aria-hidden="true"
        >
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
            {t("people.eyebrow")}
          </p>
          <h1 className="text-2xl md:text-3xl font-light tracking-tight text-foreground">
            {name}
          </h1>
          {/* No tagline. The sections below carry the substance —
              her actual voices, the actual warmth she has received.
              A one-line summary at the top would be scorekeeping
              translated into template sentences; the specifics below
              are the only honest reflection of who she is. */}
        </div>
      </Panel>

      {/* Voices she's given — her garden */}
      {voices.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] px-1">
            {t("people.voicesHeading")}
          </h2>
          <ul className="space-y-3">
            {voices.map((v, i) => (
              <li key={`${v.entity_id}-${v.created_at}-${i}`}>
                <Panel variant="neutral">
                  <VoiceQuote
                    attribution={
                      <Link
                        href={`/vision/${encodeURIComponent(v.entity_id)}`}
                        className="text-[hsl(var(--chart-2))] hover:opacity-80 underline-offset-4 hover:underline"
                      >
                        {v.entity_id.replace(/^lc-/, "")} ·{" "}
                        {v.created_at
                          ? new Date(v.created_at).toLocaleDateString(lang)
                          : ""}
                      </Link>
                    }
                  >
                    {v.snippet}
                  </VoiceQuote>
                </Panel>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Warmth received */}
      {warmth.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm uppercase tracking-[0.18em] font-semibold text-[hsl(var(--chart-2))] px-1">
            {t("people.warmthHeading")}
          </h2>
          <Panel variant="cool">
            <ul className="space-y-2">
              {warmth.map((w, i) => {
                const emoji =
                  w.snippet && w.snippet.length <= 6 ? w.snippet : null;
                return (
                  <li
                    key={`${w.entity_id}-${w.created_at}-${i}`}
                    className="flex items-start gap-2"
                  >
                    {emoji ? (
                      <span className="text-lg leading-none mt-0.5" aria-hidden="true">
                        {emoji}
                      </span>
                    ) : null}
                    <span className="text-sm text-foreground/90">
                      <span className="font-medium">
                        {w.actor_name || t("people.someone")}
                      </span>{" "}
                      <span className="text-muted-foreground">
                        {w.reason === "replied_to_me"
                          ? t("people.replied")
                          : t("people.reacted")}
                      </span>
                      {!emoji && w.snippet && (
                        <span className="block italic text-muted-foreground mt-0.5">
                          “{w.snippet}”
                        </span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Panel>
        </section>
      )}

      {/* Inspired by — the lineage this person carries, lit up
          wherever the viewer shares a thread with them. */}
      <PersonInspiredBy contributorId={id} />

      {/* Empty state when there's nothing yet */}
      {voices.length === 0 && warmth.length === 0 && (
        <Panel variant="empty" heading={t("people.emptyHeading")}>
          <p>{t("people.emptyLede")}</p>
        </Panel>
      )}

      {/* Doorway to the chronological lineage of works + influences */}
      <div className="pt-2 flex flex-wrap items-center gap-x-5 gap-y-2">
        <Link
          href={`/people/${encodeURIComponent(id)}/lineage`}
          className="inline-flex items-center gap-1 text-sm font-medium text-[hsl(var(--primary))] hover:opacity-80"
        >
          Walk this cell&apos;s lineage of works and influences →
        </Link>
        <Link
          href="/vision"
          className="inline-flex items-center gap-1 text-sm font-medium text-[hsl(var(--chart-2))] hover:opacity-80"
        >
          {t("people.backToVision")} →
        </Link>
      </div>
    </main>
  );
}
