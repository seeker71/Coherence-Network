import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

type GraphNode = {
  id: string;
  type: string;
  name?: string;
  description?: string;
  slug?: string;
  status?: string;
  source?: string;
  markdown_path?: string;
  lineage_node_ids?: string[];
  canonical_url?: string;
  schedule_rhythm?: string[];
};

async function fetchNode(id: string): Promise<GraphNode | null> {
  try {
    const res = await fetch(
      `${getApiBase()}/api/graph/nodes/${encodeURIComponent(id)}`,
      { next: { revalidate: 30 } },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchLineage(slug: string): Promise<GraphNode | null> {
  return fetchNode(`story:${slug}`);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const lineage = await fetchLineage(decodeURIComponent(slug));
  if (!lineage) return { title: "Lineage not found - Coherence Network" };
  return {
    title: `${lineage.name || lineage.id} - Coherence Network`,
    description: (lineage.description || "A lived lineage in the graph").slice(0, 200),
  };
}

function label(value?: string): string {
  return value ? value.replaceAll("-", " ") : "";
}

export default async function LineagePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const lineage = await fetchLineage(decodeURIComponent(slug));
  if (!lineage) notFound();

  const ids = Array.isArray(lineage.lineage_node_ids) ? lineage.lineage_node_ids : [];
  const nodes = (await Promise.all(ids.map((id) => fetchNode(id)))).filter(
    (node): node is GraphNode => Boolean(node),
  );

  return (
    <main className="mx-auto max-w-5xl px-4 sm:px-6 py-8 space-y-8">
      <header className="space-y-4">
        <p className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--primary))]">
          Lineage
          {lineage.status ? ` · ${label(lineage.status)}` : ""}
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {lineage.name || lineage.id}
        </h1>
        {lineage.description && (
          <p className="text-sm md:text-base text-muted-foreground leading-relaxed max-w-3xl">
            {lineage.description}
          </p>
        )}
        <div className="flex flex-wrap gap-3 text-sm">
          <Link
            href={`/nodes/${encodeURIComponent(lineage.id)}`}
            className="rounded-md border border-border/50 px-3 py-1.5 text-muted-foreground transition-colors hover:border-border hover:text-foreground"
          >
            Open graph node
          </Link>
          <Link
            href={`/graph/zoom/${encodeURIComponent(lineage.id)}`}
            className="rounded-md border border-border/50 px-3 py-1.5 text-muted-foreground transition-colors hover:border-border hover:text-foreground"
          >
            Open graph zoom
          </Link>
          {lineage.markdown_path && (
            <a
              href={`https://github.com/seeker71/Coherence-Network/blob/main/${lineage.markdown_path}`}
              className="rounded-md border border-border/50 px-3 py-1.5 text-muted-foreground transition-colors hover:border-border hover:text-foreground"
            >
              Source document
            </a>
          )}
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {nodes.map((node) => (
          <Link
            key={node.id}
            href={`/nodes/${encodeURIComponent(node.id)}`}
            className="group rounded-xl border border-border/30 bg-card/40 p-4 transition-colors hover:border-border hover:bg-card/70"
          >
            <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-muted-foreground">
              {node.type}
            </p>
            <h2 className="mt-2 text-base font-medium tracking-tight group-hover:text-[hsl(var(--primary))]">
              {node.name || node.id}
            </h2>
            {node.description && (
              <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-muted-foreground">
                {node.description}
              </p>
            )}
            {node.schedule_rhythm && node.schedule_rhythm.length > 0 && (
              <p className="mt-3 text-xs text-foreground/80">
                Rhythm: {node.schedule_rhythm.join(", ")}
              </p>
            )}
          </Link>
        ))}
      </section>
    </main>
  );
}
