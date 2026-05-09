"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { usePagedList } from "@/lib/use-paged-list";
import { useT, useLocale } from "@/components/MessagesProvider";
import { LedgerNav } from "@/app/_components/LedgerNav";
import { decodeEntities } from "@/lib/html-entities";

const API_URL = getApiBase();
const PAGE_SIZE = 100;

function formatDate(iso: string, locale: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(locale, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

function costBasisLabel(t: (key: string) => string, raw: string | undefined): string {
  if (!raw) return t("contributions.costBasisUnknown");
  const map: Record<string, string> = {
    actual_verified: t("contributions.costBasisVerified"),
    estimated: t("contributions.costBasisEstimated"),
    derived: t("contributions.costBasisDerived"),
    manual: t("contributions.costBasisManual"),
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
    description?: string;
    summary?: string;
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
  const t = useT();
  const locale = useLocale();
  const searchParams = useSearchParams();
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

  const buildContributionsUrl = useCallback(
    (offset: number, limit: number) =>
      `${API_URL}/api/contributions?offset=${offset}&limit=${limit}`,
    [],
  );

  const contributions = usePagedList<Contribution>({
    buildUrl: buildContributionsUrl,
    pageSize: PAGE_SIZE,
    timeoutMs: 10000,
    retries: 3,
  });
  const rows = contributions.items;
  const totalKnown = contributions.total;

  // Sentinel: when bottom marker enters viewport, ask for the next page.
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            contributions.loadMore();
          }
        }
      },
      { rootMargin: "300px" },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [contributions.loadMore]);

  // Auxiliary fetches: live coherence score (single value) + name lookups
  // (best-effort; names that miss fall back to truncated id).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [coherenceJson, contributorsJson, assetsJson] = await Promise.all([
        fetchJsonOrNull<CoherenceScoreResponse>(
          `${API_URL}/api/coherence/score`,
          { cache: "no-store" },
          8000,
          3,
        ),
        fetchJsonOrNull<{ items?: Array<{ id: string; name?: string }> } | Array<{ id: string; name?: string }>>(
          `${API_URL}/api/contributors?limit=1000`,
          { cache: "no-store" },
          10000,
          3,
        ),
        fetchJsonOrNull<{ items?: Array<{ id: string; description?: string; type?: string }> } | Array<{ id: string; description?: string; type?: string }>>(
          `${API_URL}/api/assets?limit=1000`,
          { cache: "no-store" },
          10000,
          3,
        ),
      ]);
      if (cancelled) return;

      if (coherenceJson && Number.isFinite(coherenceJson.score)) {
        setLiveCoherenceScore(Number(coherenceJson.score));
      }

      const cNames = new Map<string, string>();
      const cItems = Array.isArray(contributorsJson)
        ? contributorsJson
        : contributorsJson?.items ?? [];
      for (const c of cItems) {
        if (c.id && c.name) cNames.set(c.id, c.name);
      }
      setContributorNames(cNames);

      const aNames = new Map<string, string>();
      const aItems = Array.isArray(assetsJson) ? assetsJson : assetsJson?.items ?? [];
      for (const a of aItems) {
        if (a.id) aNames.set(a.id, decodeEntities(a.description || a.type || "Untitled asset"));
      }
      setAssetNames(aNames);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (contributorFilter && row.contributor_id !== contributorFilter) return false;
      if (assetFilter && row.asset_id !== assetFilter) return false;
      return true;
    });
  }, [rows, contributorFilter, assetFilter]);

  const filteredSummary = useMemo(() => {
    const contributors = new Set<string>();
    const assets = new Set<string>();
    let totalCost = 0;
    let coherenceSum = 0;
    let coherenceCount = 0;

    for (const row of filteredRows) {
      contributors.add(row.contributor_id);
      assets.add(row.asset_id);
      const raw = Number(row.cost_amount);
      if (Number.isFinite(raw)) totalCost += raw;
      if (Number.isFinite(row.coherence_score)) {
        coherenceSum += row.coherence_score;
        coherenceCount += 1;
      }
    }

    return {
      totalCost,
      contributors: contributors.size,
      assets: assets.size,
      averageCoherence: coherenceCount > 0 ? coherenceSum / coherenceCount : null,
    };
  }, [filteredRows]);

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

  const filterContext = (() => {
    if (contributorFilter && contributorNames.get(contributorFilter)) {
      return { kind: "contributor" as const, name: contributorNames.get(contributorFilter)! };
    }
    if (assetFilter && assetNames.get(assetFilter)) {
      return { kind: "asset" as const, name: assetNames.get(assetFilter)! };
    }
    return null;
  })();

  const isFirstLoad = contributions.loading && rows.length === 0;
  const initialError = contributions.error && rows.length === 0 ? contributions.error : null;
  const visibleEntriesLabel =
    totalKnown !== null && rows.length < totalKnown && !contributorFilter && !assetFilter
      ? `${filteredRows.length.toLocaleString(locale)} / ${totalKnown.toLocaleString(locale)}`
      : filteredRows.length.toLocaleString(locale);

  return (
    <main className="bg-stone-950 min-h-screen">
      {/* Hero — value flowing through the body */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[40vh] min-h-[300px] max-h-[440px]">
          <div className="absolute inset-0 hero-breath">
            <Image
              src="/visuals/04-vitality.png"
              alt={t("contributions.heroAlt")}
              fill
              priority
              className="object-cover"
              sizes="100vw"
            />
          </div>
          <div
            className="absolute inset-0 hero-pulse pointer-events-none"
            style={{
              background:
                "radial-gradient(ellipse at center, hsl(38 92% 50% / 0.15) 0%, transparent 70%)",
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/40 via-stone-950/55 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-5xl px-4 sm:px-6 pb-8 sm:pb-12 hero-reveal">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                {t("contributions.eyebrow")}
              </p>
              <h1 className="mt-2 text-3xl sm:text-5xl font-light tracking-tight text-stone-50">
                <span className="sr-only">Contributions</span>
                {t("contributions.title")}
                <span className="sr-only">Contributions</span>
              </h1>
              <p className="mt-3 max-w-2xl text-base sm:text-lg text-stone-200/95 leading-relaxed">
                {t("contributions.lede")}
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-10 space-y-6 sm:space-y-8">
        <LedgerNav />

        {/* Filter context, if any */}
        {filterContext && (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm flex flex-wrap items-center gap-2">
            <span className="text-stone-400">{t("contributions.filteredBy")}</span>
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-0.5 text-amber-300">
              {filterContext.kind === "contributor" ? t("contributions.filterContributor") : t("contributions.filterAsset")} · {filterContext.name}
            </span>
            <Link
              href="/contributions"
              className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline ml-auto"
            >
              {t("contributions.filterClear")}
            </Link>
          </div>
        )}

        {/* Stat tiles */}
        <section className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("contributions.statEntries")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{visibleEntriesLabel}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributions.statEntriesHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-amber-500/10 to-amber-500/5 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-amber-400/80">{t("contributions.statCost")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">CC {filteredSummary.totalCost.toFixed(2)}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributions.statCostHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("contributions.statCells")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{filteredSummary.contributors}</p>
            <p className="mt-1 text-xs text-stone-400">{t("contributions.statCellsHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("contributions.statCoherence")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">
              {filteredSummary.averageCoherence === null ? "—" : filteredSummary.averageCoherence.toFixed(2)}
            </p>
            <p className="mt-1 text-xs text-stone-400">{t("contributions.statCoherenceHint")}</p>
          </div>
        </section>

        {isFirstLoad && <p className="text-stone-400 text-sm">{t("contributions.loading")}</p>}
        {initialError && (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-300">
            {t("contributions.errorPrefix")} {initialError}
          </div>
        )}

        {!isFirstLoad && !initialError && (
          <section className="space-y-3">
            <ul className="space-y-3">
              {filteredRows.map((c, idx) => {
                const cost = effectiveCost(c);
                const commitHash = c.metadata?.commit_hash;
                const displayCoherence = c.coherence_score > 0 ? c.coherence_score : liveCoherenceScore;
                const coherenceValue = displayCoherence !== null ? Math.min(1, Math.max(0, displayCoherence)) : null;
                const summary = decodeEntities(
                  c.metadata?.summary || c.metadata?.description ||
                  (c.metadata?.commit_hash
                    ? t("contributions.ledgerEntryFallback")
                    : t("contributions.ledgerEntryNumbered", { n: idx + 1 }))
                );
                return (
                  <li
                    key={c.id}
                    className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4 sm:p-5 space-y-3 hover:border-amber-400/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-stone-100 truncate">{summary}</p>
                        <p className="text-xs text-stone-400 mt-0.5">{formatDate(c.timestamp, locale)}</p>
                      </div>
                      <span className="font-medium whitespace-nowrap text-amber-300 text-lg">CC {cost.effective.toFixed(2)}</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      <span className="text-stone-400">{t("contributions.by")}</span>
                      <Link
                        href={`/contributors/${encodeURIComponent(c.contributor_id)}/portfolio`}
                        className="text-stone-200 hover:text-amber-300 underline-offset-4 hover:underline font-medium"
                      >
                        {contributorNames.get(c.contributor_id) || truncateId(c.contributor_id)}
                      </Link>
                      <span className="text-stone-500">→</span>
                      <Link
                        href={`/assets/${encodeURIComponent(c.asset_id)}`}
                        className="text-stone-200 hover:text-amber-300 underline-offset-4 hover:underline font-medium truncate max-w-[200px] sm:max-w-none"
                      >
                        {assetNames.get(c.asset_id) || truncateId(c.asset_id)}
                      </Link>
                    </div>

                    {coherenceValue !== null && (
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-stone-400">{t("contributions.coherence")}</span>
                        <div className="flex-1 max-w-[200px] h-1.5 rounded-full bg-stone-800 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${(coherenceValue * 100).toFixed(0)}%`,
                              backgroundColor: coherenceValue >= 0.7 ? "#34d399" : coherenceValue >= 0.4 ? "#fbbf24" : "#fb7185",
                            }}
                          />
                        </div>
                        <span className="text-stone-300 font-mono">{coherenceValue.toFixed(2)}</span>
                      </div>
                    )}

                    {(cost.normalized !== null && Math.abs(cost.raw - cost.normalized) >= 0.01) ||
                    (cost.source === "derived" && Math.abs(cost.raw - cost.effective) >= 0.01) ? (
                      <div className="text-xs text-stone-500">
                        {t("contributions.adjustedFromTo", {
                          raw: cost.raw.toFixed(2),
                          effective: cost.effective.toFixed(2),
                        })}
                      </div>
                    ) : null}

                    {(c.metadata?.cost_basis || typeof c.metadata?.cost_confidence === "number" || commitHash) && (
                      <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1 text-[11px] text-stone-500 border-t border-border/20">
                        {c.metadata?.cost_basis && <span>{costBasisLabel(t, c.metadata.cost_basis)}</span>}
                        {typeof c.metadata?.cost_confidence === "number" && (
                          <span>{t("contributions.confidence", { pct: (c.metadata.cost_confidence * 100).toFixed(0) })}</span>
                        )}
                        {commitHash && <span className="font-mono">{t("contributions.commit", { hash: commitHash.slice(0, 12) })}</span>}
                        <Link
                          href={`/contributors/${encodeURIComponent(c.contributor_id)}/portfolio/contributions/${encodeURIComponent(c.id)}`}
                          className="ml-auto text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
                        >
                          {t("contributions.audit")}
                        </Link>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>

            {filteredRows.length === 0 && (
              <div className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
                <p className="text-stone-300">
                  {contributorFilter || assetFilter
                    ? t("contributions.emptyFilteredTitle")
                    : t("contributions.emptyTitle")}
                </p>
                <p className="text-sm text-stone-500 leading-relaxed max-w-md mx-auto">
                  {t("contributions.emptyBody")}
                </p>
                <div className="pt-2">
                  <Link
                    href="/contribute"
                    className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-5 py-2 text-sm text-amber-200 hover:bg-amber-500/20 transition-colors"
                  >
                    {t("contributions.emptyCtaContribute")}
                  </Link>
                </div>
              </div>
            )}

            {/* Sentinel + loading-more — only when there's more to fetch */}
            {!contributions.loadedAll && (
              <div ref={sentinelRef} className="flex items-center justify-center py-6">
                {contributions.loading && (
                  <p className="text-stone-500 text-sm">{t("common.loading")}</p>
                )}
                {!contributions.loading && contributions.error && (
                  <button
                    type="button"
                    onClick={contributions.loadMore}
                    className="text-stone-400 hover:text-amber-300 text-sm underline-offset-4 hover:underline"
                  >
                    {t("common.loading")}
                  </button>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

function LoadingFallback() {
  const t = useT();
  return (
    <main className="min-h-screen bg-stone-950">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-10">
        <p className="text-stone-400">{t("contributions.loading")}</p>
      </div>
    </main>
  );
}

export default function ContributionsPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ContributionsPageContent />
    </Suspense>
  );
}
