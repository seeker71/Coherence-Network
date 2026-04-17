import type { Metadata } from "next";
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
  "proposal",
]);

const TYPE_LABEL: Record<string, { title: string; description: string }> = {
  concept: {
    title: "Walk the concepts — Coherence Network",
    description: "Meet one Living Collective concept at a time. Every gesture lifts both pulses.",
  },
  idea: {
    title: "Walk the ideas — Coherence Network",
    description: "Meet ideas being realized, one at a time.",
  },
  contributor: {
    title: "Walk with contributors — Coherence Network",
    description: "Meet the people weaving this network.",
  },
  proposal: {
    title: "Walk the proposals — Coherence Network",
    description: "Meet proposals the collective is considering. Vote with your reactions.",
  },
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ entityType: string }>;
}): Promise<Metadata> {
  const { entityType } = await params;
  const meta = TYPE_LABEL[entityType];
  if (!meta) return { title: "Explore — Coherence Network" };
  return {
    title: meta.title,
    description: meta.description,
    openGraph: {
      type: "website",
      siteName: "Coherence Network",
      title: meta.title,
      description: meta.description,
      images: [{ url: "/assets/logo.svg" }],
    },
    twitter: {
      card: "summary",
      title: meta.title,
      description: meta.description,
    },
  };
}

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
        othersHereOne: t("meeting.othersHereOne"),
        othersHereMany: t("meeting.othersHereMany"),
        sayHeading: t("meeting.sayHeading"),
        sayNamePlaceholder: t("meeting.sayNamePlaceholder"),
        sayPlaceholder: t("meeting.sayPlaceholder"),
        saySubmit: t("meeting.saySubmit"),
        saySending: t("meeting.saySending"),
        saySent: t("meeting.saySent"),
        sayDismiss: t("meeting.sayDismiss"),
      }}
    />
  );
}
