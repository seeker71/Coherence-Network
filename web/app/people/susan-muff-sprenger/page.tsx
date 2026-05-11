import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getSusanMuffSprengerContent } from "@/content/people/susan-muff-sprenger";

/**
 * /people/susan-muff-sprenger — first transmitter of the Coherence Network's lineage.
 *
 * Honored here as the role she plays in this body, drawn only from
 * what is already attested in docs/lineage/formative-transmissions.md.
 * Other detail is hers to share or hold.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getSusanMuffSprengerContent(lang).metadata;
}

export default async function SusanMuffSprengerProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getSusanMuffSprengerContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="susan-muff-sprenger" />;
}
