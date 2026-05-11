import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getWisdomSoupContent } from "@/content/people/wisdom-soup";

/**
 * /people/wisdom-soup — Anne Tucker's spiritual-seekers community since 2016.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getWisdomSoupContent(lang).metadata;
}

export default async function WisdomSoupProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getWisdomSoupContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="wisdom-soup" />;
}
