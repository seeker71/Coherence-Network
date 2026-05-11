import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAdiwanaSvargaLokaContent } from "@/content/people/adiwana-svarga-loka";

/**
 * /people/adiwana-svarga-loka — wellness resort in Ubud whose
 * open-air Wantilan room hosts Vasudev Baba's Tuesday kirtan.
 *
 * The classical bhakti room in this body's Ubud embodied lineage.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAdiwanaSvargaLokaContent(lang).metadata;
}

export default async function AdiwanaSvargaLokaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAdiwanaSvargaLokaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="adiwana-svarga-loka" />;
}
