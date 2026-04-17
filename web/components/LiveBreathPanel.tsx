import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";
import { createTranslator, type Translator } from "@/lib/i18n";
import type { LocaleCode } from "@/lib/locales";

/**
 * LiveBreathPanel — the "organism is alive, step in" banner for the home page.
 *
 * Server-rendered summary of presence + recent voices, with three warm
 * entry points to the living dialogue surfaces. When everything is
 * quiet, the panel still invites — "be the first breath."
 */

interface PresenceSummary {
  total_entities: number;
  top: { entity_type: string; entity_id: string; present: number }[];
}

interface RecentVoice {
  id: string;
  concept_id: string;
  author_name: string;
  created_at: string | null;
}

interface RecentReaction {
  id: string;
  entity_type: string;
  entity_id: string;
  author_name: string;
  created_at: string | null;
}

async function loadBreath(): Promise<{
  presence: PresenceSummary | null;
  recentVoices: RecentVoice[];
  recentReactions: RecentReaction[];
}> {
  const base = getApiBase();
  const [presence, voicesData, reactionsData] = await Promise.all([
    fetchJsonOrNull<PresenceSummary>(`${base}/api/presence/summary`, {}, 4000),
    fetchJsonOrNull<{ voices: RecentVoice[] }>(
      `${base}/api/concepts/voices/recent?limit=3`,
      {},
      4000,
    ),
    fetchJsonOrNull<{ reactions: RecentReaction[] }>(
      `${base}/api/reactions/recent?limit=3`,
      {},
      4000,
    ),
  ]);
  return {
    presence,
    recentVoices: voicesData?.voices || [],
    recentReactions: reactionsData?.reactions || [],
  };
}

interface Props {
  lang: LocaleCode;
}

export async function LiveBreathPanel({ lang }: Props) {
  const t: Translator = createTranslator(lang);
  const { presence, recentVoices, recentReactions } = await loadBreath();

  const meetingNow = presence?.top.reduce((sum, row) => sum + row.present, 0) || 0;
  const entitiesWithPresence = presence?.total_entities || 0;
  const hasSignal =
    meetingNow > 0 || recentVoices.length > 0 || recentReactions.length > 0;

  return (
    <section
      className="relative z-10 w-full border-b border-border/40 bg-[linear-gradient(180deg,hsl(var(--chart-2)/0.08),transparent)]"
      aria-label={t("homeBreath.ariaLabel")}
    >
      <div className="max-w-4xl mx-auto px-5 py-4 flex flex-col md:flex-row md:items-center gap-4">
        <div className="flex-1 min-w-0">
          {/* Eyebrow tokens match the Panel primitive and adapt to both
              themes via the chart-2 (teal) semantic token. */}
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--chart-2))] mb-1.5">
            {t("homeBreath.label")}
          </p>
          {hasSignal ? (
            <p className="text-base md:text-lg text-foreground">
              {meetingNow > 0 && (
                <>
                  <span className="text-[hsl(var(--chart-2))] font-medium">
                    {meetingNow === 1
                      ? t("homeBreath.oneMeetingNow")
                      : t("homeBreath.manyMeetingNow").replace(
                          "{count}",
                          String(meetingNow),
                        )}
                    {entitiesWithPresence > 1 &&
                      ` ${t("homeBreath.acrossEntities").replace(
                        "{count}",
                        String(entitiesWithPresence),
                      )}`}
                  </span>
                  {(recentVoices.length > 0 || recentReactions.length > 0) && " · "}
                </>
              )}
              {recentVoices.length > 0 && (
                <span className="text-muted-foreground">
                  {t("homeBreath.recentVoicesLine").replace(
                    "{count}",
                    String(recentVoices.length),
                  )}
                </span>
              )}
              {recentVoices.length === 0 && recentReactions.length > 0 && (
                <span className="text-muted-foreground">
                  {t("homeBreath.recentReactionsLine").replace(
                    "{count}",
                    String(recentReactions.length),
                  )}
                </span>
              )}
            </p>
          ) : (
            <p className="text-base md:text-lg text-foreground">
              {t("homeBreath.quiet")}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href="/here"
            className="rounded-full bg-[hsl(var(--chart-2))] hover:opacity-90 text-[hsl(var(--primary-foreground))] px-4 py-2 text-sm font-medium transition-opacity"
          >
            {t("homeBreath.goHere")}
          </Link>
          <Link
            href="/explore/concept"
            className="rounded-full bg-[hsl(var(--primary))] hover:opacity-90 text-[hsl(var(--primary-foreground))] px-4 py-2 text-sm font-medium transition-opacity"
          >
            {t("homeBreath.goExplore")}
          </Link>
          <Link
            href="/propose"
            className="rounded-full border border-[hsl(var(--chart-2)/0.4)] hover:bg-[hsl(var(--chart-2)/0.1)] text-[hsl(var(--chart-2))] px-4 py-2 text-sm font-medium transition-colors"
          >
            {t("homeBreath.goPropose")}
          </Link>
        </div>
      </div>
    </section>
  );
}
