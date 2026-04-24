import { cookies, headers } from "next/headers";

import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export async function resolveRequestLocale(): Promise<LocaleCode> {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  if (isSupportedLocale(cookieLang)) return cookieLang;

  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  return isSupportedLocale(headerLang) ? headerLang : DEFAULT_LOCALE;
}
