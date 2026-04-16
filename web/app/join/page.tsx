import Link from "next/link";
import { cookies } from "next/headers";
import { ContributorSetup } from "./_components/ContributorSetup";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export const metadata = {
  title: "Join — Coherence Network",
  description: "Generate your identity, register as a contributor, and start building your frequency profile.",
};

export default async function JoinPage() {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/vision" className="hover:text-amber-400/80 transition-colors">{t("vision.breadcrumbRoot")}</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">{t("join.breadcrumb")}</span>
      </nav>

      <div className="mb-10 space-y-3">
        <h1 className="text-3xl font-extralight text-white">{t("join.title")}</h1>
        <p className="text-stone-400 leading-relaxed">{t("join.lede")}</p>
      </div>

      <ContributorSetup />
    </main>
  );
}
