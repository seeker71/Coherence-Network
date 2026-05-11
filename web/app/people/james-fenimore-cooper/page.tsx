import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getJamesFenimoreCooperContent } from "@/content/people/james-fenimore-cooper";

/**
 * /people/james-fenimore-cooper — author of the Leatherstocking Tales.
 *
 * Honored here as the original source of the chosen-brotherhood
 * teaching (Hawkeye / Chingachgook), received in German as
 * Der Lederstrumpf in Urs's Swiss childhood.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getJamesFenimoreCooperContent(lang).metadata;
}

export default async function JamesFenimoreCooperProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getJamesFenimoreCooperContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="james-fenimore-cooper" />;
}
