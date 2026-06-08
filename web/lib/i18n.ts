/** Locale-text-as-data helpers.
 *
 * All user-facing strings live in web/messages/{lang}.json. The installed
 * locale list is generated from those files, so adding a language means adding
 * a bundle and regenerating web/messages/manifest.ts.
 *
 * Works both server-side (getMessages, translateWith) and client-side (via
 * MessagesProvider + useT hook). The resolveLocale priority matches the
 * feedback in memory/feedback_profile_locale.md:
 *   1. ?lang= query param
 *   2. profile locale (when available — passed in by caller)
 *   3. NEXT_LOCALE cookie
 *   4. default (en)
 */

import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { BUNDLES, type MessageTree } from "@/messages/manifest";

export function getMessages(lang: LocaleCode): MessageTree {
  return BUNDLES[lang] ?? BUNDLES[DEFAULT_LOCALE];
}

function lookup(tree: MessageTree, key: string): string | undefined {
  const parts = key.split(".");
  let current: unknown = tree;
  for (const part of parts) {
    if (typeof current !== "object" || current === null) return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) => {
    const v = params[k];
    return v === undefined ? `{${k}}` : String(v);
  });
}

export type Translator = (key: string, params?: Record<string, string | number>) => string;

export function createTranslator(lang: LocaleCode): Translator {
  const target = getMessages(lang);
  const fallback = getMessages(DEFAULT_LOCALE);
  return (key: string, params?: Record<string, string | number>) => {
    const hit = lookup(target, key) ?? lookup(fallback, key);
    if (hit === undefined) {
      if (process.env.NODE_ENV !== "production") {
        console.warn(`[i18n] missing key: ${key} (lang=${lang})`);
      }
      return key;
    }
    return interpolate(hit, params);
  };
}

export type ResolveInput = {
  searchParamLang?: string | null;
  profileLocale?: string | null;
  cookieLocale?: string | null;
};

export function resolveLocale(input: ResolveInput): LocaleCode {
  const candidates = [input.searchParamLang, input.profileLocale, input.cookieLocale];
  for (const c of candidates) {
    if (isSupportedLocale(c)) return c;
  }
  return DEFAULT_LOCALE;
}

export { DEFAULT_LOCALE, type LocaleCode };
