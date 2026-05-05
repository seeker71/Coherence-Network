import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMoseContent } from "@/content/people/mose";

/**
 * /people/mose — the embodiment of ecstatic dance in this network.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/mose/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMoseContent(lang).metadata;
}

export default async function MoseProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMoseContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
