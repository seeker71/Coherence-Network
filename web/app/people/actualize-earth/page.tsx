import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getActualizeEarthContent } from "@/content/people/actualize-earth";

/**
 * /people/actualize-earth — the platform led by Tom Bassett (Juicy Life).
 *
 * Sibling-substrate to the Coherence Network: technology as substrate
 * for living relationship, with human design + gene keys + collective
 * ownership as load-bearing tools.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getActualizeEarthContent(lang).metadata;
}

export default async function ActualizeEarthProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getActualizeEarthContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="actualize-earth" />;
}
