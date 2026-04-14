import Image from "next/image";
import Link from "next/link";
import {
  galleryImagePath,
  placeToLink,
  RESOURCE_ICONS,
  CLIMATE_LABELS,
} from "@/lib/vision-utils";
import type { Concept, Edge, RelatedItems } from "@/lib/types/vision";
import { ConnectedConcepts } from "./ConnectedConcepts";
import { FrequencyDisplay } from "./FrequencyDisplay";
import type { LCConcept } from "@/lib/types/vision";

export function StructuredContent({
  concept,
  conceptId,
  outgoing,
  incoming,
  nameMap,
  related,
  frequencySiblings,
}: {
  concept: Concept;
  conceptId: string;
  outgoing: Edge[];
  incoming: Edge[];
  nameMap: Record<string, string>;
  related: RelatedItems;
  frequencySiblings: LCConcept[];
}) {
  return (
    <>
      {concept.details && (
        <div className="mb-10 max-w-3xl">
          <p className="text-base text-stone-400 leading-relaxed">{concept.details}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-8">
          {/* How it fits */}
          {concept.how_it_fits && (
            <section className="rounded-2xl border border-amber-800/20 bg-amber-900/10 p-6 space-y-3">
              <h2 className="text-sm font-medium text-amber-400/70 uppercase tracking-wider">How it fits into the whole</h2>
              <p className="text-stone-300 leading-relaxed">{concept.how_it_fits}</p>
            </section>
          )}

          {/* Examples */}
          {concept.examples && concept.examples.length > 0 && (
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
              <h2 className="text-lg font-light text-stone-300">Living examples</h2>
              <div className="space-y-3">
                {concept.examples.map((ex, i) => {
                  const dashIdx = ex.indexOf(" \u2014 ");
                  const title = dashIdx > 0 ? ex.slice(0, dashIdx) : null;
                  const body = dashIdx > 0 ? ex.slice(dashIdx) : ex;
                  return (
                    <div key={i} className="flex gap-3 text-sm text-stone-400 leading-relaxed">
                      <span className="text-amber-500/50 mt-0.5 shrink-0">{"\u2726"}</span>
                      <span>
                        {title ? (
                          <>
                            <a href={`https://en.wikipedia.org/wiki/Special:Search/${encodeURIComponent(title)}`}
                              target="_blank" rel="noopener noreferrer"
                              className="text-stone-300 hover:text-amber-300/80 transition-colors border-b border-stone-700/40 hover:border-amber-500/30">
                              {title}
                            </a>
                            {body}
                          </>
                        ) : ex}
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Aligned places */}
          {concept.aligned_places && concept.aligned_places.length > 0 && (
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
              <h2 className="text-lg font-light text-stone-300">Places already expressing this</h2>
              <div className="space-y-4">
                {concept.aligned_places.map((place, i) => {
                  const internalLink = placeToLink(place.name);
                  return (
                    <div key={i} className="space-y-1">
                      <div className="flex items-baseline gap-2">
                        {internalLink ? (
                          <Link href={internalLink} className="text-amber-300/80 hover:text-amber-300 transition-colors font-medium">
                            {place.name} &rarr;
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
                See all aligned communities &rarr;
              </Link>
            </section>
          )}

          {/* Aligned communities */}
          {concept.aligned_communities && concept.aligned_communities.length > 0 && (
            <section className="rounded-2xl border border-violet-800/20 bg-violet-900/10 p-6 space-y-4">
              <h2 className="text-lg font-light text-stone-300">Communities embodying this</h2>
              <div className="space-y-3">
                {concept.aligned_communities.map((comm, i) => {
                  const internalLink = placeToLink(comm.name);
                  return (
                    <div key={i} className="flex gap-3">
                      <span className="text-violet-400/50 mt-0.5 shrink-0">&loz;</span>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {internalLink ? (
                            <Link href={internalLink} className="text-violet-300/80 hover:text-violet-300 transition-colors font-medium text-sm">
                              {comm.name} &rarr;
                            </Link>
                          ) : (
                            <span className="text-violet-300/80 font-medium text-sm">{comm.name}</span>
                          )}
                          <a href={comm.url} target="_blank" rel="noopener noreferrer"
                            className="text-stone-600 hover:text-violet-300/60 transition-colors text-xs">
                            website &nearr;
                          </a>
                        </div>
                        <p className="text-sm text-stone-500 leading-relaxed">{comm.what}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
              <Link href="/vision/aligned" className="text-xs text-stone-600 hover:text-violet-300/60 transition-colors">
                See all aligned communities &rarr;
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

          {/* Visual gallery */}
          {concept.visuals && concept.visuals.length > 0 && (
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
              <h2 className="text-lg font-light text-stone-300">How it looks and feels</h2>
              <div className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-4 -mx-2 px-2">
                {concept.visuals.map((v, i) => (
                  <div key={i} className="flex-shrink-0 w-80 snap-start space-y-2">
                    <div className="relative aspect-[16/9] rounded-xl overflow-hidden bg-stone-800/50">
                      <Image
                        src={galleryImagePath(conceptId, i)}
                        alt={v.caption}
                        fill
                        className="object-cover"
                        sizes="320px"
                        unoptimized
                      />
                    </div>
                    <p className="text-xs text-stone-500 leading-relaxed">{v.caption}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Resources */}
          {concept.resources && concept.resources.length > 0 && (
            <section className="rounded-2xl border border-emerald-800/20 bg-emerald-900/10 p-6 space-y-4">
              <h2 className="text-sm font-medium text-emerald-400/70 uppercase tracking-wider">Resources &amp; References</h2>
              <div className="space-y-3">
                {concept.resources.map((r, i) => (
                  <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                    className="flex gap-3 p-3 rounded-xl hover:bg-emerald-900/20 transition-colors group">
                    <span className="text-lg flex-shrink-0 mt-0.5">{RESOURCE_ICONS[r.type] || "\u{1F4C4}"}</span>
                    <div className="flex-1 min-w-0 space-y-0.5">
                      <div className="text-sm text-emerald-300/80 group-hover:text-emerald-300 transition-colors font-medium">
                        {r.name} <span className="text-stone-600">&nearr;</span>
                      </div>
                      <p className="text-xs text-stone-500 leading-relaxed">{r.description}</p>
                    </div>
                    <span className="text-xs text-stone-700 flex-shrink-0 px-2 py-0.5 rounded-full border border-stone-800/30">{r.type}</span>
                  </a>
                ))}
              </div>
            </section>
          )}

          {/* Materials & methods */}
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

          {/* Scale notes */}
          {concept.scale_notes && (concept.scale_notes.small || concept.scale_notes.medium || concept.scale_notes.large) && (
            <section className="rounded-2xl border border-amber-800/20 bg-amber-900/5 p-6 space-y-4">
              <h2 className="text-sm font-medium text-amber-400/70 uppercase tracking-wider">At different scales</h2>
              <div className="grid md:grid-cols-3 gap-4">
                {([
                  { key: "small" as const, count: 50, color: "text-emerald-300/70", border: "border-stone-800/20 bg-stone-900/20" },
                  { key: "medium" as const, count: 100, color: "text-amber-300/70", border: "border-amber-800/10 bg-amber-900/5" },
                  { key: "large" as const, count: 200, color: "text-violet-300/70", border: "border-stone-800/20 bg-stone-900/20" },
                ] as const).map(({ key, count, color, border }) =>
                  concept.scale_notes?.[key] ? (
                    <div key={key} className={`space-y-2 p-4 rounded-xl border ${border}`}>
                      <div className={`text-xl font-light ${color}`}>{count}</div>
                      <div className="text-xs text-stone-600 uppercase tracking-wider mb-2">people</div>
                      <p className="text-sm text-stone-400 leading-relaxed">{concept.scale_notes[key]}</p>
                    </div>
                  ) : null
                )}
              </div>
            </section>
          )}

          {/* Climate adaptations */}
          {concept.location_adaptations && concept.location_adaptations.length > 0 && (
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
              <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Climate adaptations</h2>
              <div className="space-y-3">
                {concept.location_adaptations.map((la, i) => {
                  const cl = CLIMATE_LABELS[la.climate] || { label: la.climate, color: "bg-stone-800/30 text-stone-400 border-stone-700/30" };
                  return (
                    <div key={i} className="flex gap-3 items-start">
                      <span className={`text-xs px-2 py-0.5 rounded-full border flex-shrink-0 mt-0.5 ${cl.color}`}>{cl.label}</span>
                      <p className="text-sm text-stone-400 leading-relaxed">{la.notes}</p>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Cost notes */}
          {concept.cost_notes && (
            <section className="rounded-2xl border border-emerald-800/20 bg-emerald-900/5 p-6 space-y-3">
              <h2 className="text-sm font-medium text-emerald-400/70 uppercase tracking-wider">Practical costs</h2>
              <div className="space-y-2">
                {concept.cost_notes.split("\n").filter((line: string) => line.trim()).map((line: string, i: number) => {
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

          <ConnectedConcepts outgoing={outgoing} incoming={incoming} nameMap={nameMap} mode="full" />

          {/* Related ideas */}
          <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
            <h2 className="text-lg font-light text-stone-300">
              {related.total > 0
                ? `Ideas resonating with this concept (${related.total})`
                : "This concept is waiting for contributions"}
            </h2>
            {related.ideas.length > 0 ? (
              <div className="space-y-2">
                {related.ideas.map((ideaId) => (
                  <Link key={ideaId} href={`/ideas/${ideaId}`}
                    className="block py-2 px-3 rounded-xl hover:bg-stone-800/40 transition-colors text-stone-400 hover:text-stone-200 text-sm">
                    {ideaId}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-stone-500 leading-relaxed">
                No ideas have been tagged with this concept yet. Be the first to contribute.
              </p>
            )}
            <Link href={`/contribute?tags=living-collective,${conceptId}`}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all text-sm font-medium">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M12 5v14m-7-7h14" />
              </svg>
              Contribute to this vision
            </Link>
          </section>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {concept.keywords && concept.keywords.length > 0 && (
            <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
              <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Frequencies</h2>
              <div className="flex flex-wrap gap-1.5">
                {concept.keywords.map((kw) => (
                  <span key={kw} className="text-xs px-2 py-1 rounded-full bg-stone-800/60 text-stone-400">{kw}</span>
                ))}
              </div>
            </section>
          )}

          {concept.sacred_frequency && (
            <FrequencyDisplay frequency={concept.sacred_frequency} siblings={frequencySiblings} mode="sidebar" />
          )}

          <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-3">
            <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Navigate</h2>
            <div className="space-y-2 text-sm">
              <Link href="/vision" className="block text-stone-400 hover:text-amber-300/80 transition-colors">&larr; The Living Collective</Link>
              <Link href="/vision/join" className="block text-stone-400 hover:text-teal-300/80 transition-colors">Join the vision</Link>
              <Link href="/concepts/garden?domain=living-collective" className="block text-stone-400 hover:text-teal-300/80 transition-colors">Browse all concepts</Link>
            </div>
          </section>

          <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 space-y-2 text-xs text-stone-600">
            <div><span className="text-stone-500">ID:</span> <span className="font-mono">{concept.id}</span></div>
            <div><span className="text-stone-500">Domain:</span> {concept.domains?.join(", ") || "\u2014"}</div>
          </section>
        </div>
      </div>
    </>
  );
}
