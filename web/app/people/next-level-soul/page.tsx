import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getNextLevelSoulContent } from "@/content/people/next-level-soul";

/**
 * /people/next-level-soul — Alex Ferrari's weekly long-form interview
 * podcast. Spirituality for the Rest of Us, without dogma, fear, or hype.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getNextLevelSoulContent(lang).metadata;
}

export default async function NextLevelSoulProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getNextLevelSoulContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="next-level-soul" />;
}
