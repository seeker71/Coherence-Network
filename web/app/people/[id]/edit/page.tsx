import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PresenceRefineForm } from "@/components/presence/PresenceRefineForm";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";

/**
 * /people/[id]/edit — refine any presence's primary data.
 *
 * Anyone arriving here can shape the data this presence is composed
 * from: the core text fields (name, tagline, description, image,
 * slug), the public presence URLs across platforms, and the
 * relationship edges that weave this presence into the field. The
 * page that visitors read at /people/{slug} is rendered from this
 * primary data, so refining it here is what better-represents the
 * presence — the bio doesn't get edited, the data the bio harmonizes
 * from gets edited.
 *
 * The id segment accepts both graph-canonical ids and human-readable
 * slugs (the API resolves either).
 */

export const dynamic = "force-dynamic";

type GraphNode = {
  id: string;
  type: string;
  name?: string;
  description?: string;
  slug?: string | null;
  tagline?: string | null;
  image_url?: string | null;
  presences?: { provider: string; url: string }[];
};

async function fetchNode(id: string): Promise<GraphNode | null> {
  return fetchJsonOrNull<GraphNode>(
    `${getApiBase()}/api/graph/nodes/${encodeURIComponent(id)}`,
    {},
    5000,
  );
}

function decodeRouteParam(rawId: string): string {
  try {
    return decodeURIComponent(rawId);
  } catch {
    return rawId;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id: rawId } = await params;
  const id = decodeRouteParam(rawId);
  const node = await fetchNode(id);
  const name = node?.name || id.replace(/-[a-z0-9]{6,}$/, "").replace(/-/g, " ");
  return {
    title: `Refine ${name} — Coherence Network`,
    description: `Refine the primary data this presence is composed from. The page reflects the data; the data reflects the field.`,
  };
}

export default async function PresenceEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: rawId } = await params;
  const id = decodeRouteParam(rawId);
  const node = await fetchNode(id);
  if (!node) notFound();

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-8 space-y-8">
      <header className="space-y-3">
        <p className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[hsl(var(--primary))]">
          Refine
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {node.name || node.id}
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
          Anything below can be corrected. The presence page rebuilds
          itself from this data, so what you change here is what visitors
          will see — image, tagline, description, the platforms linked
          from the page, and the relationships that weave this presence
          into the field.
        </p>
      </header>

      <PresenceRefineForm node={node} />
    </main>
  );
}
