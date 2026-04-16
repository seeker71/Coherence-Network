import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import { formatUsd } from "@/lib/humanize";
import { createTranslator, type Translator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

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

type NewsItem = {
  title: string;
  description: string;
  url: string;
  published_at: string | null;
  source: string;
};

async function loadResonance(lang: LocaleCode): Promise<ResonanceItem[]> {
  try {
    const API = getApiBase();
    const langParam = lang === DEFAULT_LOCALE ? "" : `&lang=${lang}`;
    const res = await fetch(`${API}/api/ideas/resonance?window_hours=72&limit=30${langParam}`, {
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

function timeAgo(iso: string, t: Translator): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return t("time.justNow");
  if (minutes < 60) return t("time.minutesAgo", { n: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("time.hoursAgo", { n: hours });
  const days = Math.floor(hours / 24);
  return t("time.daysAgo", { n: days });
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

async function loadNewsFeed(): Promise<NewsItem[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/news/feed?limit=10`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

async function loadFallbackIdeas(lang: LocaleCode): Promise<FallbackIdea[]> {
  try {
    const API = getApiBase();
    const langParam = lang === DEFAULT_LOCALE ? "" : `&lang=${lang}`;
    const res = await fetch(`${API}/api/ideas?limit=60${langParam}`, { cache: "no-store" });
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
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const [items, newsItems] = await Promise.all([
    loadResonance(lang),
    loadNewsFeed(),
  ]);

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
          {t("resonance.title")}
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t("resonance.lede")}
        </p>
      </header>

      {itemsWithActivity.length === 0 ? (
        <FallbackIdeasSection lang={lang} t={t} />
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
                      {t("resonance.energy")}: {item.free_energy_score?.toFixed(1) || "?"}
                    </span>
                    <span>&middot;</span>
                    <span>
                      {timeAgo(item.last_activity_at, t)}
                    </span>
                  </div>
                </div>
                <Link
                  href={`/ideas/${item.idea_id}`}
                  className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                >
                  {t("resonance.join")}
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
                        {timeAgo(event.timestamp, t)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {/* News Feed */}
      {newsItems.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold text-foreground">{t("resonance.newsFeed")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("resonance.newsFeedLede")}
          </p>
          <div className="space-y-3">
            {newsItems.map((news, idx) => (
              <article
                key={`${news.url}-${idx}`}
                className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 animate-fade-in-up"
                style={{ animationDelay: `${idx * 0.04}s` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <a
                      href={news.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-base font-medium text-foreground hover:text-primary transition-colors duration-300"
                    >
                      {news.title}
                    </a>
                    <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="font-medium">{news.source}</span>
                      {news.published_at && (
                        <>
                          <span>&middot;</span>
                          <span>{timeAgo(news.published_at, t)}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* Where to go next */}
      <nav className="py-8 text-center space-y-2 border-t border-border/20" aria-label={t("ideas.whereNext")}>
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">{t("ideas.whereNext")}</p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/ideas" className="text-amber-600 dark:text-amber-400 hover:underline">{t("nav.ideas")}</Link>
          <Link href="/contribute" className="text-amber-600 dark:text-amber-400 hover:underline">{t("nav.contribute")}</Link>
          <Link href="/invest" className="text-amber-600 dark:text-amber-400 hover:underline">{t("nav.invest")}</Link>
        </div>
      </nav>
    </main>
  );
}

async function FallbackIdeasSection({ lang, t }: { lang: LocaleCode; t: Translator }) {
  const ideas = await loadFallbackIdeas(lang);

  if (ideas.length === 0) {
    return (
      <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 text-center">
        <p className="text-muted-foreground mb-3">
          {t("resonance.quiet")}
        </p>
        <Link
          href="/"
          className="text-primary hover:text-foreground transition-colors underline underline-offset-4"
        >
          {t("ideas.shareArrow")}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground text-center">
        {t("resonance.noRecent")}
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
                <span>{t("resonance.growthPotential", { amount: formatUsd(idea.value_gap) })}</span>
                <span>&middot;</span>
                <span>{idea.manifestation_status}</span>
              </div>
            </div>
            <Link
              href={`/ideas/${encodeURIComponent(idea.id)}`}
              className="shrink-0 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
            >
              {t("common.learnMore")}
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
