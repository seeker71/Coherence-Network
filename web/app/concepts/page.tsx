import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Concepts — Coherence Network",
  description: "Browse the Living Codex ontology: 184 universal concepts with typed relationships",
};

type Concept = {
  id: string;
  name: string;
  description: string;
  typeId?: string;
  level?: number;
  keywords?: string[];
  axes?: string[];
};

type ConceptsResponse = {
  items: Concept[];
  total: number;
  limit: number;
  offset: number;
};

type Stats = {
  concepts: number;
  relationship_types: number;
  axes: number;
  user_edges: number;
};

async function fetchConcepts(q?: string): Promise<ConceptsResponse> {
  const base = getApiBase();
  try {
    if (q) {
      const res = await fetch(`${base}/api/concepts/search?q=${encodeURIComponent(q)}&limit=100`, {
        next: { revalidate: 30 },
      });
      if (!res.ok) return { items: [], total: 0, limit: 100, offset: 0 };
      const items = await res.json();
      return { items: Array.isArray(items) ? items : [], total: Array.isArray(items) ? items.length : 0, limit: 100, offset: 0 };
    }
    const res = await fetch(`${base}/api/concepts?limit=200`, { next: { revalidate: 30 } });
    if (!res.ok) return { items: [], total: 0, limit: 200, offset: 0 };
    return res.json();
  } catch {
    return { items: [], total: 0, limit: 200, offset: 0 };
  }
}

async function fetchStats(): Promise<Stats | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/stats`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

const TYPE_COLORS: Record<string, string> = {
  root: "bg-purple-100 text-purple-800",
  foundation: "bg-blue-100 text-blue-800",
  element: "bg-green-100 text-green-800",
  force: "bg-red-100 text-red-800",
  principle: "bg-yellow-100 text-yellow-800",
  pattern: "bg-orange-100 text-orange-800",
  process: "bg-teal-100 text-teal-800",
  faculty: "bg-indigo-100 text-indigo-800",
  emotion: "bg-pink-100 text-pink-800",
  quality: "bg-cyan-100 text-cyan-800",
  state: "bg-lime-100 text-lime-800",
  practice: "bg-violet-100 text-violet-800",
  structure: "bg-amber-100 text-amber-800",
  entity: "bg-emerald-100 text-emerald-800",
  activity: "bg-rose-100 text-rose-800",
  event: "bg-sky-100 text-sky-800",
  concept: "bg-gray-100 text-gray-800",
  symbol: "bg-fuchsia-100 text-fuchsia-800",
  metaphor: "bg-stone-100 text-stone-800",
  role: "bg-zinc-100 text-zinc-800",
  relationship: "bg-slate-100 text-slate-800",
  dimension: "bg-blue-50 text-blue-700",
  system: "bg-green-50 text-green-700",
};

export default async function ConceptsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const params = await searchParams;
  const query = params.q;
  const [data, stats] = await Promise.all([fetchConcepts(query), fetchStats()]);

  const groupedByLevel: Record<number, Concept[]> = {};
  for (const c of data.items) {
    const lvl = c.level ?? 2;
    if (!groupedByLevel[lvl]) groupedByLevel[lvl] = [];
    groupedByLevel[lvl].push(c);
  }
  const levels = Object.keys(groupedByLevel)
    .map(Number)
    .sort((a, b) => a - b);

  const levelLabels: Record<number, string> = {
    0: "Root",
    1: "Foundational",
    2: "Core",
    3: "Applied",
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Concepts Ontology</h1>
          <p className="text-gray-600 text-lg">
            Living Codex — universal concepts, typed relationships, and navigable axes
          </p>
          {stats && (
            <div className="mt-4 flex flex-wrap gap-4">
              <div className="bg-white rounded-lg px-4 py-2 shadow-sm border border-gray-200">
                <span className="text-2xl font-bold text-blue-600">{stats.concepts}</span>
                <span className="text-gray-600 ml-2 text-sm">Concepts</span>
              </div>
              <div className="bg-white rounded-lg px-4 py-2 shadow-sm border border-gray-200">
                <span className="text-2xl font-bold text-green-600">{stats.relationship_types}</span>
                <span className="text-gray-600 ml-2 text-sm">Relationship Types</span>
              </div>
              <div className="bg-white rounded-lg px-4 py-2 shadow-sm border border-gray-200">
                <span className="text-2xl font-bold text-purple-600">{stats.axes}</span>
                <span className="text-gray-600 ml-2 text-sm">Axes</span>
              </div>
              <div className="bg-white rounded-lg px-4 py-2 shadow-sm border border-gray-200">
                <span className="text-2xl font-bold text-orange-600">{stats.user_edges}</span>
                <span className="text-gray-600 ml-2 text-sm">User Edges</span>
              </div>
            </div>
          )}
        </div>

        {/* Search */}
        <form method="GET" className="mb-8">
          <div className="flex gap-2">
            <input
              type="text"
              name="q"
              defaultValue={query}
              placeholder="Search concepts by name or description..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            />
            <button
              type="submit"
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Search
            </button>
            {query && (
              <Link
                href="/concepts"
                className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Clear
              </Link>
            )}
          </div>
        </form>

        {query && (
          <p className="text-gray-600 mb-6">
            Found <strong>{data.items.length}</strong> results for &quot;{query}&quot;
          </p>
        )}

        {/* Concepts Grid */}
        {query ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data.items.map((concept) => (
              <ConceptCard key={concept.id} concept={concept} />
            ))}
            {data.items.length === 0 && (
              <div className="col-span-4 text-center py-12 text-gray-500">
                No concepts found matching &quot;{query}&quot;
              </div>
            )}
          </div>
        ) : (
          <div>
            {levels.map((level) => (
              <div key={level} className="mb-10">
                <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-blue-500"></span>
                  {levelLabels[level] ?? `Level ${level}`}
                  <span className="text-sm font-normal text-gray-500">
                    ({groupedByLevel[level].length} concepts)
                  </span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {groupedByLevel[level].map((concept) => (
                    <ConceptCard key={concept.id} concept={concept} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Quick Links */}
        <div className="mt-10 border-t border-gray-200 pt-6 flex gap-4 text-sm">
          <Link href="/concepts" className="text-blue-600 hover:underline">
            All Concepts
          </Link>
          <span className="text-gray-300">|</span>
          <Link href="/ideas" className="text-blue-600 hover:underline">
            Ideas
          </Link>
          <span className="text-gray-300">|</span>
          <Link href="/specs" className="text-blue-600 hover:underline">
            Specs
          </Link>
        </div>
      </div>
    </div>
  );
}

function ConceptCard({ concept }: { concept: Concept }) {
  const typeColor = TYPE_COLORS[concept.typeId ?? "concept"] ?? "bg-gray-100 text-gray-800";

  return (
    <Link
      href={`/concepts/${concept.id}`}
      className="bg-white rounded-lg p-4 shadow-sm border border-gray-200 hover:shadow-md hover:border-blue-300 transition-all group"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900 group-hover:text-blue-700 transition-colors">
          {concept.name}
        </h3>
        {concept.typeId && (
          <span className={`text-xs px-2 py-0.5 rounded-full ml-2 shrink-0 ${typeColor}`}>
            {concept.typeId}
          </span>
        )}
      </div>
      <p className="text-sm text-gray-600 line-clamp-3">{concept.description}</p>
      {concept.keywords && concept.keywords.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {concept.keywords.slice(0, 3).map((kw) => (
            <span key={kw} className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
              {kw}
            </span>
          ))}
        </div>
      )}
      {concept.axes && concept.axes.length > 0 && (
        <div className="mt-2 text-xs text-gray-400">
          Axes: {concept.axes.join(", ")}
        </div>
      )}
    </Link>
  );
}
