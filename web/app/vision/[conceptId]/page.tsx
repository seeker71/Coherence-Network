import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getApiBase } from "@/lib/api";
import type { Concept, Edge, RelatedItems, LCConcept } from "@/lib/types/vision";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import {
  DEFAULT_LOCALE,
  isSupportedLocale,
  type LocaleCode,
  type LanguageMeta,
} from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { createLocaleFetch } from "@/lib/locale-fetch";

import { LevelBadge } from "./_components/LevelBadge";
import { StoryContent } from "./_components/StoryContent";
import { ConnectedConcepts } from "./_components/ConnectedConcepts";
import { FrequencyDisplay } from "./_components/FrequencyDisplay";
import { StructuredContent } from "./_components/StructuredContent";
import { TrackingSuggestion } from "./_components/TrackingSuggestion";
import { ReaderPresence } from "./_components/ReaderPresence";
import { WorldSignals } from "./_components/WorldSignals";
import { EnergyContributors } from "./_components/EnergyContributors";
import { ResonantAssets } from "./_components/ResonantAssets";
import { ConceptVoices } from "./_components/ConceptVoices";
import { ReactionBar } from "@/components/ReactionBar";

export const dynamic = "force-dynamic";

/* ── Data fetching ─────────────────────────────────────────────────── */

async function fetchConcept(id: string, lang?: LocaleCode): Promise<Concept | null> {
  const base = getApiBase();
  // Always forward the lang — the API decides whether a view exists and what
  // to return. Omitting lang would surface the anchor (freshest) view, which
  // is correct for "no preference" but wrong for "explicitly chose English".
  const qs = lang ? `?lang=${lang}` : "";
  try {
    const res = await fetch(`${base}/api/concepts/${id}${qs}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

async function fetchEdges(id: string): Promise<Edge[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}/edges`, { next: { revalidate: 30 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch { return []; }
}

async function fetchAllLC(lang: LocaleCode): Promise<LCConcept[]> {
  const base = getApiBase();
  const qs = lang === DEFAULT_LOCALE ? "?limit=200" : `?limit=200&lang=${lang}`;
  try {
    const res = await fetch(`${base}/api/concepts/domain/living-collective${qs}`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.items || [];
  } catch { return []; }
}

async function fetchRelated(id: string): Promise<RelatedItems> {
  const base = getApiBase();
  const empty = { concept_id: id, ideas: [], specs: [], total: 0 };
  try {
    const res = await fetch(`${base}/api/concepts/${id}/related`, { next: { revalidate: 30 } });
    if (!res.ok) return empty;
    return res.json();
  } catch { return empty; }
}

/* ── Metadata ──────────────────────────────────────────────────────── */

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ conceptId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const { conceptId } = await params;
  const sp = await searchParams;
  const raw = typeof sp.lang === "string" ? sp.lang : undefined;
  const lang: LocaleCode | undefined = isSupportedLocale(raw) ? raw : undefined;
  const concept = await fetchConcept(conceptId, lang);

  // Pull the most alive description: first from The Feeling section,
  // falling back to the concept description
  const storyContent: string = concept?.story_content || "";
  const feelingMatch = storyContent.match(/## The Feeling\s*\n+([\s\S]*?)(?=\n##|\n→|$)/);
  const feelingText = feelingMatch?.[1]?.trim().split("\n")[0] || "";
  const ogDescription = feelingText.slice(0, 200) || concept?.description?.slice(0, 200) || "";
  const metaDescription = feelingText.slice(0, 300) || concept?.description?.slice(0, 300) || "";

  // Use the concept's visual as the OG image
  const ogImage = concept?.visual_path || undefined;

  return {
    title: concept ? `${concept.name} — The Living Collective` : "Concept",
    description: metaDescription,
    openGraph: {
      title: concept?.name || "Living Collective Concept",
      description: ogDescription,
      ...(ogImage ? { images: [{ url: ogImage, width: 1200, height: 630 }] } : {}),
    },
    twitter: {
      card: ogImage ? "summary_large_image" : "summary",
      title: concept?.name || "Living Collective Concept",
      description: ogDescription,
      ...(ogImage ? { images: [ogImage] } : {}),
    },
  };
}

/* ── Page ──────────────────────────────────────────────────────────── */

export default async function VisionConceptPage({
  params,
  searchParams,
}: {
  params: Promise<{ conceptId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { conceptId } = await params;
  const sp = await searchParams;
  const rawLang = typeof sp.lang === "string" ? sp.lang : undefined;
  const lang: LocaleCode = isSupportedLocale(rawLang) ? rawLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const [concept, edges, related, allLC] = await Promise.all([
    fetchConcept(conceptId, lang),
    fetchEdges(conceptId),
    fetchRelated(conceptId),
    fetchAllLC(lang),
  ]);

  if (!concept) notFound();

  const languageMeta = concept.language_meta;

  const isLC = concept.domains?.includes("living-collective");
  if (!isLC) redirect(`/concepts/${conceptId}`);

  // Name map for all LC concepts
  const nameMap: Record<string, string> = {};
  for (const c of allLC) {
    if (c.id && c.name) nameMap[c.id] = c.name;
  }

  // Frequency siblings (other concepts at the same Hz)
  const myHz = concept.sacred_frequency?.hz;
  const frequencySiblings = myHz
    ? allLC.filter((c) => c.id !== conceptId && c.sacred_frequency?.hz === myHz)
    : [];

  const visual = concept.visual_path;
  const lcEdges = edges.filter((e) => e.from.startsWith("lc-") || e.to.startsWith("lc-"));
  const outgoing = lcEdges.filter((e) => e.from === conceptId);
  const incoming = lcEdges.filter((e) => e.to === conceptId);
  const hasStory = !!concept.story_content;

  return (
    <main>
      {/* NFT sensing suggestion for unregistered readers */}
      <TrackingSuggestion conceptId={conceptId} />

      {/* Hero */}
      {visual ? (
        <section className="relative w-full aspect-[16/6] overflow-hidden">
          <Image src={visual} alt={concept.name} fill className="object-cover" sizes="100vw" priority unoptimized={visual.startsWith("http")} />
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-transparent to-transparent" />
        </section>
      ) : (
        <section className="h-32 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.06)_0%,_transparent_70%)]" />
      )}

      <div className={`relative ${visual ? "-mt-32 md:-mt-44" : ""} z-10 max-w-4xl mx-auto px-6 pb-20`}>
        {/* Language switcher */}
        <div className="mb-4">
          <LocaleSwitcher currentLang={lang} meta={languageMeta ?? null} />
        </div>

        {/* Breadcrumb */}
        <nav className="text-sm text-stone-500 mb-6 flex items-center gap-2" aria-label="breadcrumb">
          <Link href="/vision" className="hover:text-amber-400/80 transition-colors">{t("vision.breadcrumbRoot")}</Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">{concept.name}</span>
        </nav>

        {/* Title + level */}
        <div className="mb-6 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-4xl md:text-5xl font-extralight tracking-tight text-foreground">{concept.name}</h1>
            <LevelBadge level={concept.level} />
          </div>
          <p className="text-lg md:text-xl text-foreground/85 font-light leading-relaxed max-w-3xl">{concept.description}</p>
          <ReaderPresence conceptId={conceptId} />
        </div>

        {/*
         * Above-the-fold meeting affordance.
         *
         * A friend who lands here from a shared link should see the
         * two gestures that make this a meeting instead of a read-only
         * article — a quick reaction, and a doorway to leave their own
         * voice — in the first viewport, before the long prose below.
         * Both also appear again after the story for anyone who wants
         * to dwell first and respond after.
         */}
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <ReactionBar entityType="concept" entityId={conceptId} compact />
          <a
            href="#voices"
            className="inline-flex items-center gap-2 rounded-full border border-[hsl(var(--primary)/0.4)] bg-[hsl(var(--primary)/0.1)] hover:bg-[hsl(var(--primary)/0.2)] text-[hsl(var(--primary))] px-4 py-2 text-sm font-medium transition-colors"
          >
            <span aria-hidden="true">🗣</span>
            {t("vision.shareVoiceCta")}
          </a>
        </div>

        {/* Story mode (primary when story_content exists) */}
        {hasStory && (
          <>
            <StoryContent content={concept.story_content!} conceptId={conceptId} nameMap={nameMap} />

            {/* Who brought this concept to life */}
            <div className="max-w-3xl">
              <EnergyContributors conceptId={conceptId} />
            </div>

            {/* Multiple visual expressions — most resonant rises */}
            <div className="max-w-3xl">
              <ResonantAssets conceptId={conceptId} />
            </div>

            {/* Live signals from the world resonating with this concept */}
            <div className="max-w-3xl">
              <WorldSignals conceptId={conceptId} />
            </div>

            {/* Quick reactions — a pulse of felt-ness on this concept */}
            <section className="max-w-3xl pt-6">
              <ReactionBar entityType="concept" entityId={conceptId} compact />
            </section>

            {/* Community voices — lived experience from those living it.
                Anchor target for the above-fold "Share your voice ↓" link. */}
            <div id="voices" className="scroll-mt-16">
              <ConceptVoices conceptId={conceptId} />
            </div>

            <div className="max-w-3xl space-y-4 pt-8">
              <ConnectedConcepts outgoing={outgoing} incoming={incoming} nameMap={nameMap} mode="full" />
              <div className="flex gap-4 text-sm pt-4">
                <Link href="/vision" className="text-stone-500 hover:text-amber-300/80 transition-colors">{t("vision.backToRoot")}</Link>
                <Link href="/vision/realize" className="text-stone-500 hover:text-amber-300/80 transition-colors">{t("vision.livingIt")}</Link>
                <Link href="/vision/join" className="text-stone-500 hover:text-teal-300/80 transition-colors">{t("vision.join")}</Link>
                <Link href={`/vision/${conceptId}/edit`} className="text-stone-600 hover:text-amber-300/60 transition-colors ml-auto">{t("vision.editStory")}</Link>
              </div>
            </div>
          </>
        )}

        {/* Structured mode (fallback when no story_content) */}
        {!hasStory && (
          <StructuredContent
            concept={concept}
            conceptId={conceptId}
            outgoing={outgoing}
            incoming={incoming}
            nameMap={nameMap}
            related={related}
            frequencySiblings={frequencySiblings}
          />
        )}
      </div>
    </main>
  );
}
