"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

interface TableRow {
  name: string;
  row_count: number;
  previous_snapshot_at?: string | null;
  previous_row_count?: number | null;
  delta_24h?: number | null;
  pct_change_24h?: number | null;
  status: string;
}

interface DataHealthPayload {
  generated_at: string;
  database_kind: string;
  health_score: number;
  last_snapshot_at?: string | null;
  snapshot_stale_hours?: number | null;
  tables: TableRow[];
  open_friction_ids: string[];
  investigation_hints: string[];
  runtime_events_facets?: Record<string, unknown> | null;
}

export function DataHealthDashboard() {
  const [data, setData] = useState<DataHealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const base = getApiBase();
    const url = `${base}/api/data-health`;
    let cancelled = false;
    fetch(url, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (!cancelled) {
          setData(json as DataHealthPayload);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <section className="rounded-2xl border border-destructive/40 bg-destructive/5 p-6 text-sm">
        Could not load data health: {error}
      </section>
    );
  }
  if (!data) {
    return (
      <section className="rounded-2xl border border-border/30 bg-card/40 p-8 text-center text-muted-foreground">
        Loading database health…
      </section>
    );
  }

  const scoreColor =
    data.health_score >= 0.85 ? "text-emerald-600" : data.health_score >= 0.5 ? "text-amber-600" : "text-red-600";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline gap-4">
        <p className="text-sm text-muted-foreground">
          {data.database_kind} · generated {new Date(data.generated_at).toLocaleString()}
        </p>
        <p className={`text-2xl font-semibold ${scoreColor}`}>Health {(data.health_score * 100).toFixed(0)}%</p>
      </div>
      {data.snapshot_stale_hours != null && data.snapshot_stale_hours > 48 && (
        <p className="text-sm text-amber-700">
          Snapshot ledger is stale ({data.snapshot_stale_hours.toFixed(0)}h). Schedule periodic POST /api/data-health/snapshot.
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-border/40">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left">
            <tr>
              <th className="p-3 font-medium">Table</th>
              <th className="p-3 font-medium">Rows</th>
              <th className="p-3 font-medium">24h ref</th>
              <th className="p-3 font-medium">Δ 24h</th>
              <th className="p-3 font-medium">% 24h</th>
              <th className="p-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.tables.map((t) => (
              <tr key={t.name} className="border-t border-border/30">
                <td className="p-3 font-mono">{t.name}</td>
                <td className="p-3">{t.row_count.toLocaleString()}</td>
                <td className="p-3 text-muted-foreground">
                  {t.previous_row_count != null ? t.previous_row_count.toLocaleString() : "—"}
                </td>
                <td className="p-3">{t.delta_24h != null ? t.delta_24h.toLocaleString() : "—"}</td>
                <td className="p-3">{t.pct_change_24h != null ? `${t.pct_change_24h.toFixed(2)}%` : "—"}</td>
                <td className="p-3">
                  <span
                    className={
                      t.status === "breach"
                        ? "text-red-600"
                        : t.status === "warn"
                          ? "text-amber-600"
                          : "text-emerald-700"
                    }
                  >
                    {t.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.investigation_hints.length > 0 && (
        <div>
          <h2 className="mb-2 text-lg font-semibold">Investigation hints</h2>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {data.investigation_hints.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      )}

      {data.open_friction_ids.length > 0 && (
        <p className="text-sm text-amber-800">
          Open friction events: {data.open_friction_ids.join(", ")} — see also{" "}
          <a href="/friction" className="underline">
            /friction
          </a>
        </p>
      )}
    </div>
  );
}
