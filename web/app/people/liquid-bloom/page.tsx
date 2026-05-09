import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getLiquidBloomContent } from "@/content/people/liquid-bloom";

/**
 * /people/liquid-bloom — Amani Friend's solo journey-music project.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/liquid-bloom/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getLiquidBloomContent(lang).metadata;
}

export default async function LiquidBloomProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getLiquidBloomContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="liquid-bloom" />;
}
