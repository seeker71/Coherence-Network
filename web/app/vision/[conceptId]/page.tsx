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
  "lc-v-shelter-organism": "/visuals/10-living-space.png",
  "lc-network": "/visuals/11-the-network.png",
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
  const [concept, edges, related] = await Promise.all([
    fetchConcept(conceptId),
    fetchEdges(conceptId),
    fetchRelated(conceptId),
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

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Main content */}
          <div className="md:col-span-2 space-y-8">
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
                        {e.to.replace("lc-", "").replace("lc-v-", "").replace(/-/g, " ")}
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
                        {e.from.replace("lc-", "").replace("lc-v-", "").replace(/-/g, " ")}
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

            {/* Explore */}
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
              <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Explore</h2>
              <div className="space-y-2 text-sm">
                <Link href="/vision" className="block text-stone-400 hover:text-amber-300/80 transition-colors">
                  ← The Living Collective
                </Link>
                <Link href="/concepts/garden?domain=living-collective" className="block text-stone-400 hover:text-teal-300/80 transition-colors">
                  Concept Garden
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
