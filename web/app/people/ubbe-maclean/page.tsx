import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getUbbeMacleanContent } from "@/content/people/ubbe-maclean";

/**
 * /people/ubbe-maclean — a doorway held open.
 *
 * Previously composted as a placeholder; restored once Urs named
 * the real person behind the name. Sparse on purpose, awaiting
 * Ubbe's own framing.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getUbbeMacleanContent(lang).metadata;
}

export default async function UbbeMacleanProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getUbbeMacleanContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ubbe-maclean" />;
}
