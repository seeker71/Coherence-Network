import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";

import { TreasuryDepositForm } from "./TreasuryDepositForm";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export const metadata: Metadata = {
  title: "Treasury",
  description: "Deposit ETH or BTC, convert to CC, and stake on ideas.",
};

export default async function TreasuryPage() {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          {t("treasury.title")}
        </h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          {t("treasury.lede")}
        </p>
      </header>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-4">
        <h2 className="text-lg font-semibold">{t("treasury.howItWorks")}</h2>
        <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground leading-relaxed">
          <li>
            <span className="text-foreground/80">{t("treasury.step1Label")}</span>{t("treasury.step1After")}
          </li>
          <li>
            <span className="text-foreground/80">{t("treasury.step2Label")}</span>{t("treasury.step2After")}
          </li>
          <li>
            <span className="text-foreground/80">{t("treasury.step3Label")}</span>{t("treasury.step3After")}
          </li>
          <li>
            <span className="text-foreground/80">{t("treasury.step4Label")}</span>{t("treasury.step4After")}
          </li>
        </ol>
        <p className="text-xs text-muted-foreground/80">
          {t("treasury.footnote")}
        </p>
      </section>

      <TreasuryDepositForm />

      <footer className="text-center text-sm text-muted-foreground/80 pt-4">
        <Link
          href="/invest"
          className="text-primary hover:text-foreground transition-colors underline underline-offset-4"
        >
          {t("treasury.viewIdeas")}
        </Link>
      </footer>
    </main>
  );
}
