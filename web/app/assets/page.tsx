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
import { AssetGlyph, assetTypeTone } from "@/app/_components/AssetGlyph";
import { assetTypeLabel } from "@/lib/asset-types";
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

function formatCost(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "CC 0.00";
  return `CC ${n.toFixed(2)}`;
}

function externalHost(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

type Asset = {
  id: string;
  type: string;
  description: string;
  total_cost: string;
  created_at: string;
  image_url?: string | null;
  file_path?: string | null;
  // Extended fields the body holds — not all populated for every asset.
  name?: string | null;
  canonical_url?: string | null;
  creator_id?: string | null;
  creation_kind?: string | null;
  asset_type?: string | null;
  era?: string | null;
  company?: string | null;
  language?: string | null;
  runtime_length_min?: number | null;
  isbn?: string | null;
  asin?: string | null;
  ipfs_cid?: string | null;
  arweave_tx?: string | null;
  content_hash?: string | null;
  slug?: string | null;
};

function AssetsPageContent() {
  const t = useT();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [creatorNames, setCreatorNames] = useState<Map<string, string>>(new Map());

  const selectedAssetId = useMemo(() => (searchParams.get("asset_id") || "").trim(), [searchParams]);

  const buildAssetsUrl = useCallback(
    (offset: number, limit: number) => `${API_URL}/api/assets?offset=${offset}&limit=${limit}`,
    [],
  );

  const assets = usePagedList<Asset>({
    buildUrl: buildAssetsUrl,
    pageSize: PAGE_SIZE,
    timeoutMs: 10000,
    retries: 3,
  });
  const rows = assets.items;
  const totalKnown = assets.total;

  // Resolve creator names so the "by {creator}" chip can link with a real
  // name instead of a uuid. Best-effort — if the lookup fails, the chip
  // falls back to the raw id (still navigable).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const json = await fetchJsonOrNull<
        { items?: Array<{ id: string; name?: string }> } | Array<{ id: string; name?: string }>
      >(`${API_URL}/api/contributors?limit=1000`, { cache: "no-store" }, 10000, 3);
      if (cancelled || !json) return;
      const items = Array.isArray(json) ? json : json.items ?? [];
      const map = new Map<string, string>();
      for (const c of items) {
        if (c.id && c.name) map.set(c.id, c.name);
      }
      setCreatorNames(map);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Sentinel: when the bottom marker enters the viewport, ask for more.
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            assets.loadMore();
          }
        }
      },
      { rootMargin: "300px" },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [assets.loadMore]);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rows) {
      const key = row.type || "UNKNOWN";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const filteredRows = useMemo(() => {
    let r = rows;
    if (typeFilter !== "ALL") {
      r = r.filter((row) => (row.type || "").toUpperCase() === typeFilter);
    }
    if (selectedAssetId) {
      r = r.filter((row) => row.id === selectedAssetId);
    }
    return r;
  }, [rows, typeFilter, selectedAssetId]);

  const totalCost = useMemo(
    () => filteredRows.reduce((sum, row) => sum + (Number(row.total_cost) || 0), 0),
    [filteredRows],
  );

  const isFirstLoad = assets.loading && rows.length === 0;
  const initialError = assets.error && rows.length === 0 ? assets.error : null;
  const visibleTotal = totalKnown !== null && totalKnown > rows.length ? totalKnown : rows.length;

  return (
    <main className="bg-stone-950 min-h-screen">
      {/* Hero — vessels and artifacts */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[40vh] min-h-[300px] max-h-[440px]">
          <div className="absolute inset-0 hero-breath">
            <Image
              src="/visuals/05-nourishing.png"
              alt={t("assets.heroAlt")}
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
                {t("assets.eyebrow")}
              </p>
              <h1 className="mt-2 text-3xl sm:text-5xl font-light tracking-tight text-stone-50">
                <span className="sr-only">Assets</span>
                {t("assets.title")}
                <span className="sr-only">Assets</span>
              </h1>
              <p className="mt-3 max-w-2xl text-base sm:text-lg text-stone-200/95 leading-relaxed">
                {t("assets.lede")}
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-10 space-y-6 sm:space-y-8">
        <LedgerNav />

        {/* Stat tiles */}
        <section className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.statVisible")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{visibleTotal.toLocaleString(locale)}</p>
            <p className="mt-1 text-xs text-stone-400">{t("assets.statVisibleHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-amber-500/10 to-amber-500/5 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-amber-400/80">{t("assets.statCost")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{formatCost(totalCost)}</p>
            <p className="mt-1 text-xs text-stone-400">{t("assets.statCostHint")}</p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.statTopType")}</p>
            <p className="mt-2 text-2xl font-light text-stone-100">{typeCounts[0] ? assetTypeLabel(t, typeCounts[0][0]) : "—"}</p>
            <p className="mt-1 text-xs text-stone-400">
              {t("assets.statTopTypeHint", { count: typeCounts[0]?.[1] ?? 0, total: rows.length })}
            </p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{t("assets.statKinds")}</p>
            <p className="mt-2 text-3xl font-light text-stone-100">{typeCounts.length}</p>
            <p className="mt-1 text-xs text-stone-400">{t("assets.statKindsHint")}</p>
          </div>
        </section>

        {/* Type filter pills */}
        {typeCounts.length > 0 && (
          <div className="-mx-4 sm:mx-0 px-4 sm:px-0 overflow-x-auto">
            <div className="flex items-center gap-2 min-w-max">
              <button
                type="button"
                onClick={() => setTypeFilter("ALL")}
                className={[
                  "rounded-full border px-3 py-1.5 text-xs whitespace-nowrap transition-all",
                  typeFilter === "ALL"
                    ? "border-amber-400/50 bg-amber-500/10 text-amber-200"
                    : "border-border/30 bg-card/30 text-stone-400 hover:border-amber-400/30 hover:text-amber-200",
                ].join(" ")}
              >
                {t("assets.filterAll")} <span className="text-stone-500">· {rows.length}</span>
              </button>
              {typeCounts.map(([type, count]) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setTypeFilter(typeFilter === type ? "ALL" : type)}
                  className={[
                    "rounded-full border px-3 py-1.5 text-xs whitespace-nowrap transition-all",
                    typeFilter === type
                      ? "border-amber-400/50 bg-amber-500/10 text-amber-200"
                      : "border-border/30 bg-card/30 text-stone-400 hover:border-amber-400/30 hover:text-amber-200",
                  ].join(" ")}
                >
                  {assetTypeLabel(t, type)} <span className="text-stone-500">· {count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Filter banner */}
        {selectedAssetId && (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm flex items-center gap-2">
            <span className="text-stone-400">{t("assets.filterShowingOne")}</span>
            <Link
              href="/assets"
              className="ml-auto text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
            >
              {t("assets.filterClear")}
            </Link>
          </div>
        )}

        {isFirstLoad && <p className="text-stone-400 text-sm">{t("common.loading")}</p>}
        {initialError && (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-300">
            {t("assets.errorPrefix")} {initialError}
          </div>
        )}

        {!isFirstLoad && !initialError && (
          <section className="space-y-3">
            <ul className="grid gap-3 sm:grid-cols-2">
              {filteredRows.map((a) => {
                const title = decodeEntities(a.name || a.description || a.type || t("assets.untitled"));
                const story =
                  a.name && a.description && a.description !== a.name
                    ? decodeEntities(a.description)
                    : null;
                const thumbSrc = a.file_path || a.image_url || null;
                const tone = assetTypeTone(a.type);
                const sourceHost = a.canonical_url ? externalHost(a.canonical_url) : null;
                const creatorName = a.creator_id ? creatorNames.get(a.creator_id) : null;
                const identifierChips: { label: string; value: string }[] = [];
                if (a.isbn) identifierChips.push({ label: "ISBN", value: a.isbn });
                if (a.asin) identifierChips.push({ label: "ASIN", value: a.asin });
                if (a.ipfs_cid) identifierChips.push({ label: "IPFS", value: a.ipfs_cid.slice(0, 12) + "…" });
                if (a.arweave_tx) identifierChips.push({ label: "AR", value: a.arweave_tx.slice(0, 10) + "…" });
                if (a.content_hash) identifierChips.push({ label: "sha", value: a.content_hash.slice(0, 10) + "…" });
                return (
                  <li
                    key={a.id}
                    className={[
                      "group relative tone-card",
                      tone.glowClass,
                      "rounded-2xl border border-border/30 bg-gradient-to-br from-card/60 to-card/30 overflow-hidden hover:border-amber-400/30 hover:from-card/80 hover:to-card/40",
                    ].join(" ")}
                  >
                    <span
                      aria-hidden="true"
                      className={[
                        "absolute left-0 top-0 bottom-0 w-[3px] z-10",
                        tone.stripe,
                      ].join(" ")}
                    />
                    {thumbSrc && (
                      <Link
                        href={`/assets/${encodeURIComponent(a.id)}`}
                        className="block relative aspect-video w-full bg-stone-900/40 overflow-hidden"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={thumbSrc}
                          alt={t("assets.thumbnailAlt", { description: title })}
                          loading="lazy"
                          className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.02]"
                        />
                      </Link>
                    )}
                    <div className="flex items-start gap-3 sm:gap-4 p-4 sm:p-5">
                      <AssetGlyph type={a.type} className="flex-shrink-0" />
                      <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <Link
                            href={`/assets/${encodeURIComponent(a.id)}`}
                            className="font-medium text-stone-100 hover:text-amber-200 transition-colors leading-snug min-w-0 break-words"
                          >
                            {title}
                          </Link>
                          {Number(a.total_cost) > 0 && (
                            <span className="text-amber-300 text-sm whitespace-nowrap font-medium">
                              {formatCost(a.total_cost)}
                            </span>
                          )}
                        </div>

                        {story && (
                          <p className="text-xs text-stone-400 leading-snug line-clamp-3">
                            {story}
                          </p>
                        )}

                        {/* Provenance chips: who made it, when, in what tongue */}
                        {(creatorName || a.creator_id || a.era || a.company || a.language || a.runtime_length_min) && (
                          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                            {(creatorName || a.creator_id) && (
                              <Link
                                href={`/contributors/${encodeURIComponent(a.creator_id || "")}/portfolio`}
                                className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-300 hover:border-amber-400/50 transition-colors"
                              >
                                {t("assets.byCreator", { name: creatorName || a.creator_id || "" })}
                              </Link>
                            )}
                            {a.era && (
                              <span className="inline-flex items-center rounded-full border border-stone-600/40 bg-card/40 px-2 py-0.5 text-stone-300" title={t("assets.eraTitle")}>
                                {a.era}
                              </span>
                            )}
                            {a.company && (
                              <span className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-stone-400">
                                {a.company}
                              </span>
                            )}
                            {a.language && (
                              <span className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-stone-400">
                                {a.language}
                              </span>
                            )}
                            {a.runtime_length_min && a.runtime_length_min > 0 && (
                              <span className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-stone-400">
                                {t("assets.runtimeMin", { n: a.runtime_length_min })}
                              </span>
                            )}
                          </div>
                        )}

                        {/* Type + date — kept compact */}
                        <div className="flex flex-wrap items-center gap-2 text-[11px]">
                          {a.type && (
                            <span className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-stone-400">
                              {assetTypeLabel(t, a.type)}
                            </span>
                          )}
                          {a.created_at && (
                            <span className="text-stone-500">
                              {formatDate(a.created_at, locale)}
                            </span>
                          )}
                        </div>

                        {/* Identifier chips — content-addressed proofs */}
                        {identifierChips.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1 text-[10px] font-mono">
                            {identifierChips.map((chip) => (
                              <span
                                key={`${chip.label}:${chip.value}`}
                                className="inline-flex items-center rounded border border-border/20 bg-card/30 px-1.5 py-0.5 text-stone-500"
                                title={chip.label}
                              >
                                <span className="text-stone-600">{chip.label}</span>
                                <span className="ml-1 text-stone-400">{chip.value}</span>
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Bottom links — open in body, view source, contributions */}
                        <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs">
                          <Link
                            href={`/assets/${encodeURIComponent(a.id)}`}
                            className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
                          >
                            {t("assets.linkOpen")}
                          </Link>
                          {a.canonical_url && (
                            <a
                              href={a.canonical_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
                              title={a.canonical_url}
                            >
                              {sourceHost ? t("assets.linkSourceHost", { host: sourceHost }) : t("assets.linkSource")}
                              <span aria-hidden="true"> ↗</span>
                            </a>
                          )}
                          <Link
                            href={`/contributions?asset_id=${encodeURIComponent(a.id)}`}
                            className="text-stone-400 hover:text-amber-300 underline-offset-4 hover:underline"
                          >
                            {t("assets.linkContributions")}
                          </Link>
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>

            {filteredRows.length === 0 && (
              <div className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
                <p className="text-stone-300">
                  {selectedAssetId || typeFilter !== "ALL"
                    ? t("assets.emptyFilteredTitle")
                    : t("assets.emptyTitle")}
                </p>
                <p className="text-sm text-stone-500 leading-relaxed max-w-md mx-auto">
                  {t("assets.emptyBody")}
                </p>
                <div className="pt-2 flex flex-wrap justify-center gap-3">
                  <Link
                    href="/contribute"
                    className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-5 py-2 text-sm text-amber-200 hover:bg-amber-500/20 transition-colors"
                  >
                    {t("assets.emptyCtaContribute")}
                  </Link>
                  <Link
                    href="/contributions"
                    className="inline-flex items-center rounded-full border border-border/40 px-5 py-2 text-sm text-stone-300 hover:border-amber-400/30 hover:text-amber-200 transition-colors"
                  >
                    {t("assets.emptyCtaLedger")}
                  </Link>
                </div>
              </div>
            )}

            {/* Sentinel + loading-more — only when there's more to fetch */}
            {!assets.loadedAll && (
              <div ref={sentinelRef} className="flex items-center justify-center py-6">
                {assets.loading && (
                  <p className="text-stone-500 text-sm">{t("common.loading")}</p>
                )}
                {!assets.loading && assets.error && (
                  <button
                    type="button"
                    onClick={assets.loadMore}
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
        <p className="text-stone-400">{t("assets.loadingAssets")}</p>
      </div>
    </main>
  );
}

export default function AssetsPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <AssetsPageContent />
    </Suspense>
  );
}
