"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

type Contribution = {
  id: string;
  contributor_id: string;
  asset_id: string;
  cost_amount: string;
  coherence_score: number;
  timestamp: string;
  metadata?: {
    commit_hash?: string;
    raw_cost_amount?: string;
    normalized_cost_amount?: string;
    cost_estimator_version?: string;
    files_changed?: number;
    lines_added?: number;
  };
};

export default function ContributionsPage() {
  const [rows, setRows] = useState<Contribution[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setStatus("loading");
      setError(null);
      try {
        const res = await fetch(`${API_URL}/v1/contributions`, { cache: "no-store" });
        const json = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(json));
        setRows(Array.isArray(json) ? json : []);
        setStatus("ok");
      } catch (e) {
        setStatus("error");
        setError(String(e));
      }
    })();
  }, []);

  const toFinite = (value: string | number | undefined): number | null => {
    if (value === undefined) return null;
    const parsed = typeof value === "number" ? value : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const deriveLegacyNormalizedCost = (row: Contribution): number | null => {
    const files = toFinite(row.metadata?.files_changed);
    const lines = toFinite(row.metadata?.lines_added);
    if (files === null && lines === null) return null;
    const filesN = Math.max(0, Math.trunc(files ?? 0));
    const linesN = Math.max(0, Math.trunc(lines ?? 0));
    let derived = 0.1 + (filesN * 0.15) + (linesN * 0.002);
    if (derived < 0.05) derived = 0.05;
    if (derived > 10.0) derived = 10.0;
    return Number(derived.toFixed(2));
  };

  const effectiveCost = (
    row: Contribution,
  ): { effective: number; raw: number; normalized: number | null; source: "normalized" | "derived" | "raw" } => {
    const raw = toFinite(row.cost_amount) ?? 0;
    const normalized = toFinite(row.metadata?.normalized_cost_amount);
    const derived = normalized === null ? deriveLegacyNormalizedCost(row) : null;
    return {
      effective: normalized ?? derived ?? raw,
      raw,
      normalized,
      source: normalized !== null ? "normalized" : derived !== null ? "derived" : "raw",
    };
  };

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex gap-3">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Contributions</h1>
      <p className="text-muted-foreground">Human interface for `GET /v1/contributions`.</p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">Total: {rows.length}</p>
          <ul className="space-y-2 text-sm">
            {rows.slice(0, 100).map((c) => (
              <li key={c.id} className="rounded border p-2 space-y-1">
                {(() => {
                  const cost = effectiveCost(c);
                  const commitHash = c.metadata?.commit_hash;
                  return (
                    <>
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{c.id}</span>
                  <span className="text-muted-foreground">{c.timestamp}</span>
                </div>
                <div className="text-muted-foreground">
                  contributor {c.contributor_id} | asset {c.asset_id} | cost {cost.effective.toFixed(2)} | coherence {c.coherence_score}
                </div>
                {cost.normalized !== null && Math.abs(cost.raw - cost.normalized) >= 0.01 && (
                  <div className="text-xs text-muted-foreground">
                    raw {cost.raw.toFixed(2)} → normalized {cost.normalized.toFixed(2)} ({c.metadata?.cost_estimator_version ?? "v2"})
                  </div>
                )}
                {cost.source === "derived" && Math.abs(cost.raw - cost.effective) >= 0.01 && (
                  <div className="text-xs text-muted-foreground">
                    raw {cost.raw.toFixed(2)} → normalized {cost.effective.toFixed(2)} (legacy-derived-v2)
                  </div>
                )}
                {commitHash && (
                  <div className="text-xs text-muted-foreground">commit {commitHash.slice(0, 12)}</div>
                )}
                    </>
                  );
                })()}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
