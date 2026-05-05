import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getElonMuskContent } from "@/content/people/elon-musk";

/**
 * /people/elon-musk — an invitation page for Elon Musk that reads his
 * public work through this network's resonance grammar without claiming
 * endorsement, membership, or investment advice.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getElonMuskContent(lang).metadata;
}

export default async function ElonMuskProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getElonMuskContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
