import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getPoranguiContent } from "@/content/people/porangui";

/**
 * /people/porangui — music as medicine, the ceremonial-musician cell.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/porangui/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getPoranguiContent(lang).metadata;
}

export default async function PoranguiProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getPoranguiContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="porangui" />;
}
