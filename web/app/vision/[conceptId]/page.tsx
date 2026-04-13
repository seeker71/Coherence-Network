import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

/* ── Types ─────────────────────────────────────────────────────────── */

type Concept = {
  id: string;
  name: string;
  description: string;
  typeId?: string;
  level?: number;
  keywords?: string[];
  axes?: string[];
  domains?: string[];
  parentConcepts?: string[];
  childConcepts?: string[];
  // Rich content fields (stored in graph node properties)
  details?: string;
  examples?: string[];
  aligned_places?: Array<{ name: string; location: string; note: string }>;
  aligned_communities?: Array<{ name: string; url: string; what: string }>;
  how_it_fits?: string;
  blueprint_notes?: string;
  visualization_notes?: string;
};

type Edge = {
  id: string;
  from: string;
  to: string;
  type: string;
};

type RelatedItems = {
  concept_id: string;
  ideas: string[];
  specs: string[];
  total: number;
};

/* ── Visual mapping ────────────────────────────────────────────────── */

const VISUAL_MAP: Record<string, string> = {
  // Root concepts (11)
  "lc-pulse": "/visuals/01-the-pulse.png",
  "lc-sensing": "/visuals/02-sensing.png",
  "lc-attunement": "/visuals/03-attunement.png",
  "lc-vitality": "/visuals/04-vitality.png",
  "lc-nourishing": "/visuals/05-nourishing.png",
  "lc-resonating": "/visuals/06-resonating.png",
  "lc-expressing": "/visuals/07-expressing.png",
  "lc-spiraling": "/visuals/08-spiraling.png",
  "lc-field-sensing": "/visuals/09-field-intelligence.png",
  "lc-v-living-spaces": "/visuals/10-living-space.png",
  "lc-network": "/visuals/11-the-network.png",
  // Emerging visions (8)
  "lc-v-ceremony": "/visuals/v-ceremony.png",
  "lc-v-harmonizing": "/visuals/v-harmonizing.png",
  "lc-v-food-practice": "/visuals/v-food-practice.png",
  "lc-v-shelter-organism": "/visuals/v-shelter-organism.png",
  "lc-v-comfort-joy": "/visuals/v-comfort-joy.png",
  "lc-v-play-expansion": "/visuals/v-play-expansion.png",
  "lc-v-inclusion-diversity": "/visuals/v-inclusion.png",
  "lc-v-freedom-expression": "/visuals/v-freedom.png",
  // Sacred spaces (8)
  "lc-space": "/visuals/space-hearth-interior.png",
  "lc-rest": "/visuals/space-nest-ground.png",
  "lc-stillness": "/visuals/space-stillness-sanctuary.png",
  "lc-nourishment": "/visuals/space-hearth-interior.png",
  "lc-offering": "/visuals/space-creation-arc-overview.png",
  "lc-beauty": "/visuals/space-creation-arc-overview.png",
  // Practices
  "lc-play": "/visuals/life-children-play.png",
  "lc-intimacy": "/visuals/practice-tantra-circle.png",
  "lc-ceremony": "/visuals/practice-drum-circle.png",
  "lc-transmission": "/visuals/practice-sound-healing.png",
  "lc-discovery": "/visuals/nature-food-forest-walk.png",
  // Nature
  "lc-land": "/visuals/nature-food-forest-walk.png",
  "lc-energy": "/visuals/nature-living-roof-close.png",
  "lc-health": "/visuals/life-breathwork.png",
  // Cycle
  "lc-rhythm": "/visuals/08-spiraling.png",
  "lc-elders": "/visuals/practice-storytelling-elder.png",
  "lc-composting": "/visuals/nature-herb-spiral.png",
  "lc-circulation": "/visuals/05-nourishing.png",
  "lc-harmonic-rebalancing": "/visuals/practice-drum-circle.png",
  "lc-field-edge": "/visuals/life-nomad-arrival.png",
  "lc-attunement-joining": "/visuals/life-nomad-arrival.png",
  "lc-instruments": "/visuals/09-field-intelligence.png",
  "lc-phase-transitions": "/visuals/08-spiraling.png",
};

/* ── Level labels in vitality language ─────────────────────────────── */

function levelLabel(level?: number) {
  const labels: Record<number, string> = {
    0: "Root Pulse",
    1: "System / Flow",
    2: "Living Expression",
    3: "Vocabulary",
  };
  const colors: Record<number, string> = {
    0: "border-amber-500/40 text-amber-300/90",
    1: "border-teal-500/40 text-teal-300/90",
    2: "border-violet-500/40 text-violet-300/90",
    3: "border-stone-500/40 text-stone-400",
  };
  const l = level ?? 0;
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full border ${colors[l] || "border-stone-600 text-stone-400"}`}>
      {labels[l] || `Level ${l}`}
    </span>
  );
}

/* ── Data fetching ─────────────────────────────────────────────────── */

async function fetchConcept(id: string): Promise<Concept | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchEdges(id: string): Promise<Edge[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}/edges`, { next: { revalidate: 30 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function fetchLCNames(): Promise<Record<string, string>> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/domain/living-collective?limit=200`, { next: { revalidate: 60 } });
    if (!res.ok) return {};
    const data = await res.json();
    const items = data?.items || [];
    const map: Record<string, string> = {};
    for (const c of items) {
      if (c.id && c.name) map[c.id] = c.name;
    }
    return map;
  } catch {
    return {};
  }
}

async function fetchRelated(id: string): Promise<RelatedItems> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}/related`, { next: { revalidate: 30 } });
    if (!res.ok) return { concept_id: id, ideas: [], specs: [], total: 0 };
    return res.json();
  } catch {
    return { concept_id: id, ideas: [], specs: [], total: 0 };
  }
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

/* ── Edge type descriptions in vitality language ───────────────────── */

const EDGE_LABELS: Record<string, string> = {
  "resonates-with": "resonates with",
  "emerges-from": "emerges from",
  "enables": "enables",
  "embodies": "embodies",
  "instantiates": "gives form to",
  "complements": "complements",
  "fractal-scaling": "fractal of",
  "transforms-into": "transforms into",
  "catalyzes": "catalyzes",
};

/* ── Page ──────────────────────────────────────────────────────────── */

export default async function VisionConceptPage({ params }: { params: Promise<{ conceptId: string }> }) {
  const { conceptId } = await params;
  const [concept, edges, related, nameMap] = await Promise.all([
    fetchConcept(conceptId),
    fetchEdges(conceptId),
    fetchRelated(conceptId),
    fetchLCNames(),
  ]);

  if (!concept) notFound();

  const isLC = concept.domains?.includes("living-collective");
  if (!isLC) {
    // Non-LC concept — redirect to standard concept page
    return (
      <meta httpEquiv="refresh" content={`0; url=/concepts/${conceptId}`} />
    );
  }

  const visual = VISUAL_MAP[conceptId];
  const lcEdges = edges.filter(
    (e) => e.from.startsWith("lc-") || e.to.startsWith("lc-"),
  );
  const outgoing = lcEdges.filter((e) => e.from === conceptId);
  const incoming = lcEdges.filter((e) => e.to === conceptId);
  const isVision = conceptId.startsWith("lc-v-");
  const isVocab = concept.level === 3;

  return (
    <main>
      {/* Hero — visual or gradient */}
      {visual ? (
        <section className="relative w-full aspect-[16/6] overflow-hidden">
          <Image src={visual} alt={concept.name} fill className="object-cover" sizes="100vw" priority />
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-transparent to-transparent" />
        </section>
      ) : (
        <section className="h-32 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.06)_0%,_transparent_70%)]" />
      )}

      <div className={`relative ${visual ? "-mt-32 md:-mt-44" : ""} z-10 max-w-4xl mx-auto px-6 pb-20`}>
        {/* Breadcrumb */}
        <nav className="text-sm text-stone-500 mb-6 flex items-center gap-2">
          <Link href="/vision" className="hover:text-amber-400/80 transition-colors">
            The Living Collective
          </Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">{concept.name}</span>
        </nav>

        {/* Title + level */}
        <div className="mb-8 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-4xl md:text-5xl font-extralight tracking-tight text-white">
              {concept.name}
            </h1>
            {levelLabel(concept.level)}
          </div>
          <p className="text-lg md:text-xl text-stone-300 font-light leading-relaxed max-w-3xl">
            {concept.description}
          </p>
        </div>

        {/* Rich content — details, examples, aligned places, blueprint */}
        {concept.details && (
          <div className="mb-10 max-w-3xl">
            <p className="text-base text-stone-400 leading-relaxed">{concept.details}</p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Main content */}
          <div className="md:col-span-2 space-y-8">

            {/* How it fits */}
            {concept.how_it_fits && (
              <section className="rounded-2xl border border-amber-800/20 bg-amber-900/10 p-6 space-y-3">
                <h2 className="text-sm font-medium text-amber-400/70 uppercase tracking-wider">How it fits into the whole</h2>
                <p className="text-stone-300 leading-relaxed">{concept.how_it_fits}</p>
              </section>
            )}

            {/* Examples from nature, culture, practice */}
            {concept.examples && concept.examples.length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">Living examples</h2>
                <div className="space-y-3">
                  {(concept.examples as string[]).map((ex: string, i: number) => (
                    <div key={i} className="flex gap-3 text-sm text-stone-400 leading-relaxed">
                      <span className="text-amber-500/50 mt-0.5 shrink-0">✦</span>
                      <span>{ex}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Aligned places */}
            {concept.aligned_places && (concept.aligned_places as Array<{name: string; location: string; note: string}>).length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">Places already expressing this</h2>
                <div className="space-y-4">
                  {(concept.aligned_places as Array<{name: string; location: string; note: string}>).map((place, i: number) => (
                    <div key={i} className="space-y-1">
                      <div className="flex items-baseline gap-2">
                        <span className="text-stone-200 font-medium">{place.name}</span>
                        <span className="text-xs text-stone-600">{place.location}</span>
                      </div>
                      <p className="text-sm text-stone-500 leading-relaxed">{place.note}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Aligned communities — living examples with links */}
            {concept.aligned_communities && (concept.aligned_communities as Array<{name: string; url: string; what: string}>).length > 0 && (
              <section className="rounded-2xl border border-violet-800/20 bg-violet-900/10 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">Communities embodying this</h2>
                <div className="space-y-3">
                  {(concept.aligned_communities as Array<{name: string; url: string; what: string}>).map((comm, i: number) => (
                    <div key={i} className="flex gap-3">
                      <span className="text-violet-400/50 mt-0.5 shrink-0">◈</span>
                      <div className="space-y-0.5">
                        <a href={comm.url} target="_blank" rel="noopener noreferrer"
                          className="text-violet-300/80 hover:text-violet-300 transition-colors font-medium text-sm">
                          {comm.name} ↗
                        </a>
                        <p className="text-sm text-stone-500 leading-relaxed">{comm.what}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <Link href="/vision/aligned" className="text-xs text-stone-600 hover:text-violet-300/60 transition-colors">
                  See all aligned communities →
                </Link>
              </section>
            )}

            {/* Blueprint notes */}
            {concept.blueprint_notes && (
              <section className="rounded-2xl border border-teal-800/20 bg-teal-900/10 p-6 space-y-3">
                <h2 className="text-sm font-medium text-teal-400/70 uppercase tracking-wider">Blueprint notes</h2>
                <p className="text-stone-300 leading-relaxed text-sm">{concept.blueprint_notes}</p>
              </section>
            )}

            {/* Connected concepts */}
            {(outgoing.length > 0 || incoming.length > 0) && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">Connected Frequencies</h2>
                <div className="space-y-2">
                  {outgoing.map((e) => (
                    <Link
                      key={e.id}
                      href={`/vision/${e.to}`}
                      className="flex items-center gap-3 py-2 px-3 rounded-xl hover:bg-stone-800/40 transition-colors group"
                    >
                      <span className="text-xs text-amber-400/60 font-medium min-w-[120px]">
                        {EDGE_LABELS[e.type] || e.type}
                      </span>
                      <span className="text-stone-300 group-hover:text-amber-300/80 transition-colors">
                        {nameMap[e.to] || e.to.replace("lc-", "").replace(/-/g, " ")}
                      </span>
                      <span className="text-stone-700 ml-auto">→</span>
                    </Link>
                  ))}
                  {incoming.map((e) => (
                    <Link
                      key={e.id}
                      href={`/vision/${e.from}`}
                      className="flex items-center gap-3 py-2 px-3 rounded-xl hover:bg-stone-800/40 transition-colors group"
                    >
                      <span className="text-xs text-teal-400/60 font-medium min-w-[120px]">
                        {EDGE_LABELS[e.type] || e.type}
                      </span>
                      <span className="text-stone-300 group-hover:text-teal-300/80 transition-colors">
                        {nameMap[e.from] || e.from.replace("lc-", "").replace(/-/g, " ")}
                      </span>
                      <span className="text-stone-700 ml-auto">←</span>
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Ideas contributing to this vision */}
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
              <h2 className="text-lg font-light text-stone-300">
                {related.total > 0
                  ? `Ideas resonating with this concept (${related.total})`
                  : "This concept is waiting for contributions"}
              </h2>
              {related.ideas.length > 0 ? (
                <div className="space-y-2">
                  {related.ideas.map((ideaId) => (
                    <Link
                      key={ideaId}
                      href={`/ideas/${ideaId}`}
                      className="block py-2 px-3 rounded-xl hover:bg-stone-800/40 transition-colors text-stone-400 hover:text-stone-200 text-sm"
                    >
                      {ideaId}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-stone-500 leading-relaxed">
                  {isVision
                    ? "This vision is an open invitation. What does it look like in practice? How would you bring it to life? Share your ideas, designs, references, or lived experience."
                    : "No ideas have been tagged with this concept yet. Be the first to contribute — share how this frequency expresses in your experience."}
                </p>
              )}
              <Link
                href={`/contribute?tags=living-collective,${conceptId}`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all text-sm font-medium"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14m-7-7h14" />
                </svg>
                Contribute to this vision
              </Link>
            </section>

            {/* Parent concepts — hierarchy navigation */}
            {concept.parentConcepts && concept.parentConcepts.length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-3">
                <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Part of</h2>
                <div className="flex flex-wrap gap-2">
                  {concept.parentConcepts.filter((p) => p.startsWith("lc-")).map((pid) => (
                    <Link
                      key={pid}
                      href={`/vision/${pid}`}
                      className="px-3 py-1.5 rounded-full border border-stone-700/40 text-stone-400 hover:text-amber-300/80 hover:border-amber-500/30 transition-colors text-sm"
                    >
                      {pid.replace("lc-", "").replace(/-/g, " ")}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Child concepts */}
            {concept.childConcepts && concept.childConcepts.length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-3">
                <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Expresses through</h2>
                <div className="flex flex-wrap gap-2">
                  {concept.childConcepts.filter((c) => c.startsWith("lc-")).map((cid) => (
                    <Link
                      key={cid}
                      href={`/vision/${cid}`}
                      className="px-3 py-1.5 rounded-full border border-stone-700/40 text-stone-400 hover:text-teal-300/80 hover:border-teal-500/30 transition-colors text-sm"
                    >
                      {cid.replace("lc-", "").replace(/-/g, " ")}
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Keywords */}
            {concept.keywords && concept.keywords.length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
                <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Frequencies</h2>
                <div className="flex flex-wrap gap-1.5">
                  {concept.keywords.map((kw) => (
                    <span key={kw} className="text-xs px-2 py-1 rounded-full bg-stone-800/60 text-stone-400">
                      {kw}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Sacred frequency badge */}
            {(() => {
              const FREQ_MAP: Record<string, { hz: number; quality: string; color: string }> = {
                "lc-pulse": { hz: 432, quality: "Healing", color: "text-amber-300/80 border-amber-500/30" },
                "lc-sensing": { hz: 741, quality: "Consciousness", color: "text-violet-300/80 border-violet-500/30" },
                "lc-attunement": { hz: 432, quality: "Healing", color: "text-amber-300/80 border-amber-500/30" },
                "lc-vitality": { hz: 528, quality: "Transformation", color: "text-teal-300/80 border-teal-500/30" },
                "lc-nourishing": { hz: 174, quality: "Foundation", color: "text-rose-300/80 border-rose-500/30" },
                "lc-resonating": { hz: 528, quality: "Transformation", color: "text-teal-300/80 border-teal-500/30" },
                "lc-expressing": { hz: 741, quality: "Consciousness", color: "text-violet-300/80 border-violet-500/30" },
                "lc-spiraling": { hz: 432, quality: "Healing", color: "text-amber-300/80 border-amber-500/30" },
                "lc-field-sensing": { hz: 741, quality: "Consciousness", color: "text-violet-300/80 border-violet-500/30" },
              };
              const freq = FREQ_MAP[conceptId];
              return freq ? (
                <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-2">
                  <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Sacred Frequency</h2>
                  <div className={`text-2xl font-extralight ${freq.color}`}>{freq.hz} Hz</div>
                  <div className="text-xs text-stone-600">{freq.quality}</div>
                </section>
              ) : null;
            })()}

            {/* Explore — full navigation */}
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
              <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Explore</h2>
              <div className="space-y-2 text-sm">
                <Link href="/vision" className="block text-stone-400 hover:text-amber-300/80 transition-colors">
                  ← The Living Collective
                </Link>
                <Link href="/vision/lived" className="block text-stone-400 hover:text-amber-300/80 transition-colors">
                  The lived experience
                </Link>
                <Link href="/vision/realize" className="block text-stone-400 hover:text-amber-300/80 transition-colors">
                  How it becomes real
                </Link>
                <Link href="/vision/aligned" className="block text-stone-400 hover:text-violet-300/80 transition-colors">
                  Aligned communities
                </Link>
                <Link href="/vision/join" className="block text-stone-400 hover:text-teal-300/80 transition-colors">
                  Join the vision
                </Link>
                <Link href="/concepts/garden?domain=living-collective" className="block text-stone-400 hover:text-teal-300/80 transition-colors">
                  All 51 concepts
                </Link>
                <Link href="/resonance" className="block text-stone-400 hover:text-violet-300/80 transition-colors">
                  Resonance Discovery
                </Link>
              </div>
            </section>

            {/* Type info */}
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-2 text-xs text-stone-600">
              <div>
                <span className="text-stone-500">ID:</span>{" "}
                <span className="font-mono">{concept.id}</span>
              </div>
              <div>
                <span className="text-stone-500">Domain:</span>{" "}
                {concept.domains?.join(", ") || "—"}
              </div>
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}
