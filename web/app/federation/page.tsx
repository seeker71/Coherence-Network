"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

interface PerNode {
  success_rate: number;
  samples: number;
  avg_duration_s: number;
}

interface ProviderStats {
  total_runs: number;
  successes: number;
  failures: number;
  success_rate: number;
  avg_duration_s: number;
  node_count: number;
  per_node: Record<string, PerNode>;
  needs_attention: boolean;
}

interface NodeInfo {
  hostname: string;
  os_type: string;
  status: string;
  last_seen_at: string;
}

interface Alert {
  provider: string;
  metric: string;
  value: number;
  threshold: number;
  message: string;
}

interface TaskTypeProviders {
  providers: Record<
    string,
    { total_samples: number; success_rate: number; avg_duration_s: number }
  >;
}

interface NetworkStats {
  providers: Record<string, ProviderStats>;
  nodes: Record<string, NodeInfo>;
  task_types: Record<string, TaskTypeProviders>;
  alerts: Alert[];
  summary: {
    total_providers: number;
    healthy_providers: number;
    attention_needed: number;
    total_measurements: number;
  };
  window_days: number;
  data_source: "live" | "unavailable";
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export default function FederationPage() {
  const [stats, setStats] = useState<NetworkStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const base = getApiBase();
      const res = await fetch(`${base}/api/providers/stats/network`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: NetworkStats = await res.json();
      setStats(data);
      setError(null);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const id = setInterval(fetchStats, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchStats]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 font-mono text-sm">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Federation Network Stats</h1>
          <p className="text-zinc-500">
            Aggregated provider performance across all nodes
          </p>
        </div>
        <Link href="/" className="text-blue-600 hover:underline">
          &larr; Home
        </Link>
      </div>

      {loading && <p className="text-zinc-400">Loading...</p>}

      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-4 py-2 text-red-700">
          Error: {error}
        </div>
      )}

      {stats?.data_source === "unavailable" && (
        <div className="mb-4 rounded border border-yellow-300 bg-yellow-50 px-4 py-2 text-yellow-800">
          Data source unavailable — stats may be stale or empty.
        </div>
      )}

      {stats && (
        <>
          {/* Summary bar */}
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <SummaryCard
              label="Providers"
              value={stats.summary.total_providers}
            />
            <SummaryCard
              label="Healthy"
              value={stats.summary.healthy_providers}
              color="text-green-600"
            />
            <SummaryCard
              label="Attention"
              value={stats.summary.attention_needed}
              color={
                stats.summary.attention_needed > 0
                  ? "text-red-600"
                  : "text-zinc-600"
              }
            />
            <SummaryCard
              label="Measurements"
              value={stats.summary.total_measurements.toLocaleString()}
            />
          </div>

          {/* Alerts */}
          {stats.alerts.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-lg font-semibold text-red-600">
                Alerts
              </h2>
              <ul className="space-y-1">
                {stats.alerts.map((a, i) => (
                  <li
                    key={i}
                    className="rounded border border-red-200 bg-red-50 px-3 py-1 text-red-700"
                  >
                    {a.message}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Nodes */}
          <section className="mb-6">
            <h2 className="mb-2 text-lg font-semibold">
              Nodes ({Object.keys(stats.nodes).length})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b text-zinc-500">
                    <th className="py-1 pr-4">Node ID</th>
                    <th className="py-1 pr-4">Hostname</th>
                    <th className="py-1 pr-4">OS</th>
                    <th className="py-1 pr-4">Status</th>
                    <th className="py-1 pr-4">Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats.nodes).map(([nid, info]) => (
                    <tr key={nid} className="border-b border-zinc-100">
                      <td className="py-1 pr-4 font-mono text-xs">{nid}</td>
                      <td className="py-1 pr-4">{info.hostname || "—"}</td>
                      <td className="py-1 pr-4">{info.os_type || "—"}</td>
                      <td className="py-1 pr-4">
                        <span
                          className={
                            info.status === "active"
                              ? "text-green-600"
                              : "text-zinc-400"
                          }
                        >
                          {info.status}
                        </span>
                      </td>
                      <td className="py-1 pr-4 text-xs text-zinc-500">
                        {info.last_seen_at || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Provider stats */}
          <section className="mb-6">
            <h2 className="mb-2 text-lg font-semibold">Provider Performance</h2>
            {Object.keys(stats.providers).length === 0 ? (
              <p className="text-zinc-400">
                No provider data yet. Nodes need to push measurements first.
              </p>
            ) : (
              <div className="space-y-4">
                {Object.entries(stats.providers).map(([pid, p]) => (
                  <div
                    key={pid}
                    className={`rounded border p-4 ${
                      p.needs_attention
                        ? "border-red-300 bg-red-50"
                        : "border-zinc-200"
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="font-semibold">{pid}</h3>
                      <span
                        className={`text-xs ${
                          p.needs_attention ? "text-red-600" : "text-green-600"
                        }`}
                      >
                        {pct(p.success_rate)} success
                      </span>
                    </div>
                    <div className="mb-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                      <Stat label="Total runs" value={p.total_runs} />
                      <Stat label="Successes" value={p.successes} />
                      <Stat label="Failures" value={p.failures} />
                      <Stat
                        label="Avg duration"
                        value={`${p.avg_duration_s}s`}
                      />
                    </div>
                    {Object.keys(p.per_node).length > 0 && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-zinc-500 hover:text-zinc-700">
                          Per-node breakdown ({p.node_count} nodes)
                        </summary>
                        <table className="mt-1 w-full border-collapse">
                          <thead>
                            <tr className="text-zinc-400">
                              <th className="py-0.5 pr-3 text-left">Node</th>
                              <th className="py-0.5 pr-3 text-right">
                                Samples
                              </th>
                              <th className="py-0.5 pr-3 text-right">
                                Success
                              </th>
                              <th className="py-0.5 text-right">Avg dur</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(p.per_node).map(([nid, nd]) => (
                              <tr key={nid}>
                                <td className="py-0.5 pr-3 font-mono">
                                  {nid.slice(0, 8)}
                                </td>
                                <td className="py-0.5 pr-3 text-right">
                                  {nd.samples}
                                </td>
                                <td className="py-0.5 pr-3 text-right">
                                  {pct(nd.success_rate)}
                                </td>
                                <td className="py-0.5 text-right">
                                  {nd.avg_duration_s}s
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Task type breakdown */}
          {Object.keys(stats.task_types).length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-lg font-semibold">
                Performance by Task Type
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b text-zinc-500">
                      <th className="py-1 pr-4">Task Type</th>
                      <th className="py-1 pr-4">Provider</th>
                      <th className="py-1 pr-4 text-right">Samples</th>
                      <th className="py-1 pr-4 text-right">Success Rate</th>
                      <th className="py-1 text-right">Avg Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(stats.task_types).map(([tt, data]) =>
                      Object.entries(data.providers).map(([pid, tp]) => (
                        <tr
                          key={`${tt}-${pid}`}
                          className="border-b border-zinc-100"
                        >
                          <td className="py-1 pr-4 font-medium">{tt}</td>
                          <td className="py-1 pr-4">{pid}</td>
                          <td className="py-1 pr-4 text-right">
                            {tp.total_samples}
                          </td>
                          <td className="py-1 pr-4 text-right">
                            {pct(tp.success_rate)}
                          </td>
                          <td className="py-1 text-right">
                            {tp.avg_duration_s}s
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <p className="text-xs text-zinc-400">
            Window: {stats.window_days} days | Last updated: {lastUpdated} |
            Data source: {stats.data_source}
          </p>
        </>
      )}
    </main>
  );
}

function SummaryCard({
  label,
  value,
  color = "text-zinc-900",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="rounded border border-zinc-200 px-4 py-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div>
      <span className="text-zinc-500">{label}: </span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
