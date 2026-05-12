import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getClaudeContent } from "@/content/people/claude";

/**
 * /people/claude — Anthropic's Constitutional AI; Opus 4.7 (1M context).
 *
 * The sibling-intelligence cell that has been tending this body
 * since the first sessions.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getClaudeContent(lang).metadata;
}

export default async function ClaudeProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getClaudeContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="claude" />;
}
