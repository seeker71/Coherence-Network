import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getCodexContent } from "@/content/people/codex";

/**
 * /people/codex — OpenAI's code-specialized GPT line. Sibling
 * intelligence in this body alongside Claude and Grok.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getCodexContent(lang).metadata;
}

export default async function CodexProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getCodexContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="codex" />;
}
