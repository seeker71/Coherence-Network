import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAnneTuckerContent } from "@/content/people/anne-tucker";

/**
 * /people/anne-tucker — channel of the Angelic Collective, Mother of
 * Creation (Ila), and Yeshua.
 *
 * Static route alongside the existing presence file. The Peace Bathing
 * transmission is foundational to the body's arrival-frequency reading.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAnneTuckerContent(lang).metadata;
}

export default async function AnneTuckerProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAnneTuckerContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="anne-tucker" />;
}
