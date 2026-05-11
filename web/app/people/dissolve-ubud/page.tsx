import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getDissolveUbudContent } from "@/content/people/dissolve-ubud";

/**
 * /people/dissolve-ubud — contact improvisation + authentic relating
 * facilitated by Tara Li at Paradiso Ubud.
 *
 * The relational edge of this body's Ubud embodied lineage —
 * where it learns consent in real time and emotional availability
 * without absorption.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getDissolveUbudContent(lang).metadata;
}

export default async function DissolveUbudProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getDissolveUbudContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="dissolve-ubud" />;
}
