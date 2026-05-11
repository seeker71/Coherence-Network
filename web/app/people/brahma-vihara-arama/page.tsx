import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBrahmaViharaAramaContent } from "@/content/people/brahma-vihara-arama";

/**
 * /people/brahma-vihara-arama — the largest Buddhist monastery on Bali,
 * in Banjar Tegeha (north Bali). Hosts the long-weekend silent retreats
 * co-held by Vasudev Baba and Prof Jem Bendell, 2-3 times a year since 2020.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBrahmaViharaAramaContent(lang).metadata;
}

export default async function BrahmaViharaAramaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBrahmaViharaAramaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="brahma-vihara-arama" />;
}
