import { cookies, headers } from "next/headers";
import { notFound } from "next/navigation";

import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { ExplorePager } from "@/components/ExplorePager";

/**
 * /explore/[entityType] — a walk through entities, one full-screen meeting
 * at a time. Tap care/amplify/move-on to travel; the queue lazily refreshes
 * when the end approaches so the walk never hits a wall.
 */

export const dynamic = "force-dynamic";

const SUPPORTED_TYPES = new Set([
  "concept",
  "idea",
  "contributor",
]);

export default async function ExplorePage({
  params,
}: {
  params: Promise<{ entityType: string }>;
}) {
  const { entityType } = await params;
  if (!SUPPORTED_TYPES.has(entityType)) notFound();

  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <ExplorePager
      entityType={entityType}
      strings={{
        empty: t("explore.empty"),
        exploreMore: t("explore.exploreMore"),
        loading: t("explore.loading"),
        walkDone: t("explore.walkDone"),
        restart: t("explore.restart"),
        viewerPulse: t("meeting.viewerPulse"),
        contentPulse: t("meeting.contentPulse"),
        firstMeeting: t("meeting.firstMeeting"),
        familiar: t("meeting.familiar"),
        resonant: t("meeting.resonant"),
        quiet: t("meeting.quiet"),
        offer: t("meeting.offer"),
        dismiss: t("meeting.dismiss"),
        amplify: t("meeting.amplify"),
        inviteHint: t("meeting.inviteHint"),
      }}
    />
  );
}
