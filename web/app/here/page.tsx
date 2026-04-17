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

export const dynamic = "force-dynamic";

interface PresenceRow {
  entity_type: string;
  entity_id: string;
  present: number;
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

  const [presenceData, reactionsData, voicesData] = await Promise.all([
    fetchJson<{ total_entities: number; top: PresenceRow[] }>("/api/presence/summary"),
    fetchJson<{ reactions: RecentReaction[] }>("/api/reactions/recent?limit=10"),
    fetchJson<{ voices: RecentVoice[] }>("/api/concepts/voices/recent?limit=10"),
  ]);

  const presenceRows = presenceData?.top || [];
  const recentReactions = (reactionsData?.reactions || []).slice(0, 8);
  const recentVoices = (voicesData?.voices || []).slice(0, 6);

  const quiet =
    presenceRows.length === 0 &&
    recentReactions.length === 0 &&
    recentVoices.length === 0;

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl md:text-3xl font-light text-white mb-1">
            {t("here.heading")}
          </h1>
          <p className="text-sm text-stone-400">{t("here.lede")}</p>
        </div>
        <NotificationBell />
      </header>

      <FeedTabs />

      {quiet ? (
        <section className="rounded-lg border border-stone-800/60 bg-stone-900/40 p-6 text-center">
          <p className="text-stone-300 mb-3">{t("here.empty")}</p>
          <Link
            href="/vision"
            className="inline-block rounded-md bg-amber-700/80 hover:bg-amber-600/90 text-stone-950 px-4 py-2 text-sm font-medium"
          >
            {t("here.emptyCta")}
          </Link>
        </section>
      ) : (
        <div className="space-y-6">
          {presenceRows.length > 0 && (
            <section>
              <h2 className="text-xs uppercase tracking-widest text-teal-300/90 mb-2">
                {t("here.meetingNow")}
              </h2>
              <ul className="space-y-2">
                {presenceRows.map((row) => (
                  <li
                    key={`${row.entity_type}-${row.entity_id}`}
                    className="rounded-lg border border-teal-800/40 bg-teal-950/10"
                  >
                    <Link
                      href={entityHref(row.entity_type, row.entity_id)}
                      className="flex items-center gap-3 p-3 hover:bg-teal-950/30 rounded-lg"
                    >
                      <div className="h-10 w-10 rounded-full bg-teal-500/10 ring-2 ring-teal-400/40 flex items-center justify-center text-sm font-light tabular-nums text-teal-200">
                        {row.present}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-stone-200 truncate">{row.entity_id}</p>
                        <p className="text-xs text-stone-500">
                          {row.entity_type} · {row.present === 1 ? t("here.onePresent") : t("here.manyPresent").replace("{count}", String(row.present))}
                        </p>
                      </div>
                      <span className="text-teal-300">→</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {recentVoices.length > 0 && (
            <section>
              <h2 className="text-xs uppercase tracking-widest text-amber-300/90 mb-2">
                {t("here.recentVoices")}
              </h2>
              <ul className="space-y-2">
                {recentVoices.map((v) => (
                  <li
                    key={v.id}
                    className="rounded-lg border border-amber-800/30 bg-amber-950/10"
                  >
                    <Link
                      href={`/vision/${encodeURIComponent(v.concept_id)}`}
                      className="flex items-start gap-3 p-3 hover:bg-amber-950/30 rounded-lg"
                    >
                      <div className="text-2xl leading-none shrink-0 w-10 text-center">🌱</div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-stone-200 line-clamp-2">{v.body}</p>
                        <p className="text-xs text-stone-500 mt-1 flex flex-wrap gap-x-2">
                          <span className="text-amber-300/90">{v.author_name}</span>
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
              <h2 className="text-xs uppercase tracking-widest text-stone-400 mb-2">
                {t("here.recentReactions")}
              </h2>
              <ul className="space-y-2">
                {recentReactions.map((r) => (
                  <li
                    key={r.id}
                    className="rounded-lg border border-stone-800/50 bg-stone-900/40"
                  >
                    <Link
                      href={entityHref(r.entity_type, r.entity_id)}
                      className="flex items-start gap-3 p-3 hover:bg-stone-900 rounded-lg"
                    >
                      <div className="text-2xl leading-none shrink-0 w-10 text-center">
                        {r.emoji || "💬"}
                      </div>
                      <div className="min-w-0 flex-1">
                        {r.comment ? (
                          <p className="text-sm text-stone-200 line-clamp-2">{r.comment}</p>
                        ) : (
                          <p className="text-sm text-stone-400">
                            {r.entity_type}: {r.entity_id}
                          </p>
                        )}
                        <p className="text-xs text-stone-500 mt-1 flex flex-wrap gap-x-2">
                          <span className="text-amber-300/90">{r.author_name}</span>
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

      <footer className="mt-8 flex items-center justify-between gap-3 text-xs text-stone-500">
        <Link href="/explore/concept" className="hover:text-amber-300/90">
          {t("here.goExplore")}
        </Link>
        <Link href="/propose" className="hover:text-teal-300/90">
          {t("here.goPropose")}
        </Link>
      </footer>
    </main>
  );
}
