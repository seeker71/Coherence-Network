import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getIsmaelPerezContent } from "@/content/people/ismael-perez";

/**
 * /people/ismael-perez — cosmic-history and consciousness teacher.
 *
 * Source-marked transmission. The Just Tap In conversation with
 * Emilio Ortiz (May 2026) seeded the body's reading of cells-are-
 * universes, triple temporal alliance, and Lyran substrate
 * vulnerability.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getIsmaelPerezContent(lang).metadata;
}

export default async function IsmaelPerezProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getIsmaelPerezContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ismael-perez" />;
}
