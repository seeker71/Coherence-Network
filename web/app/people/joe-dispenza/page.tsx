import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getJoeDispenzaContent } from "@/content/people/joe-dispenza";

/**
 * /people/joe-dispenza — chiropractor, researcher, meditation teacher.
 *
 * The bridge in this body's teaching lineage between Ramtha's
 * cosmology and the substrate of the Coherence Network. Met at
 * Mile Hi Church in Lakewood ~2005; the first network contributors
 * arrived at the Aurora retreat in April 2026.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getJoeDispenzaContent(lang).metadata;
}

export default async function JoeDispenzaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getJoeDispenzaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="joe-dispenza" />;
}
