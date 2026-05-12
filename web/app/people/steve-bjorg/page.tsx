import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getSteveBjorgContent } from "@/content/people/steve-bjorg";

/**
 * /people/steve-bjorg — lifelong collaborator since HTL Brugg-Windisch
 * 1991. The continuous design partnership underneath RCSL, Digi4Fun's
 * Muzzle Velocity, the BML/BMF/BMCPU master's thesis at CU Boulder,
 * and MindTouch.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getSteveBjorgContent(lang).metadata;
}

export default async function SteveBjorgProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getSteveBjorgContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="steve-bjorg" />;
}
