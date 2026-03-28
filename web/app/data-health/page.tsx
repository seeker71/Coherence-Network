"use client";

import { useEffect, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

type TableStatus = {
  table: string;
  row_count: number;
  exists: boolean;
  error?: string;
  expected_max_daily?: number;
  alert: boolean;
  alert_reason?: string;
};

type DbStatusReport = {
  generated_at: string;
  tables: TableStatus[];
  total_rows: number;
  alert_count: number;
  alerts: Array<{ table: string; row_count: number; reason: string; severity: string }>;
};

type RuntimeInvestigation = {
  table: string;
  row_count?: number;
  investigation?: {
    by_event_type?: Array<{ event_type: string; count: number }> | string;
    by_age?: Record<string, number> | string;
  };
  error?: string;
};

// ── API ──────────────────────────────────────────────────────────────────────

const HUB = process.env.NEXT_PUBLIC_HUB_URL || "https://api.coherencycoin.com";

async function fetchDbStatus(): Promise<DbStatusReport | null> {
  try {
    const res = await fetch(`${HUB}/api/db-status`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchRuntimeInvestigation(): Promise<RuntimeInvestigation | null> {
  try {
    const res = await fetch(`${HUB}/api/db-status/investigate/runtime-events`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtCount(n: number): string {
  return n.toLocaleString("en-US");
}

function relativeTime(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ── Components ───────────────────────────────────────────────────────────────

function AlertBadge({ alert, reason }: { alert: boolean; reason?: string }) {
  if (!alert) {
    return <span className="text-xs px-2 py-0.5 rounded bg-green-900/30 text-green-400">ok</span>;
  }
  return (
    <span
      className="text-xs px-2 py-0.5 rounded bg-yellow-900/30 text-yellow-400 cursor-help"
      title={reason}
    >
      ⚠ alert
    </span>
  );
}

function TableRow({ t }: { t: TableStatus }) {
  if (!t.exists) {
    return (
      <tr className="opacity-40">
        <td className="py-2 pr-4 font-mono text-sm">{t.table}</td>
        <td className="py-2 pr-4 text-right text-sm">—</td>
        <td className="py-2 pr-4 text-right text-sm">—</td>
        <td className="py-2 text-sm text-neutral-500">missing</td>
      </tr>
    );
  }
  return (
    <>
      <tr className={t.alert ? "bg-yellow-950/20" : ""}>
        <td className="py-2 pr-4 font-mono text-sm">{t.table}</td>
        <td className={`py-2 pr-4 text-right font-mono text-sm ${t.alert ? "text-yellow-400" : ""}`}>
          {fmtCount(t.row_count)}
        </td>
        <td className="py-2 pr-4 text-right text-sm text-neutral-500">
          {t.expected_max_daily != null ? fmtCount(t.expected_max_daily) : "—"}
        </td>
        <td className="py-2">
          <AlertBadge alert={t.alert} reason={t.alert_reason} />
        </td>
      </tr>
      {t.alert && t.alert_reason && (
        <tr className="bg-yellow-950/10">
          <td colSpan={4} className="pb-2 pl-4 text-xs text-yellow-500 italic">
            ↳ {t.alert_reason}
          </td>
        </tr>
      )}
    </>
  );
}

function InvestigationPanel({ data }: { data: RuntimeInvestigation }) {
  const inv = data.investigation || {};
  const byType = Array.isArray(inv.by_event_type) ? inv.by_event_type : null;
  const byAge = inv.by_age && typeof inv.by_age === "object" && !Array.isArray(inv.by_age)
    ? (inv.by_age as Record<string, number>)
    : null;

  return (
    <div className="mt-6 border border-yellow-800/40 rounded-lg p-4 bg-yellow-950/10">
      <h2 className="text-sm font-semibold text-yellow-400 mb-3">
        🔍 runtime_events Investigation
        {data.row_count !== undefined && (
          <span className="ml-2 font-mono text-yellow-300">{fmtCount(data.row_count)} rows</span>
        )}
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* By age */}
        {byAge && (
          <div>
            <h3 className="text-xs text-neutral-400 mb-2 uppercase tracking-wide">By Age</h3>
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(byAge).map(([bucket, count]) => (
                  <tr key={bucket}>
                    <td className="pr-4 font-mono text-neutral-300">{bucket}</td>
                    <td className="text-right font-mono text-white">{fmtCount(count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* By event type */}
        {byType && byType.length > 0 && (
          <div>
            <h3 className="text-xs text-neutral-400 mb-2 uppercase tracking-wide">Top Event Types</h3>
            <table className="w-full text-sm">
              <tbody>
                {byType.slice(0, 10).map((row) => (
                  <tr key={row.event_type}>
                    <td className="pr-4 font-mono text-neutral-300 truncate max-w-[200px]">
                      {row.event_type || "(null)"}
                    </td>
                    <td className="text-right font-mono text-white">{fmtCount(row.count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {data.error && (
        <p className="text-xs text-red-400 mt-2">Error: {data.error}</p>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DataHealthPage() {
  const [report, setReport] = useState<DbStatusReport | null>(null);
  const [investigation, setInvestigation] = useState<RuntimeInvestigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    const [r, inv] = await Promise.all([fetchDbStatus(), fetchRuntimeInvestigation()]);
    if (!r) {
      setError("Could not reach API. Is the server running?");
    } else {
      setReport(r);
    }
    if (inv) setInvestigation(inv);
    setRefreshedAt(new Date());
    setLoading(false);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 60_000); // auto-refresh every 60s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-black text-white p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Data Health</h1>
          <p className="text-sm text-neutral-400 mt-1">
            Row counts, growth anomalies, and noise detection for all monitored tables.
          </p>
        </div>
        <div className="text-right">
          <button
            onClick={load}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded border border-neutral-700 hover:border-neutral-500 disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          {refreshedAt && (
            <p className="text-xs text-neutral-600 mt-1">{relativeTime(refreshedAt.toISOString())}</p>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded bg-red-950/40 border border-red-800 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Alert summary */}
      {report && report.alert_count > 0 && (
        <div className="mb-4 p-3 rounded bg-yellow-950/40 border border-yellow-800 text-yellow-400 text-sm">
          ⚠ {report.alert_count} alert{report.alert_count !== 1 ? "s" : ""} detected —
          tables with row counts exceeding noise thresholds.
        </div>
      )}
      {report && report.alert_count === 0 && (
        <div className="mb-4 p-3 rounded bg-green-950/40 border border-green-800 text-green-400 text-sm">
          ✓ No anomalies detected.
        </div>
      )}

      {/* Table */}
      {report && (
        <div className="border border-neutral-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-neutral-900">
              <tr>
                <th className="text-left py-2 px-4 text-xs text-neutral-400 uppercase tracking-wide">Table</th>
                <th className="text-right py-2 px-4 text-xs text-neutral-400 uppercase tracking-wide">Rows</th>
                <th className="text-right py-2 px-4 text-xs text-neutral-400 uppercase tracking-wide">Max/day</th>
                <th className="text-left py-2 px-4 text-xs text-neutral-400 uppercase tracking-wide">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-900">
              {report.tables.map((t) => (
                <TableRow key={t.table} t={t} />
              ))}
            </tbody>
            <tfoot className="bg-neutral-950 border-t border-neutral-800">
              <tr>
                <td className="py-2 px-4 text-sm text-neutral-400">Total</td>
                <td className="py-2 px-4 text-right font-mono text-sm font-semibold">
                  {fmtCount(report.total_rows)}
                </td>
                <td colSpan={2} className="py-2 px-4 text-xs text-neutral-600 text-right">
                  as of {report.generated_at}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* runtime_events investigation */}
      {investigation && <InvestigationPanel data={investigation} />}

      {/* CLI hint */}
      <div className="mt-6 text-xs text-neutral-600 border border-neutral-900 rounded p-3">
        <span className="text-neutral-500">CLI: </span>
        <code className="font-mono">cc db-status</code>
        {"  ·  "}
        <code className="font-mono">cc db-status investigate runtime-events</code>
      </div>
    </div>
  );
}
