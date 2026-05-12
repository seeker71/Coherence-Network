import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { get5RhythmsUbudContent } from "@/content/people/5rhythms-ubud";

/**
 * /people/5rhythms-ubud — Gabrielle Roth's wave map in Ubud.
 *
 * The lineage of conscious dance Urs walked into through feet,
 * breath, and shared time; inseparable from how this body came
 * to know coherence-as-motion.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return get5RhythmsUbudContent(lang).metadata;
}

export default async function FiveRhythmsUbudProfilePage() {
  const lang = await resolveRequestLocale();
  const content = get5RhythmsUbudContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="5rhythms-ubud" />;
}
