import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";

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
  createdAt?: string;
};

type Edge = {
  id: string;
  from: string;
  to: string;
  type: string;
  created_by?: string;
  created_at?: string;
};

type RelatedItems = {
  concept_id: string;
  ideas: string[];
  specs: string[];
  total: number;
};

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
    return res.json();
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

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const concept = await fetchConcept(id);
  return {
    title: concept ? `${concept.name} — Concepts` : "Concept Not Found",
    description: concept?.description || "",
  };
}

function levelLabel(level?: number) {
  const labels: Record<number, string> = { 0: "Core", 1: "Primary", 2: "Secondary", 3: "Derived" };
  const colors: Record<number, string> = {
    0: "bg-violet-100 text-violet-700 border-violet-200",
    1: "bg-blue-100 text-blue-700 border-blue-200",
    2: "bg-teal-100 text-teal-700 border-teal-200",
    3: "bg-green-100 text-green-700 border-green-200",
  };
  const l = level ?? 0;
  return (
    <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded border font-medium ${colors[l] ?? "bg-gray-100 text-gray-600 border-gray-200"}`}>
      {labels[l] ?? `Level ${l}`}
    </span>
  );
}

function EdgeRow({ edge, selfId }: { edge: Edge; selfId: string }) {
  const isOutgoing = edge.from === selfId;
  const otherId = isOutgoing ? edge.to : edge.from;
  return (
    <div className="flex items-center gap-3 py-2 border-b last:border-0 text-sm">
      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${isOutgoing ? "bg-blue-50 text-blue-600" : "bg-orange-50 text-orange-600"}`}>
        {isOutgoing ? "→" : "←"}
      </span>
      <span className="text-muted-foreground font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
        {edge.type}
      </span>
      <Link href={`/concepts/${otherId}`} className="text-primary hover:underline font-medium">
        {otherId}
      </Link>
    </div>
  );
}

export default async function ConceptDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [concept, edges, related] = await Promise.all([
    fetchConcept(id),
    fetchEdges(id),
    fetchRelated(id),
  ]);

  if (!concept) notFound();

  const outgoingEdges = edges.filter((e) => e.from === id);
  const incomingEdges = edges.filter((e) => e.to === id);

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <nav className="text-sm text-muted-foreground mb-6">
        <Link href="/concepts" className="hover:text-foreground">Concepts</Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">{concept.name}</span>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start gap-3 mb-2">
          <h1 className="text-3xl font-bold tracking-tight">{concept.name}</h1>
          {levelLabel(concept.level)}
          {concept.userDefined && (
            <span className="text-xs text-amber-600 font-medium border border-amber-200 bg-amber-50 px-2 py-0.5 rounded">
              user-defined
            </span>
          )}
        </div>
        <p className="text-xs font-mono text-muted-foreground mb-4">{concept.id}</p>
        {concept.description && (
          <p className="text-base text-muted-foreground max-w-2xl leading-relaxed">{concept.description}</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Main details */}
        <div className="md:col-span-2 space-y-6">
          {/* Edges */}
          <section className="rounded-xl border bg-card p-5">
            <h2 className="font-semibold mb-4">
              Relationships
              <span className="ml-2 text-xs text-muted-foreground font-normal">({edges.length})</span>
            </h2>
            {edges.length === 0 ? (
              <p className="text-sm text-muted-foreground">No typed relationships recorded.</p>
            ) : (
              <div>
                {outgoingEdges.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                      Outgoing ({outgoingEdges.length})
                    </h3>
                    {outgoingEdges.map((e) => <EdgeRow key={e.id} edge={e} selfId={id} />)}
                  </div>
                )}
                {incomingEdges.length > 0 && (
                  <div>
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                      Incoming ({incomingEdges.length})
                    </h3>
                    {incomingEdges.map((e) => <EdgeRow key={e.id} edge={e} selfId={id} />)}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Related items */}
          {related.total > 0 && (
            <section className="rounded-xl border bg-card p-5">
              <h2 className="font-semibold mb-4">
                Tagged In
                <span className="ml-2 text-xs text-muted-foreground font-normal">({related.total})</span>
              </h2>
              {related.ideas.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    Ideas ({related.ideas.length})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {related.ideas.map((ideaId) => (
                      <Link key={ideaId} href={`/ideas/${ideaId}`}
                        className="text-xs px-2 py-1 rounded bg-muted hover:bg-muted/70 transition-colors font-mono">
                        {ideaId}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
              {related.specs.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    Specs ({related.specs.length})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {related.specs.map((specId) => (
                      <Link key={specId} href={`/specs/${specId}`}
                        className="text-xs px-2 py-1 rounded bg-muted hover:bg-muted/70 transition-colors font-mono">
                        {specId}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Metadata */}
          <section className="rounded-xl border bg-card p-4 text-sm space-y-3">
            <h2 className="font-semibold text-sm">Metadata</h2>
            {concept.typeId && (
              <div>
                <span className="text-xs text-muted-foreground block">Type</span>
                <span className="font-mono text-xs">{concept.typeId}</span>
              </div>
            )}
            {concept.createdAt && (
              <div>
                <span className="text-xs text-muted-foreground block">Created</span>
                <span className="text-xs">{new Date(concept.createdAt).toLocaleDateString()}</span>
              </div>
            )}
          </section>

          {/* Keywords */}
          {concept.keywords && concept.keywords.length > 0 && (
            <section className="rounded-xl border bg-card p-4">
              <h2 className="font-semibold text-sm mb-3">Keywords</h2>
              <div className="flex flex-wrap gap-1.5">
                {concept.keywords.map((kw) => (
                  <span key={kw} className="text-xs bg-muted px-2 py-0.5 rounded text-muted-foreground">
                    {kw}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Axes */}
          {concept.axes && concept.axes.length > 0 && (
            <section className="rounded-xl border bg-card p-4">
              <h2 className="font-semibold text-sm mb-3">Axes</h2>
              <div className="flex flex-wrap gap-1.5">
                {concept.axes.map((axis) => (
                  <span key={axis} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium">
                    {axis}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Parent / Child concepts */}
          {concept.parentConcepts && concept.parentConcepts.length > 0 && (
            <section className="rounded-xl border bg-card p-4">
              <h2 className="font-semibold text-sm mb-3">Parent Concepts</h2>
              <div className="space-y-1">
                {concept.parentConcepts.map((pid) => (
                  <Link key={pid} href={`/concepts/${pid}`}
                    className="block text-xs text-primary hover:underline font-mono">
                    {pid}
                  </Link>
                ))}
              </div>
            </section>
          )}

          {concept.childConcepts && concept.childConcepts.length > 0 && (
            <section className="rounded-xl border bg-card p-4">
              <h2 className="font-semibold text-sm mb-3">Child Concepts</h2>
              <div className="space-y-1">
                {concept.childConcepts.map((cid) => (
                  <Link key={cid} href={`/concepts/${cid}`}
                    className="block text-xs text-primary hover:underline font-mono">
                    {cid}
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Back link */}
      <div className="mt-8">
        <Link href="/concepts" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
          ← Back to all concepts
        </Link>
      </div>
    </main>
  );
}
