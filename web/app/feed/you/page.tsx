import { cookies, headers } from "next/headers";

import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { FeedTabs } from "@/components/FeedTabs";
import { NotificationBell } from "@/components/NotificationBell";
import { PersonalFeed } from "@/components/PersonalFeed";
import { InviteFriend } from "@/components/InviteFriend";
import { SinceLastVisit } from "@/components/SinceLastVisit";

/**
 * /feed/you — your corner of the organism.
 *
 * The viewer's footprint made visible: voices you gave, reactions you
 * offered, replies that came back to you, proposals you authored or
 * supported, and the ideas they became. Client-rendered because the
 * identity lives in localStorage; the server doesn't know who you are.
 */

import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Your corner — Coherence Network",
  description: "Voices you gave, reactions you offered, replies that came back to you, proposals you lifted.",
  openGraph: {
    type: "website",
    siteName: "Coherence Network",
    title: "Your corner of the organism",
    description: "Voices you gave, reactions you offered, replies that came back to you.",
    images: [{ url: "/assets/logo.svg" }],
  },
  twitter: {
    card: "summary",
    title: "Your corner — Coherence Network",
    description: "Your corner of the organism.",
  },
};

export default async function PersonalFeedPage() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl md:text-3xl font-light text-white mb-1">
            {t("feed.personalHeading")}
          </h1>
          <p className="text-sm text-stone-400">{t("feed.personalLede")}</p>
        </div>
        <NotificationBell />
      </header>
      <FeedTabs />
      <div className="mb-4">
        <SinceLastVisit />
      </div>
      <PersonalFeed
        strings={{
          empty: t("feed.personalEmpty"),
          emptyCta: t("feed.personalEmptyCta"),
          noIdentity: t("feed.personalNoIdentity"),
          noIdentityCta: t("feed.personalNoIdentityCta"),
          loading: t("feed.personalLoading"),
        }}
      />
      <div className="mt-8">
        <InviteFriend />
      </div>
    </main>
  );
}
