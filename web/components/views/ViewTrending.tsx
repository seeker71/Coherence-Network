"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

interface TrendingAsset {
  asset_id: string;
  asset_type: string;
  title: string;
  total_views: number;
  recent_views: number;
  trend: number[];
}

interface ViewTrendingProps {
  limit?: number;
  className?: string;
}

function Sparkline({ data, className = "" }: { data: number[]; className?: string }) {
  if (!data.length) return null;

  const max = Math.max(...data, 1);
  const barCount = data.length;

  return (
    <div className={`flex items-end gap-px ${className}`} style={{ height: 24 }}>
      {data.map((value, i) => {
        const height = Math.max(2, (value / max) * 24);
        const opacity = 0.3 + (i / Math.max(barCount - 1, 1)) * 0.7;
        return (
          <div
            key={i}
            className="w-1 rounded-sm bg-primary"
            style={{ height, opacity }}
          />
        );
      })}
    </div>
  );
}

export default function ViewTrending({ limit = 10, className = "" }: ViewTrendingProps) {
  const [assets, setAssets] = useState<TrendingAsset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(
          `${getApiBase()}/api/views/trending?limit=${limit}`
        );
        if (!res.ok) return;
        const data = (await res.json()) as TrendingAsset[];
        if (!cancelled) setAssets(data);
      } catch {
        // Trending data is supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [limit]);

  if (loading) {
    return (
      <div className={`space-y-3 ${className}`}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-muted/50" />
        ))}
      </div>
    );
  }

  if (!assets.length) {
    return (
      <p className="text-sm text-muted-foreground">
        Views are gathering. Trending data appears as traffic arrives.
      </p>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {assets.map((asset, index) => (
        <Link
          key={asset.asset_id}
          href={`/analytics/${encodeURIComponent(asset.asset_id)}`}
          className="flex items-center gap-3 rounded-lg border border-border/40 bg-card/50 p-3 transition-colors hover:bg-card"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
            {index + 1}
          </span>

          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium">{asset.title}</p>
            <p className="text-xs text-muted-foreground">
              {asset.total_views} total · {asset.recent_views} recent
            </p>
          </div>

          <Sparkline data={asset.trend} className="shrink-0" />

          <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {asset.asset_type}
          </span>
        </Link>
      ))}
    </div>
  );
}
