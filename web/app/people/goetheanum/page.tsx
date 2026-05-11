import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getGoetheanumContent } from "@/content/people/goetheanum";

/**
 * /people/goetheanum — the Steiner-designed building in Dornach, Switzerland.
 *
 * Honored here as the lineage node where the Central-European
 * esoteric Goethe-Steiner stream entered this body. Urs attended
 * the week-long Faust I+II performance in eurythmy at age 19.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getGoetheanumContent(lang).metadata;
}

export default async function GoetheanumProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getGoetheanumContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="goetheanum" />;
}
