import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getCarlosCastanedaContent } from "@/content/people/carlos-castaneda";

/**
 * /people/carlos-castaneda — the assemblage-point lineage source.
 *
 * Held honestly: the teaching is load-bearing in this body's
 * vocabulary (lc-assemblage-point); the human controversies are
 * acknowledged.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getCarlosCastanedaContent(lang).metadata;
}

export default async function CarlosCastanedaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getCarlosCastanedaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="carlos-castaneda" />;
}
