export type LocaleCode = "en" | "de" | "es" | "id";

export type Locale = {
  code: LocaleCode;
  name: string;
  nativeName: string;
};

export const LOCALES: Locale[] = [
  { code: "en", name: "English", nativeName: "English" },
  { code: "de", name: "German", nativeName: "Deutsch" },
  { code: "es", name: "Spanish", nativeName: "Español" },
  { code: "id", name: "Indonesian", nativeName: "Bahasa Indonesia" },
];

export const DEFAULT_LOCALE: LocaleCode = "en";

export function isSupportedLocale(code: string | null | undefined): code is LocaleCode {
  return !!code && LOCALES.some((l) => l.code === code);
}

export function localeByCode(code: string | null | undefined): Locale | undefined {
  if (!code) return undefined;
  return LOCALES.find((l) => l.code === code);
}

export type LanguageMeta = {
  lang: LocaleCode;
  is_anchor: boolean;
  stale: boolean;
  pending: boolean;
  available_langs: LocaleCode[];
  anchor: {
    lang: LocaleCode;
    author_type: string;
    updated_at: string | null;
    content_hash: string;
  } | null;
};
