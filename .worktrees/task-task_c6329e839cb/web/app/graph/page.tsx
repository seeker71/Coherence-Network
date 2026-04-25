import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Graph — Edge Types",
  description: "Browse the 46 typed relationships that connect every entity in the Coherence Network.",
};

type EdgeTypeEntry = {
  slug: string;
  description: string;
  canonical: boolean;
};

type EdgeTypeFamily = {
  name: string;
  slug: string;
  types: EdgeTypeEntry[];
};

type EdgeTypesResponse = {
  total: number;
  families: EdgeTypeFamily[];
};

type NodeStub = {
  id: string;
  type: string;
  name: string;
};

type EdgeItem = {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  strength: number;
  canonical: boolean;
  from_node: NodeStub | null;
  to_node: NodeStub | null;
  created_at: string;
};

type EntityEdgesResponse = {
  items: EdgeItem[];
  total: number;
  limit: number;
  offset: number;
};

const FAMILY_COLORS: Record<string, string> = {
  ontological: "text-purple-400",
  process: "text-yellow-400",
  knowledge: "text-blue-400",
  scale: "text-cyan-400",
  temporal: "text-green-400",
  tension: "text-red-400",
  attribution: "text-gray-300",
};

const FAMILY_BG: Record<string, string> = {
  ontological: "border-purple-500/30 bg-purple-500/5",
  process: "border-yellow-500/30 bg-yellow-500/5",
  knowledge: "border-blue-500/30 bg-blue-500/5",
  scale: "border-cyan-500/30 bg-cyan-500/5",
  temporal: "border-green-500/30 bg-green-500/5",
  tension: "border-red-500/30 bg-red-500/5",
  attribution: "border-gray-500/30 bg-gray-500/5",
};

async function loadEdgeTypes(): Promise<EdgeTypesResponse | null> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/edges/types`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as EdgeTypesResponse;
  } catch {
    return null;
  }
}

async function loadEntityEdges(
  entityId: string,
  edgeType?: string,
): Promise<EntityEdgesResponse | null> {
  try {
    const api = getApiBase();
    const params = new URLSearchParams({ limit: "100" });
    if (edgeType) params.set("type", edgeType);
    const res = await fetch(
      `${api}/api/entities/${encodeURIComponent(entityId)}/edges?${params}`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as EntityEdgesResponse;
  } catch {
    return null;
  }
}

export default async function GraphPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await searchParams;
  const entityId = sp.id ?? null;
  const filterType = sp.type ?? null;

  const [data, entityEdges] = await Promise.all([
    loadEdgeTypes(),
    entityId ? loadEntityEdges(entityId, filterType ?? undefined) : Promise.resolve(null),
  ]);

  return (
    <main className="max-w-5xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Graph Navigation</h1>
        <p className="text-gray-400 text-sm">
          Every entity in the Coherence Network — ideas, concepts, contributors, specs, tasks, news
          — connects through{" "}
          <span className="text-white font-medium">{data?.total ?? 46} typed relationships</span>{" "}
          from the Living Codex ontology.
        </p>
        <p className="text-gray-500 text-xs mt-2">
          Browse edges via{" "}
          <code className="bg-gray-800 px-1 rounded">/api/edges</code>,{" "}
          <code className="bg-gray-800 px-1 rounded">/api/edges/types</code>, or{" "}
          <code className="bg-gray-800 px-1 rounded">/api/entities/&#123;id&#125;/edges</code>.
          CLI: <code className="bg-gray-800 px-1 rounded">coh edges &lt;id&gt;</code>{" "}
          (alias: <code className="bg-gray-800 px-1 rounded">coh edg &lt;id&gt;</code>)
        </p>
      </div>

      {/* Entity edge browser */}
      <div className="mb-10 border border-gray-700 rounded p-5 bg-gray-800/30">
        <h3 className="text-white font-semibold mb-3">Navigate an Entity&apos;s Edges</h3>
        <p className="text-gray-400 text-sm mb-3">
          Enter any entity ID to see its connections. You can also filter by relationship type.
        </p>
        <form method="GET" action="/graph" className="flex gap-2 flex-wrap mb-4">
          <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
            <label htmlFor="entity-id" className="text-xs text-gray-500">
              Entity ID
            </label>
            <input
              id="entity-id"
              name="id"
              type="text"
              defaultValue={entityId ?? ""}
              placeholder="e.g. idea_abc123"
              className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex flex-col gap-1 min-w-[160px]">
            <label htmlFor="edge-type" className="text-xs text-gray-500">
              Relationship type (optional)
            </label>
            <input
              id="edge-type"
              name="type"
              type="text"
              defaultValue={filterType ?? ""}
              placeholder="e.g. resonates-with"
              className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex flex-col justify-end">
            <button
              type="submit"
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-medium"
            >
              Browse Edges
            </button>
          </div>
        </form>

        {entityId && (
          <div>
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <span className="text-gray-400 text-sm">
                Edges for{" "}
                <code className="bg-gray-900 px-1 rounded text-white">{entityId}</code>
                {filterType && (
                  <>
                    {" "}filtered by{" "}
                    <code className="bg-gray-900 px-1 rounded text-purple-300">{filterType}</code>
                  </>
                )}
              </span>
              {entityEdges && (
                <span className="text-gray-500 text-xs">({entityEdges.total} total)</span>
              )}
            </div>

            {!entityEdges && (
              <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded p-3">
                Entity not found or API unavailable.
              </div>
            )}

            {entityEdges && entityEdges.items.length === 0 && (
              <div className="text-gray-500 text-sm italic">No edges found for this entity.</div>
            )}

            {entityEdges && entityEdges.items.length > 0 && (
              <div className="space-y-2 mt-2">
                {entityEdges.items.map((edge) => {
                  const isOutgoing = edge.from_id === entityId;
                  const peer = isOutgoing ? edge.to_node : edge.from_node;
                  const peerId = isOutgoing ? edge.to_id : edge.from_id;
                  return (
                    <div
                      key={edge.id}
                      className="border border-gray-700 rounded p-3 bg-gray-900/50 flex items-start gap-3"
                    >
                      <span
                        className={`text-xs font-mono font-semibold flex-shrink-0 mt-0.5 ${
                          isOutgoing ? "text-blue-400" : "text-green-400"
                        }`}
                      >
                        {isOutgoing ? "→" : "←"}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-purple-300 font-mono text-xs font-semibold">
                            {edge.type}
                          </span>
                          {!edge.canonical && (
                            <span className="text-gray-500 text-xs">(custom)</span>
                          )}
                          <span className="text-gray-600 text-xs">
                            strength: {edge.strength?.toFixed(2)}
                          </span>
                        </div>
                        <Link
                          href={`/graph?id=${encodeURIComponent(peerId)}`}
                          className="text-white text-sm hover:text-blue-300 truncate block mt-0.5"
                        >
                          {peer?.name ?? peerId}
                        </Link>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-gray-600 text-xs font-mono">{peerId}</span>
                          {peer?.type && (
                            <span className="text-gray-600 text-xs">· {peer.type}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {!data && (
        <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded p-4">
          Could not load edge types from API.
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
            {data.families.map((f) => (
              <div
                key={f.slug}
                className={`border rounded p-3 text-center ${FAMILY_BG[f.slug] ?? "border-gray-700 bg-gray-800/30"}`}
              >
                <div className={`font-semibold text-sm ${FAMILY_COLORS[f.slug] ?? "text-white"}`}>
                  {f.name}
                </div>
                <div className="text-gray-500 text-xs mt-0.5">{f.types.length} types</div>
              </div>
            ))}
          </div>

          <div className="space-y-6">
            {data.families.map((family) => (
              <section key={family.slug}>
                <h2 className={`text-lg font-semibold mb-3 ${FAMILY_COLORS[family.slug] ?? "text-white"}`}>
                  {family.name}
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {family.types.map((t) => (
                    <div
                      key={t.slug}
                      className={`border rounded p-3 flex items-start gap-3 ${FAMILY_BG[family.slug] ?? "border-gray-700 bg-gray-800/30"}`}
                    >
                      <Link
                        href={`/graph?type=${t.slug}`}
                        className={`font-mono text-sm font-semibold ${FAMILY_COLORS[family.slug] ?? "text-white"} hover:underline flex-shrink-0`}
                      >
                        {t.slug}
                      </Link>
                      <span className="text-gray-400 text-xs leading-relaxed">{t.description}</span>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
