"use client";

import { Suspense, useCallback, useState } from "react";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

type FeedItem = {
  id: string;
  contributor_id: string;
  display_name: string;
  type: string;
  amount_cc: number;
  idea_id: string | null;
  recorded_at: string | null;
  metadata: Record<string, unknown>;
};

type FeedResponse = {
  items: FeedItem[];
  total: number;
  limit: number;
  offset: number;
};

const TYPE_ICONS: Record<string, string> = {
  code: "⚙️",
  spec: "📐",
  question: "❓",
  review: "🔍",
  share: "📣",
  research: "🔬",
  design: "🎨",
  testing: "🧪",
  documentation: "📝",
  mentoring: "🌱",
  feedback: "💬",
  direction: "🧭",
  compute: "💻",
  infrastructure: "🏗️",
  attention: "👁️",
  stake: "💎",
  deposit: "📥",
  promotion: "📢",
};

const TYPE_COLORS: Record<string, string> = {
  code: "text-blue-400",
  spec: "text-purple-400",
  question: "text-yellow-400",
  review: "text-green-400",
  share: "text-pink-400",
  research: "text-indigo-400",
  design: "text-orange-400",
  testing: "text-teal-400",
  documentation: "text-cyan-400",
  mentoring: "text-rose-400",
  feedback: "text-amber-400",
  direction: "text-violet-400",
};

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "unknown time";
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso ?? "";
  }
}

function FeedCard({ item }: { item: FeedItem }) {
  const icon = TYPE_ICONS[item.type] ?? "✦";
  const color = TYPE_COLORS[item.type] ?? "text-gray-400";
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-4 space-y-2 hover:bg-white/8 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <div>
            <Link
              href={`/contributors/${encodeURIComponent(item.contributor_id)}/growth`}
              className="font-medium hover:underline text-white"
            >
              {item.display_name}
            </Link>
            <span className="text-white/40 mx-1">·</span>
            <span className={`text-sm font-medium ${color}`}>{item.type}</span>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-medium text-white/70">
            {item.amount_cc > 0 ? `CC ${item.amount_cc.toFixed(2)}` : ""}
          </div>
          <div className="text-xs text-white/30">{formatRelative(item.recorded_at)}</div>
        </div>
      </div>
      {item.idea_id && (
        <div className="text-xs text-white/40">
          Idea:{" "}
          <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="underline hover:text-white/70">
            {item.idea_id.slice(0, 12)}…
          </Link>
        </div>
      )}
    </div>
  );
}

function FeedPageContent() {
  const [data, setData] = useState<FeedResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setStatus((s) => (s === "ok" ? "ok" : "loading"));
    try {
      const res = await fetch(`${API_URL}/api/contributions/feed?limit=60`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(load);

  return (
    <main className="min-h-screen p-6 max-w-3xl mx-auto text-white space-y-6">
      {/* Nav */}
      <div className="flex flex-wrap gap-3 text-sm text-white/50">
        <Link href="/" className="hover:text-white">← Home</Link>
        <Link href="/contributions" className="hover:text-white">Contributions</Link>
        <Link href="/contributors" className="hover:text-white">Contributors</Link>
      </div>

      <div className="space-y-1">
        <h1 className="text-2xl font-bold">Community Feed</h1>
        <p className="text-white/50 text-sm">
          Every contribution — a question, a spec, a review, a share — visible as it happens.
        </p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(TYPE_ICONS)
          .slice(0, 10)
          .map(([type, icon]) => (
            <span
              key={type}
              className={`text-xs px-2 py-0.5 rounded-full border border-white/10 ${TYPE_COLORS[type] ?? "text-white/50"}`}
            >
              {icon} {type}
            </span>
          ))}
      </div>

      {status === "loading" && <p className="text-white/40">Loading feed…</p>}
      {status === "error" && <p className="text-red-400">Error: {error}</p>}

      {status === "ok" && data && (
        <div className="space-y-3">
          <p className="text-xs text-white/30">{data.total} contributions recorded</p>
          {data.items.length === 0 ? (
            <div className="rounded-lg bg-white/5 p-6 text-center text-white/40">
              No contributions yet. Be the first to contribute.
            </div>
          ) : (
            data.items.map((item) => <FeedCard key={item.id} item={item} />)
          )}
        </div>
      )}
    </main>
  );
}

export default function CommunityFeedPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen p-6 max-w-3xl mx-auto text-white">
        <p className="text-white/40">Loading…</p>
      </main>
    }>
      <FeedPageContent />
    </Suspense>
  );
}
