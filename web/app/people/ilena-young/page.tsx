import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getIlenaContent } from "@/content/people/ilena";

/**
 * /people/ilena-young — full-name alias of /people/ilena.
 *
 * Both URLs serve the same rich content from `web/content/people/ilena/`.
 * The short slug (`/people/ilena`) is the older route; this full-name
 * route honors her surname and is the form most natural to type. Keep
 * the content module single-sourced so any update lands on both pages
 * in the same breath.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getIlenaContent(lang).metadata;
}

export default async function IlenaYoungProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getIlenaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ilena-young" />;
}
