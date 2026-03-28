import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { notFound } from "next/navigation";

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

type Edge = {
  id: string;
  from: string;
  to: string;
  type: string;
  created_by: string;
  created_at: string;
};

async function fetchConcept(id: string): Promise<Concept | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${id}`, { next: { revalidate: 30 } });
    if (res.status === 404) return null;
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
    return res.json();
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const concept = await fetchConcept(id);
  if (!concept) return { title: "Concept Not Found" };
  return {
    title: `${concept.name} — Concepts — Coherence Network`,
    description: concept.description,
  };
}

export default async function ConceptDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [concept, edges] = await Promise.all([fetchConcept(id), fetchEdges(id)]);

  if (!concept) {
    notFound();
  }

  const outEdges = edges.filter((e) => e.from === id);
  const inEdges = edges.filter((e) => e.to === id);

  const levelLabels: Record<number, string> = {
    0: "Root",
    1: "Foundational",
    2: "Core",
    3: "Applied",
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <nav className="mb-6 text-sm text-gray-500">
          <Link href="/concepts" className="hover:text-blue-600 transition-colors">
            Concepts
          </Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">{concept.name}</span>
        </nav>

        {/* Main Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{concept.name}</h1>
              <p className="text-gray-500 text-sm mt-1 font-mono">#{concept.id}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              {concept.typeId && (
                <span className="text-sm px-3 py-1 rounded-full bg-blue-100 text-blue-800">
                  {concept.typeId}
                </span>
              )}
              {concept.level !== undefined && (
                <span className="text-xs text-gray-500">
                  {levelLabels[concept.level] ?? `Level ${concept.level}`}
                </span>
              )}
            </div>
          </div>

          <p className="text-gray-700 text-lg leading-relaxed mb-6">{concept.description}</p>

          {/* Keywords */}
          {concept.keywords && concept.keywords.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">Keywords</h3>
              <div className="flex flex-wrap gap-2">
                {concept.keywords.map((kw) => (
                  <span key={kw} className="text-sm bg-gray-100 text-gray-700 px-3 py-1 rounded-full">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Axes */}
          {concept.axes && concept.axes.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-600 mb-2">Ontology Axes</h3>
              <div className="flex flex-wrap gap-2">
                {concept.axes.map((axis) => (
                  <span key={axis} className="text-sm bg-purple-50 text-purple-700 px-3 py-1 rounded-full border border-purple-200">
                    {axis}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Edges Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Outgoing edges */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <span className="text-green-600">→</span>
              Outgoing Edges
              <span className="text-sm font-normal text-gray-400">({outEdges.length})</span>
            </h2>
            {outEdges.length === 0 ? (
              <p className="text-gray-400 text-sm italic">No outgoing edges yet</p>
            ) : (
              <ul className="space-y-2">
                {outEdges.map((edge) => (
                  <li key={edge.id} className="flex items-center gap-2 text-sm">
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded font-mono">
                      {edge.type}
                    </span>
                    <Link
                      href={`/concepts/${edge.to}`}
                      className="text-blue-600 hover:underline font-medium"
                    >
                      {edge.to}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Incoming edges */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <span className="text-blue-600">←</span>
              Incoming Edges
              <span className="text-sm font-normal text-gray-400">({inEdges.length})</span>
            </h2>
            {inEdges.length === 0 ? (
              <p className="text-gray-400 text-sm italic">No incoming edges yet</p>
            ) : (
              <ul className="space-y-2">
                {inEdges.map((edge) => (
                  <li key={edge.id} className="flex items-center gap-2 text-sm">
                    <Link
                      href={`/concepts/${edge.from}`}
                      className="text-blue-600 hover:underline font-medium"
                    >
                      {edge.from}
                    </Link>
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-mono">
                      {edge.type}
                    </span>
                    <span className="text-gray-500">→ you</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Link a concept */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Link Concept via CLI</h2>
          <p className="text-sm text-gray-600 mb-3">
            Use the CLI to create typed relationships between concepts:
          </p>
          <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm text-green-400">
            <div># Link this concept to another</div>
            <div>cc concept link {concept.id} resonates-with &lt;target-id&gt;</div>
            <div className="mt-2 text-gray-400"># View all relationship types</div>
            <div>cc concepts relationships</div>
          </div>
        </div>

        {/* Footer navigation */}
        <div className="flex justify-between items-center text-sm text-gray-500">
          <Link href="/concepts" className="text-blue-600 hover:underline">
            ← Back to All Concepts
          </Link>
          <Link href="/ideas" className="text-blue-600 hover:underline">
            Browse Ideas →
          </Link>
        </div>
      </div>
    </div>
  );
}
