import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getRoccoTortorellaContent } from "@/content/people/rocco-tortorella";

/**
 * /people/rocco-tortorella — Aly Constantine's husband, co-host of
 * Courtyard Constellations, videographer (roccomountain.com), naturally
 * flowing presence at Rise & Vibes, Unison, and Burning Man.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/rocco-tortorella/{locale}.tsx`; chrome strings
 * come from `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getRoccoTortorellaContent(lang).metadata;
}

export default async function RoccoTortorellaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getRoccoTortorellaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="rocco-tortorella" />;
}
