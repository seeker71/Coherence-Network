import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "News",
  description:
    "News feed with resonance matching. See how current events connect to ideas in the network.",
};

type NewsItem = {
  title: string;
  description: string;
  url: string;
  published_at: string | null;
  source: string;
};

type NewsFeedResponse = {
  count: number;
  items: NewsItem[];
};

type ResonanceMatch = {
  news_item: NewsItem;
  idea_id: string;
  idea_name: string;
  resonance_score: number;
  matched_keywords: string[];
  phrase_matches: string[];
  reason: string;
};

type IdeaResonanceResult = {
  idea_id: string;
  idea_name: string;
  matches: ResonanceMatch[];
};

type ResonanceResponse = {
  news_count: number;
  idea_count: number;
  results: IdeaResonanceResult[];
};

function formatDate(iso: string | null): string {
  if (!iso) return "Unknown date";
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

async function loadNewsFeed(): Promise<NewsItem[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/news/feed?limit=30`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as NewsFeedResponse;
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

async function loadResonance(): Promise<IdeaResonanceResult[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/news/resonance?top_n=5`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as ResonanceResponse;
    return Array.isArray(data.results) ? data.results : [];
  } catch {
    return [];
  }
}

export default async function NewsPage() {
  const [newsItems, resonanceResults] = await Promise.all([
    loadNewsFeed(),
    loadResonance(),
  ]);

  // Flatten resonance matches for display
  const topMatches: ResonanceMatch[] = resonanceResults
    .flatMap((r) => r.matches)
    .sort((a, b) => b.resonance_score - a.resonance_score)
    .slice(0, 10);

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">News Feed</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          Real-time news from configured sources, with resonance matching to
          ideas in the network. See which current events connect to what we are
          building.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/discover"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Discover
          </Link>
        </div>
      </header>

      {/* Resonance highlights */}
      {topMatches.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-lg font-medium">Resonance Highlights</h2>
          <p className="text-sm text-muted-foreground">
            News items that resonate most strongly with ideas in the network.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {topMatches.map((match, idx) => (
              <article
                key={`${match.idea_id}-${match.news_item.title}-${idx}`}
                className="rounded-2xl border border-amber-500/20 bg-gradient-to-b from-amber-500/5 to-card/30 p-5 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400">
                        {(match.resonance_score * 100).toFixed(0)}% match
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {match.news_item.source}
                      </span>
                    </div>
                    <h3 className="text-sm font-medium leading-snug">
                      {match.news_item.url ? (
                        <a
                          href={match.news_item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-amber-400 transition-colors"
                        >
                          {match.news_item.title}
                        </a>
                      ) : (
                        match.news_item.title
                      )}
                    </h3>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground italic">
                  Resonates with{" "}
                  <Link
                    href={`/ideas/${encodeURIComponent(match.idea_id)}`}
                    className="text-amber-400 hover:underline"
                  >
                    {match.idea_name}
                  </Link>
                  {" -- "}{match.reason}
                </p>

                {match.matched_keywords.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {match.matched_keywords.slice(0, 6).map((kw) => (
                      <span
                        key={kw}
                        className="rounded-full border border-amber-500/20 bg-amber-500/5 px-2 py-0.5 text-xs text-amber-300"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {/* News feed */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Latest News</h2>
          <span className="text-xs text-muted-foreground">
            {newsItems.length} items
          </span>
        </div>

        {newsItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No news items available. Configure RSS sources or check back later.
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {newsItems.map((item, idx) => (
              <li
                key={`${item.title}-${idx}`}
                className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
                    {item.source}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDate(item.published_at)}
                  </span>
                </div>
                <h3 className="font-medium">
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-400 transition-colors"
                    >
                      {item.title}
                    </a>
                  ) : (
                    item.title
                  )}
                </h3>
                {item.description ? (
                  <p className="text-muted-foreground line-clamp-2">
                    {item.description}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/discover" className="text-purple-400 hover:underline">
            Discover
          </Link>
          <Link href="/ideas" className="text-blue-400 hover:underline">
            Ideas
          </Link>
          <Link href="/resonance" className="text-emerald-400 hover:underline">
            Resonance
          </Link>
        </div>
      </nav>
    </main>
  );
}
