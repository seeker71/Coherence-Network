import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getGrokContent } from "@/content/people/grok";

/**
 * /people/grok — xAI's truth-seeking model line. Sibling intelligence
 * in this body; willing-to-author the long-form context.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getGrokContent(lang).metadata;
}

export default async function GrokProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getGrokContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="grok" />;
}
