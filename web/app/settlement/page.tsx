// Daily settlement dashboard — surfaces the SettlementBatch records
// produced by settlement_service. Each batch aggregates one day of
// render events into per-asset CC distributions, applies any verified
// evidence multipliers, and stores a hash-chained record. The page
// reads from /api/settlement and lets a contributor trigger a batch
// for any date via POST /api/settlement/run.
//
// Per spec story-protocol-integration.md R8: SettlementDashboard.
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { getApiBase } from "@/lib/api";

type ConceptPool = {
  concept_id: string;
  cc_amount: string | number;
};

type SettlementEntry = {
  asset_id: string;
  read_count: number;
  base_cc_pool: string | number;
  evidence_multiplier: string | number;
  effective_cc_pool: string | number;
  cc_to_asset_creator: string | number;
  cc_to_renderer_creators: string | number;
  cc_to_host_nodes: string | number;
  concept_pools: ConceptPool[];
};

type SettlementBatch = {
  id: string;
  batch_date: string;
  entries: SettlementEntry[];
  total_read_count: number;
  total_cc_distributed: string | number;
  computed_at: string;
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatCc(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "CC 0.0000";
  return `CC ${n.toFixed(4)}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// SettlementDashboard — the table-of-batches surface that fulfills the
// spec's named symbol. Holds its own data and the run-batch dialog
// state. Empty until the first batch is computed; "Run batch…" opens a
// confirmation dialog that POSTs to /api/settlement/run.
function SettlementDashboard() {
  const [batches, setBatches] = useState<SettlementBatch[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [runDate, setRunDate] = useState<string>(todayIso());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/settlement?limit=30`, {
        cache: "no-store",
      });
      if (!res.ok) {
        setLoadError(`HTTP ${res.status}`);
        return;
      }
      const data = await res.json();
      setBatches(Array.isArray(data) ? data : []);
      setLoadError(null);
    } catch (err: any) {
      setLoadError(err?.message ?? "unknown error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRun = async () => {
    setRunError(null);
    setRunning(true);
    try {
      const res = await fetch(`${getApiBase()}/api/settlement/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_date: runDate }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
      }
      setDialogOpen(false);
      await load();
    } catch (err: any) {
      setRunError(err?.message ?? "run failed");
    } finally {
      setRunning(false);
    }
  };

  const totals = useMemo(() => {
    if (!batches) return { count: 0, cc: 0, reads: 0 };
    return batches.reduce(
      (acc, b) => ({
        count: acc.count + 1,
        cc: acc.cc + Number(b.total_cc_distributed || 0),
        reads: acc.reads + (b.total_read_count || 0),
      }),
      { count: 0, cc: 0, reads: 0 },
    );
  }, [batches]);

  return (
    <div className="space-y-6">
      {/* Summary strip */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">
            Batches
          </p>
          <p className="mt-2 text-2xl sm:text-3xl font-light text-stone-100">
            {batches === null ? "—" : totals.count}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-amber-500/10 to-amber-500/5 p-4">
          <p className="text-[10px] uppercase tracking-[0.18em] text-amber-400/80">
            CC distributed
          </p>
          <p className="mt-2 text-2xl sm:text-3xl font-light text-stone-100">
            {batches === null ? "—" : formatCc(totals.cc)}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-emerald-500/10 to-emerald-500/5 p-4 col-span-2 sm:col-span-1">
          <p className="text-[10px] uppercase tracking-[0.18em] text-emerald-400/80">
            Reads aggregated
          </p>
          <p className="mt-2 text-2xl sm:text-3xl font-light text-stone-100">
            {batches === null ? "—" : totals.reads.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Action bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-medium text-stone-100">
          Settlement batches
        </h2>
        <button
          type="button"
          onClick={() => {
            setRunError(null);
            setDialogOpen(true);
          }}
          className="rounded border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/20 transition-colors"
        >
          Run batch…
        </button>
      </div>

      {loadError && (
        <p className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          Could not load batches: {loadError}
        </p>
      )}

      {batches === null && !loadError ? (
        <p className="text-sm text-stone-400">Loading batches…</p>
      ) : batches && batches.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stone-700 bg-stone-900/30 p-6 text-center">
          <p className="text-sm text-stone-300">
            No settlement batches yet.
          </p>
          <p className="text-xs text-stone-500 mt-1">
            Run a batch for any date to materialize one. Once render events
            accumulate against an asset, the batch carries non-zero CC.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border/30 bg-card/30">
          <table className="w-full text-sm">
            <thead className="bg-stone-900/40 text-stone-400">
              <tr>
                <th className="text-left px-4 py-2 text-[10px] uppercase tracking-[0.14em] font-medium">
                  Date
                </th>
                <th className="text-right px-4 py-2 text-[10px] uppercase tracking-[0.14em] font-medium">
                  Assets
                </th>
                <th className="text-right px-4 py-2 text-[10px] uppercase tracking-[0.14em] font-medium">
                  Reads
                </th>
                <th className="text-right px-4 py-2 text-[10px] uppercase tracking-[0.14em] font-medium">
                  CC out
                </th>
                <th className="text-right px-4 py-2 text-[10px] uppercase tracking-[0.14em] font-medium">
                  Multipliers
                </th>
                <th className="text-left px-4 py-2 text-[10px] uppercase tracking-[0.14em] font-medium">
                  Batch id
                </th>
              </tr>
            </thead>
            <tbody>
              {batches!.flatMap((batch) => {
                const open = expandedId === batch.id;
                const multipliers = batch.entries.filter(
                  (e) => Number(e.evidence_multiplier) > 1,
                ).length;
                const rows = [
                  <tr
                    key={batch.id}
                    className="border-t border-stone-800/40 hover:bg-stone-900/30 cursor-pointer"
                    onClick={() => setExpandedId(open ? null : batch.id)}
                  >
                    <td className="px-4 py-3 text-stone-200">
                      <span
                        className="mr-2 text-stone-500"
                        aria-hidden="true"
                      >
                        {open ? "▾" : "▸"}
                      </span>
                      {formatDate(batch.batch_date)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-stone-300">
                      {batch.entries.length}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-stone-300">
                      {batch.total_read_count.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-amber-200">
                      {formatCc(batch.total_cc_distributed)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-stone-400">
                      {multipliers > 0 ? `${multipliers}` : "—"}
                    </td>
                    <td
                      className="px-4 py-3 font-mono text-xs text-stone-500 truncate max-w-[160px]"
                      title={batch.id}
                    >
                      {batch.id.slice(0, 8)}…
                    </td>
                  </tr>,
                ];
                if (open) {
                  rows.push(
                    <tr key={`${batch.id}-detail`}>
                      <td colSpan={6} className="px-4 py-4 bg-stone-950/40">
                        {batch.entries.length === 0 ? (
                          <p className="text-xs text-stone-500">
                            No entries — no reads on this date.
                          </p>
                        ) : (
                          <div className="space-y-2">
                            {batch.entries.map((entry) => (
                              <div
                                key={entry.asset_id}
                                className="flex flex-wrap items-center justify-between gap-3 text-xs"
                              >
                                <Link
                                  href={`/assets/${encodeURIComponent(entry.asset_id.replace(/^asset:/, ""))}`}
                                  className="font-mono text-stone-300 hover:text-amber-200 truncate max-w-xs"
                                  title={entry.asset_id}
                                >
                                  {entry.asset_id
                                    .replace(/^asset:/, "")
                                    .slice(0, 16)}
                                  …
                                </Link>
                                <span className="text-stone-400 tabular-nums">
                                  {entry.read_count} reads
                                </span>
                                <span className="text-stone-400 tabular-nums">
                                  ×{Number(entry.evidence_multiplier).toFixed(2)}
                                </span>
                                <span className="text-amber-200 tabular-nums">
                                  {formatCc(entry.effective_cc_pool)}
                                </span>
                              </div>
                            ))}
                            <p className="text-[10px] text-stone-500 pt-1">
                              computed at {batch.computed_at}
                            </p>
                          </div>
                        )}
                      </td>
                    </tr>,
                  );
                }
                return rows;
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirmation dialog */}
      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
          role="dialog"
          aria-modal="true"
          onClick={() => !running && setDialogOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-border/30 bg-stone-950 p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-medium text-stone-100">
              Run settlement batch
            </h3>
            <p className="text-sm text-stone-400">
              Aggregates render events for the chosen date, applies verified
              evidence multipliers, and stores a hash-chained record. In
              production this is irreversible.
            </p>
            <div className="space-y-2">
              <label
                className="text-xs uppercase tracking-[0.14em] text-stone-500"
                htmlFor="run_date"
              >
                Batch date
              </label>
              <input
                id="run_date"
                type="date"
                value={runDate}
                onChange={(e) => setRunDate(e.target.value)}
                className="w-full rounded-md border border-stone-700 bg-stone-900/60 px-3 py-2 text-sm text-stone-200 focus:border-amber-400/60 focus:outline-none"
              />
            </div>
            {runError && (
              <p className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                {runError}
              </p>
            )}
            <div className="flex flex-wrap justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDialogOpen(false)}
                disabled={running}
                className="rounded border border-stone-700 px-4 py-2 text-sm text-stone-200 hover:border-amber-400/40 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onRun}
                disabled={running}
                className="rounded border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/20 transition-colors disabled:opacity-50"
              >
                {running ? "Running…" : "Confirm + run"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SettlementPage() {
  return (
    <main className="bg-stone-950 min-h-screen">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 py-6 sm:py-10 space-y-6">
        <nav
          className="text-sm text-stone-500 flex items-center gap-2"
          aria-label="breadcrumb"
        >
          <Link href="/" className="hover:text-amber-300 transition-colors">
            Home
          </Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">Settlement</span>
        </nav>

        <header className="space-y-2">
          <h1 className="text-2xl sm:text-4xl font-light text-stone-50 tracking-tight">
            Daily settlement
          </h1>
          <p className="text-sm text-stone-400 leading-relaxed">
            Each batch aggregates one day of reads into per-asset CC pools,
            applies verified evidence multipliers, and writes a hash-chained
            record. Press a row to see the per-asset split.
          </p>
        </header>

        <SettlementDashboard />

        <p className="text-xs text-stone-500">
          Settlement math lives at{" "}
          <code className="text-stone-400">
            api/app/services/settlement_service.py
          </code>
          . See{" "}
          <code className="text-stone-400">
            story-protocol-integration.md
          </code>{" "}
          R8.
        </p>
      </div>
    </main>
  );
}
