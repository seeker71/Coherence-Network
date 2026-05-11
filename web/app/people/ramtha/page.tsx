import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getRamthaContent } from "@/content/people/ramtha";

/**
 * /people/ramtha — the teaching lineage held in this body.
 *
 * Honored here as the source of The White Book — carried by Urs in
 * the German Urania Verlag edition since age 18, and the cosmology
 * that travelled through Joe Dispenza into the Mile Hi Church
 * years and onward to the Aurora retreat where the first network
 * contributors arrived.
 *
 * The page acknowledges the controversies around RSE as an
 * institution without flattening the teaching into them.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getRamthaContent(lang).metadata;
}

export default async function RamthaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getRamthaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ramtha" />;
}
