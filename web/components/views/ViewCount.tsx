"use client";

import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";

interface ViewStats {
  total_views: number;
  unique_contributors: number;
}

interface ViewCountProps {
  assetId: string;
  compact?: boolean;
  className?: string;
}

export default function ViewCount({ assetId, compact = false, className = "" }: ViewCountProps) {
  const [stats, setStats] = useState<ViewStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${getApiBase()}/api/views/stats/${encodeURIComponent(assetId)}`);
        if (!res.ok) return;
        const data = (await res.json()) as ViewStats;
        if (!cancelled) setStats(data);
      } catch {
        // View counts are supplementary; failures render gracefully
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [assetId]);

  if (loading) {
    return (
      <span className={`inline-block animate-pulse text-xs text-muted-foreground ${className}`}>
        ...
      </span>
    );
  }

  if (!stats) return null;

  if (compact) {
    return (
      <span className={`text-xs text-muted-foreground ${className}`}>
        {stats.total_views} views
      </span>
    );
  }

  return (
    <span className={`text-xs text-muted-foreground ${className}`}>
      {stats.total_views} view{stats.total_views === 1 ? "" : "s"} · {stats.unique_contributors} contributor{stats.unique_contributors === 1 ? "" : "s"}
    </span>
  );
}
