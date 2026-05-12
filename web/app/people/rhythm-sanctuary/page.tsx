import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getRhythmSanctuaryContent } from "@/content/people/rhythm-sanctuary";

/**
 * /people/rhythm-sanctuary — Shannon Lei Gill's Colorado ecstatic-dance
 * community since 2005. Gabrielle Roth wave lineage; the altar, the
 * silence, the held closing.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getRhythmSanctuaryContent(lang).metadata;
}

export default async function RhythmSanctuaryProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getRhythmSanctuaryContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="rhythm-sanctuary" />;
}
