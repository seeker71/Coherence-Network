import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound, redirect } from "next/navigation";

import { getApiBase } from "@/lib/api";

/**
 * /nodes/[id] — a universal viewer for any graph node.
 *
 * Concepts, assets, contributors, communities, events — every node
 * type shows up here with its properties flattened and rendered. Typed
 * surfaces (ideas, concepts, people, assets) have richer dedicated
 * pages; this one is the "just show me what's in the graph" fallback
 * so links like `/nodes/visual-lc-v-shelter-organism-2` from the
 * profile page resolve instead of 404ing.
 *
 * When the node is a canonical type with a better home, redirect
 * there instead of rendering the raw view — the dedicated page is
 * always a nicer experience.
 */

export const dynamic = "force-dynamic";

type GraphNode = {
  id: string;
  type: string;
  name?: string;
  description?: string;
  phase?: string;
  created_at?: string;
  updated_at?: string;
  file_path?: string;
  asset_type?: string;
  image_url?: string;
  visual_path?: string;
  canonical_url?: string;
  [key: string]: unknown;
};

async function fetchNode(id: string): Promise<GraphNode | null> {
  const base = getApiBase();
  try {
    const res = await fetch(
      `${base}/api/graph/nodes/${encodeURIComponent(id)}`,
      { next: { revalidate: 30 } },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function preferredHome(node: GraphNode): string | null {
  // Typed surfaces have richer dedicated pages. Redirect when the
  // caller landed on /nodes/ for a node that has a better home.
  const t = node.type;
  if (t === "asset") return `/assets/${encodeURIComponent(node.id)}`;
  if (t === "concept") {
    const domains = (node as { domains?: string[] }).domains;
    if (Array.isArray(domains) && domains.includes("living-collective")) {
      return `/vision/${encodeURIComponent(node.id)}`;
    }
    return `/concepts/${encodeURIComponent(node.id)}`;
  }
  if (t === "idea") return `/ideas/${encodeURIComponent(node.id)}`;
  if (t === "spec") return `/specs/${encodeURIComponent(node.id)}`;
  // Contributors, communities, scenes, events, practices, skills all
  // live under /people (the presence directory).
  const presenceTypes = new Set([
    "contributor", "community", "network-org", "scene",
    "event", "practice", "skill",
  ]);
  if (presenceTypes.has(t)) return `/people/${encodeURIComponent(node.id)}`;
  return null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const node = await fetchNode(decodeURIComponent(id));
  if (!node) return { title: "Node not found — Coherence Network" };
  return {
    title: `${node.name || node.id} — Coherence Network`,
    description: (node.description || `A ${node.type} in the graph`).slice(0, 200),
  };
}

function formatDate(iso: string | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch {
    return iso;
  }
}

// Fields we render out of the structured hero; everything else
// falls into the properties table so no data silently disappears.
const HERO_FIELDS = new Set([
  "id", "type", "name", "description", "phase",
  "created_at", "updated_at", "file_path", "visual_path",
  "image_url", "asset_type", "canonical_url",
]);

export default async function NodePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const decoded = decodeURIComponent(id);
  const node = await fetchNode(decoded);
  if (!node) notFound();

  // Redirect to the dedicated surface when one exists.
  const home = preferredHome(node);
  if (home && home !== `/nodes/${encodeURIComponent(decoded)}`) {
    redirect(home);
  }

  const image = (node.visual_path || node.image_url || node.file_path) as
    | string
    | undefined;
  const isAbsoluteImage = image?.startsWith("http");
  const otherProps = Object.entries(node).filter(([k]) => !HERO_FIELDS.has(k));

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-8">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          {node.type}
          {node.asset_type ? ` · ${node.asset_type}` : ""}
          {node.phase ? ` · ${node.phase}` : ""}
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {node.name || node.id}
        </h1>
        {node.description && (
          <p className="text-sm md:text-base text-foreground/80 leading-relaxed max-w-2xl">
            {node.description}
          </p>
        )}
        {(node.created_at || node.updated_at) && (
          <p className="text-xs text-muted-foreground">
            {node.created_at && <>Created {formatDate(node.created_at)}</>}
            {node.updated_at && node.updated_at !== node.created_at && (
              <> · Updated {formatDate(node.updated_at)}</>
            )}
          </p>
        )}
        {node.canonical_url && (
          <a
            href={node.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-[hsl(var(--primary))] hover:underline"
          >
            {node.canonical_url} ↗
          </a>
        )}
      </section>

      {image && (
        <section className="rounded-2xl border border-border/30 bg-card/30 overflow-hidden">
          {isAbsoluteImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={image}
              alt={node.name || node.id}
              className="w-full h-auto max-h-[70vh] object-contain mx-auto"
            />
          ) : (
            <Image
              src={image}
              alt={node.name || node.id}
              width={1200}
              height={800}
              className="w-full h-auto max-h-[70vh] object-contain mx-auto"
              unoptimized
            />
          )}
        </section>
      )}

      {otherProps.length > 0 && (
        <section className="rounded-2xl border border-border/30 bg-card/30 p-6 sm:p-8 space-y-3">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Properties
          </p>
          <dl className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            {otherProps.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="font-mono text-muted-foreground text-xs sm:text-sm">
                  {key}
                </dt>
                <dd className="text-foreground/90 break-all">
                  {typeof value === "string" ? value :
                   typeof value === "number" || typeof value === "boolean" ? String(value) :
                   Array.isArray(value) ? value.join(", ") :
                   JSON.stringify(value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <nav
        className="py-6 text-center border-t border-border/20"
        aria-label="Related pages"
      >
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link
            href="/people"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            All Presences
          </Link>
          <Link href="/vision" className="text-amber-400 hover:underline">
            Vision
          </Link>
          <Link href="/resonance" className="text-purple-400 hover:underline">
            Resonance
          </Link>
        </div>
      </nav>
    </main>
  );
}
