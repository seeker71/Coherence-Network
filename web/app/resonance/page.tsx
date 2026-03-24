import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { formatUsd } from "@/lib/humanize";

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

type FallbackIdea = {
  id: string;
  name: string;
  manifestation_status: string;
  value_gap: number;
  free_energy_score: number;
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

async function loadFallbackIdeas(): Promise<FallbackIdea[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/ideas?limit=60`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    const ideas: FallbackIdea[] = data.ideas ?? [];
    return [...ideas]
      .sort((a, b) => (b.free_energy_score ?? 0) - (a.free_energy_score ?? 0))
      .slice(0, 5);
  } catch {
    return [];
  }
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
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Resonance
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          This is the heartbeat of the network. Every question asked, every spec
          written, every contribution — it shows up here.
        </p>
      </header>

      {itemsWithActivity.length === 0 ? (
        <FallbackIdeasSection />
      ) : (
        <div className="space-y-4">
          {itemsWithActivity.map((item, idx) => (
            <article
              key={item.idea_id}
              className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 animate-fade-in-up"
              style={{ animationDelay: `${idx * 0.05}s` }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/ideas/${item.idea_id}`}
                    className="text-lg font-medium hover:text-primary transition-colors duration-300"
                  >
                    {statusIcon(item.manifestation_status)} {item.name}
                  </Link>
                  <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                    <span>
                      Energy: {item.free_energy_score?.toFixed(1) || "?"}
                    </span>
                    <span>&middot;</span>
                    <span>
                      {timeAgo(item.last_activity_at)}
                    </span>
                  </div>
                </div>
                <Link
                  href={`/ideas/${item.idea_id}`}
                  className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                >
                  Join
                </Link>
              </div>

              {item.activity && item.activity.length > 0 && (
                <div className="mt-4 space-y-1.5 border-t border-border/20 pt-3">
                  {item.activity.slice(0, 3).map((event, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <span className="shrink-0">
                        {activityIcon(event.type)}
                      </span>
                      <span className="flex-1">{event.summary}</span>
                      <span className="shrink-0 text-xs text-muted-foreground/80">
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

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label="Where to go next">
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">Where to go next</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">All ideas</Link>
          <Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">Contribute</Link>
          <Link href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">Invest</Link>
        </div>
      </nav>
    </main>
  );
}

async function FallbackIdeasSection() {
  const ideas = await loadFallbackIdeas();

  if (ideas.length === 0) {
    return (
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center">
        <p className="text-muted-foreground mb-3">
          The network is quiet right now. Be the first to share an idea.
        </p>
        <Link
          href="/"
          className="text-primary hover:text-foreground transition-colors underline underline-offset-4"
        >
          Share an idea &rarr;
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground text-center">
        No recent resonance activity. Here are the most active ideas:
      </p>
      {ideas.map((idea, idx) => (
        <article
          key={idea.id}
          className="hover-lift rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 animate-fade-in-up"
          style={{ animationDelay: `${idx * 0.05}s` }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <Link
                href={`/ideas/${encodeURIComponent(idea.id)}`}
                className="text-lg font-medium text-foreground hover:text-primary transition-colors duration-300"
              >
                {statusIcon(idea.manifestation_status)} {idea.name}
              </Link>
              <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                <span>Value gap: {formatUsd(idea.value_gap)}</span>
                <span>&middot;</span>
                <span>{idea.manifestation_status}</span>
              </div>
            </div>
            <Link
              href={`/ideas/${encodeURIComponent(idea.id)}`}
              className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
            >
              Learn more
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
