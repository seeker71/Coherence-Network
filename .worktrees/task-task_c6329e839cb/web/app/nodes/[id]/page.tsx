import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";

import { getApiBase } from "@/lib/api";

/**
 * /nodes/[id] — the universal node viewer.
 *
 * Any graph node id — concept, contributor, asset, idea, spec, scene,
 * event, community, practice — resolves here and renders in the viewer
 * best suited to its kind. A caller never has to know a node's shape
 * to link to it: `/nodes/{id}` always works and always picks the right
 * view.
 *
 * The viewer picker reads the node type (and for concepts, the domain)
 * and composes the appropriate typed page as a server component. The
 * typed URLs (/vision, /concepts, /assets, /ideas, /specs, /people)
 * stay available for direct access; /nodes/ is the one surface that
 * unifies them.
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
  domains?: string[];
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

const PRESENCE_TYPES = new Set([
  "contributor",
  "community",
  "network-org",
  "scene",
  "event",
  "practice",
  "skill",
]);

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
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

const HERO_FIELDS = new Set([
  "id",
  "type",
  "name",
  "description",
  "phase",
  "created_at",
  "updated_at",
  "file_path",
  "visual_path",
  "image_url",
  "asset_type",
  "canonical_url",
]);

/**
 * Generic fallback viewer — renders whatever properties a node carries
 * when its type doesn't match a specialized viewer. Every known type
 * composes a richer viewer above; this one ensures a caller never hits
 * a 404 on an id the graph already recognizes.
 */
function GenericNodeViewer({ node }: { node: GraphNode }) {
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
                  {typeof value === "string"
                    ? value
                    : typeof value === "number" || typeof value === "boolean"
                    ? String(value)
                    : Array.isArray(value)
                    ? value.join(", ")
                    : JSON.stringify(value)}
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

export default async function NodePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: rawId } = await params;
  const decoded = decodeURIComponent(rawId);
  const node = await fetchNode(decoded);
  if (!node) notFound();

  const t = node.type;
  const emptySearchParams = Promise.resolve(
    {} as Record<string, string | string[] | undefined>,
  );

  // Concepts fork by domain: living-collective concepts render as the
  // rich vision page; other concepts render the terser concept browser.
  if (t === "concept") {
    const domains = node.domains;
    const isLiving =
      Array.isArray(domains) && domains.includes("living-collective");
    if (isLiving) {
      const VisionPage = (await import("@/app/vision/[conceptId]/page")).default;
      return (
        <VisionPage
          params={Promise.resolve({ conceptId: rawId })}
          searchParams={emptySearchParams}
        />
      );
    }
    const ConceptPage = (await import("@/app/concepts/[id]/page")).default;
    return <ConceptPage params={Promise.resolve({ id: rawId })} />;
  }

  if (t === "asset") {
    const AssetPage = (await import("@/app/assets/[asset_id]/page")).default;
    return <AssetPage params={Promise.resolve({ asset_id: rawId })} />;
  }

  if (t === "idea") {
    const IdeaPage = (await import("@/app/ideas/[idea_id]/page")).default;
    return <IdeaPage params={Promise.resolve({ idea_id: rawId })} />;
  }

  if (t === "spec") {
    const SpecPage = (await import("@/app/specs/[spec_id]/page")).default;
    return <SpecPage params={Promise.resolve({ spec_id: rawId })} />;
  }

  // Contributors, communities, scenes, events, practices, skills all
  // land on the presence garden. /people itself picks the richer
  // PresencePage when the node carries a canonical_url, or the warm
  // voices view otherwise; either way it's the welcoming surface a
  // visitor wants for any person or place.
  if (PRESENCE_TYPES.has(t)) {
    const PeoplePage = (await import("@/app/people/[id]/page")).default;
    return <PeoplePage params={Promise.resolve({ id: rawId })} />;
  }

  // Unknown type — fall back to the generic properties renderer so no
  // recognized graph node ever 404s just because its shape hasn't been
  // specialized.
  return <GenericNodeViewer node={node} />;
}
