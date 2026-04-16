/**
 * Server-side helper for locale-aware API fetches.
 *
 * Reads the NEXT_LOCALE cookie once and returns:
 *   - lang: the resolved locale code
 *   - fetchWithLocale(path, init?): a fetch that automatically appends ?lang=
 *     to every request (unless the path already has one, or lang is the default)
 *
 * Use in server components and async pages. For the DEFAULT_LOCALE (en) the
 * helper still appends the lang so the API returns the English view when one
 * exists (the caller can always override by passing an explicit lang in path).
 */

import { cookies } from "next/headers";
import { getApiBase } from "@/lib/api";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export async function resolveLocaleFromCookie(): Promise<LocaleCode> {
  const cookieStore = await cookies();
  const v = cookieStore.get("NEXT_LOCALE")?.value;
  return isSupportedLocale(v) ? v : DEFAULT_LOCALE;
}

function appendLang(url: string, lang: LocaleCode): string {
  if (/[?&]lang=/.test(url)) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}lang=${lang}`;
}

export type LocaleFetch = (path: string, init?: RequestInit) => Promise<Response>;

export async function createLocaleFetch(): Promise<{ lang: LocaleCode; fetchWithLocale: LocaleFetch }> {
  const lang = await resolveLocaleFromCookie();
  const base = getApiBase();
  const fetchWithLocale: LocaleFetch = (path, init) => {
    const abs = path.startsWith("http") ? path : `${base}${path.startsWith("/") ? "" : "/"}${path}`;
    return fetch(appendLang(abs, lang), init);
  };
  return { lang, fetchWithLocale };
}

/**
 * Convenience: fetch JSON with locale, return null on any failure.
 * Mirrors fetchJsonOrNull's error shape so callers can swap in-place.
 */
export async function fetchJsonWithLocale<T>(
  path: string,
  init?: RequestInit,
): Promise<{ lang: LocaleCode; data: T | null }> {
  const { lang, fetchWithLocale } = await createLocaleFetch();
  try {
    const res = await fetchWithLocale(path, init);
    if (!res.ok) return { lang, data: null };
    const data = (await res.json()) as T;
    return { lang, data };
  } catch {
    return { lang, data: null };
  }
}
