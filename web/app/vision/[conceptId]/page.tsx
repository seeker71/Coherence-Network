import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";
// PollinationsImage import removed — using pre-generated static images instead

export const dynamic = "force-dynamic";

/* ── Types ─────────────────────────────────────────────────────────── */

type Concept = {
  id: string;
  name: string;
  description: string;
  typeId?: string;
  level?: number;
  // Full living story (markdown) — the primary content
  story_content?: string;
  keywords?: string[];
  axes?: string[];
  domains?: string[];
  parentConcepts?: string[];
  childConcepts?: string[];
  // Rich content fields (all from graph node JSONB properties)
  details?: string;
  examples?: string[];
  aligned_places?: Array<{ name: string; location: string; note: string }>;
  aligned_communities?: Array<{ name: string; url: string; what: string }>;
  how_it_fits?: string;
  blueprint_notes?: string;
  visualization_notes?: string;
  visual_path?: string;
  sacred_frequency?: { hz: number; quality: string };
  // Deep enrichment fields
  resources?: Array<{ name: string; url: string; type: string; description: string }>;
  materials_and_methods?: Array<{ name: string; description: string }>;
  scale_notes?: { small?: string; medium?: string; large?: string };
  location_adaptations?: Array<{ climate: string; notes: string }>;
  visuals?: Array<{ prompt: string; caption: string; location?: string }>;
  cost_notes?: string;
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

/* ── Visual + frequency data now comes from the API (concept.visual_path, concept.sacred_frequency) ── */

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

type LCConcept = { id: string; name: string; level?: number; sacred_frequency?: { hz: number; quality: string }; visual_path?: string };

async function fetchAllLC(): Promise<LCConcept[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/domain/living-collective?limit=200`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.items || [];
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

/* ── Pollinations image URL generator ──────────────────────────────── */

function pollinationsUrl(prompt: string, seed = 42, width = 1024, height = 576): string {
  return `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=${width}&height=${height}&model=flux&nologo=true&seed=${seed}`;
}

const RESOURCE_ICONS: Record<string, string> = {
  blueprint: "📐",
  guide: "📖",
  video: "▶️",
  course: "🎓",
  community: "🏘️",
  book: "📕",
  wiki: "🌐",
  tool: "🔧",
  dataset: "📊",
};

const CLIMATE_LABELS: Record<string, { label: string; color: string }> = {
  temperate: { label: "Temperate", color: "bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20" },
  tropical: { label: "Tropical", color: "bg-amber-500/10 text-amber-400/80 border-amber-500/20" },
  arid: { label: "Arid", color: "bg-orange-500/10 text-orange-400/80 border-orange-500/20" },
  coastal: { label: "Coastal", color: "bg-sky-500/10 text-sky-400/80 border-sky-500/20" },
  alpine: { label: "Alpine", color: "bg-indigo-500/10 text-indigo-400/80 border-indigo-500/20" },
};

/* ── Known community mapping: place name → internal community page ID ── */

const PLACE_TO_COMMUNITY: Record<string, string> = {
  "auroville": "community-auroville",
  "findhorn": "community-findhorn",
  "findhorn foundation": "community-findhorn",
  "findhorn ecovillage": "community-findhorn",
  "tamera": "community-tamera",
  "damanhur": "community-damanhur",
  "gaviotas": "community-gaviotas",
  "earthship": "community-earthship",
  "earthship biotecture": "community-earthship",
  "new earth": "community-new-earth-micronation",
  "new earth micronation": "community-new-earth-micronation",
  "new earth horizon": "community-new-earth-horizon",
  "new earth exchange": "community-new-earth-exchange",
};

function placeToLink(name: string): string | null {
  const key = name.toLowerCase().trim();
  const id = PLACE_TO_COMMUNITY[key];
  return id ? `/vision/aligned/${id}` : null;
}

function communityToInternalLink(name: string): string | null {
  const key = name.toLowerCase().trim();
  for (const [place, id] of Object.entries(PLACE_TO_COMMUNITY)) {
    if (key.includes(place)) return `/vision/aligned/${id}`;
  }
  return null;
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
  const [concept, edges, related, allLC] = await Promise.all([
    fetchConcept(conceptId),
    fetchEdges(conceptId),
    fetchRelated(conceptId),
    fetchAllLC(),
  ]);

  if (!concept) notFound();

  const isLC = concept.domains?.includes("living-collective");
  if (!isLC) {
    return (
      <meta httpEquiv="refresh" content={`0; url=/concepts/${conceptId}`} />
    );
  }

  // Derive name map from full concept list
  const nameMap: Record<string, string> = {};
  for (const c of allLC) {
    if (c.id && c.name) nameMap[c.id] = c.name;
  }

  // Build frequency family — other concepts at the same Hz
  const myHz = concept.sacred_frequency?.hz;
  const frequencySiblings = myHz
    ? allLC.filter((c) => c.id !== conceptId && c.sacred_frequency?.hz === myHz)
    : [];

  const visual = concept.visual_path;
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
          <Image src={visual} alt={concept.name} fill className="object-cover" sizes="100vw" priority unoptimized={visual.startsWith("http")} />
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

        {/* Story content — the living narrative (primary display when available) */}
        {concept.story_content ? (
          <div className="mb-12 max-w-3xl space-y-6">
            {concept.story_content.split("\n\n").map((block, i) => {
              const trimmed = block.trim();
              if (!trimmed) return null;

              // Heading: ## Title
              if (trimmed.startsWith("## ")) {
                return <h2 key={i} className="text-2xl font-light text-stone-300 pt-8 pb-2">{trimmed.slice(3)}</h2>;
              }
              // Heading: ### Title
              if (trimmed.startsWith("### ")) {
                return <h3 key={i} className="text-lg font-light text-stone-400 pt-4 pb-1">{trimmed.slice(4)}</h3>;
              }
              // Blockquote
              if (trimmed.startsWith("> ")) {
                return (
                  <blockquote key={i} className="border-l-2 border-amber-500/30 pl-4 text-stone-400 italic leading-relaxed">
                    {trimmed.slice(2)}
                  </blockquote>
                );
              }
              // Inline visual: ![caption](visuals:prompt)
              const visualMatch = trimmed.match(/^!\[([^\]]*)\]\(visuals:([^)]+)\)$/);
              if (visualMatch) {
                const caption = visualMatch[1];
                const prompt = visualMatch[2];
                const seed = (concept.id || "").split("").reduce((a: number, c: string) => a + c.charCodeAt(0), 0) + i * 13;
                return (
                  <figure key={i} className="py-4">
                    <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-stone-800/50">
                      <Image
                        src={pollinationsUrl(prompt, seed)}
                        alt={caption}
                        fill
                        className="object-cover"
                        sizes="(max-width: 768px) 100vw, 768px"
                        unoptimized
                      />
                    </div>
                    <figcaption className="text-xs text-stone-600 mt-2 italic">{caption}</figcaption>
                  </figure>
                );
              }
              // List items (- text or - **bold** text)
              if (trimmed.startsWith("- ")) {
                const items = trimmed.split("\n").filter((l: string) => l.trim().startsWith("- "));
                return (
                  <ul key={i} className="space-y-2 pl-4">
                    {items.map((item: string, j: number) => (
                      <li key={j} className="text-sm text-stone-400 leading-relaxed list-disc"
                        dangerouslySetInnerHTML={{
                          __html: item.slice(2)
                            .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-stone-300">$1</strong>')
                            .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-amber-400/70 hover:text-amber-300 transition-colors">$1</a>')
                        }}
                      />
                    ))}
                  </ul>
                );
              }
              // Cross-references (→ lc-xxx, lc-yyy) — render as linked pills
              if (trimmed.startsWith("→ ")) {
                const refs = trimmed.slice(2).split(",").map((r: string) => r.trim()).filter(Boolean);
                return (
                  <div key={i} className="flex flex-wrap gap-2 pt-4">
                    <span className="text-xs text-stone-600">Connected:</span>
                    {refs.map((ref: string) => (
                      <Link key={ref} href={`/vision/${ref}`}
                        className="text-xs px-2 py-1 rounded-full border border-stone-700/30 text-stone-500 hover:text-amber-300/70 hover:border-amber-500/20 transition-colors">
                        {nameMap[ref] || ref.replace("lc-", "").replace("lc-v-", "").replace("lc-w-", "").replace(/-/g, " ")}
                      </Link>
                    ))}
                  </div>
                );
              }
              // Regular paragraph (handle bold, links, italic)
              return (
                <p key={i} className="text-base text-stone-400 leading-relaxed"
                  dangerouslySetInnerHTML={{
                    __html: trimmed
                      .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-stone-300">$1</strong>')
                      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
                      .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-amber-400/70 hover:text-amber-300 border-b border-amber-500/20 hover:border-amber-500/40 transition-colors">$1</a>')
                  }}
                />
              );
            })}
          </div>
        ) : concept.details ? (
          <div className="mb-10 max-w-3xl">
            <p className="text-base text-stone-400 leading-relaxed">{concept.details}</p>
          </div>
        ) : null}

        {/* Old structured content — only shown when NO story_content */}
        {!concept.story_content && (
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
                  {(concept.examples as string[]).map((ex: string, i: number) => {
                    // Extract the title part before the em dash for search linkability
                    const dashIdx = ex.indexOf(" — ");
                    const title = dashIdx > 0 ? ex.slice(0, dashIdx) : null;
                    const body = dashIdx > 0 ? ex.slice(dashIdx) : ex;
                    return (
                      <div key={i} className="flex gap-3 text-sm text-stone-400 leading-relaxed">
                        <span className="text-amber-500/50 mt-0.5 shrink-0">✦</span>
                        <span>
                          {title ? (
                            <>
                              <a
                                href={`https://en.wikipedia.org/wiki/Special:Search/${encodeURIComponent(title)}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-stone-300 hover:text-amber-300/80 transition-colors border-b border-stone-700/40 hover:border-amber-500/30"
                              >
                                {title}
                              </a>
                              {body}
                            </>
                          ) : (
                            ex
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Aligned places */}
            {concept.aligned_places && (concept.aligned_places as Array<{name: string; location: string; note: string}>).length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">Places already expressing this</h2>
                <div className="space-y-4">
                  {(concept.aligned_places as Array<{name: string; location: string; note: string}>).map((place, i: number) => {
                    const internalLink = placeToLink(place.name);
                    return (
                      <div key={i} className="space-y-1">
                        <div className="flex items-baseline gap-2">
                          {internalLink ? (
                            <Link href={internalLink} className="text-amber-300/80 hover:text-amber-300 transition-colors font-medium">
                              {place.name} →
                            </Link>
                          ) : (
                            <span className="text-stone-200 font-medium">{place.name}</span>
                          )}
                          <span className="text-xs text-stone-600">{place.location}</span>
                        </div>
                        <p className="text-sm text-stone-500 leading-relaxed">{place.note}</p>
                      </div>
                    );
                  })}
                </div>
                <Link href="/vision/aligned" className="text-xs text-stone-600 hover:text-amber-300/60 transition-colors">
                  See all aligned communities →
                </Link>
              </section>
            )}

            {/* Aligned communities — living examples with links */}
            {concept.aligned_communities && (concept.aligned_communities as Array<{name: string; url: string; what: string}>).length > 0 && (
              <section className="rounded-2xl border border-violet-800/20 bg-violet-900/10 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">Communities embodying this</h2>
                <div className="space-y-3">
                  {(concept.aligned_communities as Array<{name: string; url: string; what: string}>).map((comm, i: number) => {
                    const internalLink = communityToInternalLink(comm.name);
                    return (
                      <div key={i} className="flex gap-3">
                        <span className="text-violet-400/50 mt-0.5 shrink-0">◈</span>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            {internalLink ? (
                              <Link href={internalLink} className="text-violet-300/80 hover:text-violet-300 transition-colors font-medium text-sm">
                                {comm.name} →
                              </Link>
                            ) : (
                              <span className="text-violet-300/80 font-medium text-sm">{comm.name}</span>
                            )}
                            <a href={comm.url} target="_blank" rel="noopener noreferrer"
                              className="text-stone-600 hover:text-violet-300/60 transition-colors text-xs">
                              website ↗
                            </a>
                          </div>
                          <p className="text-sm text-stone-500 leading-relaxed">{comm.what}</p>
                        </div>
                      </div>
                    );
                  })}
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

            {/* ═══ Visual Gallery — pre-generated static images ═══ */}
            {concept.visuals && concept.visuals.length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
                <h2 className="text-lg font-light text-stone-300">How it looks and feels</h2>
                <div className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-4 -mx-2 px-2">
                  {concept.visuals.map((v, i) => {
                    // Pre-generated images stored at /visuals/generated/{conceptId}-{i}.jpg
                    // Falls back to Pollinations URL if static file doesn't exist
                    const staticPath = `/visuals/generated/${conceptId}-${i}.jpg`;
                    const seed = conceptId.split("").reduce((a, c) => a + c.charCodeAt(0), 0) + i * 17;
                    return (
                      <div key={i} className="flex-shrink-0 w-80 snap-start space-y-2">
                        <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-stone-800/50">
                          <Image
                            src={staticPath}
                            alt={v.caption}
                            fill
                            className="object-cover"
                            sizes="320px"
                            unoptimized
                          />
                        </div>
                        <p className="text-xs text-stone-500 leading-relaxed">{v.caption}</p>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* ═══ Resources & References — real blueprints, guides, videos ═══ */}
            {concept.resources && concept.resources.length > 0 && (
              <section className="rounded-2xl border border-emerald-800/20 bg-emerald-900/10 p-6 space-y-4">
                <h2 className="text-sm font-medium text-emerald-400/70 uppercase tracking-wider">Resources &amp; References</h2>
                <div className="space-y-3">
                  {concept.resources.map((r, i) => (
                    <a
                      key={i}
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex gap-3 p-3 rounded-xl hover:bg-emerald-900/20 transition-colors group"
                    >
                      <span className="text-lg flex-shrink-0 mt-0.5">{RESOURCE_ICONS[r.type] || "📄"}</span>
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <div className="text-sm text-emerald-300/80 group-hover:text-emerald-300 transition-colors font-medium">
                          {r.name} <span className="text-stone-600">↗</span>
                        </div>
                        <p className="text-xs text-stone-500 leading-relaxed">{r.description}</p>
                      </div>
                      <span className="text-xs text-stone-700 flex-shrink-0 px-2 py-0.5 rounded-full border border-stone-800/30">
                        {r.type}
                      </span>
                    </a>
                  ))}
                </div>
              </section>
            )}

            {/* ═══ Materials & Methods ═══ */}
            {concept.materials_and_methods && concept.materials_and_methods.length > 0 && (
              <section className="rounded-2xl border border-teal-800/20 bg-teal-900/10 p-6 space-y-4">
                <h2 className="text-sm font-medium text-teal-400/70 uppercase tracking-wider">Materials &amp; Methods</h2>
                <div className="space-y-4">
                  {concept.materials_and_methods.map((m, i) => (
                    <div key={i} className="space-y-1">
                      <h3 className="text-sm font-medium text-stone-300">{m.name}</h3>
                      <p className="text-sm text-stone-500 leading-relaxed">{m.description}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ═══ At Different Scales — 50 / 100 / 200 people ═══ */}
            {concept.scale_notes && (concept.scale_notes.small || concept.scale_notes.medium || concept.scale_notes.large) && (
              <section className="rounded-2xl border border-amber-800/20 bg-amber-900/5 p-6 space-y-4">
                <h2 className="text-sm font-medium text-amber-400/70 uppercase tracking-wider">At different scales</h2>
                <div className="grid md:grid-cols-3 gap-4">
                  {concept.scale_notes.small && (
                    <div className="space-y-2 p-4 rounded-xl border border-stone-800/20 bg-stone-900/20">
                      <div className="text-xl font-light text-emerald-300/70">50</div>
                      <div className="text-xs text-stone-600 uppercase tracking-wider mb-2">people</div>
                      <p className="text-sm text-stone-400 leading-relaxed">{concept.scale_notes.small}</p>
                    </div>
                  )}
                  {concept.scale_notes.medium && (
                    <div className="space-y-2 p-4 rounded-xl border border-amber-800/10 bg-amber-900/5">
                      <div className="text-xl font-light text-amber-300/70">100</div>
                      <div className="text-xs text-stone-600 uppercase tracking-wider mb-2">people</div>
                      <p className="text-sm text-stone-400 leading-relaxed">{concept.scale_notes.medium}</p>
                    </div>
                  )}
                  {concept.scale_notes.large && (
                    <div className="space-y-2 p-4 rounded-xl border border-stone-800/20 bg-stone-900/20">
                      <div className="text-xl font-light text-violet-300/70">200</div>
                      <div className="text-xs text-stone-600 uppercase tracking-wider mb-2">people</div>
                      <p className="text-sm text-stone-400 leading-relaxed">{concept.scale_notes.large}</p>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* ═══ Location Adaptations ═══ */}
            {concept.location_adaptations && concept.location_adaptations.length > 0 && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
                <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Climate adaptations</h2>
                <div className="space-y-3">
                  {concept.location_adaptations.map((la, i) => {
                    const cl = CLIMATE_LABELS[la.climate] || { label: la.climate, color: "bg-stone-800/30 text-stone-400 border-stone-700/30" };
                    return (
                      <div key={i} className="flex gap-3 items-start">
                        <span className={`text-xs px-2 py-0.5 rounded-full border flex-shrink-0 mt-0.5 ${cl.color}`}>
                          {cl.label}
                        </span>
                        <p className="text-sm text-stone-400 leading-relaxed">{la.notes}</p>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* ═══ Practical Costs ═══ */}
            {concept.cost_notes && (
              <section className="rounded-2xl border border-emerald-800/20 bg-emerald-900/5 p-6 space-y-3">
                <h2 className="text-sm font-medium text-emerald-400/70 uppercase tracking-wider">Practical costs</h2>
                <div className="space-y-2">
                  {concept.cost_notes.split("\n").filter((line: string) => line.trim()).map((line: string, i: number) => {
                    // Parse: - **Label**: description
                    const cleaned = line.replace(/^[-*]\s*/, "").trim();
                    const boldMatch = cleaned.match(/^\*\*([^*]+)\*\*[:\s]*(.*)/);
                    if (boldMatch) {
                      return (
                        <div key={i} className="text-sm leading-relaxed">
                          <span className="text-stone-300 font-medium">{boldMatch[1]}</span>
                          <span className="text-stone-500">: {boldMatch[2]}</span>
                        </div>
                      );
                    }
                    return <p key={i} className="text-sm text-stone-400 leading-relaxed">{cleaned}</p>;
                  })}
                </div>
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

            {/* Sacred frequency — with resonance family */}
            {concept.sacred_frequency && (
              <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-4">
                <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Sacred Frequency</h2>
                <div className={`text-3xl font-extralight ${
                  concept.sacred_frequency.hz === 432 ? "text-amber-300/80" :
                  concept.sacred_frequency.hz === 528 ? "text-teal-300/80" :
                  concept.sacred_frequency.hz === 741 ? "text-violet-300/80" :
                  concept.sacred_frequency.hz === 174 ? "text-rose-300/80" :
                  concept.sacred_frequency.hz === 285 ? "text-rose-200/70" :
                  concept.sacred_frequency.hz === 396 ? "text-orange-300/80" :
                  concept.sacred_frequency.hz === 417 ? "text-yellow-300/70" :
                  concept.sacred_frequency.hz === 639 ? "text-emerald-300/70" :
                  concept.sacred_frequency.hz === 852 ? "text-indigo-300/70" :
                  concept.sacred_frequency.hz === 963 ? "text-fuchsia-300/70" :
                  "text-stone-300"
                }`}>{concept.sacred_frequency.hz} Hz</div>
                <p className="text-xs text-stone-500 leading-relaxed">{concept.sacred_frequency.quality}</p>

                {/* Frequency family — other concepts vibrating at the same Hz */}
                {frequencySiblings.length > 0 && (
                  <div className="pt-2 border-t border-stone-800/30 space-y-2">
                    <p className="text-xs text-stone-600">
                      Resonates with {frequencySiblings.length} other{frequencySiblings.length === 1 ? "" : ""} concept{frequencySiblings.length === 1 ? "" : "s"} at this frequency:
                    </p>
                    <div className="space-y-1">
                      {frequencySiblings.map((sib) => (
                        <Link
                          key={sib.id}
                          href={`/vision/${sib.id}`}
                          className="block text-xs text-stone-500 hover:text-amber-300/70 transition-colors truncate"
                        >
                          {sib.name}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* Navigate */}
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
              <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Navigate</h2>
              <div className="space-y-2 text-sm">
                <Link href="/vision" className="block text-stone-400 hover:text-amber-300/80 transition-colors">
                  ← The Living Collective
                </Link>
                <Link href="/vision/join" className="block text-stone-400 hover:text-teal-300/80 transition-colors">
                  Join the vision
                </Link>
                <Link href="/concepts/garden?domain=living-collective" className="block text-stone-400 hover:text-teal-300/80 transition-colors">
                  Browse all concepts
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
        )}

        {/* Sidebar for story mode — frequency + navigate */}
        {concept.story_content && (
          <div className="max-w-3xl space-y-4 pt-8">
            {/* Sacred frequency */}
            {concept.sacred_frequency && (
              <div className="flex items-center gap-4 p-4 rounded-xl border border-stone-800/30 bg-stone-900/20">
                <div className={`text-2xl font-extralight ${
                  concept.sacred_frequency.hz === 432 ? "text-amber-300/80" :
                  concept.sacred_frequency.hz === 528 ? "text-teal-300/80" :
                  concept.sacred_frequency.hz === 741 ? "text-violet-300/80" :
                  concept.sacred_frequency.hz === 174 ? "text-rose-300/80" :
                  "text-stone-300"
                }`}>{concept.sacred_frequency.hz} Hz</div>
                <p className="text-xs text-stone-500">{concept.sacred_frequency.quality}</p>
                {frequencySiblings.length > 0 && (
                  <div className="flex flex-wrap gap-2 ml-auto">
                    {frequencySiblings.slice(0, 5).map((sib) => (
                      <Link key={sib.id} href={`/vision/${sib.id}`}
                        className="text-xs text-stone-600 hover:text-amber-300/60 transition-colors">
                        {sib.name}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Connected concepts from edges */}
            {(outgoing.length > 0 || incoming.length > 0) && (
              <div className="flex flex-wrap gap-2 p-4 rounded-xl border border-stone-800/30 bg-stone-900/20">
                <span className="text-xs text-stone-600 mr-2">Connected:</span>
                {outgoing.map((e) => (
                  <Link key={e.id} href={`/vision/${e.to}`}
                    className="text-xs px-2 py-1 rounded-full border border-stone-700/30 text-stone-500 hover:text-amber-300/70 hover:border-amber-500/20 transition-colors">
                    {nameMap[e.to] || e.to.replace("lc-", "").replace(/-/g, " ")}
                  </Link>
                ))}
                {incoming.map((e) => (
                  <Link key={e.id} href={`/vision/${e.from}`}
                    className="text-xs px-2 py-1 rounded-full border border-stone-700/30 text-stone-500 hover:text-teal-300/70 hover:border-teal-500/20 transition-colors">
                    {nameMap[e.from] || e.from.replace("lc-", "").replace(/-/g, " ")}
                  </Link>
                ))}
              </div>
            )}

            {/* Navigate */}
            <div className="flex gap-4 text-sm pt-4">
              <Link href="/vision" className="text-stone-500 hover:text-amber-300/80 transition-colors">← The Living Collective</Link>
              <Link href="/vision/realize" className="text-stone-500 hover:text-amber-300/80 transition-colors">Living it</Link>
              <Link href="/vision/join" className="text-stone-500 hover:text-teal-300/80 transition-colors">Join</Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
