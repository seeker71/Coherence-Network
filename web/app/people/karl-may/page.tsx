import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getKarlMayContent } from "@/content/people/karl-may";

/**
 * /people/karl-may — author of Winnetou and Old Shatterhand.
 *
 * Honored here as the source of the German-language frontier
 * imagination Urs walked through in childhood. Apache country was
 * alive in him before Colorado was geography.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getKarlMayContent(lang).metadata;
}

export default async function KarlMayProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getKarlMayContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="karl-may" />;
}
