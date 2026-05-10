import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getTammyBeattieContent } from "@/content/people/tammy-beattie";

/**
 * /people/tammy-beattie — facilitator of Ecstatic Movement Tribe at
 * Vali Soul Sanctuary; the doorway-opener for Contact Improv in this
 * body's arc.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/tammy-beattie/{locale}.tsx`; chrome strings
 * (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getTammyBeattieContent(lang).metadata;
}

export default async function TammyBeattieProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getTammyBeattieContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="tammy-beattie" />;
}
