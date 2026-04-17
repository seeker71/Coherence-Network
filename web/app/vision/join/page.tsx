import type { Metadata } from "next";
import Link from "next/link";
import { cookies, headers } from "next/headers";

import { InterestForm } from "@/components/vision";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  return {
    title: t("visionJoin.metaTitle"),
    description: t("visionJoin.metaDescription"),
    openGraph: {
      type: "website",
      siteName: "Coherence Network",
      title: t("visionJoin.metaTitle"),
      description: t("visionJoin.metaDescription"),
      images: [{ url: "/assets/logo.svg" }],
    },
    twitter: {
      card: "summary",
      title: t("visionJoin.metaTitle"),
      description: t("visionJoin.metaDescription"),
    },
  };
}

const ROLE_KEYS = [
  "livingStructureWeaver",
  "nourishmentAlchemist",
  "frequencyHolder",
  "vitalityKeeper",
  "transmissionSource",
  "formGrower",
] as const;

export default async function JoinPage() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="max-w-4xl mx-auto px-6 py-20 space-y-24">
      {/* Hero */}
      <section className="text-center space-y-8">
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          {t("visionJoin.heroLine1")}{" "}
          <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
            {t("visionJoin.heroLine2")}
          </span>
        </h1>
        <p className="text-xl text-stone-400 font-light leading-relaxed max-w-2xl mx-auto">
          {t("visionJoin.heroLede")}
        </p>
      </section>

      {/* Three paths */}
      <section className="grid md:grid-cols-3 gap-8">
        <Link
          href="/vision"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-amber-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">✦</div>
          <h2 className="text-xl font-light text-amber-300/80 group-hover:text-amber-300 transition-colors">
            {t("visionJoin.pathExploreTitle")}
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            {t("visionJoin.pathExploreBody")}
          </p>
        </Link>

        <a
          href="#register"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-teal-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">◈</div>
          <h2 className="text-xl font-light text-teal-300/80 group-hover:text-teal-300 transition-colors">
            {t("visionJoin.pathJoinTitle")}
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            {t("visionJoin.pathJoinBody")}
          </p>
        </a>

        <Link
          href="/vision/community"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-violet-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">◉</div>
          <h2 className="text-xl font-light text-violet-300/80 group-hover:text-violet-300 transition-colors">
            {t("visionJoin.pathGatherTitle")}
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            {t("visionJoin.pathGatherBody")}
          </p>
        </Link>
      </section>

      {/* What the field calls for */}
      <section className="space-y-8">
        <h2 className="text-2xl font-light text-stone-300 text-center">
          {t("visionJoin.callingHeading")}
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          {ROLE_KEYS.map((k) => (
            <div
              key={k}
              className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2"
            >
              <h3 className="text-amber-300/70 font-medium text-sm">
                {t(`interestForm.roles.${k}.name`)}
              </h3>
              <p className="text-stone-500 text-sm leading-relaxed">
                {t(`interestForm.roles.${k}.desc`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Registration form */}
      <section id="register" className="space-y-8 scroll-mt-20">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-200">
            {t("visionJoin.registerHeading")}
          </h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            {t("visionJoin.registerLede")}
          </p>
        </div>

        <InterestForm />
      </section>

      {/* Footer */}
      <section className="text-center text-xs text-stone-700 space-y-2 pt-8 border-t border-stone-800/20">
        <p>{t("visionJoin.footerLine1")}</p>
        <p>{t("visionJoin.footerLine2")}</p>
      </section>
    </main>
  );
}
