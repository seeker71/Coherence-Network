import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getGabrielleRothContent } from "@/content/people/gabrielle-roth";

/**
 * /people/gabrielle-roth — creator of the 5Rhythms moving-meditation
 * practice. Her wave map (flowing, staccato, chaos, lyrical, stillness)
 * underlies multiple lineage threads in this network.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getGabrielleRothContent(lang).metadata;
}

export default async function GabrielleRothProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getGabrielleRothContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="gabrielle-roth" />;
}
