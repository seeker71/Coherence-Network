"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const POLL_MS = 120_000;

type TableRow = {
  key: string;
  sql_table: string;
  description?: string;
  row_count: number;
  previous_count?: number | null;
  previous_captured_at?: string | null;
  delta_rows?: number | null;
  growth_rows_per_hour?: number | null;
  growth_pct_vs_previous?: number | null;
  hours_since_previous?: number | null;
};

type Alert = {
  severity: string;
  table_key: string;
  message: string;
  delta_rows?: number;
  growth_pct_vs_previous?: number;
};

export default function DataHealthPage() {
  const base = getApiBase();
  const url = `${base || ""}/api/data-hygiene/status?record=false`;
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [tables, setTables] = useState<TableRow[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [capturedAt, setCapturedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(url, { cache: "no-store" })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((data) => {
          if (cancelled) return;
          setTables(Array.isArray(data.tables) ? data.tables : []);
          setAlerts(Array.isArray(data.alerts) ? data.alerts : []);
          setMeta(typeof data.meta === "object" && data.meta ? data.meta : null);
          setCapturedAt(typeof data.captured_at === "string" ? data.captured_at : null);
          setError(null);
          setStatus("ok");
        })
        .catch((e) => {
          if (cancelled) return;
          setError(String(e));
          setStatus("error");
        });
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [url]);

  const health = typeof meta?.health === "string" ? meta.health : "unknown";
  const healthClass =
    health === "ok" ? "text-green-600" : health === "degraded" ? "text-amber-600" : "text-red-600";

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto">
      <div className="mb-6 flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/api-health" className="text-muted-foreground hover:text-foreground">
          API health
        </Link>
      </div>

      <h1 className="text-2xl font-bold mb-2">Data health</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Row counts and growth for high-volume tables. Refreshes every {POLL_MS / 1000}s. Compare samples over time
        with <code className="text-xs bg-muted px-1 rounded">cc db-status --record</code> on the API host.
      </p>

      {status === "loading" && (
        <p className="text-muted-foreground">Loading data hygiene status…</p>
      )}

      {status === "error" && (
        <section className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm">
          <p className="font-medium text-destructive">Could not load /api/data-hygiene/status</p>
          <p className="mt-1 text-muted-foreground">{error}</p>
        </section>
      )}

      {status === "ok" && (
        <>
          <section className="mb-6 flex flex-wrap items-center gap-4 text-sm">
            <span>
              Overall: <span className={`font-semibold ${healthClass}`}>{health}</span>
            </span>
            {capturedAt && (
              <span className="text-muted-foreground">Captured: {capturedAt}</span>
            )}
            {meta?.insufficient_history === true && (
              <span className="text-amber-700 dark:text-amber-400">
                No prior samples — growth rates need at least one stored sample per table.
              </span>
            )}
          </section>

          {alerts.length > 0 && (
            <section className="mb-6 space-y-2">
              <h2 className="text-lg font-semibold">Alerts</h2>
              <ul className="space-y-2">
                {alerts.map((a, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm"
                  >
                    <span className="font-mono text-xs uppercase text-muted-foreground">{a.severity}</span>{" "}
                    {a.message}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <h2 className="text-lg font-semibold mb-3">Tables</h2>
            <div className="overflow-x-auto rounded-xl border border-border/40">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40 bg-muted/30 text-left">
                    <th className="p-3 font-medium">Key</th>
                    <th className="p-3 font-medium">Rows</th>
                    <th className="p-3 font-medium">Δ vs sample</th>
                    <th className="p-3 font-medium">Rows/h</th>
                  </tr>
                </thead>
                <tbody>
                  {tables.map((t) => (
                    <tr key={t.key} className="border-b border-border/20">
                      <td className="p-3 align-top">
                        <div className="font-medium">{t.key}</div>
                        <div className="text-xs text-muted-foreground">{t.sql_table}</div>
                      </td>
                      <td className="p-3 font-mono">{t.row_count}</td>
                      <td className="p-3 font-mono text-muted-foreground">
                        {t.delta_rows != null ? (
                          <>
                            {t.delta_rows > 0 ? "+" : ""}
                            {t.delta_rows}{" "}
                            {t.growth_pct_vs_previous != null ? `(${t.growth_pct_vs_previous}%)` : ""}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="p-3 font-mono text-muted-foreground">
                        {t.growth_rows_per_hour != null ? t.growth_rows_per_hour : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
