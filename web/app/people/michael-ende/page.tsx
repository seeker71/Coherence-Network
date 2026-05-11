import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMichaelEndeContent } from "@/content/people/michael-ende";

/**
 * /people/michael-ende — author of Momo and Die unendliche Geschichte.
 *
 * Honored here as the source of two of the three foundational books
 * Urs received from his mother in childhood. The teachings — listening
 * as resistance and the dreamer's responsibility — are load-bearing
 * in the network's vocabulary.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMichaelEndeContent(lang).metadata;
}

export default async function MichaelEndeProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMichaelEndeContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="michael-ende" />;
}
