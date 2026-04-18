import { cookies, headers } from "next/headers";
import type { Metadata } from "next";

import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { MePage } from "@/components/MePage";
import { InspiredByPreview } from "@/components/InspiredByPreview";

/**
 * /me — your presence in the field, made visible.
 *
 * The viewer's identity lives in localStorage (anonymous fingerprint
 * unless they've graduated to a contributor). This page shows what
 * the app currently knows about them, in warm prose, and offers a
 * single "Clear identity" affordance so anyone can begin again.
 *
 * Server component just for the metadata + locale resolution; the
 * rendering happens client-side because identity isn't on the server.
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Your presence — Coherence Network",
  description: "Who the field knows you as, what you've offered, and how to begin again.",
};

export default async function YourPresencePage() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="max-w-2xl mx-auto px-4 py-6">
      <header className="mb-5">
        <h1 className="text-2xl md:text-3xl font-light text-foreground mb-1">
          {t("me.heading")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("me.lede")}</p>
      </header>
      <MePage />
      <div className="mt-8">
        <InspiredByPreview />
      </div>
    </main>
  );
}
