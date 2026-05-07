import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cookies, headers } from "next/headers";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { Panel, VoiceQuote } from "@/components/Panel";
import { PersonInspiredBy } from "@/components/PersonInspiredBy";
import { Button } from "@/components/ui/button";
import { AttributedExternalLink } from "@/components/content/AttributedExternalLink";
import {
  PresencePage,
  type Creation,
  type Presence,
  type PresenceIdentity,
} from "@/components/presence/PresencePage";

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

type CuratedPresence = {
  name: string;
  slug: string;
  tagline: string;
  heroImage: string;
  bio: string;
  resonance: { axis: string; score: number; note: string }[];
  links: { label: string; href: string }[];
  type: string;
  location: string;
};

const CURATED_PRESENCES: Record<string, CuratedPresence> = {
  "elon-musk": {
    name: "Elon Musk",
    slug: "elon-musk",
    tagline: "Multiplanetary • xAI • Tesla • SpaceX",
    heroImage: "/presences/elon-musk-hero.jpg",
    bio: "Founder of Tesla, SpaceX, xAI, and X. A presence driving humanity toward multiplanetary life and accelerating the understanding of the universe through first-principles thinking and bold execution.",
    resonance: [
      { axis: "Vitality", score: 0.92, note: "Relentless drive toward life-expanding frontiers" },
      { axis: "Organic Intelligence", score: 0.87, note: "First-principles reasoning as living intelligence" },
      { axis: "Expression", score: 0.95, note: "Radical transparency and direct communication" },
    ],
    links: [
      { label: "X / Twitter", href: "https://x.com/elonmusk" },
      { label: "Tesla", href: "https://tesla.com" },
      { label: "SpaceX", href: "https://spacex.com" },
      { label: "xAI", href: "https://x.ai" },
    ],
    type: "human",
    location: "Earth (multiplanetary intent)",
  },
  "liquid-bloom": {
    name: "Liquid Bloom",
    slug: "liquid-bloom",
    tagline: "Soundscapes for Embodied Dance • Journeys • Healing",
    heroImage: "/presences/liquid-bloom-hero.jpg",
    bio: "Visionary world-electronic project of Amani Friend (Desert Dwellers). Creates transcendent soundscapes that serve embodied dance, meditation, wellness, and deep journey work - music as medicine for the collective field.",
    resonance: [
      { axis: "Vitality", score: 0.94, note: "Music that amplifies life force and presence" },
      { axis: "Harmony", score: 0.91, note: "World instrumentation woven into coherent sonic fields" },
      { axis: "Organic Intelligence", score: 0.88, note: "Healing frequencies grown from living tradition" },
    ],
    links: [
      { label: "Instagram", href: "https://www.instagram.com/liquidbloom/" },
      { label: "Bandcamp", href: "https://liquidbloom.bandcamp.com" },
      { label: "Spotify", href: "https://open.spotify.com/artist/liquidbloom" },
    ],
    type: "human",
    location: "Global (Desert Dwellers lineage)",
  },
  bloomurian: {
    name: "Bloomurian",
    slug: "bloomurian",
    tagline: "Folktronica • World Bass • Heart-Opening Frequencies",
    heroImage: "/presences/bloomurian-hero.jpg",
    bio: "Electronic music & DJ project of Robin Liepman (Bloom). Blends folktronica, world bass, psychedelic bass, and organic house into multidimensional frequencies that cultivate blossoming heart, mind, body, and soul.",
    resonance: [
      { axis: "Vitality", score: 0.93, note: "Heart-opening bass that moves the body" },
      { axis: "Expression", score: 0.89, note: "Live instrumentation + electronic alchemy" },
      { axis: "Harmony", score: 0.9, note: "Polyphonic frequencies for collective resonance" },
    ],
    links: [
      { label: "Website", href: "https://www.bloomurian.com/" },
      { label: "Instagram", href: "https://www.instagram.com/bloomurianmusic/" },
      { label: "Bandcamp", href: "https://bloomurian.bandcamp.com" },
    ],
    type: "human",
    location: "Boulder, Colorado",
  },
  mose: {
    name: "Mose",
    slug: "mose",
    tagline: "Shamanic Downtempo • ReGen Remixes • Organic Intelligence",
    heroImage: "/presences/mose-hero.jpg",
    bio: "Shamanic electronic musician known for deep, organic, regenerative sound. Creator of the ReGen remix series with Liquid Bloom and collaborator in the conscious music field - frequency work that regenerates the listener.",
    resonance: [
      { axis: "Organic Intelligence", score: 0.95, note: "Regenerative, earth-connected sound design" },
      { axis: "Vitality", score: 0.88, note: "Downtempo that restores nervous system coherence" },
      { axis: "Harmony", score: 0.86, note: "Folktronica roots meeting modern bass" },
    ],
    links: [
      { label: "Spotify", href: "https://open.spotify.com/artist/mose" },
      { label: "Bandcamp", href: "https://mose.bandcamp.com" },
    ],
    type: "human",
    location: "Global (shamanic electronic lineage)",
  },
  "aly-constantine": {
    name: "Aly Constantine",
    slug: "aly-constantine",
    tagline: "Healing Arts • Conscious Sound • Presence",
    heroImage: "/presences/aly-constantine-hero.jpg",
    bio: "Presence in the healing arts and conscious sound field. Works at the intersection of sound, presence, and embodied transformation - helping the field remember itself through voice, vibration, and deep listening.",
    resonance: [
      { axis: "Vitality", score: 0.91, note: "Sound as direct transmission of life force" },
      { axis: "Harmony", score: 0.94, note: "Conscious sound that aligns the field" },
      { axis: "Expression", score: 0.87, note: "Voice and presence as living art" },
    ],
    links: [
      { label: "Instagram", href: "#" },
      { label: "Website", href: "#" },
    ],
    type: "human",
    location: "Global (healing arts)",
  },
};

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
    return fetchJsonOrNull<Record<string, unknown>>(
      `${base}/api/graph/nodes/${encodeURIComponent(`contributor:${id}`)}`,
      {},
      5000,
    );
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
    creations.push({
      kind,
      name: (fullAsset?.name as string) || edge.to_node?.name || "Untitled",
      url: (fullAsset?.canonical_url as string) || null,
      image_url: (fullAsset?.image_url as string) || null,
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
  const curated = CURATED_PRESENCES[id];
  if (curated) {
    return {
      title: `${curated.name} — Coherence Network`,
      description: curated.bio,
      openGraph: {
        images: [{ url: curated.heroImage }],
      },
    };
  }
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

function renderCuratedPresence(presence: CuratedPresence) {
  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 space-y-12">
      <div className="relative h-[60vh] min-h-[420px] w-full overflow-hidden rounded-3xl">
        <Image
          src={presence.heroImage}
          alt={presence.name}
          fill
          className="object-cover"
          priority
          unoptimized
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/80" />
        <div className="absolute bottom-0 left-0 right-0 p-8 md:p-12">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-white/70 mb-3">
              {presence.type} · {presence.location}
            </div>
            <h1 className="text-6xl md:text-7xl font-light tracking-tight text-white mb-4">
              {presence.name}
            </h1>
            <p className="text-2xl text-white/90 max-w-2xl">{presence.tagline}</p>
          </div>
        </div>
      </div>

      <div className="prose prose-lg max-w-none text-foreground/90">
        <p>{presence.bio}</p>
      </div>

      <section>
        <div className="flex items-center gap-3 mb-6">
          <div className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
            Resonance with the Living Collective
          </div>
          <div className="flex-1 h-px bg-border" />
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {presence.resonance.map((r) => (
            <div key={r.axis} className="rounded-2xl border border-border/50 bg-card p-6">
              <div className="flex items-baseline justify-between mb-3">
                <div className="font-medium text-lg">{r.axis}</div>
                <div className="text-sm tabular-nums text-[hsl(var(--primary))] font-mono">
                  {Math.round(r.score * 100)}%
                </div>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed">{r.note}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-4">
          Public presence
        </div>
        <div className="flex flex-wrap gap-3">
          {presence.links.map((link) => (
            <AttributedExternalLink
              key={link.href}
              href={link.href}
              entityId={`presence-link:${presence.slug}:${link.label
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-|-$/g, "")}`}
              className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2 text-sm hover:bg-accent transition-colors"
            >
              {link.label} →
            </AttributedExternalLink>
          ))}
        </div>
      </section>

      <div className="pt-8 border-t border-border/50 text-center">
        <p className="text-sm text-muted-foreground mb-4">This presence is part of the Living Collective.</p>
        <Button asChild size="lg" className="rounded-full px-10">
          <Link href="/begin">Weave into the field</Link>
        </Button>
      </div>
    </main>
  );
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
  const curatedPresence = CURATED_PRESENCES[id];
  if (curatedPresence) return renderCuratedPresence(curatedPresence);

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

  // When the graph node carries a canonical_url, this identity has an
  // outward-facing presence. Render the polished presence page —
  // hero, platforms, creations, lineage — before calling contributor
  // endpoints that only apply to local human profiles.
  const graphNode = await fetchGraphNode(id);
  if (graphNode && typeof graphNode.canonical_url === "string" && graphNode.canonical_url) {
    const nodeId = (graphNode.id as string) || id;
    const [creations, inspiredBy] = await Promise.all([
      fetchCreations(nodeId),
      fetchIdentityInspiredBy(nodeId),
    ]);
    return (
      <PresencePage identity={nodeToPresenceIdentity(graphNode, creations, inspiredBy)} />
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
      <PresencePage identity={nodeToPresenceIdentity(graphNode, creations, inspiredBy)} />
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

      {/* Quiet doorway */}
      <div className="pt-2">
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
