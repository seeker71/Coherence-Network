import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBrigitteMarsContent } from "@/content/people/brigitte-mars";

/**
 * /people/brigitte-mars — Boulder herbalist, Naropa professor,
 * author of 18 books, 60+ years with plant medicine, 50+ years
 * holding psychedelic ceremonies. Deep part of the pagan rituals
 * at Anchor the Light. A presence Urs knows personally.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBrigitteMarsContent(lang).metadata;
}

export default async function BrigitteMarsProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBrigitteMarsContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="brigitte-mars" />;
}
