import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getEcstaticMovementTribeContent } from "@/content/people/ecstatic-movement-tribe";

/**
 * /people/ecstatic-movement-tribe — Tammy Beattie's recurring room
 * at Vali Soul Sanctuary; the container in which this body's
 * practice crossed from solo journey into relational Contact Improv.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/ecstatic-movement-tribe/{locale}.tsx`; chrome
 * strings (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getEcstaticMovementTribeContent(lang).metadata;
}

export default async function EcstaticMovementTribePage() {
  const lang = await resolveRequestLocale();
  const content = getEcstaticMovementTribeContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ecstatic-movement-tribe" />;
}
