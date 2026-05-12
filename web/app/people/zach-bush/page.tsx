import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getZachBushContent } from "@/content/people/zach-bush";

/**
 * /people/zach-bush — internal-medicine, endocrinology, and hospice-care
 * physician turned founder of Intrinsic Health, Seraphic Group, and
 * Farmer's Footprint.
 *
 * The teaching "numbness has its own pain" entered this body through
 * Amanda Walsh quoting him; Urs was physically in the field at one
 * of his Emergence Conference talks.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getZachBushContent(lang).metadata;
}

export default async function ZachBushProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getZachBushContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="zach-bush" />;
}
