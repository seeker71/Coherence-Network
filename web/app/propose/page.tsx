import { cookies, headers } from "next/headers";

import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { ProposeForm } from "@/components/ProposeForm";

/**
 * /propose — one screen to offer a proposal to the collective.
 *
 * The form is deliberately small: title, body, your name. The proposal
 * enters the /explore/proposal queue immediately. Votes are whatever
 * reactions it collects in the meeting. Resolution is a read of that
 * tally after the window closes.
 */

import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Propose — Coherence Network",
  description: "Offer something for the collective to meet. Reactions become the vote.",
  openGraph: {
    type: "website",
    siteName: "Coherence Network",
    title: "Propose to the collective",
    description: "Offer something for the collective to meet. Reactions become the vote.",
    images: [{ url: "/assets/logo.svg" }],
  },
  twitter: {
    card: "summary",
    title: "Propose — Coherence Network",
    description: "Offer something for the collective to meet.",
  },
};

export default async function ProposePage() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl md:text-3xl font-light text-white mb-1">
          {t("propose.heading")}
        </h1>
        <p className="text-sm text-stone-400">{t("propose.lede")}</p>
      </header>
      <ProposeForm
        strings={{
          titlePlaceholder: t("propose.titlePlaceholder"),
          bodyPlaceholder: t("propose.bodyPlaceholder"),
          authorPlaceholder: t("propose.authorPlaceholder"),
          submit: t("propose.submit"),
          submitting: t("propose.submitting"),
          thanks: t("propose.thanks"),
          viewAll: t("propose.viewAll"),
        }}
        locale={lang}
      />
    </main>
  );
}
