import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Resonance",
  description:
    "Ideas actively evolving right now. Find where attention is flowing and join the work.",
};

type ResonanceItem = {
  idea_id: string;
  name: string;
  last_activity_at: string;
  free_energy_score: number;
  manifestation_status: string;
  activity_type?: string;
};

type ActivityEvent = {
  type: string;
  timestamp: string;
  summary: string;
  contributor_id?: string;
};

async function loadResonance(): Promise<ResonanceItem[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/resonance?window_hours=72&limit=30`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.ideas || [];
  } catch {
    return [];
  }
}

async function loadActivity(ideaId: string): Promise<ActivityEvent[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas/${ideaId}/activity?limit=5`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.events || [];
  } catch {
    return [];
  }
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusIcon(status: string): string {
  if (status === "validated") return "\u2705";
  if (status === "partial") return "\uD83D\uDD28";
  return "\uD83D\uDCCB";
}

function activityIcon(type: string): string {
  if (type === "change_request") return "\uD83D\uDCDD";
  if (type === "question_answered") return "\uD83D\uDCA1";
  if (type === "question_added") return "\u2753";
  if (type === "stage_advanced") return "\uD83D\uDE80";
  if (type === "value_recorded") return "\uD83D\uDCCA";
  if (type === "lineage_link") return "\uD83D\uDD17";
  return "\u2022";
}

export default async function ResonancePage() {
  const items = await loadResonance();

  // Load activity for top items
  const itemsWithActivity = await Promise.all(
    items.slice(0, 15).map(async (item) => ({
      ...item,
      activity: await loadActivity(item.idea_id),
    }))
  );

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">
          Resonance
        </h1>
        <p className="mt-2 text-lg text-stone-500 dark:text-stone-400">
          Ideas actively evolving right now. Where attention flows, realization
          follows.
        </p>
      </header>

      {itemsWithActivity.length === 0 ? (
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-8 text-center dark:border-stone-700 dark:bg-stone-800/50">
          <p className="text-stone-500 dark:text-stone-400">
            No recent activity. Ideas are waiting for attention.
          </p>
          <Link
            href="/ideas"
            className="mt-3 inline-block text-amber-600 hover:text-amber-500"
          >
            Browse ideas &rarr;
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {itemsWithActivity.map((item) => (
            <article
              key={item.idea_id}
              className="group rounded-xl border border-stone-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md dark:border-stone-700 dark:bg-stone-800/60"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/ideas/${item.idea_id}`}
                    className="text-lg font-medium text-stone-900 hover:text-amber-600 dark:text-stone-100 dark:hover:text-amber-400"
                  >
                    {statusIcon(item.manifestation_status)} {item.name}
                  </Link>
                  <div className="mt-1 flex items-center gap-3 text-sm text-stone-500 dark:text-stone-400">
                    <span>
                      Energy: {item.free_energy_score?.toFixed(1) || "?"}
                    </span>
                    <span>&middot;</span>
                    <span>
                      Last active: {timeAgo(item.last_activity_at)}
                    </span>
                  </div>
                </div>
                <Link
                  href={`/ideas/${item.idea_id}`}
                  className="shrink-0 rounded-lg bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100 dark:bg-amber-900/30 dark:text-amber-300 dark:hover:bg-amber-900/50"
                >
                  Join
                </Link>
              </div>

              {item.activity && item.activity.length > 0 && (
                <div className="mt-4 space-y-1.5 border-t border-stone-100 pt-3 dark:border-stone-700">
                  {item.activity.slice(0, 3).map((event, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-sm text-stone-600 dark:text-stone-400"
                    >
                      <span className="shrink-0">
                        {activityIcon(event.type)}
                      </span>
                      <span className="flex-1">{event.summary}</span>
                      <span className="shrink-0 text-xs text-stone-400 dark:text-stone-500">
                        {timeAgo(event.timestamp)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      <footer className="mt-12 text-center text-sm text-stone-400 dark:text-stone-500">
        <p>
          This feed shows temporal activity &mdash; what people are working on
          right now. No algorithm, no ranking. Just attention flowing to ideas.
        </p>
        <div className="mt-4 flex justify-center gap-4">
          <Link href="/ideas" className="hover:text-amber-500">
            All ideas
          </Link>
          <Link href="/contribute" className="hover:text-amber-500">
            Contribute
          </Link>
          <Link href="/flow" className="hover:text-amber-500">
            Pipeline
          </Link>
        </div>
      </footer>
    </main>
  );
}
