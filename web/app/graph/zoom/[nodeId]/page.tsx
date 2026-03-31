"use client";

/**
 * Fractal zoom page (Spec 182).
 *
 * URL structure:
 *   /graph/zoom/trust          — zoom into Trust node (depth=1)
 *   /graph/zoom/coherence-scoring — zoom into Coherence Scoring
 *
 * Renders Card/Garden view (ZoomCard) or Graph view (ZoomGraph)
 * based on view_hint, with a toggle button to override.
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ZoomCardGrid, type ZoomNodeSummary } from "@/components/graph/ZoomCard";
import { ZoomGraph } from "@/components/graph/ZoomGraph";

interface OpenQuestion {
  id: string;
  question: string;
  created_at: string;
  resolved: boolean;
  resolved_at?: string | null;
}

interface ZoomNodeData extends ZoomNodeSummary {
  open_questions: OpenQuestion[];
  edges: Array<{ from: string; to: string; edge_type: string }>;
}

interface ZoomResponse {
  node: ZoomNodeData;
  depth_requested: number;
  total_nodes_in_subtree: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function fetchZoom(nodeId: string, depth = 1): Promise<ZoomResponse> {
  const url = `${API_BASE}/graph/zoom/${encodeURIComponent(nodeId)}?depth=${depth}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export default function ZoomPage() {
  const params = useParams();
  const router = useRouter();
  const nodeId = Array.isArray(params.nodeId) ? params.nodeId[0] : params.nodeId ?? "";

  const [data, setData] = useState<ZoomResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"auto" | "cards" | "graph">("auto");

  useEffect(() => {
    if (!nodeId) return;
    setLoading(true);
    setError(null);
    fetchZoom(nodeId, 1)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [nodeId]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-gray-500">
        Loading…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error ?? "Node not found."}
        </div>
        <Link href="/graph" className="mt-4 inline-block text-sm text-indigo-600 hover:underline">
          ← Back to pillars
        </Link>
      </div>
    );
  }

  const node = data.node;
  const effectiveView =
    viewMode === "auto" ? node.view_hint : viewMode;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500 flex items-center gap-1">
        <Link href="/graph" className="hover:underline">Pillars</Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">{node.name}</span>
      </nav>

      {/* Node header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{node.name}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
            <span>{node.node_type}</span>
            <span>·</span>
            <span>{node.lifecycle_state}</span>
            <span>·</span>
            <span>
              Coherence: <strong>{Math.round(node.coherence_score * 100)}%</strong>
            </span>
            <span>·</span>
            <span>{data.total_nodes_in_subtree} node{data.total_nodes_in_subtree !== 1 ? "s" : ""}</span>
          </div>
        </div>

        {/* View toggle */}
        <div className="flex gap-2 shrink-0">
          {(["auto", "cards", "graph"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
                viewMode === mode
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
              }`}
            >
              {mode === "auto" ? `Auto (${node.view_hint})` : mode === "cards" ? "Cards" : "Graph"}
            </button>
          ))}
        </div>
      </div>

      {/* Open questions */}
      {node.open_questions.filter((q) => !q.resolved).length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 space-y-1">
          <h2 className="text-sm font-semibold text-yellow-800">Open Questions</h2>
          <ul className="space-y-1">
            {node.open_questions
              .filter((q) => !q.resolved)
              .map((q) => (
                <li key={q.id} className="text-sm text-yellow-700">
                  {q.question}
                </li>
              ))}
          </ul>
        </div>
      )}

      {/* Main content — card grid or graph */}
      {node.children.length === 0 ? (
        <p className="text-gray-500 text-sm">This node has no children.</p>
      ) : effectiveView === "graph" ? (
        <ZoomGraph
          rootNode={node}
          onNodeClick={(id) => router.push(`/graph/zoom/${id}`)}
        />
      ) : (
        <ZoomCardGrid nodes={node.children as ZoomNodeSummary[]} />
      )}
    </div>
  );
}
