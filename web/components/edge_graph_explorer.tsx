"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

type Peer = { id: string; type?: string; name?: string; phase?: string };

type NavEdge = {
  id: string;
  type: string;
  from_id: string;
  to_id: string;
  peer_id: string;
  peer: Peer;
  edge_direction: string;
  strength?: number;
};

type GraphNode = {
  id: string;
  type: string;
  name: string;
  description?: string;
  phase?: string;
};

type RelType = { id: string; name: string; description?: string };

function apiPath(path: string): string {
  if (path.startsWith("/api/")) return path;
  return `/api${path.startsWith("/") ? "" : "/"}${path}`;
}

export default function EdgeGraphExplorer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const idFromUrl = searchParams.get("id")?.trim() || "";

  const [inputId, setInputId] = useState(idFromUrl);
  const [node, setNode] = useState<GraphNode | null>(null);
  const [edges, setEdges] = useState<NavEdge[]>([]);
  const [relTypes, setRelTypes] = useState<RelType[]>([]);
  const [filterType, setFilterType] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setInputId(idFromUrl);
  }, [idFromUrl]);

  const loadTypes = useCallback(async () => {
    try {
      const r = await fetch(apiPath("/edges/types"), { cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      setRelTypes(Array.isArray(data.items) ? data.items : []);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadTypes();
  }, [loadTypes]);

  const fetchEntity = useCallback(async (id: string, typeFilter: string) => {
    if (!id.trim()) {
      setNode(null);
      setEdges([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const nodeRes = await fetch(apiPath(`/graph/nodes/${encodeURIComponent(id)}`), {
        cache: "no-store",
      });
      if (!nodeRes.ok) {
        setNode(null);
        setEdges([]);
        setError(nodeRes.status === 404 ? `No entity '${id}'` : `HTTP ${nodeRes.status}`);
        return;
      }
      const n = (await nodeRes.json()) as GraphNode;
      setNode(n);

      let url = apiPath(`/entities/${encodeURIComponent(id)}/edges`);
      if (typeFilter) url += `?type=${encodeURIComponent(typeFilter)}`;
      const eRes = await fetch(url, { cache: "no-store" });
      if (!eRes.ok) {
        setEdges([]);
        setError(`Edges: HTTP ${eRes.status}`);
        return;
      }
      const list = (await eRes.json()) as NavEdge[];
      setEdges(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setEdges([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (idFromUrl) void fetchEntity(idFromUrl, filterType);
    else {
      setNode(null);
      setEdges([]);
    }
  }, [idFromUrl, filterType, fetchEntity]);

  const onGo = () => {
    const id = inputId.trim();
    const q = new URLSearchParams();
    if (id) q.set("id", id);
    router.push(`/edges${q.toString() ? `?${q}` : ""}`);
  };

  const onSelectPeer = (peerId: string) => {
    setInputId(peerId);
    const q = new URLSearchParams();
    q.set("id", peerId);
    router.push(`/edges?${q}`);
  };

  const typeOptions = useMemo(() => relTypes.map((t) => t.id).sort(), [relTypes]);

  const activeId = node?.id || idFromUrl;

  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-border/50 bg-card/40 p-6 shadow-sm backdrop-blur-sm">
        <h2 className="text-lg font-semibold tracking-tight">Browse by entity</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter a graph node id, then follow typed edges to connected ideas, specs, contributors, and more.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm">
            <span className="mb-1 block text-muted-foreground">Entity id</span>
            <input
              className="w-full rounded-lg border border-border/60 bg-background px-3 py-2 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring"
              value={inputId}
              onChange={(e) => setInputId(e.target.value)}
              placeholder="e.g. idea slug or graph node id"
              onKeyDown={(e) => e.key === "Enter" && onGo()}
            />
          </label>
          <label className="sm:w-56 text-sm">
            <span className="mb-1 block text-muted-foreground">Relationship type (optional)</span>
            <select
              className="w-full rounded-lg border border-border/60 bg-background px-3 py-2 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
            >
              <option value="">All types</option>
              {typeOptions.map((tid) => (
                <option key={tid} value={tid}>
                  {tid}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={onGo}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:opacity-95"
          >
            Load
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      </section>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {node && !loading && (
        <section
          className="rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/5 to-transparent p-6"
          aria-live="polite"
        >
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-primary">
              {node.type}
            </span>
            <h3 className="text-xl font-semibold">{node.name || node.id}</h3>
          </div>
          {node.description ? (
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{node.description}</p>
          ) : null}
          <p className="mt-2 font-mono text-xs text-muted-foreground">id: {activeId}</p>
        </section>
      )}

      {edges.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted-foreground">
            Edges ({edges.length})
          </h3>
          <ul className="space-y-2">
            {edges.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => onSelectPeer(e.peer_id)}
                  className="w-full rounded-xl border border-border/40 bg-card/50 px-4 py-3 text-left text-sm transition hover:border-primary/40 hover:bg-accent/30"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-xs">{e.type}</span>
                    <span className="text-xs text-muted-foreground">{e.edge_direction}</span>
                  </div>
                  <div className="mt-1 font-medium">
                    {e.peer.name || e.peer_id}{" "}
                    <span className="font-normal text-muted-foreground">
                      ({e.peer.type || "?"})
                    </span>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                    → {e.peer_id}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {node && !loading && edges.length === 0 && !error && (
        <p className="text-sm text-muted-foreground">No edges for this entity with the current filter.</p>
      )}
    </div>
  );
}
