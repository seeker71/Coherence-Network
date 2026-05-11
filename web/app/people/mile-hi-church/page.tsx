import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMileHiChurchContent } from "@/content/people/mile-hi-church";

/**
 * /people/mile-hi-church — Lakewood, CO. The physical-arrival anchor
 * of the Ramtha → Dispenza → Urs teaching chain.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMileHiChurchContent(lang).metadata;
}

export default async function MileHiChurchProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMileHiChurchContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="mile-hi-church" />;
}
