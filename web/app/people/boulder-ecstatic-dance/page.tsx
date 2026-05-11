import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBoulderEcstaticDanceContent } from "@/content/people/boulder-ecstatic-dance";

/**
 * /people/boulder-ecstatic-dance — Sunday morning at the Avalon Ballroom
 * in Boulder. The embodied-community substrate beneath the Boulder cluster.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBoulderEcstaticDanceContent(lang).metadata;
}

export default async function BoulderEcstaticDanceProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBoulderEcstaticDanceContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="boulder-ecstatic-dance" />;
}
