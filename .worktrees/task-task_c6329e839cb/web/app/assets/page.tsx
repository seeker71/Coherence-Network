"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";
import { useT, useLocale } from "@/components/MessagesProvider";

const API_URL = getApiBase();

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

type Asset = {
  id: string;
  type: string;
  description: string;
  total_cost: string;
  created_at: string;
};

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

function AssetsPageContent() {
  const t = useT();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Asset[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const selectedAssetId = useMemo(() => (searchParams.get("asset_id") || "").trim(), [searchParams]);

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/assets`, { cache: "no-store" });
      // Check res.ok BEFORE parsing — FastAPI returns plain-text
      // 'Internal Server Error' on 500, which JSON.parse can't handle
      // and would surface as a cryptic SyntaxError instead of the
      // actual HTTP status.
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      const json = await res.json();
      const data = json?.items ?? (Array.isArray(json) ? json : []);
      setRows(data);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(loadRows);

  const filteredRows = useMemo(() => {
    if (!selectedAssetId) return rows;
    return rows.filter((row) => row.id === selectedAssetId);
  }, [rows, selectedAssetId]);

  const totalCost = useMemo(
    () => filteredRows.reduce((sum, row) => sum + (Number(row.total_cost) || 0), 0),
    [filteredRows],
  );
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of filteredRows) {
      const key = row.type || "UNKNOWN";
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [filteredRows]);

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      {/* Peer pages (Ideas · Contribute · Pipeline · Work Cards ·
          Contributors · Assets) live in the layer sub-nav under The
          Work — no need to duplicate them here. */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{t("assets.title")}</h1>
        <p className="max-w-3xl text-muted-foreground">
          {t("assets.lede")}
        </p>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("assets.statVisible")}</p>
          <p className="mt-2 text-3xl font-light">{formatCount(filteredRows.length)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("assets.statCost")}</p>
          <p className="mt-2 text-3xl font-light">{formatCost(totalCost)}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("assets.statTopType")}</p>
          <p className="mt-2 text-3xl font-light">{typeCounts[0]?.[0] || "—"}</p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">{t("assets.statLinked")}</p>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("assets.linkedHint")}
          </p>
        </div>
      </section>

      <p className="text-muted-foreground">
        {t("assets.browseAll")}
        {selectedAssetId ? (
          <>
            {" "}
            {t("assets.showingOne")}
          </>
        ) : null}
      </p>

      {status === "loading" && <p className="text-muted-foreground">{t("common.loading")}</p>}
      {status === "error" && <p className="text-destructive">{t("contributors.errorPrefix")}{error}</p>}

      {status === "ok" && (
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
          <p className="text-sm text-muted-foreground">
            {t(filteredRows.length === 1 ? "assets.assetOne" : "assets.assetMany", { n: filteredRows.length })}
            {selectedAssetId ? (
              <>
                {" "}
                · <Link href="/assets" className="underline hover:text-foreground">{t("contributors.clearFilter")}</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((a) => (
              <li key={a.id} className="rounded-2xl border border-border/20 bg-background/40 p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Link href={`/assets/${encodeURIComponent(a.id)}`} className="font-medium hover:underline">
                      {a.description || a.type || "Untitled asset"}
                    </Link>
                    {a.type && (
                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                        {a.type}
                      </span>
                    )}
                  </div>
                  <span className="font-medium whitespace-nowrap">{formatCost(a.total_cost)}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Created {formatDate(a.created_at, locale)}</span>
                  <Link
                    href={`/assets/${encodeURIComponent(a.id)}`}
                    className="underline hover:text-foreground"
                  >
                    Asset detail
                  </Link>
                  <Link
                    href={`/contributions?asset_id=${encodeURIComponent(a.id)}`}
                    className="underline hover:text-foreground"
                  >
                    View contributions
                  </Link>
                </div>
              </li>
            ))}
            {filteredRows.length === 0 ? (
              <li className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-6 text-sm text-muted-foreground">
                No assets are registered yet. Once assets land through the API, this page will show their cost, type, and contribution history. Until then, start from{" "}
                <Link href="/contribute" className="underline hover:text-foreground">
                  Contribution Console
                </Link>{" "}
                or review the{" "}
                <Link href="/contributions" className="underline hover:text-foreground">
                  contribution ledger
                </Link>
                .
              </li>
            ) : null}
          </ul>
        </section>
      )}
    </main>
  );
}

function AssetsFallback() {
  const t = useT();
  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-4">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">{t("assets.title")}</h1>
      </div>
      <p className="text-muted-foreground">{t("assets.loadingAssets")}</p>
    </main>
  );
}

export default function AssetsPage() {
  return (
    <Suspense fallback={<AssetsFallback />}>
      <AssetsPageContent />
    </Suspense>
  );
}
