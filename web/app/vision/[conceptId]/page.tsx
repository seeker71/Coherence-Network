import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getApiBase } from "@/lib/api";
import type { Concept, Edge, RelatedItems, LCConcept } from "@/lib/types/vision";

import { LevelBadge } from "./_components/LevelBadge";
import { StoryContent } from "./_components/StoryContent";
import { ConnectedConcepts } from "./_components/ConnectedConcepts";
import { FrequencyDisplay } from "./_components/FrequencyDisplay";
import { StructuredContent } from "./_components/StructuredContent";

export const dynamic = "force-dynamic";

/* ── Data fetching ─────────────────────────────────────────────────── */

async function fetchConcept(id: string): Promise<Concept | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}`, { next: { revalidate: 30 } });
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

async function fetchAllLC(): Promise<LCConcept[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/domain/living-collective?limit=200`, { next: { revalidate: 60 } });
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

export async function generateMetadata({ params }: { params: Promise<{ conceptId: string }> }): Promise<Metadata> {
  const { conceptId } = await params;
  const concept = await fetchConcept(conceptId);
  return {
    title: concept ? `${concept.name} — The Living Collective` : "Concept",
    description: concept?.description?.slice(0, 300) || "",
    openGraph: {
      title: concept?.name || "Living Collective Concept",
      description: concept?.description?.slice(0, 200) || "",
    },
  };
}

/* ── Page ──────────────────────────────────────────────────────────── */

export default async function VisionConceptPage({ params }: { params: Promise<{ conceptId: string }> }) {
  const { conceptId } = await params;
  const [concept, edges, related, allLC] = await Promise.all([
    fetchConcept(conceptId),
    fetchEdges(conceptId),
    fetchRelated(conceptId),
    fetchAllLC(),
  ]);

  if (!concept) notFound();

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
        {/* Breadcrumb */}
        <nav className="text-sm text-stone-500 mb-6 flex items-center gap-2" aria-label="breadcrumb">
          <Link href="/vision" className="hover:text-amber-400/80 transition-colors">The Living Collective</Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">{concept.name}</span>
        </nav>

        {/* Title + level */}
        <div className="mb-8 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-4xl md:text-5xl font-extralight tracking-tight text-white">{concept.name}</h1>
            <LevelBadge level={concept.level} />
          </div>
          <p className="text-lg md:text-xl text-stone-300 font-light leading-relaxed max-w-3xl">{concept.description}</p>
        </div>

        {/* Story mode (primary when story_content exists) */}
        {hasStory && (
          <>
            <StoryContent content={concept.story_content!} conceptId={conceptId} nameMap={nameMap} />

            <div className="max-w-3xl space-y-4 pt-8">
              {concept.sacred_frequency && (
                <FrequencyDisplay frequency={concept.sacred_frequency} siblings={frequencySiblings} mode="inline" />
              )}
              <ConnectedConcepts outgoing={outgoing} incoming={incoming} nameMap={nameMap} mode="full" />
              <div className="flex gap-4 text-sm pt-4">
                <Link href="/vision" className="text-stone-500 hover:text-amber-300/80 transition-colors">&larr; The Living Collective</Link>
                <Link href="/vision/realize" className="text-stone-500 hover:text-amber-300/80 transition-colors">Living it</Link>
                <Link href="/vision/join" className="text-stone-500 hover:text-teal-300/80 transition-colors">Join</Link>
                <Link href={`/vision/${conceptId}/edit`} className="text-stone-600 hover:text-amber-300/60 transition-colors ml-auto">Edit story</Link>
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
