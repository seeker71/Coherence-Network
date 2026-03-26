"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

function formatCostBasis(raw: string | undefined): string {
  if (!raw) return "Unknown";
  const map: Record<string, string> = {
    actual_verified: "Verified",
    estimated: "Estimated",
    derived: "Derived",
    manual: "Manual",
  };
  return map[raw] ?? raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

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

type CoherenceScoreResponse = {
  score: number;
};

type NameLookup = Map<string, string>;

function ContributionsPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Contribution[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [liveCoherenceScore, setLiveCoherenceScore] = useState<number | null>(null);
  const [contributorNames, setContributorNames] = useState<NameLookup>(new Map());
  const [assetNames, setAssetNames] = useState<NameLookup>(new Map());

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
      const [contribRes, coherenceRes, contributorsRes, assetsRes] = await Promise.all([
        fetch(`${API_URL}/api/contributions`, { cache: "no-store" }),
        fetch(`${API_URL}/api/coherence/score`, { cache: "no-store" }),
        fetch(`${API_URL}/api/contributors`, { cache: "no-store" }).catch(() => null),
        fetch(`${API_URL}/api/assets`, { cache: "no-store" }).catch(() => null),
      ]);
      const contribJson = await contribRes.json();
      if (!contribRes.ok) throw new Error(JSON.stringify(contribJson));
      const data = contribJson?.items ?? (Array.isArray(contribJson) ? contribJson : []);
      const coherenceJson = coherenceRes.ok ? ((await coherenceRes.json()) as CoherenceScoreResponse) : null;

      // Build name lookups from contributors and assets
      const cNames = new Map<string, string>();
      const aNames = new Map<string, string>();
      if (contributorsRes?.ok) {
        const cJson = await contributorsRes.json();
        for (const c of cJson?.items ?? (Array.isArray(cJson) ? cJson : [])) {
          if (c.id && c.name) cNames.set(c.id, c.name);
        }
      }
      if (assetsRes?.ok) {
        const aJson = await assetsRes.json();
        for (const a of aJson?.items ?? (Array.isArray(aJson) ? aJson : [])) {
          if (a.id) aNames.set(a.id, a.description || a.type || "Untitled asset");
        }
      }
      setContributorNames(cNames);
      setAssetNames(aNames);

      setRows(data);
      setLiveCoherenceScore(
        coherenceJson && Number.isFinite(coherenceJson.score) ? Number(coherenceJson.score) : null,
      );
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
        Track all value contributions to the network.
        {contributorFilter ? (
          <>
            {" "}
            Filtered by contributor.
          </>
        ) : null}
        {assetFilter ? (
          <>
            {" "}
            Filtered by asset.
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
            {filteredRows.slice(0, 100).map((c, idx) => {
              const cost = effectiveCost(c);
              const commitHash = c.metadata?.commit_hash;
              const displayCoherence = c.coherence_score > 0 ? c.coherence_score : liveCoherenceScore;
              const coherenceValue = displayCoherence !== null ? Math.min(1, Math.max(0, displayCoherence)) : null;
              return (
              <li key={c.id} className="rounded border p-3 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-muted-foreground">#{idx + 1}</span>
                  <span className="text-muted-foreground text-xs">{formatDate(c.timestamp)}</span>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  <span>
                    by{" "}
                    <Link
                      href={`/contributors?contributor_id=${encodeURIComponent(c.contributor_id)}`}
                      className="underline hover:text-foreground font-medium"
                    >
                      {contributorNames.get(c.contributor_id) || truncateId(c.contributor_id)}
                    </Link>
                  </span>
                  <span className="text-muted-foreground">→</span>
                  <span>
                    <Link
                      href={`/assets?asset_id=${encodeURIComponent(c.asset_id)}`}
                      className="underline hover:text-foreground font-medium"
                    >
                      {assetNames.get(c.asset_id) || truncateId(c.asset_id)}
                    </Link>
                  </span>
                  <span className="font-medium">CC {cost.effective.toFixed(2)}</span>
                </div>
                {coherenceValue !== null && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>Coherence</span>
                    <div className="flex-1 max-w-[120px] h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(coherenceValue * 100).toFixed(0)}%`,
                          backgroundColor: coherenceValue >= 0.7 ? "#22c55e" : coherenceValue >= 0.4 ? "#eab308" : "#ef4444",
                        }}
                      />
                    </div>
                    <span>{coherenceValue.toFixed(2)}</span>
                  </div>
                )}
                {cost.normalized !== null && Math.abs(cost.raw - cost.normalized) >= 0.01 && (
                  <div className="text-xs text-muted-foreground">
                    Adjusted from CC {cost.raw.toFixed(2)} to CC {cost.normalized.toFixed(2)}
                  </div>
                )}
                {cost.source === "derived" && Math.abs(cost.raw - cost.effective) >= 0.01 && (
                  <div className="text-xs text-muted-foreground">
                    Adjusted from CC {cost.raw.toFixed(2)} to CC {cost.effective.toFixed(2)}
                  </div>
                )}
                {(c.metadata?.cost_basis || typeof c.metadata?.cost_confidence === "number") && (
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    {c.metadata?.cost_basis && (
                      <span>Cost basis: {formatCostBasis(c.metadata.cost_basis)}</span>
                    )}
                    {typeof c.metadata?.cost_confidence === "number" && (
                      <span>Confidence: {(c.metadata.cost_confidence * 100).toFixed(0)}%</span>
                    )}
                    {c.metadata?.estimation_used && (
                      <span>Estimated</span>
                    )}
                  </div>
                )}
                {commitHash && (
                  <div className="text-xs text-muted-foreground font-mono">Commit {commitHash.slice(0, 12)}</div>
                )}
              </li>
              );
            })}
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
