import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMichaelLevinContent } from "@/content/people/michael-levin";

/**
 * /people/michael-levin — developmental and synthetic biologist at Tufts.
 *
 * The empirical-scientific peer of this body's otherwise channeled
 * and esoteric lineage. Bioelectric pattern memory, TAME, xenobots
 * and anthrobots; the same recognition the rest of the lineage
 * carries, reached from inside experimental biology.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMichaelLevinContent(lang).metadata;
}

export default async function MichaelLevinProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMichaelLevinContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="michael-levin" />;
}
