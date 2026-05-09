import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getContactImprovContent } from "@/content/people/contact-improv";

/**
 * /people/contact-improv — the practice form (Steve Paxton et al.,
 * 1972 onward) whose entire grammar is two bodies negotiating
 * gravity together; the substrate practice this body's lineage
 * chain — Liquid Bloom → Pagan Ritual → Vali → EMT → CI — led to.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/contact-improv/{locale}.tsx`; chrome strings
 * (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getContactImprovContent(lang).metadata;
}

export default async function ContactImprovPage() {
  const lang = await resolveRequestLocale();
  const content = getContactImprovContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="contact-improv" />;
}
