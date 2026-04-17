import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { cookies, headers } from "next/headers";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";

/**
 * /feed — the felt pulse of the collective.
 *
 * One scroll that answers: what is alive on the network right now?
 * Recent reactions, new voices on concepts, freshly shared ideas.
 * Mobile-first: thumb-sized tap targets, no fixed chrome, timestamps
 * that hint relative time. This is the place that should feel familiar
 * to anyone coming from a social feed — but every item invites the
 * reader deeper, not toward outrage or comparison.
 */

export const dynamic = "force-dynamic";

interface Reaction {
  id: string;
  entity_type: string;
  entity_id: string;
  author_name: string;
  emoji: string | null;
  comment: string | null;
  locale: string;
  created_at: string | null;
}

interface Voice {
  id: string;
  concept_id: string;
  author_name: string;
  locale: string;
  body: string;
  location: string | null;
  created_at: string | null;
}

interface FeedItem {
  kind: "reaction" | "voice";
  key: string;
  ts: number;
  node: React.ReactNode;
}

async function fetchReactions(): Promise<Reaction[]> {
  try {
    const base = getApiBase();
    const res = await fetch(`${base}/api/reactions/recent?limit=30`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.reactions || [];
  } catch {
    return [];
  }
}

async function fetchVoices(): Promise<Voice[]> {
  try {
    const base = getApiBase();
    const res = await fetch(`${base}/api/concepts/voices/recent?limit=30`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.voices || [];
  } catch {
    return [];
  }
}

function parseTs(iso: string | null): number {
  if (!iso) return 0;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? 0 : t;
}

function relativeTime(iso: string | null, lang: LocaleCode): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const delta = Math.max(0, Date.now() - t);
  const minutes = Math.round(delta / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d`;
  // Fallback to short date
  return new Date(t).toLocaleDateString(lang);
}

function entityHref(entity_type: string, entity_id: string): string {
  switch (entity_type) {
    case "concept":
      return `/vision/${entity_id}`;
    case "idea":
      return `/ideas/${entity_id}`;
    case "spec":
      return `/specs/${entity_id}`;
    case "contributor":
      return `/contributors/${entity_id}/portfolio`;
    case "community":
      return `/vision/aligned/${entity_id}`;
    default:
      return `/concepts/${entity_id}`;
  }
}

export default async function FeedPage() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const [reactions, voices] = await Promise.all([fetchReactions(), fetchVoices()]);

  const items: FeedItem[] = [];

  for (const r of reactions) {
    const ts = parseTs(r.created_at);
    const href = entityHref(r.entity_type, r.entity_id);
    const meetHref = `/meet/${r.entity_type}/${encodeURIComponent(r.entity_id)}`;
    items.push({
      kind: "reaction",
      key: `r-${r.id}`,
      ts,
      node: (
        <article
          key={`r-${r.id}`}
          className="flex items-start gap-3 rounded-lg border border-stone-800/50 bg-stone-900/40 p-4"
        >
          <div className="text-2xl leading-none shrink-0 w-10 text-center">
            {r.emoji || "💬"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs text-stone-500 mb-1">
              <span className="text-amber-300/90 font-medium">{r.author_name}</span>
              <span>·</span>
              <Link href={href} className="text-stone-400 hover:text-amber-300/90">
                {r.entity_type}: {r.entity_id}
              </Link>
              <Link href={meetHref} className="ml-1 text-teal-400 hover:text-teal-300" aria-label="full screen">
                ↗
              </Link>
              <span className="ml-auto">{relativeTime(r.created_at, lang)}</span>
            </div>
            {r.comment && (
              <p className="text-stone-200 leading-relaxed break-words">{r.comment}</p>
            )}
          </div>
        </article>
      ),
    });
  }

  for (const v of voices) {
    const ts = parseTs(v.created_at);
    items.push({
      kind: "voice",
      key: `v-${v.id}`,
      ts,
      node: (
        <article
          key={`v-${v.id}`}
          className="flex items-start gap-3 rounded-lg border border-amber-800/30 bg-amber-950/10 p-4"
        >
          <div className="text-2xl leading-none shrink-0 w-10 text-center">🌱</div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-xs text-stone-500 mb-2">
              <span className="text-amber-300/90 font-medium">{v.author_name}</span>
              {v.location && <span>· {v.location}</span>}
              <span>·</span>
              <Link
                href={`/vision/${v.concept_id}`}
                className="text-stone-400 hover:text-amber-300/90"
              >
                {v.concept_id}
              </Link>
              <span className="ml-auto">{relativeTime(v.created_at, lang)}</span>
            </div>
            <p className="text-stone-200 leading-relaxed whitespace-pre-wrap break-words">
              {v.body}
            </p>
          </div>
        </article>
      ),
    });
  }

  items.sort((a, b) => b.ts - a.ts);

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-6">
        <h1 className="text-2xl md:text-3xl font-light text-white mb-1">
          {t("feed.heading")}
        </h1>
        <p className="text-sm text-stone-400">{t("feed.lede")}</p>
      </header>

      {items.length === 0 ? (
        <div className="rounded-lg border border-stone-800/50 bg-stone-900/40 p-6 text-center">
          <p className="text-sm text-stone-400 mb-3">{t("feed.empty")}</p>
          <Link
            href="/vision"
            className="inline-block rounded-md bg-amber-700/80 hover:bg-amber-600/90 text-stone-950 px-4 py-2 text-sm font-medium"
          >
            {t("feed.exploreVision")}
          </Link>
        </div>
      ) : (
        <div className="space-y-3">{items.map((i) => i.node)}</div>
      )}

      <footer className="mt-8 flex items-center justify-between text-xs text-stone-500">
        <Link href="/vision" className="hover:text-amber-300/90">
          {t("feed.exploreVision")}
        </Link>
        <Link href="/join" className="hover:text-teal-300/90">
          {t("feed.stepIn")}
        </Link>
      </footer>
    </main>
  );
}
