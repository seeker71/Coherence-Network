import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getJoshuaGoldenContent } from "@/content/people/joshua-golden";

/**
 * /people/joshua-golden — a welcoming page held open for Joshua Golden,
 * met at Joe Dispenza's Aurora retreat (April 2026); the reason Bali
 * entered the body's path.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/joshua-golden/{locale}.tsx`; chrome strings come
 * from `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getJoshuaGoldenContent(lang).metadata;
}

export default async function JoshuaGoldenProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getJoshuaGoldenContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="joshua-golden" />;
}
