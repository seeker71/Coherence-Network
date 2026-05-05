import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getEliosContent } from "@/content/people/elios";

/**
 * /people/elios — co-holds the Sunday spontaneous chanting practice
 * at Ranakami with Ilena, often found at Mudra Cafe in Ubud.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/elios/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getEliosContent(lang).metadata;
}

export default async function EliosProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getEliosContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
