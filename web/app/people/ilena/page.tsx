import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getIlenaContent } from "@/content/people/ilena";

/**
 * /people/ilena — a welcome page for Ilena Young of Ranakami.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/ilena/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getIlenaContent(lang).metadata;
}

export default async function IlenaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getIlenaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ilena" />;
}
