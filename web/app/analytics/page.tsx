"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import ViewTrending from "@/components/views/ViewTrending";

interface ViewSummary {
  total_views: number;
  unique_contributors: number;
  assets_viewed: number;
  by_type: AssetTypeSummary[];
}

interface AssetTypeSummary {
  asset_type: string;
  total_views: number;
  asset_count: number;
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<ViewSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${getApiBase()}/api/views/summary`);
        if (!res.ok) return;
        const data = (await res.json()) as ViewSummary;
        if (!cancelled) setSummary(data);
      } catch {
        // Summary data is supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 sm:px-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How attention flows through the network.
        </p>
      </header>

      {/* Aggregate summary */}
      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <SummaryCard label="Total views" value={summary.total_views} />
          <SummaryCard label="Contributors" value={summary.unique_contributors} />
          <SummaryCard label="Assets viewed" value={summary.assets_viewed} />
        </div>
      ) : null}

      {/* Trending */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">Trending</h2>
        <ViewTrending limit={10} />
      </section>

      {/* Views by asset type */}
      {summary?.by_type && summary.by_type.length > 0 && (
        <section>
          <h2 className="mb-4 text-lg font-semibold">Views by type</h2>
          <div className="space-y-2">
            {summary.by_type.map((entry) => {
              const maxViews = Math.max(...summary.by_type.map((t) => t.total_views), 1);
              const width = Math.max(4, (entry.total_views / maxViews) * 100);
              return (
                <div key={entry.asset_type} className="rounded-lg border border-border/40 bg-card/50 p-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium capitalize">{entry.asset_type}</span>
                    <span className="text-muted-foreground">
                      {entry.total_views} view{entry.total_views === 1 ? "" : "s"} across {entry.asset_count} asset{entry.asset_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary/70 transition-all"
                      style={{ width: `${width}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <footer className="border-t border-border/30 pt-4">
        <Link
          href="/"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          Back to home
        </Link>
      </footer>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border/40 bg-card/50 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value.toLocaleString()}</p>
    </div>
  );
}
