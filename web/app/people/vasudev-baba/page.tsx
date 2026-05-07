import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getVasudevBabaContent } from "@/content/people/vasudev-baba";

/**
 * /people/vasudev-baba — kirtan-wala and satsang holder in Bali for 11
 * years; lineage of Swami Shyam.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/vasudev-baba/{locale}.tsx`; chrome strings
 * (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template. See
 * `web/components/people/PersonProfileTemplate.tsx` for the rendering
 * shape.
 *
 * Hero portrait: self-published teacher photo from sacredsongcircle.com,
 * the same kirtan-teaching profile network where he is publicly listed.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getVasudevBabaContent(lang).metadata;
}

export default async function VasudevBabaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getVasudevBabaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="vasudev-baba" />;
}
