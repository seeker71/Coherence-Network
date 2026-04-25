import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Concepts — Coherence Network",
  description: "Browse the Living Codex ontology: 184 universal concepts with typed relationships and axes.",
};

export const dynamic = "force-dynamic";

type Concept = {
  id: string;
  name: string;
  description: string;
  typeId?: string;
  level?: number;
  keywords?: string[];
  axes?: string[];
  parentConcepts?: string[];
  childConcepts?: string[];
  userDefined?: boolean;
};

type ConceptsResponse = {
  items: Concept[];
  total: number;
  limit: number;
  offset: number;
};

type StatsResponse = {
  concepts: number;
  relationship_types: number;
  axes: number;
  user_edges: number;
  user_concepts: number;
};

async function fetchConcepts(limit = 200): Promise<ConceptsResponse> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts?limit=${limit}`, { next: { revalidate: 60 } });
    if (!res.ok) return { items: [], total: 0, limit, offset: 0 };
    return res.json();
  } catch {
    return { items: [], total: 0, limit, offset: 0 };
  }
}

async function fetchStats(): Promise<StatsResponse> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/stats`, { next: { revalidate: 60 } });
    if (!res.ok) return { concepts: 0, relationship_types: 0, axes: 0, user_edges: 0, user_concepts: 0 };
    return res.json();
  } catch {
    return { concepts: 0, relationship_types: 0, axes: 0, user_edges: 0, user_concepts: 0 };
  }
}

function levelBadge(level?: number) {
  const colors: Record<number, string> = {
    0: "bg-violet-100 text-violet-700",
    1: "bg-blue-100 text-blue-700",
    2: "bg-teal-100 text-teal-700",
    3: "bg-green-100 text-green-700",
  };
  const labels: Record<number, string> = { 0: "Core", 1: "Primary", 2: "Secondary", 3: "Derived" };
  const l = level ?? 0;
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${colors[l] ?? "bg-gray-100 text-gray-600"}`}>
      {labels[l] ?? `L${l}`}
    </span>
  );
}

export default async function ConceptsPage() {
  const [data, stats] = await Promise.all([fetchConcepts(200), fetchStats()]);
  const concepts = data.items;

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-3xl font-bold tracking-tight">Concepts</h1>
          <a
            href="/concepts/garden"
            className="text-xs bg-primary/10 text-primary border border-primary/20 rounded px-2 py-1 hover:bg-primary/20 transition-colors font-medium"
          >
            Garden view (contribute)
          </a>
        </div>
        <p className="text-muted-foreground text-sm max-w-2xl">
          The Living Codex ontology — {stats.concepts} universal concepts spanning {stats.axes} axes
          with {stats.relationship_types} typed relationship patterns. Click any concept to explore
          its connections.
        </p>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        {[
          { label: "Concepts", value: stats.concepts },
          { label: "Relationship Types", value: stats.relationship_types },
          { label: "Axes", value: stats.axes },
          { label: "User Edges", value: stats.user_edges },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border bg-card px-4 py-3">
            <div className="text-2xl font-bold tabular-nums">{s.value}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Concept grid */}
      {concepts.length === 0 ? (
        <p className="text-muted-foreground text-sm">No concepts loaded. Check API connectivity.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {concepts.map((concept) => (
            <Link
              key={concept.id}
              href={`/concepts/${concept.id}`}
              className="group rounded-xl border bg-card hover:border-primary/50 hover:shadow-md transition-all p-4 flex flex-col gap-2"
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold text-sm group-hover:text-primary transition-colors leading-snug">
                  {concept.name}
                </h2>
                {levelBadge(concept.level)}
              </div>
              <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed flex-1">
                {concept.description || "No description."}
              </p>
              {concept.axes && concept.axes.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {concept.axes.slice(0, 3).map((axis) => (
                    <span key={axis} className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                      {axis}
                    </span>
                  ))}
                  {concept.axes.length > 3 && (
                    <span className="text-[10px] text-muted-foreground">+{concept.axes.length - 3}</span>
                  )}
                </div>
              )}
              {concept.userDefined && (
                <span className="text-[10px] text-amber-600 font-medium">user-defined</span>
              )}
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
