"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

interface Node {
  id: string;
  type: string;
  name: string;
  description: string;
  phase: string;
  created_at: string;
  updated_at: string;
  [key: string]: any; // merged properties
}

interface Edge {
  id: string;
  type: string;
  from_id: string;
  to_id: string;
  strength: number;
  created_at: string;
  [key: string]: any; // merged properties
}

interface NeighborsResponse {
  node: {
    id: string;
    type: string;
    name: string;
    description: string;
    phase: string;
    created_at: string;
    updated_at: string;
  };
  edge: {
    id: string;
    type: string;
    strength: number;
    direction: "incoming" | "outgoing";
  };
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function nodeTypeColor(type: string): string {
  const colors: Record<string, string> = {
    idea: "text-emerald-400",
    concept: "text-yellow-400",
    spec: "text-blue-400",
    implementation: "text-green-400",
    service: "text-purple-400",
    contributor: "text-pink-400",
    domain: "text-indigo-400",
    "pipeline-run": "text-orange-400",
    event: "text-red-400",
    artifact: "text-gray-400",
  };
  return colors[type] || "text-muted-foreground";
}

function edgeTypeColor(type: string): string {
  const colors: Record<string, string> = {
    inspires: "text-blue-400",
    "depends-on": "text-green-400",
    implements: "text-purple-400",
    contradicts: "text-red-400",
    extends: "text-orange-400",
    "analogous-to": "text-yellow-400",
    "parent-of": "text-indigo-400",
  };
  return colors[type] || "text-muted-foreground";
}

export default function GraphPage() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [neighbors, setNeighbors] = useState<NeighborsResponse[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nodeFilter, setNodeFilter] = useState("");

  const loadNodes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nodesRes, edgesRes] = await Promise.all([
        fetch(`${API}/api/graph/nodes`),
        fetch(`${API}/api/graph/edges`),
      ]);
      if (!nodesRes.ok) throw new Error(`Nodes failed (${nodesRes.status})`);
      if (!edgesRes.ok) throw new Error(`Edges failed (${edgesRes.status})`);
      const [nodesData, edgesData] = await Promise.all([
        nodesRes.json(),
        edgesRes.json(),
      ]);
      setNodes(nodesData);
      setEdges(edgesData);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadNeighbors = useCallback(async () => {
    if (!selectedNodeId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/graph/nodes/${selectedNodeId}/neighbors`);
      if (!res.ok) throw new Error(`Neighbors failed (${res.status})`);
      const data = await res.json();
      setNeighbors(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [selectedNodeId]);

  useEffect(() => { void loadNodes(); }, []);
  useEffect(() => { void loadNeighbors(); }, [selectedNodeId]);

  const filteredNodes = nodes.filter((n) =>
    n.name.toLowerCase().includes(nodeFilter.toLowerCase()) ||
    n.type.toLowerCase().includes(nodeFilter.toLowerCase())
  );

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-6xl mx-auto space-y-6">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <p className="text-xs text-muted-foreground uppercase tracking-widest">Graph</p>
        <h1 className="text-3xl font-light tracking-tight">Universal Knowledge Graph</h1>
        <p className="text-muted-foreground">
          Explore the unified node+edge data layer. Every entity is a node, every relationship is an edge.
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={nodeFilter}
            onChange={(e) => setNodeFilter(e.target.value)}
            placeholder="Filter nodes by name or type..."
            className="flex-1 min-w-48 rounded-xl border border-border/40 bg-card/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <select
            value={selectedNodeId || ""}
            onChange={(e) => {
              setSelectedNodeId(e.target.value || null);
              if (e.target.value) void loadNeighbors();
            }}
            className="rounded-xl border border-border/40 bg-card/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Select a node to see neighbors</option>
            {filteredNodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.name} ({node.type})
              </option>
            ))}
          </select>
        </div>
      </section>

      {loading && <p className="text-muted-foreground">Loading graph data…</p>}
      {error && <p className="text-destructive">Error: {error}</p>}

      {!loading && !error && nodes.length === 0 && (
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center space-y-3">
          <p className="text-4xl" aria-hidden="true">🌐</p>
          <p className="text-lg text-muted-foreground">
            No nodes in the graph yet. Create a node via CLI or API to get started.
          </p>
          <div className="flex justify-center space-x-3">
            <Link href="/contribute" className="text-primary hover:text-foreground transition-colors">
              Contribute an idea →
            </Link>
            <Link href="/invest" className="text-primary hover:text-foreground transition-colors">
              Visit the garden →
            </Link>
          </div>
        </div>
      )}

      {!loading && !error && nodes.length > 0 && (
        <>
          <div className="space-y-4">
            <div className="rounded-xl border border-border/20 bg-background/40 p-4">
              <h2 className="text-lg font-medium">Node Explorer</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b border-border/20">
                      <th className="pb-2 pr-4">Name</th>
                      <th className="pb-2 pr-4">Type</th>
                      <th className="pb-2 pr-4">ID (click to explore)</th>
                      <th className="pb-2 pr-4">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/10">
                    {filteredNodes.slice(0, 50).map((node) => (
                      <tr
                        key={node.id}
                        className={`hover:bg-accent/20 transition-colors cursor-pointer ${
                          selectedNodeId === node.id ? "border-l-4 border-primary" : ""
                        }`}
                        onClick={() => {
                          if (selectedNodeId === node.id) {
                            setSelectedNodeId(null);
                            setNeighbors([]);
                          } else {
                            setSelectedNodeId(node.id);
                          }
                        }}
                      >
                        <td className="py-3 pr-4">
                          <span className={nodeTypeColor(node.type)}>{node.name}</span>
                        </td>
                        <td className="py-3 pr-4 text-xs">{node.type}</td>
                        <td className="py-3 pr-4 font-mono truncate max-w-[10rem]">{node.id}</td>
                        <td className="py-3 pr-4 text-xs">{fmtDate(node.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {selectedNodeId && (
              <div className="rounded-xl border border-border/20 bg-background/40 p-4">
                <h2 className="text-lg font-medium">Neighbors of {selectedNodeId}</h2>
                {neighbors.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No neighbors found. This node may be isolated or have no relationships yet.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-muted-foreground border-b border-border/20">
                          <th className="pb-2 pr-4">Neighbor</th>
                          <th className="pb-2 pr-4">Relationship</th>
                          <th className="pb-2 pr-4">Strength</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/10">
                        {neighbors.map((rel, idx) => (
                          <tr key={idx} className="hover:bg-accent/20 transition-colors">
                            <td className="py-3 pr-4">
                              <span className={nodeTypeColor(rel.node.type)}>{rel.node.name}</span>
                            </td>
                            <td className="py-3 pr-4 text-xs">
                              <span className={edgeTypeColor(rel.edge.type)}>{rel.edge.type}</span>
                            </td>
                            <td className="py-3 pr-4 text-xs">{rel.edge.strength.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      <div className="flex gap-4 text-sm text-muted-foreground pt-2">
        <Link href="/invest" className="hover:text-foreground transition-colors">← Visit the Garden</Link>
        <Link href="/contribute" className="hover:text-foreground transition-colors">Contribute →</Link>
        <Link href="/ideas" className="hover:text-foreground transition-colors">Browse Ideas →</Link>
      </div>
    </main>
  );
}
