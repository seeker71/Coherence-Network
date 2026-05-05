import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getUrsContent } from "@/content/people/urs";

/**
 * /people/urs — the central cell of this body's tending.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/urs/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. The hero is a custom radial-gradient
 * network-themed background blended with `/visuals/scale-network-map.png`
 * (see `hero.background` + `hero.extraImage` in en.tsx). See
 * `web/components/people/PersonProfileTemplate.tsx` for rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getUrsContent(lang).metadata;
}

export default async function UrsProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getUrsContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
