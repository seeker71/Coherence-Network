"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

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
    cost_basis?: string;
    cost_confidence?: number;
    estimation_used?: boolean;
    files_changed?: number;
    lines_added?: number;
  };
};

function ContributionsPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Contribution[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const contributorFilter = useMemo(
    () => (searchParams.get("contributor_id") || "").trim(),
    [searchParams]
  );
  const assetFilter = useMemo(
    () => (searchParams.get("asset_id") || "").trim(),
    [searchParams]
  );

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/contributions`, { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setRows(Array.isArray(json) ? json : []);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(loadRows);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (contributorFilter && row.contributor_id !== contributorFilter) return false;
      if (assetFilter && row.asset_id !== assetFilter) return false;
      return true;
    });
  }, [rows, contributorFilter, assetFilter]);

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
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Contributions</h1>
      <p className="text-muted-foreground">
        Human interface for `GET /api/contributions`.
        {contributorFilter ? (
          <>
            {" "}
            Filter contributor <code>{contributorFilter}</code>.
          </>
        ) : null}
        {assetFilter ? (
          <>
            {" "}
            Filter asset <code>{assetFilter}</code>.
          </>
        ) : null}
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">
            Total: {filteredRows.length}
            {(contributorFilter || assetFilter) ? (
              <>
                {" "}
                | <Link href="/contributions" className="underline hover:text-foreground">Clear filters</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((c) => (
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
                  contributor{" "}
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(c.contributor_id)}`}
                    className="underline hover:text-foreground"
                  >
                    {c.contributor_id}
                  </Link>{" "}
                  | asset{" "}
                  <Link
                    href={`/assets?asset_id=${encodeURIComponent(c.asset_id)}`}
                    className="underline hover:text-foreground"
                  >
                    {c.asset_id}
                  </Link>{" "}
                  | cost {cost.effective.toFixed(2)} | coherence {c.coherence_score}
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
                {(c.metadata?.cost_basis || c.metadata?.cost_confidence !== undefined) && (
                  <div className="text-xs text-muted-foreground">
                    basis {c.metadata?.cost_basis ?? "unknown"} | confidence{" "}
                    {typeof c.metadata?.cost_confidence === "number"
                      ? c.metadata.cost_confidence.toFixed(2)
                      : "n/a"}{" "}
                    | estimation {c.metadata?.estimation_used ? "yes" : "no"}
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

export default function ContributionsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen p-8 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading contributions…</p></main>}>
      <ContributionsPageContent />
    </Suspense>
  );
}
