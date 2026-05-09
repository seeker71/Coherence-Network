import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getPaganRitualContent } from "@/content/people/pagan-ritual";

/**
 * /people/pagan-ritual — the first ceremonial floor this body
 * recognized as home; the Liquid Bloom room that became the
 * threshold for the chain of gatherings that followed.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/pagan-ritual/{locale}.tsx`; chrome strings
 * (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getPaganRitualContent(lang).metadata;
}

export default async function PaganRitualPage() {
  const lang = await resolveRequestLocale();
  const content = getPaganRitualContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="pagan-ritual" />;
}
