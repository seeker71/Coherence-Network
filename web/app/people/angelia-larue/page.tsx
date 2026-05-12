import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAngeliaLarueContent } from "@/content/people/angelia-larue";

/**
 * /people/angelia-larue — Master Crystologist, Reiki Master, Reverend.
 *
 * Main priestess during the Anchor the Light Ceremony alongside
 * Ubbe MacLean. Hawaii-based, operates internationally. Founder
 * of Inner Passage Mystery School and Church of Inner Mystery.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAngeliaLarueContent(lang).metadata;
}

export default async function AngeliaLarueProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAngeliaLarueContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="angelia-larue" />;
}
