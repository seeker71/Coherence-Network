"use client";

import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";

interface DailyViews {
  date: string;
  views: number;
}

interface AssetAnalytics {
  asset_id: string;
  total_views: number;
  unique_contributors: number;
  anonymous_views: number;
  authenticated_views: number;
  daily_views: DailyViews[];
  discovery_chain: DiscoveryLink[];
}

interface DiscoveryLink {
  referrer_id: string;
  referrer_label: string;
  referred_count: number;
}

interface ViewAnalyticsProps {
  assetId: string;
  className?: string;
}

function DailyChart({ data }: { data: DailyViews[] }) {
  if (!data.length) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        Daily view data is still accumulating.
      </p>
    );
  }

  const max = Math.max(...data.map((d) => d.views), 1);

  return (
    <div className="flex items-end gap-1" style={{ height: 120 }}>
      {data.map((day) => {
        const height = Math.max(2, (day.views / max) * 120);
        return (
          <div key={day.date} className="group flex flex-1 flex-col items-center gap-1">
            <span className="hidden text-[10px] text-muted-foreground group-hover:block">
              {day.views}
            </span>
            <div
              className="w-full rounded-t bg-primary/80 transition-colors hover:bg-primary"
              style={{ height }}
            />
            <span className="text-[10px] text-muted-foreground">
              {day.date.slice(5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ViewAnalytics({ assetId, className = "" }: ViewAnalyticsProps) {
  const [analytics, setAnalytics] = useState<AssetAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${getApiBase()}/api/views/stats/${encodeURIComponent(assetId)}`);
        if (!res.ok) return;
        const data = (await res.json()) as AssetAnalytics;
        if (!cancelled) setAnalytics(data);
      } catch {
        // Analytics are supplementary
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [assetId]);

  if (loading) {
    return (
      <div className={`space-y-4 ${className}`}>
        <div className="h-8 w-48 animate-pulse rounded bg-muted/50" />
        <div className="h-32 animate-pulse rounded-lg bg-muted/50" />
        <div className="h-24 animate-pulse rounded-lg bg-muted/50" />
      </div>
    );
  }

  if (!analytics) {
    return (
      <p className="text-sm text-muted-foreground">
        Analytics for this asset are still gathering.
      </p>
    );
  }

  const authPct = analytics.total_views > 0
    ? Math.round((analytics.authenticated_views / analytics.total_views) * 100)
    : 0;
  const anonPct = 100 - authPct;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total views" value={analytics.total_views} />
        <StatCard label="Contributors" value={analytics.unique_contributors} />
        <StatCard label="Authenticated" value={`${authPct}%`} />
        <StatCard label="Anonymous" value={`${anonPct}%`} />
      </div>

      {/* Daily chart */}
      <section>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Daily views</h3>
        <div className="rounded-xl border border-border/40 bg-card/50 p-4">
          <DailyChart data={analytics.daily_views ?? []} />
        </div>
      </section>

      {/* Auth breakdown bar */}
      <section>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">
          Visitor breakdown
        </h3>
        <div className="flex h-3 overflow-hidden rounded-full bg-muted">
          {authPct > 0 && (
            <div
              className="bg-primary transition-all"
              style={{ width: `${authPct}%` }}
            />
          )}
          {anonPct > 0 && (
            <div
              className="bg-muted-foreground/30 transition-all"
              style={{ width: `${anonPct}%` }}
            />
          )}
        </div>
        <div className="mt-1 flex justify-between text-xs text-muted-foreground">
          <span>Authenticated ({analytics.authenticated_views})</span>
          <span>Anonymous ({analytics.anonymous_views})</span>
        </div>
      </section>

      {/* Discovery chain */}
      {analytics.discovery_chain?.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">
            Discovery chain
          </h3>
          <div className="space-y-2">
            {analytics.discovery_chain.map((link) => (
              <div
                key={link.referrer_id}
                className="flex items-center justify-between rounded-lg border border-border/40 bg-card/50 px-3 py-2"
              >
                <span className="text-sm">{link.referrer_label}</span>
                <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {link.referred_count} referral{link.referred_count === 1 ? "" : "s"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border/40 bg-card/50 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}
