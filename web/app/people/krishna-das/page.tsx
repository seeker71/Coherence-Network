import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getKrishnaDasContent } from "@/content/people/krishna-das";

/**
 * /people/krishna-das — the foundational Western kirtan elder.
 *
 * The Neem Karoli Baba lineage carrier whose work prepared the
 * ground every Western kirtan teacher (including Vasudev Baba)
 * has stepped into.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getKrishnaDasContent(lang).metadata;
}

export default async function KrishnaDasProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getKrishnaDasContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="krishna-das" />;
}
