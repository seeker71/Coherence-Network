import Link from "next/link";
import { cookies, headers } from "next/headers";

import { getApiBase } from "@/lib/api";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { FeedTabs } from "@/components/FeedTabs";
import { NotificationBell } from "@/components/NotificationBell";

/**
 * /here — a map of the organism's current attention.
 *
 * Three signals rendered as one quiet page:
 *   · presence — entities viewers are meeting in the last 90s
 *   · recent voices — concepts where someone just offered lived testimony
 *   · recent reactions — entities that just received a gesture of care
 *
 * Each item is a link to the meeting surface. The page answers "where
 * is the organism's attention right now" for anyone who lands fresh.
 */

import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Here now — Coherence Network",
  description: "Where the organism's attention is right now — who is meeting what, and what was just voiced.",
  openGraph: {
    type: "website",
    siteName: "Coherence Network",
    title: "Here now",
    description: "Where the organism's attention is right now.",
    images: [{ url: "/assets/logo.svg" }],
  },
  twitter: {
    card: "summary",
    title: "Here now — Coherence Network",
    description: "Where the organism's attention is right now.",
  },
};

interface PresenceRow {
  entity_type: string;
  entity_id: string;
  present: number;
}

interface WaitingConcept {
  id: string;
  name: string;
  description: string;
  visual_path?: string | null;
}

interface RecentReaction {
  id: string;
  entity_type: string;
  entity_id: string;
  author_name: string;
  emoji: string | null;
  comment: string | null;
  locale: string;
  created_at: string | null;
}

interface RecentVoice {
  id: string;
  concept_id: string;
  author_name: string;
  body: string;
  locale: string;
  location: string | null;
  created_at: string | null;
}

function entityHref(entity_type: string, entity_id: string): string {
  return `/meet/${entity_type}/${encodeURIComponent(entity_id)}`;
}

function relativeTime(iso: string | null, lang: LocaleCode): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const delta = Math.max(0, Date.now() - t);
  const m = Math.round(delta / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d`;
  return new Date(t).toLocaleDateString(lang);
}

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${getApiBase()}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export default async function HerePage() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const [presenceData, reactionsData, voicesData, waitingData] = await Promise.all([
    fetchJson<{ total_entities: number; top: PresenceRow[] }>("/api/presence/summary"),
    fetchJson<{ reactions: RecentReaction[] }>("/api/reactions/recent?limit=10"),
    fetchJson<{ voices: RecentVoice[] }>("/api/concepts/voices/recent?limit=10"),
    // Grab a generous set so we can shuffle and surface a variable feel
    fetchJson<{ items: WaitingConcept[] }>(
      "/api/concepts/domain/living-collective?limit=30",
    ),
  ]);

  const presenceRows = presenceData?.top || [];
  const recentReactions = (reactionsData?.reactions || []).slice(0, 8);
  const recentVoices = (voicesData?.voices || []).slice(0, 6);

  // Shuffle the waiting pool so each visit feels fresh; pick 3 concepts that
  // don't already appear in presence/voices (they are truly "waiting").
  const presentIds = new Set(
    presenceRows.filter((r) => r.entity_type === "concept").map((r) => r.entity_id),
  );
  const voicedIds = new Set(recentVoices.map((v) => v.concept_id));
  const waitingPool = (waitingData?.items || [])
    .filter((c) => c.id && !presentIds.has(c.id) && !voicedIds.has(c.id));
  const waiting: WaitingConcept[] = waitingPool
    .map((c) => ({ c, r: Math.random() }))
    .sort((a, b) => a.r - b.r)
    .slice(0, 3)
    .map((p) => p.c);

  const quiet =
    presenceRows.length === 0 &&
    recentReactions.length === 0 &&
    recentVoices.length === 0;

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl md:text-3xl font-light text-foreground mb-1">
            {t("here.heading")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("here.lede")}</p>
        </div>
        <NotificationBell />
      </header>

      <FeedTabs />

      {quiet ? (
        <section className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-6 text-center">
            <p className="text-foreground mb-3">{t("here.empty")}</p>
          </div>
          {waiting.length > 0 && (
            <div>
              <h2 className="text-xs uppercase tracking-widest text-[hsl(var(--primary))] mb-2">
                {t("here.waitingHeading")}
              </h2>
              <p className="text-sm text-muted-foreground mb-3">
                {t("here.waitingLede")}
              </p>
              <ul className="space-y-2">
                {waiting.map((c) => (
                  <li
                    key={c.id}
                    className="rounded-lg border border-[hsl(var(--primary)/0.3)] bg-[hsl(var(--primary)/0.05)]"
                  >
                    <Link
                      href={`/meet/concept/${encodeURIComponent(c.id)}`}
                      className="flex items-start gap-3 p-3 hover:bg-[hsl(var(--primary)/0.1)] rounded-lg"
                    >
                      <div className="text-2xl leading-none shrink-0 w-10 text-center">
                        🌱
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-foreground font-medium">{c.name}</p>
                        <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                          {c.description}
                        </p>
                      </div>
                      <span className="text-[hsl(var(--primary))] self-center">→</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="text-center pt-2">
            <Link
              href="/vision"
              className="inline-block rounded-md bg-[hsl(var(--primary))] hover:opacity-90 text-[hsl(var(--primary-foreground))] px-4 py-2 text-sm font-medium"
            >
              {t("here.walkAll")}
            </Link>
          </div>
        </section>
      ) : (
        <div className="space-y-6">
          {presenceRows.length > 0 && (
            <section>
              <h2 className="text-xs uppercase tracking-widest text-[hsl(var(--chart-2))] mb-2">
                {t("here.meetingNow")}
              </h2>
              <ul className="space-y-2">
                {presenceRows.map((row) => (
                  <li
                    key={`${row.entity_type}-${row.entity_id}`}
                    className="rounded-lg border border-[hsl(var(--chart-2)/0.3)] bg-[hsl(var(--chart-2)/0.05)]"
                  >
                    <Link
                      href={entityHref(row.entity_type, row.entity_id)}
                      className="flex items-center gap-3 p-3 hover:bg-[hsl(var(--chart-2)/0.1)] rounded-lg"
                    >
                      <div className="h-10 w-10 rounded-full bg-[hsl(var(--chart-2)/0.15)] ring-2 ring-[hsl(var(--chart-2)/0.4)] flex items-center justify-center text-sm font-light tabular-nums text-[hsl(var(--chart-2))]">
                        {row.present}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-foreground truncate">{row.entity_id}</p>
                        <p className="text-xs text-muted-foreground">
                          {row.entity_type} · {row.present === 1 ? t("here.onePresent") : t("here.manyPresent").replace("{count}", String(row.present))}
                        </p>
                      </div>
                      <span className="text-[hsl(var(--chart-2))]">→</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {recentVoices.length > 0 && (
            <section>
              <h2 className="text-xs uppercase tracking-widest text-[hsl(var(--primary))] mb-2">
                {t("here.recentVoices")}
              </h2>
              <ul className="space-y-2">
                {recentVoices.map((v) => (
                  <li
                    key={v.id}
                    className="rounded-lg border border-[hsl(var(--primary)/0.3)] bg-[hsl(var(--primary)/0.05)]"
                  >
                    <Link
                      href={`/vision/${encodeURIComponent(v.concept_id)}`}
                      className="flex items-start gap-3 p-3 hover:bg-[hsl(var(--primary)/0.1)] rounded-lg"
                    >
                      <div className="text-2xl leading-none shrink-0 w-10 text-center">🌱</div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-foreground line-clamp-2">{v.body}</p>
                        <p className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-x-2">
                          <span className="text-[hsl(var(--primary))]">{v.author_name}</span>
                          {v.location && <span>· {v.location}</span>}
                          <span>· {v.concept_id}</span>
                          <span className="ml-auto">{relativeTime(v.created_at, lang)}</span>
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {recentReactions.length > 0 && (
            <section>
              <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
                {t("here.recentReactions")}
              </h2>
              <ul className="space-y-2">
                {recentReactions.map((r) => (
                  <li
                    key={r.id}
                    className="rounded-lg border border-border bg-card"
                  >
                    <Link
                      href={entityHref(r.entity_type, r.entity_id)}
                      className="flex items-start gap-3 p-3 hover:bg-muted rounded-lg"
                    >
                      <div className="text-2xl leading-none shrink-0 w-10 text-center">
                        {r.emoji || "💬"}
                      </div>
                      <div className="min-w-0 flex-1">
                        {r.comment ? (
                          <p className="text-sm text-foreground line-clamp-2">{r.comment}</p>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            {r.entity_type}: {r.entity_id}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-x-2">
                          <span className="text-[hsl(var(--primary))]">{r.author_name}</span>
                          <span>· {r.entity_type}: {r.entity_id}</span>
                          <span className="ml-auto">{relativeTime(r.created_at, lang)}</span>
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      <footer className="mt-8 flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <Link href="/vision" className="hover:text-[hsl(var(--primary))]">
          {t("here.goExplore")}
        </Link>
        <Link href="/propose" className="hover:text-[hsl(var(--chart-2))]">
          {t("here.goPropose")}
        </Link>
      </footer>
    </main>
  );
}
