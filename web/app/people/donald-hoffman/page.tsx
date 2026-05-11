import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getDonaldHoffmanContent } from "@/content/people/donald-hoffman";

/**
 * /people/donald-hoffman — UC Irvine cognitive scientist; Interface
 * Theory of Perception. The empirical-mathematical peer of Castaneda's
 * assemblage point and Levin's bioelectric pattern memory.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getDonaldHoffmanContent(lang).metadata;
}

export default async function DonaldHoffmanProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getDonaldHoffmanContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="donald-hoffman" />;
}
