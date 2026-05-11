import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getIndozConferenceContent } from "@/content/people/indoz-conference";

/**
 * /people/indoz-conference — annual Indonesia-Australia bilateral
 * conference in Brisbane since 2012. The legible-public surface of
 * Ilena Young's SaBali bridge practice.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getIndozConferenceContent(lang).metadata;
}

export default async function IndozConferenceProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getIndozConferenceContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="indoz-conference" />;
}
