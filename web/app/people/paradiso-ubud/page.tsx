import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getParadisoUbudContent } from "@/content/people/paradiso-ubud";

/**
 * /people/paradiso-ubud — cultural-hall venue in Ubud.
 *
 * Holds 5Rhythms, DISSOLVE, film, ceremony. The architectural
 * anchor of the Ubud embodied lineage in this body.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getParadisoUbudContent(lang).metadata;
}

export default async function ParadisoUbudProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getParadisoUbudContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="paradiso-ubud" />;
}
