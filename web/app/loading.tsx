import { cookies, headers } from "next/headers";

import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

// Route-level loading skeleton. Resolves the viewer's locale the same way the
// root layout does (cookie → Accept-Language → default) so even the busy-state
// label meets them in their own tongue instead of a hardcoded English string.
export default async function Loading() {
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
  return (
    <main className="mx-auto max-w-6xl px-4 md:px-8 py-12" aria-busy="true" aria-label={t("common.loadingContent")}>
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-48 rounded bg-muted" />
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-lg bg-muted" />
          ))}
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-6 rounded bg-muted" style={{ width: `${80 - i * 10}%` }} />
          ))}
        </div>
      </div>
    </main>
  );
}
