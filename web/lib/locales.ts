import {
  DEFAULT_LOCALE,
  LOCALES,
  type Locale,
  type LocaleCode,
} from "@/messages/manifest";

export { DEFAULT_LOCALE, LOCALES, type Locale, type LocaleCode };

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
