"use client";

import { Suspense, useCallback, useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

type WeekBucket = {
  week_start: string;
  count: number;
  types: Record<string, number>;
  total_cc: number;
};

type Milestone = {
  name: string;
  description: string;
  reached_at: string | null;
  contribution_count: number;
};

type Level = {
  name: string;
  description: string;
  index: number;
  progress_to_next: number;
  next_threshold: number | null;
};

type GrowthSnapshot = {
  contributor_id: string;
  display_name: string;
  total_contributions: number;
  total_cc: number;
  contributions_by_type: Record<string, number>;
  level: Level;
  current_streak_weeks: number;
  longest_streak_weeks: number;
  last_active_at: string | null;
  weekly_timeline: WeekBucket[];
  contributions_last_30d: number;
  contributions_prev_30d: number;
  growth_pct: number | null;
  milestones: Milestone[];
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function GrowthBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(1, value / max) : 0;
  const color =
    pct >= 0.7 ? "#22c55e" : pct >= 0.3 ? "#3b82f6" : pct > 0 ? "#a3a3a3" : "#1f2937";
  return (
    <div className="h-8 w-4 rounded-sm flex items-end" style={{ background: "#1f2937" }} title={`${value} contributions`}>
      <div
        className="w-full rounded-sm transition-all"
        style={{ height: `${Math.max(2, pct * 100)}%`, background: color }}
      />
    </div>
  );
}

function TypeBadge({ type, count }: { type: string; count: number }) {
  const colorMap: Record<string, string> = {
    code: "bg-blue-900 text-blue-200",
    spec: "bg-purple-900 text-purple-200",
    question: "bg-yellow-900 text-yellow-200",
    review: "bg-green-900 text-green-200",
    share: "bg-pink-900 text-pink-200",
    research: "bg-indigo-900 text-indigo-200",
    design: "bg-orange-900 text-orange-200",
    testing: "bg-teal-900 text-teal-200",
    documentation: "bg-cyan-900 text-cyan-200",
    mentoring: "bg-rose-900 text-rose-200",
    feedback: "bg-amber-900 text-amber-200",
    direction: "bg-violet-900 text-violet-200",
  };
  const cls = colorMap[type] ?? "bg-gray-800 text-gray-300";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {type}
      <span className="font-bold">{count}</span>
    </span>
  );
}

function LevelCard({ level, total }: { level: Level; total: number }) {
  const levelColors = [
    "from-gray-700 to-gray-600",
    "from-green-900 to-green-700",
    "from-teal-900 to-teal-700",
    "from-blue-900 to-blue-700",
    "from-indigo-900 to-indigo-700",
    "from-violet-900 to-violet-700",
  ];
  const gradClass = levelColors[level.index] ?? "from-gray-700 to-gray-600";
  return (
    <div className={`rounded-lg p-4 bg-gradient-to-br ${gradClass} space-y-2`}>
      <div className="flex items-baseline justify-between">
        <span className="text-xl font-bold">{level.name}</span>
        <span className="text-sm text-white/60">{total} contributions</span>
      </div>
      <p className="text-sm text-white/80 italic">{level.description}</p>
      {level.next_threshold !== null && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-white/60">
            <span>Progress to next level</span>
            <span>{level.next_threshold - total} to go</span>
          </div>
          <div className="h-2 rounded-full bg-black/30 overflow-hidden">
            <div
              className="h-full rounded-full bg-white/50 transition-all"
              style={{ width: `${(level.progress_to_next * 100).toFixed(1)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function GrowthPageContent() {
  const params = useParams();
  const contributorId = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : "";

  const [data, setData] = useState<GrowthSnapshot | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!contributorId) return;
    setStatus((s) => (s === "ok" ? "ok" : "loading"));
    try {
      const res = await fetch(`${API_URL}/api/contributors/${encodeURIComponent(contributorId)}/growth`, {
        cache: "no-store",
      });
      if (res.status === 404) {
        setStatus("error");
        setError("No contributions found for this contributor.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, [contributorId]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const maxWeekCount =
    data?.weekly_timeline.reduce((m, w) => Math.max(m, w.count), 0) ?? 1;

  const growthSign = data?.growth_pct !== null && data?.growth_pct !== undefined
    ? data.growth_pct >= 0 ? "+" : ""
    : null;

  return (
    <main className="min-h-screen p-6 max-w-4xl mx-auto space-y-6 text-white">
      {/* Nav */}
      <div className="flex flex-wrap gap-3 text-sm text-white/50">
        <Link href="/" className="hover:text-white">← Home</Link>
        <Link href="/contributors" className="hover:text-white">Contributors</Link>
        <Link href="/contributions" className="hover:text-white">Contributions</Link>
        {contributorId && (
          <Link href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`} className="hover:text-white">
            Profile
          </Link>
        )}
      </div>

      {status === "loading" && <p className="text-white/40">Loading growth data…</p>}
      {status === "error" && <p className="text-red-400">Error: {error}</p>}

      {status === "ok" && data && (
        <>
          {/* Header */}
          <div className="space-y-1">
            <h1 className="text-3xl font-bold">{data.display_name}</h1>
            <p className="text-white/50 text-sm">
              Last active: {formatDate(data.last_active_at)}
              {data.current_streak_weeks > 0 && (
                <span className="ml-3 text-green-400 font-medium">
                  🔥 {data.current_streak_weeks}-week streak
                </span>
              )}
            </p>
          </div>

          {/* Level card */}
          <LevelCard level={data.level} total={data.total_contributions} />

          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className="text-2xl font-bold">{data.total_contributions}</div>
              <div className="text-xs text-white/50 mt-1">Total contributions</div>
            </div>
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className="text-2xl font-bold">{data.total_cc.toFixed(1)}</div>
              <div className="text-xs text-white/50 mt-1">CC earned</div>
            </div>
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className="text-2xl font-bold">{data.current_streak_weeks}</div>
              <div className="text-xs text-white/50 mt-1">Week streak</div>
            </div>
            <div className="rounded-lg bg-white/5 p-3 text-center">
              <div className={`text-2xl font-bold ${
                data.growth_pct !== null
                  ? data.growth_pct >= 0 ? "text-green-400" : "text-red-400"
                  : ""
              }`}>
                {data.growth_pct !== null ? `${growthSign}${data.growth_pct}%` : "—"}
              </div>
              <div className="text-xs text-white/50 mt-1">Growth (30d)</div>
            </div>
          </div>

          {/* 30d comparison */}
          <div className="rounded-lg bg-white/5 p-4 space-y-1">
            <div className="text-sm font-medium text-white/70">Activity comparison</div>
            <div className="flex items-end gap-4 text-sm">
              <div>
                <span className="text-2xl font-bold">{data.contributions_last_30d}</span>
                <span className="text-white/50 ml-1">last 30 days</span>
              </div>
              <div className="text-white/30">vs</div>
              <div>
                <span className="text-lg font-medium text-white/60">{data.contributions_prev_30d}</span>
                <span className="text-white/50 ml-1">prior 30 days</span>
              </div>
            </div>
          </div>

          {/* Contribution types */}
          {Object.keys(data.contributions_by_type).length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-medium text-white/60 uppercase tracking-wide">By type</h2>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.contributions_by_type)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, count]) => (
                    <TypeBadge key={type} type={type} count={count} />
                  ))}
              </div>
            </div>
          )}

          {/* 26-week timeline */}
          <div className="space-y-2">
            <h2 className="text-sm font-medium text-white/60 uppercase tracking-wide">
              26-week activity
            </h2>
            <div className="flex items-end gap-1 overflow-x-auto pb-1">
              {data.weekly_timeline.map((week) => (
                <div key={week.week_start} className="flex flex-col items-center gap-1 shrink-0">
                  <GrowthBar value={week.count} max={maxWeekCount} />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-xs text-white/30">
              <span>26 weeks ago</span>
              <span>Today</span>
            </div>
          </div>

          {/* Milestones */}
          {data.milestones.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-medium text-white/60 uppercase tracking-wide">Milestones</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {data.milestones.map((m) => (
                  <div key={m.name} className="rounded-lg bg-white/5 border border-white/10 p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{m.name}</span>
                      <span className="text-xs text-white/40">{m.contribution_count}+</span>
                    </div>
                    <p className="text-xs text-white/50">{m.description}</p>
                    {m.reached_at && (
                      <p className="text-xs text-white/30">{formatDate(m.reached_at)}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Streak info */}
          <div className="rounded-lg bg-white/5 p-4 flex gap-6 text-sm">
            <div>
              <div className="text-lg font-bold text-green-400">{data.current_streak_weeks}w</div>
              <div className="text-white/50 text-xs">Current streak</div>
            </div>
            <div>
              <div className="text-lg font-bold text-white/70">{data.longest_streak_weeks}w</div>
              <div className="text-white/50 text-xs">Longest streak</div>
            </div>
          </div>
        </>
      )}
    </main>
  );
}

export default function ContributorGrowthPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen p-6 max-w-4xl mx-auto text-white">
        <p className="text-white/40">Loading…</p>
      </main>
    }>
      <GrowthPageContent />
    </Suspense>
  );
}
