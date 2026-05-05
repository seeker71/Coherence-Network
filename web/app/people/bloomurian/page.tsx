import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBloomurianContent } from "@/content/people/bloomurian";

/**
 * /people/bloomurian — Robin Liepman, ecstatic-dance DJ in this network.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/bloomurian/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBloomurianContent(lang).metadata;
}

export default async function BloomurianProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBloomurianContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
