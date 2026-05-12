import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getTomBassettContent } from "@/content/people/tom-bassett";

/**
 * /people/tom-bassett — Juicy Life, CEO and Lead Engineer at
 * Actualize Earth. Boulder, CO. Cross-walk of large-scale
 * engineering and consciousness-evolution social networks.
 *
 * This page was previously composted as auto-harvest noise; restored
 * once Urs named the real ground.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getTomBassettContent(lang).metadata;
}

export default async function TomBassettProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getTomBassettContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="tom-bassett" />;
}
