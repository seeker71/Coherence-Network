import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";

type Concept = {
  id: string;
  name: string;
  description: string;
  typeId: string;
  level: number;
  keywords: string[];
  parentConcepts: string[];
  childConcepts: string[];
  axes: string[];
};

type EdgeEntry = {
  from: string;
  to: string;
  type: string;
  source: string;
  id?: string;
  created_by?: string;
  created_at?: string;
};

type ConceptEdges = {
  seed_edges: EdgeEntry[];
  user_edges: EdgeEntry[];
  total: number;
};

type TagEntry = {
  id: string;
  concept_id: string;
  entity_type: string;
  entity_id: string;
  tagged_by: string;
  tagged_at: string;
};

type RelatedEntities = {
  concept_id: string;
  tags: TagEntry[];
  by_type: Record<string, TagEntry[]>;
  total: number;
};

const AXIS_COLORS: Record<string, string> = {
  temporal: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  causal: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  ucore: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  spatial: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  social: "bg-green-500/20 text-green-300 border-green-500/30",
  epistemic: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  ethical: "bg-red-500/20 text-red-300 border-red-500/30",
  energetic: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  informational: "bg-teal-500/20 text-teal-300 border-teal-500/30",
};

function axisChipClass(axis: string): string {
  return AXIS_COLORS[axis] ?? "bg-gray-500/20 text-gray-300 border-gray-500/30";
}

async function loadConcept(id: string): Promise<Concept | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/concepts/${encodeURIComponent(id)}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as Concept;
  } catch {
    return null;
  }
}

async function loadEdges(id: string): Promise<ConceptEdges | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/concepts/${encodeURIComponent(id)}/edges`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as ConceptEdges;
  } catch {
    return null;
  }
}

async function loadRelated(id: string): Promise<RelatedEntities | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/concepts/${encodeURIComponent(id)}/related`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as RelatedEntities;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const concept = await loadConcept(id);
  if (!concept) return { title: "Concept Not Found" };
  return {
    title: `${concept.name} — Concepts`,
    description: concept.description || `Explore ${concept.name} in the Living Codex ontology.`,
  };
}

export default async function ConceptDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [concept, edges, related] = await Promise.all([
    loadConcept(id),
    loadEdges(id),
    loadRelated(id),
  ]);

  if (!concept) notFound();

  const parents = concept.parentConcepts ?? [];
  const children = concept.childConcepts ?? [];

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500 mb-6">
        <Link href="/concepts" className="hover:text-gray-300 transition-colors">
          Concepts
        </Link>
        <span className="mx-2">/</span>
        <span className="text-gray-300">{concept.name}</span>
      </nav>

      {/* Concept header */}
      <div className="bg-gray-900/60 border border-gray-700/40 rounded-2xl p-6 mb-6">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-2xl font-bold text-white">{concept.name}</h1>
            <span className="text-xs text-gray-500 mt-1 block">
              {concept.id} · Level {concept.level} · {concept.typeId}
            </span>
          </div>
        </div>

        <p className="text-gray-300 text-sm mb-4">{concept.description || "No description available."}</p>

        {/* Axes */}
        {concept.axes && concept.axes.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {concept.axes.map((axis) => (
              <Link
                key={axis}
                href={`/concepts?axis=${encodeURIComponent(axis)}`}
                className={`px-2.5 py-0.5 rounded-full text-xs border hover:opacity-80 transition-opacity ${axisChipClass(axis)}`}
              >
                {axis}
              </Link>
            ))}
          </div>
        )}

        {/* Keywords */}
        {concept.keywords && concept.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {concept.keywords.map((kw) => (
              <span
                key={kw}
                className="px-2.5 py-0.5 rounded-full text-xs bg-gray-700/30 text-gray-400 border border-gray-600/30"
              >
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Parent concepts */}
        {parents.length > 0 && (
          <section className="bg-gray-900/60 border border-gray-700/40 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
              Parent Concepts ({parents.length})
            </h2>
            <ul className="space-y-1.5">
              {parents.map((pid) => (
                <li key={pid}>
                  <Link
                    href={`/concepts/${pid}`}
                    className="text-sm text-purple-400 hover:text-purple-300 transition-colors"
                  >
                    ↑ {pid}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Child concepts */}
        {children.length > 0 && (
          <section className="bg-gray-900/60 border border-gray-700/40 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
              Child Concepts ({children.length})
            </h2>
            <ul className="space-y-1.5">
              {children.map((cid) => (
                <li key={cid}>
                  <Link
                    href={`/concepts/${cid}`}
                    className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                  >
                    ↓ {cid}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* User-created edges */}
      {edges && edges.user_edges.length > 0 && (
        <section className="bg-gray-900/60 border border-gray-700/40 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            User Edges ({edges.user_edges.length})
          </h2>
          <div className="space-y-2">
            {edges.user_edges.map((edge) => (
              <div
                key={edge.id ?? `${edge.from}-${edge.to}`}
                className="flex items-center gap-2 text-sm"
              >
                <Link href={`/concepts/${edge.from}`} className="text-gray-300 hover:text-white">
                  {edge.from}
                </Link>
                <span className="text-xs px-2 py-0.5 rounded bg-gray-700/50 text-gray-400">
                  {edge.type}
                </span>
                <Link href={`/concepts/${edge.to}`} className="text-gray-300 hover:text-white">
                  {edge.to}
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Related entities */}
      {related && related.total > 0 && (
        <section className="bg-gray-900/60 border border-gray-700/40 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            Tagged Entities ({related.total})
          </h2>
          {Object.entries(related.by_type).map(([etype, tags]) => (
            <div key={etype} className="mb-4">
              <div className="text-xs text-gray-500 uppercase mb-2">{etype}s ({tags.length})</div>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => {
                  const href =
                    etype === "idea"
                      ? `/ideas/${tag.entity_id}`
                      : etype === "spec"
                      ? `/specs/${tag.entity_id}`
                      : null;
                  const content = (
                    <span className="px-2.5 py-1 rounded-lg text-xs bg-gray-700/30 text-gray-300 border border-gray-600/30 hover:border-gray-400 transition-colors">
                      {tag.entity_id}
                    </span>
                  );
                  return href ? (
                    <Link key={tag.id} href={href}>
                      {content}
                    </Link>
                  ) : (
                    <span key={tag.id}>{content}</span>
                  );
                })}
              </div>
            </div>
          ))}
        </section>
      )}

      {related && related.total === 0 && (
        <section className="bg-gray-900/40 border border-dashed border-gray-700/40 rounded-xl p-5 mb-6 text-center">
          <p className="text-gray-500 text-sm">
            No ideas, specs, or news tagged with this concept yet.
          </p>
          <p className="text-gray-600 text-xs mt-1">
            Use <code className="text-gray-400">POST /api/concepts/{concept.id}/tags</code> or the CLI to tag entities.
          </p>
        </section>
      )}

      {/* Back link */}
      <div className="pt-4 border-t border-gray-800">
        <Link href="/concepts" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
          ← Back to all concepts
        </Link>
      </div>
    </main>
  );
}
