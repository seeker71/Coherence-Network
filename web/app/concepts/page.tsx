import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Concepts — Living Codex Ontology",
  description: "Browse 184 universal concepts from the Living Codex U-CORE ontology. Navigate typed relationships, resonance axes, and linked ideas.",
};

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

type ConceptsResponse = {
  items: Concept[];
  total: number;
  limit: number;
  offset: number;
};

type OntologyStats = {
  concepts: number;
  seed_concepts: number;
  custom_concepts: number;
  relationship_types: number;
  axes: number;
  user_edges: number;
  entity_tags: number;
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

async function loadConcepts(
  limit = 184,
  offset = 0,
  axis?: string,
): Promise<ConceptsResponse | null> {
  try {
    const api = getApiBase();
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (axis) params.set("axis", axis);
    const res = await fetch(`${api}/api/concepts?${params}`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return (await res.json()) as ConceptsResponse;
  } catch {
    return null;
  }
}

async function loadStats(): Promise<OntologyStats | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/concepts/stats`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return (await res.json()) as OntologyStats;
  } catch {
    return null;
  }
}

export default async function ConceptsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await searchParams;
  const filterAxis = sp.axis ?? undefined;

  const [data, stats] = await Promise.all([
    loadConcepts(184, 0, filterAxis),
    loadStats(),
  ]);

  const concepts = data?.items ?? [];

  // Collect all unique axes present
  const allAxes = Array.from(
    new Set(concepts.flatMap((c) => c.axes ?? []))
  ).sort();

  return (
    <main className="max-w-6xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">
          Living Codex Ontology
        </h1>
        <p className="text-gray-400 text-sm max-w-2xl">
          184 universal concepts, 46 relationship types, and 53 resonance axes
          from the U-CORE ontology. Every idea, spec, and news item can be
          tagged with concepts — click any concept to explore what&apos;s connected.
        </p>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            { label: "Concepts", value: stats.concepts },
            { label: "Rel. Types", value: stats.relationship_types },
            { label: "Axes", value: stats.axes },
            { label: "Entity Tags", value: stats.entity_tags },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="bg-gray-900/60 border border-gray-700/40 rounded-lg px-4 py-3 text-center"
            >
              <div className="text-xl font-bold text-white">{value}</div>
              <div className="text-xs text-gray-400 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Axis filter chips */}
      <div className="flex flex-wrap gap-2 mb-6">
        <Link
          href="/concepts"
          className={`px-3 py-1 rounded-full text-xs border transition-colors ${
            !filterAxis
              ? "bg-white/10 text-white border-white/30"
              : "text-gray-400 border-gray-700/40 hover:border-gray-500"
          }`}
        >
          All axes
        </Link>
        {allAxes.map((axis) => (
          <Link
            key={axis}
            href={`/concepts?axis=${encodeURIComponent(axis)}`}
            className={`px-3 py-1 rounded-full text-xs border transition-colors ${
              filterAxis === axis
                ? axisChipClass(axis)
                : "text-gray-400 border-gray-700/40 hover:border-gray-500"
            }`}
          >
            {axis}
          </Link>
        ))}
      </div>

      {/* Concept card grid */}
      {concepts.length === 0 ? (
        <div className="text-center text-gray-500 py-20">No concepts found.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {concepts.map((c) => (
            <Link
              key={c.id}
              href={`/concepts/${c.id}`}
              className="group bg-gray-900/60 border border-gray-700/40 rounded-xl p-4 hover:border-purple-500/50 hover:bg-purple-500/5 transition-colors"
            >
              {/* Level badge */}
              <div className="flex items-start justify-between mb-2">
                <span className="text-xs text-gray-500">L{c.level}</span>
                {c.childConcepts?.length > 0 && (
                  <span className="text-xs text-gray-500">
                    {c.childConcepts.length} children
                  </span>
                )}
              </div>

              {/* Name */}
              <div className="font-semibold text-white text-sm mb-1 group-hover:text-purple-300 transition-colors">
                {c.name}
              </div>

              {/* Description */}
              <p className="text-xs text-gray-400 line-clamp-2 mb-3">
                {c.description || "No description."}
              </p>

              {/* Axes chips */}
              {c.axes && c.axes.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {c.axes.slice(0, 3).map((axis) => (
                    <span
                      key={axis}
                      className={`px-2 py-0.5 rounded-full text-[10px] border ${axisChipClass(axis)}`}
                    >
                      {axis}
                    </span>
                  ))}
                  {c.axes.length > 3 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] border border-gray-600/30 text-gray-500">
                      +{c.axes.length - 3}
                    </span>
                  )}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Footer links */}
      <div className="mt-10 pt-6 border-t border-gray-800 flex gap-4 text-sm text-gray-500">
        <Link href="/graph" className="hover:text-gray-300 transition-colors">
          Graph / Edge Types →
        </Link>
        <Link href="/resonance" className="hover:text-gray-300 transition-colors">
          Concept Resonance →
        </Link>
      </div>
    </main>
  );
}
