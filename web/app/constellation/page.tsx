import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Constellation",
  description:
    "The living network visualized as a constellation. See ideas, people, and connections as stars in a shared sky.",
};

type ConstellationNode = {
  id: string;
  label: string;
  kind: string;
  x: number;
  y: number;
  size: number;
  color: string;
  brightness: number;
};

type ConstellationEdge = {
  source: string;
  target: string;
  weight: number;
};

type ConstellationCluster = {
  cluster_id: string;
  label: string;
  node_count: number;
};

type ConstellationResponse = {
  nodes: ConstellationNode[];
  edges: ConstellationEdge[];
  clusters: ConstellationCluster[];
};

async function loadConstellation(): Promise<ConstellationResponse | null> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/constellation?max_nodes=80`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as ConstellationResponse;
  } catch {
    return null;
  }
}

function nodePositionById(
  nodes: ConstellationNode[],
): Map<string, ConstellationNode> {
  const map = new Map<string, ConstellationNode>();
  for (const node of nodes) {
    map.set(node.id, node);
  }
  return map;
}

export default async function ConstellationPage() {
  const data = await loadConstellation();

  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const clusters = data?.clusters ?? [];
  const nodeMap = nodePositionById(nodes);

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100">
      <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <header className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Constellation
          </h1>
          <p className="max-w-3xl text-gray-400 leading-relaxed">
            The living network rendered as a galaxy. Each point of light is an
            idea, a contributor, or a connection. Brighter stars have more
            energy. Lines trace the resonance between them.
          </p>
        </header>

        {/* Stats */}
        <section className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-gray-800 bg-gray-900/60 p-4">
            <p className="text-xs uppercase tracking-widest text-gray-500">
              Nodes
            </p>
            <p className="mt-2 text-3xl font-light text-white">
              {nodes.length}
            </p>
          </div>
          <div className="rounded-2xl border border-gray-800 bg-gray-900/60 p-4">
            <p className="text-xs uppercase tracking-widest text-gray-500">
              Edges
            </p>
            <p className="mt-2 text-3xl font-light text-white">
              {edges.length}
            </p>
          </div>
          <div className="rounded-2xl border border-gray-800 bg-gray-900/60 p-4">
            <p className="text-xs uppercase tracking-widest text-gray-500">
              Clusters
            </p>
            <p className="mt-2 text-3xl font-light text-white">
              {clusters.length}
            </p>
          </div>
        </section>

        {/* Galaxy visualization */}
        {nodes.length > 0 ? (
          <section className="space-y-4">
            <div
              className="relative w-full overflow-hidden rounded-2xl border border-gray-800 bg-black"
              style={{ aspectRatio: "1 / 1" }}
            >
              {/* Subtle radial glow in the center */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "radial-gradient(circle at 50% 50%, rgba(100, 100, 255, 0.03) 0%, transparent 70%)",
                }}
              />

              {/* Edges — subtle lines between connected nodes */}
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
              >
                {edges.map((edge) => {
                  const src = nodeMap.get(edge.source);
                  const tgt = nodeMap.get(edge.target);
                  if (!src || !tgt) return null;
                  return (
                    <line
                      key={`${edge.source}-${edge.target}`}
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke="rgba(148, 163, 184, 0.08)"
                      strokeWidth={Math.max(0.05, edge.weight * 0.3)}
                    />
                  );
                })}
              </svg>

              {/* Nodes — positioned dots */}
              {nodes.map((node) => {
                const diameter = Math.max(4, Math.min(24, node.size * 16));
                return (
                  <div
                    key={node.id}
                    className="absolute group"
                    style={{
                      left: `${node.x}%`,
                      top: `${node.y}%`,
                      transform: "translate(-50%, -50%)",
                    }}
                  >
                    {/* Glow halo */}
                    <div
                      className="absolute rounded-full"
                      style={{
                        width: diameter * 2.5,
                        height: diameter * 2.5,
                        left: "50%",
                        top: "50%",
                        transform: "translate(-50%, -50%)",
                        background: `radial-gradient(circle, ${node.color}33 0%, transparent 70%)`,
                        opacity: node.brightness,
                      }}
                    />
                    {/* Core dot */}
                    <div
                      className="relative rounded-full transition-transform duration-300 group-hover:scale-150"
                      style={{
                        width: diameter,
                        height: diameter,
                        backgroundColor: node.color,
                        opacity: Math.max(0.3, node.brightness),
                        boxShadow: `0 0 ${diameter * 0.8}px ${node.color}66`,
                      }}
                    />
                    {/* Tooltip */}
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10 whitespace-nowrap rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs text-gray-200 shadow-lg">
                      <p className="font-medium">{node.label}</p>
                      <p className="text-gray-500">{node.kind}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ) : (
          <section className="rounded-2xl border border-dashed border-gray-700 bg-gray-900/30 p-8 text-center space-y-3">
            <p className="text-gray-400">
              The constellation is still forming. As ideas and contributors join
              the network, stars will appear here.
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm">
              <Link href="/ideas" className="text-blue-400 hover:underline">
                Browse ideas
              </Link>
              <Link
                href="/discover"
                className="text-purple-400 hover:underline"
              >
                Discover
              </Link>
            </div>
          </section>
        )}

        {/* Cluster legend */}
        {clusters.length > 0 ? (
          <section className="rounded-2xl border border-gray-800 bg-gray-900/60 p-5 space-y-3">
            <h2 className="text-lg font-medium text-white">Clusters</h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {clusters.map((cluster) => (
                <div
                  key={cluster.cluster_id}
                  className="rounded-xl border border-gray-800 bg-gray-900/40 p-3 space-y-1"
                >
                  <p className="text-sm font-medium text-gray-200">
                    {cluster.label}
                  </p>
                  <p className="text-xs text-gray-500">
                    {cluster.node_count} node
                    {cluster.node_count === 1 ? "" : "s"}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {/* Navigation */}
        <nav
          className="py-8 text-center space-y-2 border-t border-gray-800"
          aria-label="Related pages"
        >
          <p className="text-xs text-gray-600 uppercase tracking-wider">
            Explore more
          </p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link href="/discover" className="text-purple-400 hover:underline">
              Discover
            </Link>
            <Link href="/vitality" className="text-emerald-400 hover:underline">
              Vitality
            </Link>
            <Link href="/resonance" className="text-blue-400 hover:underline">
              Resonance
            </Link>
            <Link href="/ideas" className="text-amber-400 hover:underline">
              All Ideas
            </Link>
          </div>
        </nav>
      </div>
    </main>
  );
}
