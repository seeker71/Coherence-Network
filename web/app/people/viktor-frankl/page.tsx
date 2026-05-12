import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getViktorFranklContent } from "@/content/people/viktor-frankl";

/**
 * /people/viktor-frankl — Austrian psychiatrist, Holocaust survivor,
 * founder of logotherapy. The gap between stimulus and response
 * grounds lc-assemblage-point in this body's lineage.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getViktorFranklContent(lang).metadata;
}

export default async function ViktorFranklProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getViktorFranklContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="viktor-frankl" />;
}
