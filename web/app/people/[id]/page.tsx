import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cookies, headers } from "next/headers";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { Panel, VoiceQuote } from "@/components/Panel";

/**
 * /people/[id] — a warm public garden view of a contributor.
 *
 * When a reader encounters Mama's voice on a concept and wants to know
 * "who is this", this is where they land. The page honors her:
 *
 *   · a generous greeting with her name
 *   · the voices she has given, each quoted and attributed to the
 *     concept where she offered it
 *   · the warmth that has come back to her — reactions that others
 *     laid on her voices, gathered here as a felt register
 *   · a quiet doorway forward ("meet her here →")
 *
 * This is the companion to /profile/[contributorId], which stays the
 * deeper technical view (public-key fingerprint, frequency profile,
 * assets). /people speaks to the community; /profile speaks to
 * contributors who want the data.
 */

export const dynamic = "force-dynamic";

type ContributorNode = {
  id?: string;
  name?: string;
  properties?: Record<string, unknown>;
  [key: string]: unknown;
};

type FeedItem = {
  entity_type: string;
  entity_id: string;
  kind: string;
  title: string;
  snippet: string;
  actor_name: string | null;
  reason: string;
  reason_label: string;
  created_at: string | null;
};

type FeedResponse = {
  items: FeedItem[];
  count: number;
  locale: string;
};

async function fetchContributor(id: string): Promise<ContributorNode | null> {
  const base = getApiBase();
  return fetchJsonOrNull<ContributorNode>(
    `${base}/api/contributors/${encodeURIComponent(id)}`,
    {},
    5000,
  );
}

async function fetchFeed(id: string, lang: LocaleCode): Promise<FeedResponse | null> {
  const base = getApiBase();
  return fetchJsonOrNull<FeedResponse>(
    `${base}/api/feed/personal?contributor_id=${encodeURIComponent(id)}&limit=40&lang=${lang}`,
    {},
    5000,
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  // Best-effort: show a human-ish title. We don't fetch here to keep
  // the metadata path cheap.
  const display = id.replace(/-[a-z0-9]{6,}$/, "").replace(/-/g, " ");
  return {
    title: `${display} — Coherence Network`,
    description: `A corner of the organism held by ${display}.`,
  };
}

function initialFromName(name: string): string {
  const first = (name || "").trim().charAt(0);
  return first ? first.toUpperCase() : "·";
}

function displayName(
  node: ContributorNode | null,
  voiceAuthorName: string | null,
  fallback: string,
): string {
  // The voice's author_name is the real human name (e.g. "TestSoul",
  // "Mama") that the person typed when they spoke their first voice.
  // That's the warmest display option. Fall back to the contributor
  // node's slug name (with the fingerprint suffix trimmed) or the
  // raw id only when no voice author_name is available.
  if (voiceAuthorName && voiceAuthorName.trim()) return voiceAuthorName.trim();
  const raw = (node?.name as string) || fallback;
  return raw.replace(/-[a-z0-9]{6,}$/, "");
}

function groupByConcept(items: FeedItem[]): Map<string, FeedItem[]> {
  const map = new Map<string, FeedItem[]>();
  for (const it of items) {
    const key = it.entity_id;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }
  return map;
}

export default async function PersonPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const cookieLang = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  const lang: LocaleCode = isSupportedLocale(cookieLang)
    ? cookieLang
    : isSupportedLocale(headerLang)
    ? headerLang
    : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const [contributor, feed] = await Promise.all([
    fetchContributor(id),
    fetchFeed(id, lang),
  ]);

  const items = feed?.items || [];
  const voices = items.filter((it) => it.reason === "i_voiced");
  const warmth = items.filter(
    (it) =>
      it.reason === "reaction_on_my_voice" ||
      it.reason === "replied_to_me",
  );

  // If we know nothing about this contributor — no node, no voices,
  // no reactions — render a gentle not-found rather than a scary 404.
  if (!contributor && items.length === 0) {
    notFound();
  }

  // Prefer the author_name from one of her own voices (real human name
  // like "TestSoul") over the contributor-node slug (like
  // "testsoul-test-fp-cycle-o").
  const voiceAuthorName =
    voices.find((v) => v.actor_name)?.actor_name ||
    items.find((i) => i.reason === "i_voiced" && i.actor_name)?.actor_name ||
    null;
  const name = displayName(contributor, voiceAuthorName, id);
  const initial = initialFromName(name);

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-10 space-y-6">
      {/* Greeting */}
      <Panel variant="warm" className="flex items-start gap-4">
        <div
          className="shrink-0 w-14 h-14 rounded-full flex items-center justify-center text-2xl font-light bg-[hsl(var(--primary)/0.2)] text-[hsl(var(--primary))] border border-[hsl(var(--primary)/0.3)]"
          aria-hidden="true"
        >
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
            {t("people.eyebrow")}
          </p>
          <h1 className="text-2xl md:text-3xl font-light tracking-tight text-foreground">
            {name}
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            {t("people.tagline")
              .replace("{voices}", String(voices.length))
              .replace("{warmth}", String(warmth.length))}
          </p>
        </div>
      </Panel>

      {/* Voices she's given — her garden */}
      {voices.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] px-1">
            {t("people.voicesHeading")}
          </h2>
          <ul className="space-y-3">
            {voices.map((v, i) => (
              <li key={`${v.entity_id}-${v.created_at}-${i}`}>
                <Panel variant="neutral">
                  <VoiceQuote
                    attribution={
                      <Link
                        href={`/vision/${encodeURIComponent(v.entity_id)}`}
                        className="text-[hsl(var(--chart-2))] hover:opacity-80 underline-offset-4 hover:underline"
                      >
                        {v.entity_id.replace(/^lc-/, "")} ·{" "}
                        {v.created_at
                          ? new Date(v.created_at).toLocaleDateString(lang)
                          : ""}
                      </Link>
                    }
                  >
                    {v.snippet}
                  </VoiceQuote>
                </Panel>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Warmth received */}
      {warmth.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm uppercase tracking-[0.18em] font-semibold text-[hsl(var(--chart-2))] px-1">
            {t("people.warmthHeading")}
          </h2>
          <Panel variant="cool">
            <ul className="space-y-2">
              {warmth.map((w, i) => {
                const emoji =
                  w.snippet && w.snippet.length <= 6 ? w.snippet : null;
                return (
                  <li
                    key={`${w.entity_id}-${w.created_at}-${i}`}
                    className="flex items-start gap-2"
                  >
                    {emoji ? (
                      <span className="text-lg leading-none mt-0.5" aria-hidden="true">
                        {emoji}
                      </span>
                    ) : null}
                    <span className="text-sm text-foreground/90">
                      <span className="font-medium">
                        {w.actor_name || t("people.someone")}
                      </span>{" "}
                      <span className="text-muted-foreground">
                        {w.reason === "replied_to_me"
                          ? t("people.replied")
                          : t("people.reacted")}
                      </span>
                      {!emoji && w.snippet && (
                        <span className="block italic text-muted-foreground mt-0.5">
                          “{w.snippet}”
                        </span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Panel>
        </section>
      )}

      {/* Empty state when there's nothing yet */}
      {voices.length === 0 && warmth.length === 0 && (
        <Panel variant="empty" heading={t("people.emptyHeading")}>
          <p>{t("people.emptyLede")}</p>
        </Panel>
      )}

      {/* Quiet doorway */}
      <div className="pt-2">
        <Link
          href="/vision"
          className="inline-flex items-center gap-1 text-sm font-medium text-[hsl(var(--chart-2))] hover:opacity-80"
        >
          {t("people.backToVision")} →
        </Link>
      </div>
    </main>
  );
}
