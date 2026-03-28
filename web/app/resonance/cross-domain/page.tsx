"use client";

import { useEffect, useState, useCallback } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

type NodeSummary = {
  id: string;
  name: string;
  domain: string;
};

type ResonanceItem = {
  id: string;
  node_a: NodeSummary;
  node_b: NodeSummary;
  domain_a: string;
  domain_b: string;
  resonance_score: number;
  structural_sim: number;
  depth2_sim: number;
  crk_score: number;
  edge_id: string | null;
  discovered_at: string;
  scan_mode: string;
};

type ResonanceList = {
  items: ResonanceItem[];
  total: number;
  limit: number;
  offset: number;
};

type DomainPair = {
  domain_a: string;
  domain_b: string;
  count: number;
};

type DiscoveryDay = {
  date: string;
  new_resonances: number;
};

type TopResonance = {
  node_a: string;
  node_b: string;
  score: number;
  domain_pair: string;
};

type ProofData = {
  total_resonances: number;
  total_analogous_to_edges: number;
  analogous_to_edges_from_cdcr: number;
  domain_pairs_covered: DomainPair[];
  discovery_timeline: DiscoveryDay[];
  top_resonances: TopResonance[];
  avg_score: number;
  nodes_with_cross_domain_bridge: number;
  organic_growth_rate: number;
  proof_status: "active" | "stale";
};

type ScanStatus = {
  scan_id: string;
  status: string;
  mode: string;
  nodes_evaluated: number;
  pairs_compared: number;
  resonances_found: number;
  resonances_created: number;
  resonances_updated: number;
  duration_ms: number | null;
};

// ─── Score bar ─────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 85 ? "bg-emerald-500" : pct >= 70 ? "bg-blue-500" : "bg-amber-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-600 w-10 text-right">
        {(score).toFixed(2)}
      </span>
    </div>
  );
}

// ─── Domain bridge heatmap ─────────────────────────────────────────────────

function DomainHeatmap({ pairs }: { pairs: DomainPair[] }) {
  if (!pairs.length) {
    return (
      <p className="text-sm text-gray-400 italic">No domain pairs yet.</p>
    );
  }

  const domains = Array.from(
    new Set(pairs.flatMap((p) => [p.domain_a, p.domain_b]))
  ).sort();

  const maxCount = Math.max(...pairs.map((p) => p.count), 1);

  const getCount = (a: string, b: string) => {
    const p = pairs.find(
      (x) =>
        (x.domain_a === a && x.domain_b === b) ||
        (x.domain_a === b && x.domain_b === a)
    );
    return p?.count ?? 0;
  };

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="p-1 text-right text-gray-400 font-normal w-24"></th>
            {domains.map((d) => (
              <th
                key={d}
                className="p-1 text-center font-normal text-gray-500 max-w-16 truncate"
                title={d}
              >
                {d.slice(0, 8)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {domains.map((da) => (
            <tr key={da}>
              <td
                className="p-1 text-right text-gray-500 pr-2 truncate max-w-24"
                title={da}
              >
                {da.slice(0, 10)}
              </td>
              {domains.map((db) => {
                const count = getCount(da, db);
                const intensity =
                  da === db ? 0 : Math.round((count / maxCount) * 100);
                return (
                  <td
                    key={db}
                    className="p-1 text-center border border-gray-50"
                    title={`${da} ↔ ${db}: ${count}`}
                  >
                    <div
                      className="w-8 h-6 rounded flex items-center justify-center text-xs font-mono"
                      style={{
                        backgroundColor:
                          da === db
                            ? "#f3f4f6"
                            : `rgba(99,102,241,${intensity / 100})`,
                        color: intensity > 50 ? "#fff" : "#374151",
                      }}
                    >
                      {count > 0 ? count : ""}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Growth timeline ─────────────────────────────────────────────────────────

function GrowthTimeline({ timeline }: { timeline: DiscoveryDay[] }) {
  if (!timeline.length) {
    return <p className="text-sm text-gray-400 italic">No data yet.</p>;
  }

  const maxVal = Math.max(...timeline.map((d) => d.new_resonances), 1);
  const recent = [...timeline].slice(0, 30).reverse();

  return (
    <div className="flex items-end gap-1 h-20">
      {recent.map((day) => (
        <div
          key={day.date}
          className="flex-1 min-w-0 flex flex-col items-center justify-end gap-0.5"
          title={`${day.date}: ${day.new_resonances}`}
        >
          <div
            className="w-full bg-indigo-500 rounded-t transition-all"
            style={{
              height: `${Math.max(4, (day.new_resonances / maxVal) * 72)}px`,
            }}
          />
        </div>
      ))}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CrossDomainResonancePage() {
  const [proof, setProof] = useState<ProofData | null>(null);
  const [resonances, setResonances] = useState<ResonanceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchProof = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/resonance/cross-domain/proof`);
      if (res.ok) setProof(await res.json());
    } catch {
      // non-critical
    }
  }, []);

  const fetchResonances = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/resonance/cross-domain?limit=10&min_score=0.65`
      );
      if (res.ok) {
        const data: ResonanceList = await res.json();
        setResonances(data.items);
        setTotal(data.total);
      }
    } catch {
      // non-critical
    }
  }, []);

  useEffect(() => {
    fetchProof();
    fetchResonances();
  }, [fetchProof, fetchResonances]);

  const runScan = async () => {
    setScanning(true);
    setError(null);
    setScanStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/resonance/cross-domain/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "full" }),
      });
      if (res.status === 429) {
        setError("A scan is already in progress. Please wait.");
        setScanning(false);
        return;
      }
      if (!res.ok) {
        setError(`Scan failed: ${res.status}`);
        setScanning(false);
        return;
      }
      const scanResp = await res.json();
      const scanId = scanResp.scan_id;

      // Poll until complete
      const poll = async () => {
        const statusRes = await fetch(
          `${API_BASE}/api/resonance/cross-domain/scans/${scanId}`
        );
        if (!statusRes.ok) return;
        const status: ScanStatus = await statusRes.json();
        setScanStatus(status);
        if (status.status === "complete" || status.status === "failed") {
          setScanning(false);
          fetchProof();
          fetchResonances();
        } else {
          setTimeout(poll, 1500);
        }
      };
      setTimeout(poll, 800);
    } catch (err) {
      setError(String(err));
      setScanning(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Cross-Domain Concept Resonance
        </h1>
        <p className="mt-1 text-gray-500 text-sm">
          Ideas that solve analogous problems across different domains attract
          each other — not by keyword, but by structural similarity in the graph.
        </p>
      </div>

      {/* Proof panel */}
      <section className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Organic Growth Proof</h2>
          {proof && (
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                proof.proof_status === "active"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {proof.proof_status}
            </span>
          )}
        </div>
        {proof ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Stat label="Total resonances" value={proof.total_resonances} />
            <Stat
              label="Analogous-to edges"
              value={proof.analogous_to_edges_from_cdcr}
            />
            <Stat
              label="Nodes bridged"
              value={proof.nodes_with_cross_domain_bridge}
            />
            <Stat
              label="Growth rate"
              value={`${proof.organic_growth_rate}/day`}
            />
          </div>
        ) : (
          <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
        )}
      </section>

      {/* Active resonances feed */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">
            Active Resonances
            {total > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                ({total} total)
              </span>
            )}
          </h2>
        </div>
        {resonances.length === 0 ? (
          <p className="text-sm text-gray-400 italic">
            No resonances found yet. Run a scan to discover connections.
          </p>
        ) : (
          <div className="space-y-2">
            {resonances.map((r) => (
              <div
                key={r.id}
                className="bg-white border border-gray-200 rounded-lg p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-gray-900 truncate">
                        {r.node_a.name}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">
                        {r.node_a.domain}
                      </span>
                      <span className="text-gray-400">↔</span>
                      <span className="font-medium text-gray-900 truncate">
                        {r.node_b.name}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded">
                        {r.node_b.domain}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      Discovered{" "}
                      {new Date(r.discovered_at).toLocaleDateString()} ·{" "}
                      {r.scan_mode} scan
                      {r.edge_id && (
                        <span className="ml-1 text-emerald-600">
                          · edge persisted
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <ScoreBar score={r.resonance_score} />
                <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
                  <div>
                    Structural:{" "}
                    <span className="font-mono">
                      {r.structural_sim.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    Depth-2:{" "}
                    <span className="font-mono">
                      {r.depth2_sim.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    CRK:{" "}
                    <span className="font-mono">{r.crk_score.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Domain bridge heatmap */}
      <section className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
        <h2 className="font-semibold text-gray-800">Domain Bridge Heatmap</h2>
        <DomainHeatmap pairs={proof?.domain_pairs_covered ?? []} />
      </section>

      {/* Growth timeline */}
      <section className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
        <h2 className="font-semibold text-gray-800">Discovery Timeline</h2>
        <GrowthTimeline timeline={proof?.discovery_timeline ?? []} />
      </section>

      {/* Top resonances */}
      {proof && proof.top_resonances.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
          <h2 className="font-semibold text-gray-800">Strongest Resonances</h2>
          <div className="space-y-2">
            {proof.top_resonances.map((r, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-sm gap-4"
              >
                <div className="flex-1 min-w-0">
                  <span className="font-medium">{r.node_a}</span>
                  <span className="text-gray-400 mx-2">↔</span>
                  <span className="font-medium">{r.node_b}</span>
                  <span className="text-xs text-gray-400 ml-2">
                    {r.domain_pair}
                  </span>
                </div>
                <span className="font-mono text-indigo-600 text-xs">
                  {r.score.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Scan trigger */}
      <section className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
        <h2 className="font-semibold text-gray-800">Run Scan</h2>
        <p className="text-sm text-gray-500">
          Scan the entire graph for cross-domain structural similarities and
          persist new analogous-to edges.
        </p>
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </div>
        )}
        {scanStatus && (
          <div className="text-sm bg-gray-50 border border-gray-200 rounded p-3 space-y-1 font-mono">
            <div>
              Status:{" "}
              <span
                className={
                  scanStatus.status === "complete"
                    ? "text-emerald-600"
                    : scanStatus.status === "failed"
                    ? "text-red-600"
                    : "text-amber-600"
                }
              >
                {scanStatus.status}
              </span>
            </div>
            <div>Nodes evaluated: {scanStatus.nodes_evaluated}</div>
            <div>Pairs compared: {scanStatus.pairs_compared}</div>
            <div>Resonances found: {scanStatus.resonances_found}</div>
            <div>
              Created: {scanStatus.resonances_created} · Updated:{" "}
              {scanStatus.resonances_updated}
            </div>
            {scanStatus.duration_ms !== null && (
              <div>Duration: {scanStatus.duration_ms}ms</div>
            )}
          </div>
        )}
        <button
          onClick={runScan}
          disabled={scanning}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            scanning
              ? "bg-gray-100 text-gray-400 cursor-not-allowed"
              : "bg-indigo-600 text-white hover:bg-indigo-700"
          }`}
        >
          {scanning ? "Scanning…" : "Run Full Scan"}
        </button>
      </section>
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
    <div className="space-y-0.5">
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  );
}
