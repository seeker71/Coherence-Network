import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMudraCafeContent } from "@/content/people/mudra-cafe";

/**
 * /people/mudra-cafe — Ayurvedic dining room with handpan and live
 * music in central Ubud.
 *
 * The meeting place where one of the three Ubud cells (Elios)
 * entered this network's awareness on April 29, 2026.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMudraCafeContent(lang).metadata;
}

export default async function MudraCafeProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMudraCafeContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="mudra-cafe" />;
}
