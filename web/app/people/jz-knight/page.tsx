import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getJzKnightContent } from "@/content/people/jz-knight";

/**
 * /people/jz-knight — channeler of Ramtha; founder of RSE in Yelm, WA.
 *
 * Distinct from the Ramtha teaching page; this is the channeler herself.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getJzKnightContent(lang).metadata;
}

export default async function JzKnightProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getJzKnightContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="jz-knight" />;
}
