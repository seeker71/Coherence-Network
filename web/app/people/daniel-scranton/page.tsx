import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getDanielScrantonContent } from "@/content/people/daniel-scranton";

/**
 * /people/daniel-scranton — daily verbal channel of the 9D Arcturian
 * Council and many others since 2010.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getDanielScrantonContent(lang).metadata;
}

export default async function DanielScrantonProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getDanielScrantonContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="daniel-scranton" />;
}
