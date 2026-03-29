import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "System Map — Meta",
  description:
    "Explore every API endpoint, module, and data type as a navigable concept node. See which idea spawned it, which spec defines it.",
};

type EndpointEdge = {
  type: string;
  target_id: string;
  target_label?: string;
};

type EndpointNode = {
  id: string;
  method: string;
  path: string;
  name: string;
  summary?: string;
  tags: string[];
  spec_id?: string;
  idea_id?: string;
  module?: string;
  request_model?: string;
  response_model?: string;
  edges: EndpointEdge[];
};

type ModuleNode = {
  id: string;
  name: string;
  module_type: string;
  file_path?: string;
  spec_ids: string[];
  idea_ids: string[];
  endpoint_count: number;
};

type TypeField = {
  name: string;
  type_str: string;
  required: boolean;
  default?: string;
  description?: string;
};

type TypeNode = {
  id: string;
  name: string;
  module: string;
  fields: TypeField[];
  used_in_endpoints: string[];
  base_classes: string[];
};

type MetaGraphResponse = {
  node_count: number;
  edge_count: number;
  nodes: { node_type: string }[];
};

type MetaSummary = {
  endpoint_count: number;
  module_count: number;
  type_count: number;
  traced_count: number;
  spec_coverage: number;
};

async function fetchSummary(): Promise<MetaSummary | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/meta/summary`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchEndpoints(): Promise<EndpointNode[]> {
  try {
    const res = await fetch(`${getApiBase()}/api/meta/endpoints`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.endpoints ?? [];
  } catch {
    return [];
  }
}

async function fetchModules(): Promise<ModuleNode[]> {
  try {
    const res = await fetch(`${getApiBase()}/api/meta/modules`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.modules ?? [];
  } catch {
    return [];
  }
}

async function fetchTypes(): Promise<TypeNode[]> {
  try {
    const res = await fetch(`${getApiBase()}/api/meta/types`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.types ?? [];
  } catch {
    return [];
  }
}

async function fetchGraph(): Promise<MetaGraphResponse | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/meta/graph`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function methodBadge(method: string) {
  const colors: Record<string, string> = {
    GET: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    POST: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    PUT: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    PATCH:
      "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    DELETE: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  };
  const cls =
    colors[method] ||
    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono font-bold ${cls}`}
    >
      {method}
    </span>
  );
}

function moduleTypeBadge(type: string) {
  const colors: Record<string, string> = {
    router:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    service:
      "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
    model:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    middleware:
      "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  };
  const cls =
    colors[type] ||
    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono ${cls}`}
    >
      {type}
    </span>
  );
}

function CoverageBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 50
      ? "bg-green-500"
      : pct >= 25
        ? "bg-yellow-500"
        : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded overflow-hidden">
        <div
          className={`h-full ${color} rounded transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-mono text-muted-foreground">{pct}%</span>
    </div>
  );
}

function NodeTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    route: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    module: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
    type: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
    spec: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    idea: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  };
  const cls =
    colors[type] ||
    "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono ${cls}`}>
      {type}
    </span>
  );
}

export default async function MetaPage() {
  const [summary, endpoints, modules, types, graph] = await Promise.all([
    fetchSummary(),
    fetchEndpoints(),
    fetchModules(),
    fetchTypes(),
    fetchGraph(),
  ]);

  // Group endpoints by tag
  const byTag: Record<string, EndpointNode[]> = {};
  for (const ep of endpoints) {
    const tag = ep.tags[0] || "other";
    if (!byTag[tag]) byTag[tag] = [];
    byTag[tag].push(ep);
  }

  // Count graph node types
  const nodeTypeCounts: Record<string, number> = {};
  if (graph) {
    for (const n of graph.nodes) {
      nodeTypeCounts[n.node_type] = (nodeTypeCounts[n.node_type] ?? 0) + 1;
    }
  }

  return (
    <main className="max-w-6xl mx-auto px-4 py-10 space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">System Map</h1>
        <p className="mt-2 text-muted-foreground max-w-2xl">
          Every API route, code module, and data type is a{" "}
          <code className="font-mono text-xs">codex.meta</code> concept node.
          Click a spec or idea link to trace the full lineage — from the
          original idea through the spec to the live code.
        </p>
      </div>

      {/* Summary stats */}
      {summary && (
        <section className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {[
            { label: "Endpoints", value: summary.endpoint_count },
            { label: "Modules", value: summary.module_count },
            { label: "Types", value: summary.type_count },
            { label: "Traced", value: summary.traced_count },
            { label: "Coverage", value: null, coverage: summary.spec_coverage },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-lg border bg-card p-4 space-y-1"
            >
              <p className="text-xs text-muted-foreground uppercase tracking-wide">
                {s.label}
              </p>
              {s.coverage !== undefined && s.coverage !== null ? (
                <CoverageBar value={s.coverage} />
              ) : (
                <p className="text-2xl font-bold tabular-nums">{s.value}</p>
              )}
            </div>
          ))}
        </section>
      )}

      {/* Graph overview */}
      {graph && (
        <section className="rounded-lg border bg-card p-5 space-y-3">
          <h2 className="text-base font-semibold">
            Meta-Node Graph{" "}
            <span className="text-muted-foreground font-normal text-sm">
              {graph.node_count} nodes · {graph.edge_count} edges
            </span>
          </h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(nodeTypeCounts)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([type, count]) => (
                <div key={type} className="flex items-center gap-2">
                  <NodeTypeBadge type={type} />
                  <span className="text-sm tabular-nums text-muted-foreground">
                    {count}
                  </span>
                </div>
              ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Full graph available at{" "}
            <code className="font-mono">GET /api/meta/graph</code> ·
            Auto-generated docs at{" "}
            <code className="font-mono">GET /api/meta/docs</code>
          </p>
        </section>
      )}

      {/* Types */}
      {types.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4">
            Data Types{" "}
            <span className="text-muted-foreground font-normal text-base">
              ({types.length} codex.meta/type nodes)
            </span>
          </h2>
          <div className="border rounded-lg divide-y overflow-hidden">
            {types.map((tn) => (
              <div
                key={tn.id}
                className="px-4 py-3 hover:bg-muted/40 transition-colors"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-mono text-sm font-semibold text-foreground">
                    {tn.name}
                  </span>
                  <span className="text-xs text-muted-foreground font-mono">
                    {tn.fields.length} fields
                  </span>
                  {tn.used_in_endpoints.length > 0 && (
                    <span className="text-xs text-muted-foreground">
                      used in {tn.used_in_endpoints.length} endpoint
                      {tn.used_in_endpoints.length !== 1 ? "s" : ""}
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground font-mono truncate">
                    {tn.module}
                  </span>
                </div>
                {tn.fields.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {tn.fields.slice(0, 8).map((f) => (
                      <span
                        key={f.name}
                        className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                        title={`${f.type_str}${f.required ? "" : " (optional)"}`}
                      >
                        {f.name}
                        {!f.required && (
                          <span className="opacity-50">?</span>
                        )}
                      </span>
                    ))}
                    {tn.fields.length > 8 && (
                      <span className="text-xs text-muted-foreground px-1">
                        +{tn.fields.length - 8} more
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Endpoints by tag */}
      <section>
        <h2 className="text-xl font-semibold mb-4">
          Endpoints{" "}
          <span className="text-muted-foreground font-normal text-base">
            ({endpoints.length})
          </span>
        </h2>
        {Object.keys(byTag).length === 0 ? (
          <p className="text-muted-foreground">No endpoints found.</p>
        ) : (
          <div className="space-y-6">
            {Object.entries(byTag)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([tag, eps]) => (
                <div key={tag}>
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                    {tag}
                  </h3>
                  <div className="border rounded-lg divide-y overflow-hidden">
                    {eps.map((ep) => (
                      <div
                        key={ep.id}
                        className="px-4 py-3 flex flex-wrap items-start gap-x-3 gap-y-1 hover:bg-muted/40 transition-colors"
                      >
                        <span className="shrink-0 mt-0.5">
                          {methodBadge(ep.method)}
                        </span>
                        <span className="font-mono text-sm text-foreground min-w-0 break-all">
                          {ep.path}
                        </span>
                        {ep.spec_id && (
                          <Link
                            href={`/specs?q=${encodeURIComponent(ep.spec_id)}`}
                            className="text-xs px-1.5 py-0.5 rounded bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300 hover:opacity-80"
                          >
                            spec-{ep.spec_id}
                          </Link>
                        )}
                        {ep.idea_id && (
                          <Link
                            href={`/ideas/${encodeURIComponent(ep.idea_id)}`}
                            className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 hover:opacity-80"
                          >
                            {ep.idea_id}
                          </Link>
                        )}
                        {ep.response_model && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">
                            → {ep.response_model.split("/").pop()}
                          </span>
                        )}
                        {ep.summary && (
                          <span className="w-full text-xs text-muted-foreground mt-0.5 truncate">
                            {ep.summary}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}
      </section>

      {/* Modules */}
      <section>
        <h2 className="text-xl font-semibold mb-4">
          Modules{" "}
          <span className="text-muted-foreground font-normal text-base">
            ({modules.length})
          </span>
        </h2>
        {modules.length === 0 ? (
          <p className="text-muted-foreground">No modules found.</p>
        ) : (
          <div className="border rounded-lg divide-y overflow-hidden">
            {modules.map((mod) => (
              <div
                key={mod.id}
                className="px-4 py-3 flex flex-wrap items-center gap-x-3 gap-y-1 hover:bg-muted/40 transition-colors"
              >
                <span className="shrink-0">{moduleTypeBadge(mod.module_type)}</span>
                <span className="font-mono text-sm text-foreground">
                  {mod.name}
                </span>
                {mod.endpoint_count > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {mod.endpoint_count} ep
                  </span>
                )}
                {mod.spec_ids.map((sid) => (
                  <Link
                    key={sid}
                    href={`/specs?q=${encodeURIComponent(sid)}`}
                    className="text-xs px-1.5 py-0.5 rounded bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300 hover:opacity-80"
                  >
                    spec-{sid}
                  </Link>
                ))}
                {mod.idea_ids.slice(0, 2).map((iid) => (
                  <Link
                    key={iid}
                    href={`/ideas/${encodeURIComponent(iid)}`}
                    className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 hover:opacity-80"
                  >
                    {iid}
                  </Link>
                ))}
                {mod.idea_ids.length > 2 && (
                  <span className="text-xs text-muted-foreground">
                    +{mod.idea_ids.length - 2} ideas
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* CLI hint */}
      <section className="rounded-lg border bg-muted/30 px-5 py-4">
        <p className="text-sm text-muted-foreground">
          <strong className="text-foreground">API:</strong>{" "}
          <code className="font-mono text-xs">GET /api/meta/summary</code> ·{" "}
          <code className="font-mono text-xs">GET /api/meta/endpoints</code> ·{" "}
          <code className="font-mono text-xs">GET /api/meta/types</code> ·{" "}
          <code className="font-mono text-xs">GET /api/meta/graph</code> ·{" "}
          <code className="font-mono text-xs">GET /api/meta/docs</code>
        </p>
      </section>
    </main>
  );
}
